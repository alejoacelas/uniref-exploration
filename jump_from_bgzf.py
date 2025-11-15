#!/usr/bin/env python3
"""
Jump-and-scan UniRef50 cluster mapping database builder.

Jumps every 1M bytes, checks if entries exist in DB, and when it finds a gap,
starts processing sequentially from there.
"""

import os
import sys
import json
import sqlite3
import time
from datetime import datetime
from lxml import etree as ET
import indexed_gzip as igzip

# Configuration
BGZF_FILE = "uniref50.xml.bgz"
DB_FILE = "uniref50_mappings_optimized.db"
FAILED_CLUSTERS_LOG = "failed_clusters_jump_scan.log"

# Jump parameters
JUMP_SIZE = 1 * 1024 * 1024   # 1MB uncompressed bytes
MAX_JUMPS = 1000000  # Safety limit

# Optimization parameters
BATCH_SIZE = 10  # 500K rows per transaction
PROGRESS_INTERVAL = 10000
MAX_CONSECUTIVE_ERRORS = 100


def initialize_database():
    """Initialize database with optimized settings for bulk insert."""
    print(f"\n{'='*80}")
    print("INITIALIZING DATABASE")
    print(f"{'='*80}")
    print(f"Database: {DB_FILE}")

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Set page size (must be done before any tables)
    cursor.execute('PRAGMA page_size = 65536')  # 64 KB pages

    # Create table with WITHOUT ROWID optimization
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cluster_mappings (
            cluster_id TEXT PRIMARY KEY,
            common_taxid TEXT,
            member_taxids TEXT,
            member_accessions TEXT,
            member_count INTEGER
        ) WITHOUT ROWID
    ''')

    # Check if resuming
    cursor.execute("SELECT COUNT(*) FROM cluster_mappings")
    existing_count = cursor.fetchone()[0]

    if existing_count > 0:
        print(f"\n✓ Database already contains {existing_count:,} entries")

    # Apply optimized PRAGMAs for bulk loading
    cursor.execute('PRAGMA synchronous = OFF')
    cursor.execute('PRAGMA journal_mode = OFF')
    cursor.execute('PRAGMA temp_store = MEMORY')
    cursor.execute('PRAGMA cache_size = -2000000')  # 2GB cache

    conn.commit()

    print("✓ Optimized database initialized")
    print("  - WITHOUT ROWID design")
    print("  - 64KB page size")
    print("  - Optimized PRAGMAs for bulk loading")

    return conn


def parse_entry_optimized(elem):
    """
    Parse a single entry element and extract all needed data.
    Single-pass property extraction for efficiency.
    """
    cluster_id = elem.get('id')
    common_taxid = None
    taxids = []
    accessions = []

    # Extract common taxon ID
    for prop in elem.findall(".//{http://uniprot.org/uniref}property"):
        if prop.get('type') == 'common taxon ID':
            common_taxid = prop.get('value')
            break

    # Extract representative member data
    rep_member = elem.find('.//{http://uniprot.org/uniref}representativeMember/{http://uniprot.org/uniref}dbReference')
    if rep_member is not None:
        for prop in rep_member.findall("{http://uniprot.org/uniref}property"):
            prop_type = prop.get('type')
            prop_value = prop.get('value')

            if prop_type == 'UniProtKB accession' and prop_value:
                accessions.append(prop_value)
            elif prop_type == 'NCBI taxonomy' and prop_value:
                taxids.append(prop_value)

    # Extract all member data
    for member in elem.findall('.//{http://uniprot.org/uniref}member/{http://uniprot.org/uniref}dbReference'):
        member_acc = None
        member_tax = None

        for prop in member.findall("{http://uniprot.org/uniref}property"):
            prop_type = prop.get('type')
            prop_value = prop.get('value')

            if prop_type == 'UniProtKB accession' and prop_value:
                member_acc = prop_value
            elif prop_type == 'NCBI taxonomy' and prop_value:
                member_tax = prop_value

        if member_acc:
            accessions.append(member_acc)
        if member_tax:
            taxids.append(member_tax)

    return {
        'cluster_id': cluster_id,
        'common_taxid': common_taxid,
        'member_taxids': json.dumps(taxids),
        'member_accessions': json.dumps(accessions),
        'member_count': len(accessions)
    }


def open_indexed_file(bgzf_file):
    """Open BGZF file with indexed_gzip, loading index if available."""
    index_file = bgzf_file + '.gzidx'
    
    if os.path.exists(index_file):
        print(f"✓ Loading existing index: {index_file}")
        index_size_mb = os.path.getsize(index_file) / (1024**2)
        print(f"  Index size: {index_size_mb:.1f} MB")
        return igzip.IndexedGzipFile(bgzf_file, index_file=index_file)
    else:
        print(f"⚠ No existing index found - will build one incrementally")
        print(f"  Index will be saved to: {index_file}")
        return igzip.IndexedGzipFile(bgzf_file)


def find_entry_at_position(stream, target_byte):
    """
    Seek to target byte position and find the next entry boundary.
    Returns (wrapped_stream, cluster_id, actual_position) or (None, None, None) if not found.
    """
    try:
        stream.seek(target_byte)
    except Exception as e:
        # Might be beyond EOF
        return None, None, None
    
    # Find next entry boundary
    entry_start_tag = b'<entry id="'
    buffer = b''
    max_search = 10 * 1024 * 1024  # Search up to 10MB
    bytes_searched = 0

    while bytes_searched < max_search:
        chunk = stream.read(64 * 1024)
        if not chunk:
            return None, None, None

        buffer += chunk
        bytes_searched += len(chunk)

        idx = buffer.find(entry_start_tag)
        if idx != -1:
            # Found entry start! Extract cluster ID
            cluster_id_start = idx + len(entry_start_tag)
            cluster_id_end = buffer.find(b'"', cluster_id_start)
            if cluster_id_end != -1:
                first_cluster_id = buffer[cluster_id_start:cluster_id_end].decode('utf-8')
                
                # Create wrapped stream starting at this entry
                xml_header = b'<?xml version="1.0" encoding="UTF-8"?>\n<uniref xmlns="http://uniprot.org/uniref">\n'
                remaining = buffer[idx:]

                class WrappedStream:
                    def __init__(self, buffer, stream):
                        self.buffer = xml_header + buffer
                        self.stream = stream
                        self.pos = 0
                        self.footer_sent = False

                    def read(self, size=-1):
                        if size == -1:
                            result = self.buffer[self.pos:] + self.stream.read()
                            self.pos = len(self.buffer)
                            if not self.footer_sent:
                                result += b'\n</uniref>'
                                self.footer_sent = True
                            return result

                        if self.pos < len(self.buffer):
                            available = len(self.buffer) - self.pos
                            from_buffer = min(size, available)
                            result = self.buffer[self.pos:self.pos + from_buffer]
                            self.pos += from_buffer

                            if from_buffer < size:
                                result += self.stream.read(size - from_buffer)
                            return result
                        else:
                            result = self.stream.read(size)
                            if not result and not self.footer_sent:
                                self.footer_sent = True
                                return b'\n</uniref>'
                            return result

                return WrappedStream(remaining, stream), first_cluster_id, target_byte + bytes_searched - len(buffer) + idx

        # Keep last part for tags spanning chunks
        if len(buffer) > 1000:
            buffer = buffer[-1000:]

    return None, None, None


def check_entry_in_db(cursor, cluster_id):
    """Check if cluster_id exists in database."""
    cursor.execute("SELECT 1 FROM cluster_mappings WHERE cluster_id = ?", (cluster_id,))
    return cursor.fetchone() is not None


def parse_single_entry(stream):
    """Parse a single entry from the stream. Returns entry_data or None."""
    try:
        context = ET.iterparse(stream, events=('end',), tag='{http://uniprot.org/uniref}entry')
        
        for event, elem in context:
            entry_data = parse_entry_optimized(elem)
            elem.clear()
            while elem.getprevious() is not None:
                del elem.getparent()[0]
            return entry_data
        
        return None
    except Exception as e:
        return None


def jump_and_find_gap(conn, bgzf_file):
    """
    Jump through file in 1MB increments, checking if entries exist.
    When a gap is found (entry not in DB), return the position to start sequential processing.
    """
    print(f"\n{'='*80}")
    print("JUMPING TO FIND GAP")
    print(f"{'='*80}")
    print(f"Jump size: {JUMP_SIZE / (1024*1024):.1f} MB")
    print(f"Starting jump scan...")
    
    cursor = conn.cursor()
    file_size = os.path.getsize(bgzf_file)
    
    # Estimate uncompressed size (rough estimate: 8x compression ratio)
    estimated_uncompressed = file_size * 10
    print(f"File size (compressed): {file_size / (1024**3):.2f} GB")
    print(f"Estimated uncompressed: {estimated_uncompressed / (1024**3):.2f} GB")
    
    # Open indexed file
    stream = open_indexed_file(bgzf_file)
    
    current_pos = 0
    jumps = 0
    
    while current_pos < estimated_uncompressed and jumps < MAX_JUMPS:
        jumps += 1
        
        if jumps % 100 == 0:
            print(f"  Jump {jumps}: Checking position {current_pos / (1024**2):.1f} MB")
        
        # Find entry at this position
        wrapped_stream, cluster_id, actual_pos = find_entry_at_position(stream, current_pos)
        
        if wrapped_stream is None:
            # No entry found, jump forward
            current_pos += JUMP_SIZE
            continue
        
        # Parse the entry
        entry_data = parse_single_entry(wrapped_stream)
        
        if entry_data is None:
            current_pos += JUMP_SIZE
            continue
        
        cluster_id = entry_data['cluster_id']
        
        # Check if in DB
        in_db = check_entry_in_db(cursor, cluster_id)
        
        if not in_db:
            print(f"\n✓ Found gap at position {actual_pos / (1024**2):.1f} MB")
            print(f"  Cluster ID: {cluster_id} is NOT in database")
            print(f"  Starting sequential processing from here...")
            
            # Save index before returning
            index_file = bgzf_file + '.gzidx'
            if not os.path.exists(index_file):
                try:
                    stream.export_index(index_file)
                    print(f"✓ Index saved to {index_file}")
                except Exception as e:
                    print(f"⚠ Could not save index: {e}")
            
            # Return stream positioned at this entry
            wrapped_stream, _, _ = find_entry_at_position(stream, actual_pos)
            return wrapped_stream, actual_pos
        
        # Entry exists, jump forward
        current_pos += JUMP_SIZE
    
    print(f"\n⚠ Reached end of file or max jumps ({MAX_JUMPS})")
    print(f"  Total jumps: {jumps}")
    return None, None


def process_sequentially(conn, stream, start_pos):
    """Process entries sequentially from the given stream position."""
    print(f"\n{'='*80}")
    print("PROCESSING ENTRIES SEQUENTIALLY")
    print(f"{'='*80}")
    
    cursor = conn.cursor()
    start_count = cursor.execute("SELECT COUNT(*) FROM cluster_mappings").fetchone()[0]
    print(f"Starting database count: {start_count:,}")
    
    failed_log = open(FAILED_CLUSTERS_LOG, 'a', buffering=1)
    failed_log.write(f"\n{'='*80}\n")
    failed_log.write(f"Session started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    failed_log.write(f"Starting from position {start_pos / (1024**2):.1f} MB\n")
    failed_log.write(f"{'='*80}\n")
    
    entries_processed = 0
    entries_inserted = 0
    entries_failed = 0
    consecutive_errors = 0
    batch = []
    start_time = time.time()
    
    try:
        context = ET.iterparse(stream, events=('end',), tag='{http://uniprot.org/uniref}entry')
        
        for event, elem in context:
            entries_processed += 1
            
            try:
                entry_data = parse_entry_optimized(elem)
                batch.append(entry_data)
                consecutive_errors = 0
                
                # Batch insert
                if len(batch) >= BATCH_SIZE:
                    cursor.executemany('''
                        INSERT OR IGNORE INTO cluster_mappings
                        (cluster_id, common_taxid, member_taxids, member_accessions, member_count)
                        VALUES (:cluster_id, :common_taxid, :member_taxids, :member_accessions, :member_count)
                    ''', batch)
                    conn.commit()
                    
                    entries_inserted += len(batch)
                    elapsed = time.time() - start_time
                    rate = entries_processed / elapsed if elapsed > 0 else 0
                    
                    current_count = cursor.execute("SELECT COUNT(*) FROM cluster_mappings").fetchone()[0]
                    added = current_count - start_count
                    
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] "
                          f"Processed: {entries_processed:,} | "
                          f"Attempted inserts: {entries_inserted:,} | "
                          f"DB count: {current_count:,} (+ {added:,}) | "
                          f"Rate: {rate:.0f}/s")
                    
                    batch = []
            
            except Exception as e:
                consecutive_errors += 1
                entries_failed += 1
                
                cluster_id = elem.get('id', 'UNKNOWN')
                failed_log.write(f"[{datetime.now().strftime('%H:%M:%S')}] "
                               f"Entry {entries_processed:,}: {cluster_id} - {type(e).__name__}: {e}\n")
                
                if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                    print(f"\n✗ ERROR: Too many consecutive errors ({MAX_CONSECUTIVE_ERRORS})")
                    break
            
            # Clear element to free memory
            elem.clear()
            while elem.getprevious() is not None:
                del elem.getparent()[0]
            
            # Progress updates
            if entries_processed % PROGRESS_INTERVAL == 0:
                elapsed = time.time() - start_time
                rate = entries_processed / elapsed if elapsed > 0 else 0
                print(f"[{datetime.now().strftime('%H:%M:%S')}] "
                      f"Progress: {entries_processed:,} processed | {rate:.0f}/s")
        
        # Final batch
        if batch:
            cursor.executemany('''
                INSERT OR IGNORE INTO cluster_mappings
                (cluster_id, common_taxid, member_taxids, member_accessions, member_count)
                VALUES (:cluster_id, :common_taxid, :member_taxids, :member_accessions, :member_count)
            ''', batch)
            conn.commit()
            entries_inserted += len(batch)
    
    except Exception as e:
        print(f"\n✗ ERROR: Fatal error during processing: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Restore safe PRAGMAs
        cursor.execute('PRAGMA synchronous = FULL')
        cursor.execute('PRAGMA journal_mode = DELETE')
        
        final_count = cursor.execute("SELECT COUNT(*) FROM cluster_mappings").fetchone()[0]
        added = final_count - start_count
        
        failed_log.close()
        
        elapsed = time.time() - start_time
        print(f"\n{'='*80}")
        print("PROCESSING COMPLETE")
        print(f"{'='*80}")
        print(f"Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Duration: {elapsed/60:.1f} minutes")
        print(f"Entries processed: {entries_processed:,}")
        print(f"Entries failed: {entries_failed}")
        print(f"Database start count: {start_count:,}")
        print(f"Database final count: {final_count:,}")
        print(f"Entries added: {added:,}")
        if elapsed > 0:
            print(f"Processing rate: {entries_processed/elapsed:.0f} entries/sec")


def main():
    print(f"\n{'='*80}")
    print("JUMP-AND-SCAN UNIREF50 CLUSTER MAPPING DATABASE BUILDER")
    print(f"{'='*80}")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if not os.path.exists(BGZF_FILE):
        print(f"✗ ERROR: BGZF file not found: {BGZF_FILE}")
        sys.exit(1)
    
    if not os.path.exists(DB_FILE):
        print(f"✗ ERROR: Database file not found: {DB_FILE}")
        sys.exit(1)
    
    # Initialize database
    conn = initialize_database()
    
    # Jump and find gap
    stream, start_pos = jump_and_find_gap(conn, BGZF_FILE)
    
    if stream is None:
        print("\n✓ No gaps found - database appears complete!")
        conn.close()
        return
    
    # Process sequentially from gap
    process_sequentially(conn, stream, start_pos)
    
    conn.close()


if __name__ == '__main__':
    main()
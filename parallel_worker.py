#!/usr/bin/env python3
"""
Parallel BGZF Worker for UniRef50 Processing

Seeks to a specific position in a BGZF-compressed XML file,
resyncs to the next valid entry boundary, and processes to EOF.
Uses INSERT OR IGNORE for safe deduplication with other workers.
"""

import sys
import os
import time
import json
import csv
import sqlite3
import subprocess
import gzip
from datetime import datetime
from lxml import etree as ET

# Configuration
PROGRESS_INTERVAL = 10000
MAX_CONSECUTIVE_ERRORS = 100
CSV_LOG_FILE = "worker_progress.csv"
DB_FILE = "uniref50_mappings_optimized.db"
BATCH_SIZE = 500_000


def log(msg, flush=True):
    """Print with timestamp and flush."""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{timestamp}] {msg}", flush=flush)


def parse_entry_optimized(elem):
    """
    Parse a single entry element and extract all needed data.
    Optimized for single-pass property extraction.
    """
    cluster_id = elem.get('id')
    common_taxid = None
    taxids = []
    accessions = []

    # Extract common taxon ID (cluster-level property)
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


def seek_to_percentage(bgzf_file, percentage):
    """
    Seek to approximate byte position based on percentage.
    Returns the byte position.
    """
    file_size = os.path.getsize(bgzf_file)
    target_byte = int(file_size * percentage / 100)
    log(f"File size: {file_size:,} bytes")
    log(f"Target position: {percentage}% = {target_byte:,} bytes")
    return target_byte


def resync_to_entry_boundary(stream, max_bytes=10*1024*1024):
    """
    Read from current position until we find the start of a valid <entry> tag.
    Returns the first cluster ID found, or None if not found within max_bytes.

    Creates a wrapped stream that makes the fragment look like a complete XML document.
    """
    log("Resyncing to next <entry> boundary...")
    entry_start_tag = b'<entry id="'
    buffer = b''
    bytes_read = 0

    while bytes_read < max_bytes:
        chunk = stream.read(64 * 1024)  # 64KB chunks
        if not chunk:
            log("WARNING: Reached EOF while resyncing")
            return None

        buffer += chunk
        bytes_read += len(chunk)

        # Look for entry start tag
        idx = buffer.find(entry_start_tag)
        if idx != -1:
            # Found it! Extract cluster ID
            # Format: <entry id="UniRef50_A0A009EXU4" ...>
            cluster_id_start = idx + len(entry_start_tag)
            cluster_id_end = buffer.find(b'"', cluster_id_start)
            if cluster_id_end != -1:
                cluster_id = buffer[cluster_id_start:cluster_id_end].decode('utf-8')
                log(f"Resynced! First entry: {cluster_id}")

                # Position stream at the start of this entry
                # We need to "unread" the portion after the entry tag
                remaining = buffer[idx:]

                # Create a wrapped stream that adds XML header/footer
                # This makes iterparse think it's parsing a complete document
                class WrappedXMLStream:
                    def __init__(self, buffer, stream):
                        # Add minimal XML wrapper
                        xml_header = b'<?xml version="1.0" encoding="UTF-8"?>\n<uniref xmlns="http://uniprot.org/uniref">\n'
                        self.buffer = xml_header + buffer
                        self.stream = stream
                        self.pos = 0
                        self.footer_sent = False

                    def read(self, size=-1):
                        if size == -1:
                            # Read all remaining
                            result = self.buffer[self.pos:] + self.stream.read()
                            self.pos = len(self.buffer)
                            # Add closing tag
                            if not self.footer_sent:
                                result += b'\n</uniref>'
                                self.footer_sent = True
                            return result

                        # Read size bytes
                        if self.pos < len(self.buffer):
                            # Read from buffer first
                            available = len(self.buffer) - self.pos
                            from_buffer = min(size, available)
                            result = self.buffer[self.pos:self.pos + from_buffer]
                            self.pos += from_buffer

                            # If we need more, read from stream
                            if from_buffer < size:
                                result += self.stream.read(size - from_buffer)
                            return result
                        else:
                            # Buffer exhausted, read from stream
                            result = self.stream.read(size)
                            # If we got nothing and haven't sent footer, send it
                            if not result and not self.footer_sent:
                                self.footer_sent = True
                                return b'\n</uniref>'
                            return result

                return cluster_id, WrappedXMLStream(remaining, stream)

        # Keep last part of buffer for tags that span chunks
        if len(buffer) > 1000:
            buffer = buffer[-1000:]

    log(f"ERROR: Could not find entry boundary within {max_bytes:,} bytes")
    return None, stream


def initialize_database():
    """Initialize database with optimized settings for bulk insert."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Apply optimized PRAGMAs for bulk loading
    cursor.execute('PRAGMA synchronous = OFF')
    cursor.execute('PRAGMA journal_mode = MEMORY')
    cursor.execute('PRAGMA temp_store = MEMORY')
    cursor.execute('PRAGMA cache_size = -2000000')  # 2GB cache

    log("✓ Optimized PRAGMAs applied for bulk loading")
    return conn


def process_worker(worker_id, start_percentage, bgzf_file, db_file):
    """
    Main worker function: seek to position, resync, process to EOF.
    """
    start_time = time.time()
    log(f"Worker {worker_id} starting at {start_percentage}%")

    # Seek to target position
    target_byte = seek_to_percentage(bgzf_file, start_percentage)

    # Open BGZF file (it's just a special gzip)
    log(f"Opening {bgzf_file}...")
    stream = gzip.open(bgzf_file, 'rb')

    # Seek to approximate position
    # Note: gzip.seek() on a gzip file decompresses to that position
    # This might still take some time but faster than full iterparse skip
    log(f"Seeking to byte {target_byte:,}...")
    stream.read(target_byte)  # Advance to position

    # Resync to entry boundary
    resync_result = resync_to_entry_boundary(stream)
    if resync_result is None or resync_result[0] is None:
        log("ERROR: Failed to resync to entry boundary")
        return {
            'worker_id': worker_id,
            'percent': start_percentage,
            'start_byte': target_byte,
            'first_cluster_id': None,
            'rows_inserted': 0,
            'duration_sec': time.time() - start_time,
            'status': 'failed_resync'
        }

    first_cluster_id, stream = resync_result

    # Initialize database connection
    conn = initialize_database()
    cursor = conn.cursor()

    # Start parsing from resynced position to EOF
    log("Starting XML parsing from resynced position...")

    entries_processed = 0
    entries_inserted = 0
    entries_failed = 0
    consecutive_errors = 0
    batch = []

    try:
        # Use iterparse on the buffered stream
        context = ET.iterparse(stream, events=('end',), tag='{http://uniprot.org/uniref}entry')

        for event, elem in context:
            entries_processed += 1

            try:
                # Parse entry
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

                    log(f"[Worker {worker_id}] Processed: {entries_processed:,} | "
                        f"Inserted: {entries_inserted:,} | "
                        f"Rate: {rate:.0f}/s | "
                        f"Elapsed: {elapsed/60:.1f}min")

                    batch = []

            except Exception as e:
                consecutive_errors += 1
                entries_failed += 1

                if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                    log(f"ERROR: Too many consecutive errors ({MAX_CONSECUTIVE_ERRORS})")
                    break

                if entries_failed % 100 == 0:
                    log(f"WARNING: {entries_failed} total failures")

            # Clear element to free memory
            elem.clear()
            while elem.getprevious() is not None:
                del elem.getparent()[0]

            # Progress updates
            if entries_processed % PROGRESS_INTERVAL == 0:
                elapsed = time.time() - start_time
                rate = entries_processed / elapsed if elapsed > 0 else 0
                log(f"[Worker {worker_id}] Progress: {entries_processed:,} processed | "
                    f"{rate:.0f}/s | {elapsed/60:.1f}min")

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
        log(f"ERROR: Fatal error during processing: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # Restore safe PRAGMAs
        cursor.execute('PRAGMA synchronous = FULL')
        cursor.execute('PRAGMA journal_mode = DELETE')
        conn.close()
        log("✓ Safe PRAGMAs restored, connection closed")

    duration = time.time() - start_time
    log(f"Worker {worker_id} complete: {entries_processed:,} processed, "
        f"{entries_inserted:,} inserted, {duration/60:.1f} minutes")

    return {
        'worker_id': worker_id,
        'percent': start_percentage,
        'start_byte': target_byte,
        'first_cluster_id': first_cluster_id,
        'rows_inserted': entries_inserted,
        'rows_processed': entries_processed,
        'rows_failed': entries_failed,
        'duration_sec': duration,
        'status': 'completed'
    }


def write_csv_log(result):
    """Write worker result to CSV log."""
    file_exists = os.path.exists(CSV_LOG_FILE)

    with open(CSV_LOG_FILE, 'a', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'worker_id', 'percent', 'start_byte', 'first_cluster_id',
            'rows_processed', 'rows_inserted', 'rows_failed',
            'duration_sec', 'status', 'timestamp'
        ])

        if not file_exists:
            writer.writeheader()

        result['timestamp'] = datetime.now().isoformat()
        writer.writerow(result)


def main():
    if len(sys.argv) < 3:
        print("Usage: python parallel_worker.py <worker_id> <start_percentage> [bgzf_file] [db_file]")
        print("Example: python parallel_worker.py worker_55 55")
        sys.exit(1)

    worker_id = sys.argv[1]
    start_percentage = float(sys.argv[2])
    bgzf_file = sys.argv[3] if len(sys.argv) > 3 else "uniref50.xml.bgz"
    db_file = sys.argv[4] if len(sys.argv) > 4 else DB_FILE

    log(f"="*80)
    log(f"PARALLEL WORKER: {worker_id}")
    log(f"="*80)
    log(f"Start position: {start_percentage}%")
    log(f"BGZF file: {bgzf_file}")
    log(f"Database: {db_file}")
    log(f"="*80)

    # Check files exist
    if not os.path.exists(bgzf_file):
        log(f"ERROR: BGZF file not found: {bgzf_file}")
        sys.exit(1)

    if not os.path.exists(db_file):
        log(f"ERROR: Database file not found: {db_file}")
        sys.exit(1)

    # Run worker
    result = process_worker(worker_id, start_percentage, bgzf_file, db_file)

    # Log result to CSV
    write_csv_log(result)

    log(f"="*80)
    log(f"WORKER {worker_id} FINISHED")
    log(f"Status: {result['status']}")
    log(f"Rows inserted: {result['rows_inserted']:,}")
    log(f"Duration: {result['duration_sec']/60:.1f} minutes")
    log(f"="*80)


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""
Test script: Process from start of BGZF file to verify entry distribution.
This will process first ~100K entries to see if they're duplicates or new.
"""

import os
import sys
import json
import sqlite3
import gzip
import time
from datetime import datetime
from lxml import etree as ET

# Configuration
BGZF_FILE = "uniref50.xml.bgz"
DB_FILE = "uniref50_mappings_optimized.db"
TEST_LIMIT = 100000  # Process first 100K entries as test
BATCH_SIZE = 10000

def parse_entry_optimized(elem):
    """Parse a single entry element and extract all needed data."""
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


def test_from_start():
    """Process from start and track new vs duplicate entries."""
    print(f"{'='*80}")
    print(f"TEST: Processing from START of BGZF file")
    print(f"{'='*80}")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Test limit: {TEST_LIMIT:,} entries")

    start_time = time.time()

    # Initialize database
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Optimized PRAGMAs
    cursor.execute('PRAGMA synchronous = OFF')
    cursor.execute('PRAGMA journal_mode = MEMORY')
    cursor.execute('PRAGMA temp_store = MEMORY')
    cursor.execute('PRAGMA cache_size = -2000000')

    # Check starting count
    start_count = cursor.execute("SELECT COUNT(*) FROM cluster_mappings").fetchone()[0]
    print(f"Starting database count: {start_count:,}")

    # Open BGZF file from beginning
    print(f"\nOpening {BGZF_FILE} from start...")
    stream = gzip.open(BGZF_FILE, 'rb')

    # Process entries
    print(f"\n{'='*80}")
    print("PROCESSING ENTRIES FROM START")
    print(f"{'='*80}")

    entries_processed = 0
    entries_attempted = 0
    batch = []

    # Track first few cluster IDs and their existence
    first_10_clusters = []

    try:
        context = ET.iterparse(stream, events=('end',), tag='{http://uniprot.org/uniref}entry')

        for event, elem in context:
            entries_processed += 1

            try:
                entry_data = parse_entry_optimized(elem)
                cluster_id = entry_data['cluster_id']

                # Track first 10 cluster IDs
                if len(first_10_clusters) < 10:
                    # Check if exists in DB
                    exists = cursor.execute(
                        "SELECT 1 FROM cluster_mappings WHERE cluster_id = ?",
                        (cluster_id,)
                    ).fetchone() is not None
                    first_10_clusters.append((cluster_id, exists))

                batch.append(entry_data)

                # Batch insert
                if len(batch) >= BATCH_SIZE:
                    cursor.executemany('''
                        INSERT OR IGNORE INTO cluster_mappings
                        (cluster_id, common_taxid, member_taxids, member_accessions, member_count)
                        VALUES (:cluster_id, :common_taxid, :member_taxids, :member_accessions, :member_count)
                    ''', batch)
                    conn.commit()

                    entries_attempted += len(batch)

                    # Check actual database count
                    current_count = cursor.execute("SELECT COUNT(*) FROM cluster_mappings").fetchone()[0]
                    added = current_count - start_count

                    print(f"[{datetime.now().strftime('%H:%M:%S')}] "
                          f"Processed: {entries_processed:,} | "
                          f"Attempted inserts: {entries_attempted:,} | "
                          f"DB count: {current_count:,} (+ {added:,})")

                    batch = []

            except Exception as e:
                print(f"ERROR parsing entry {entries_processed}: {e}")

            # Clear element to free memory
            elem.clear()
            while elem.getprevious() is not None:
                del elem.getparent()[0]

            # Stop at test limit
            if entries_processed >= TEST_LIMIT:
                print(f"\nReached test limit of {TEST_LIMIT:,} entries")
                break

        # Final batch
        if batch:
            cursor.executemany('''
                INSERT OR IGNORE INTO cluster_mappings
                (cluster_id, common_taxid, member_taxids, member_accessions, member_count)
                VALUES (:cluster_id, :common_taxid, :member_taxids, :member_accessions, :member_count)
            ''', batch)
            conn.commit()
            entries_attempted += len(batch)

    finally:
        # Restore safe PRAGMAs
        cursor.execute('PRAGMA synchronous = FULL')
        cursor.execute('PRAGMA journal_mode = DELETE')

        # Final count
        final_count = cursor.execute("SELECT COUNT(*) FROM cluster_mappings").fetchone()[0]
        added = final_count - start_count

        conn.close()

        elapsed = time.time() - start_time
        print(f"\n{'='*80}")
        print("TEST COMPLETE")
        print(f"{'='*80}")
        print(f"Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Duration: {elapsed:.1f} seconds")
        print(f"Entries processed: {entries_processed:,}")
        print(f"Entries attempted: {entries_attempted:,}")
        print(f"Database start count: {start_count:,}")
        print(f"Database final count: {final_count:,}")
        print(f"Entries added: {added:,}")
        print(f"\nFirst 10 cluster IDs:")
        for cluster_id, existed in first_10_clusters:
            status = "EXISTED" if existed else "NEW"
            print(f"  {cluster_id}: {status}")


if __name__ == '__main__':
    if not os.path.exists(BGZF_FILE):
        print(f"ERROR: BGZF file not found: {BGZF_FILE}")
        sys.exit(1)

    if not os.path.exists(DB_FILE):
        print(f"ERROR: Database file not found: {DB_FILE}")
        sys.exit(1)

    test_from_start()

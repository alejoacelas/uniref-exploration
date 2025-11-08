#!/usr/bin/env python3
"""
Test the augmentation pipeline with sample data.

This script:
1. Builds a small SQLite database from uniref50_sample.xml.gz
2. Downloads a small subset of the HF dataset
3. Tests the augmentation process
4. Validates the results

Usage:
    python test_pipeline.py
"""

import os
import sys
import json
import sqlite3
import gzip
import time
from datetime import datetime

try:
    import lxml.etree as ET
except ImportError:
    print("Installing lxml...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "lxml", "-q"])
    import lxml.etree as ET

try:
    from datasets import load_dataset
except ImportError:
    print("Installing datasets...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "datasets", "-q"])
    from datasets import load_dataset


SAMPLE_XML = "uniref50_sample.xml.gz"
TEST_DB = "test_mappings.db"
TEST_SIZE = 1000  # Number of HF dataset entries to test


def build_test_database():
    """Build SQLite database from sample XML."""
    print(f"\n{'='*80}")
    print(f"BUILDING TEST DATABASE FROM SAMPLE")
    print(f"{'='*80}")
    print(f"Sample XML: {SAMPLE_XML}")
    print(f"Test DB: {TEST_DB}")

    if not os.path.exists(SAMPLE_XML):
        print(f"\n✗ ERROR: {SAMPLE_XML} not found!")
        print("Please run the sample download first.")
        sys.exit(1)

    # Remove existing test database
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
        print("Removed existing test database")

    # Create database
    conn = sqlite3.connect(TEST_DB)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE cluster_mappings (
            cluster_id TEXT PRIMARY KEY,
            common_taxid TEXT,
            member_taxids TEXT,
            member_accessions TEXT,
            member_count INTEGER
        )
    ''')
    cursor.execute('CREATE INDEX idx_cluster_id ON cluster_mappings(cluster_id)')

    print("\nParsing sample XML...")
    entries_processed = 0
    start_time = time.time()

    try:
        with gzip.open(SAMPLE_XML, 'rb') as f:
            context = ET.iterparse(f, events=('end',), tag='{http://uniprot.org/uniref}entry')

            for event, elem in context:
                entries_processed += 1

                # Extract cluster ID
                cluster_id = elem.get('id')

                # Extract common taxon ID
                common_taxid = None
                for prop in elem.findall(".//{http://uniprot.org/uniref}property[@type='common taxon ID']"):
                    common_taxid = prop.get('value')
                    break

                # Extract representative member data
                rep_member = elem.find('.//{http://uniprot.org/uniref}representativeMember/{http://uniprot.org/uniref}dbReference')

                taxids = []
                accessions = []

                if rep_member is not None:
                    for prop in rep_member.findall("{http://uniprot.org/uniref}property[@type='UniProtKB accession']"):
                        rep_acc = prop.get('value')
                        if rep_acc:
                            accessions.append(rep_acc)

                    for prop in rep_member.findall("{http://uniprot.org/uniref}property[@type='NCBI taxonomy']"):
                        rep_tax = prop.get('value')
                        if rep_tax:
                            taxids.append(rep_tax)

                # Extract all member data
                for member in elem.findall('.//{http://uniprot.org/uniref}member/{http://uniprot.org/uniref}dbReference'):
                    for prop in member.findall("{http://uniprot.org/uniref}property[@type='UniProtKB accession']"):
                        mem_acc = prop.get('value')
                        if mem_acc:
                            accessions.append(mem_acc)

                    for prop in member.findall("{http://uniprot.org/uniref}property[@type='NCBI taxonomy']"):
                        mem_tax = prop.get('value')
                        if mem_tax:
                            taxids.append(mem_tax)

                # Insert into database
                cursor.execute('''
                    INSERT INTO cluster_mappings
                    (cluster_id, common_taxid, member_taxids, member_accessions, member_count)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    cluster_id,
                    common_taxid,
                    json.dumps(taxids),
                    json.dumps(accessions),
                    len(accessions)
                ))

                if entries_processed % 5000 == 0:
                    print(f"  Processed {entries_processed:,} entries...")
                    conn.commit()

                # Clear memory
                elem.clear()
                while elem.getprevious() is not None:
                    del elem.getparent()[0]

            conn.commit()
            del context

    except Exception as e:
        print(f"\n✗ Error during parsing: {e}")
        # Even if XML is truncated, we can work with what we got
        conn.commit()

    elapsed = time.time() - start_time
    print(f"\n✓ Parsed {entries_processed:,} entries in {elapsed:.1f} seconds")
    print(f"  Rate: {entries_processed/elapsed:.0f} entries/second")

    # Verify database
    cursor.execute("SELECT COUNT(*) FROM cluster_mappings")
    count = cursor.fetchone()[0]
    print(f"✓ Database contains {count:,} cluster mappings")

    # Show sample
    cursor.execute("SELECT cluster_id, common_taxid, member_count FROM cluster_mappings LIMIT 3")
    print("\nSample mappings:")
    for row in cursor.fetchall():
        print(f"  {row[0]}: common_taxid={row[1]}, members={row[2]}")

    conn.close()
    return count


def test_augmentation():
    """Test augmentation with small subset of HF dataset."""
    print(f"\n{'='*80}")
    print(f"TESTING AUGMENTATION PROCESS")
    print(f"{'='*80}")

    # Load small subset of dataset
    print(f"\nLoading first {TEST_SIZE:,} entries from HuggingFace dataset...")
    try:
        dataset = load_dataset("alejoacelas/uniref50-2025-10", split=f"train[:{TEST_SIZE}]")
        print(f"✓ Loaded {len(dataset):,} entries")
    except Exception as e:
        print(f"✗ Error loading dataset: {e}")
        return False

    # Connect to test database
    if not os.path.exists(TEST_DB):
        print(f"\n✗ ERROR: Test database not found!")
        return False

    conn = sqlite3.connect(TEST_DB)
    cursor = conn.cursor()

    # Test augmentation
    print("\nTesting augmentation logic...")
    matched = 0
    missing = 0
    missing_ids = []

    for i, example in enumerate(dataset):
        cluster_id = example['sequence_id']

        # Lookup in database
        cursor.execute('''
            SELECT common_taxid, member_taxids, member_accessions
            FROM cluster_mappings
            WHERE cluster_id = ?
        ''', (cluster_id,))

        row = cursor.fetchone()

        if row:
            matched += 1
            common_taxid, member_taxids_json, member_accessions_json = row
            member_taxids = json.loads(member_taxids_json)
            member_accessions = json.loads(member_accessions_json)

            # Validate
            if len(member_taxids) != len(member_accessions):
                print(f"  ✗ WARNING: Mismatch at {cluster_id}")
        else:
            missing += 1
            if len(missing_ids) < 5:
                missing_ids.append(cluster_id)

    conn.close()

    match_rate = 100 * matched / len(dataset) if len(dataset) > 0 else 0

    print(f"\n✓ Augmentation test complete:")
    print(f"  Total entries: {len(dataset):,}")
    print(f"  Matched: {matched:,} ({match_rate:.2f}%)")
    print(f"  Missing: {missing:,}")

    if missing_ids:
        print(f"  Example missing IDs: {', '.join(missing_ids)}")

    # Show sample augmented entry
    if matched > 0:
        print("\nSample augmented entry:")
        for example in dataset:
            cluster_id = example['sequence_id']
            conn = sqlite3.connect(TEST_DB)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT common_taxid, member_taxids, member_accessions
                FROM cluster_mappings
                WHERE cluster_id = ?
            ''', (cluster_id,))
            row = cursor.fetchone()
            conn.close()

            if row:
                common_taxid, member_taxids_json, member_accessions_json = row
                member_taxids = json.loads(member_taxids_json)
                member_accessions = json.loads(member_accessions_json)

                print(f"  sequence_id: {cluster_id}")
                print(f"  common_taxid: {common_taxid}")
                print(f"  member_taxids: {member_taxids[:3]}{'...' if len(member_taxids) > 3 else ''} (count: {len(member_taxids)})")
                print(f"  member_accessions: {member_accessions[:3]}{'...' if len(member_accessions) > 3 else ''} (count: {len(member_accessions)})")
                break

    return match_rate > 50  # Success if we match at least 50%


def main():
    """Main test flow."""
    print(f"\n{'='*80}")
    print(f"PIPELINE TEST")
    print(f"{'='*80}")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Step 1: Build test database
    db_count = build_test_database()

    # Step 2: Test augmentation
    success = test_augmentation()

    # Summary
    print(f"\n{'='*80}")
    print(f"TEST SUMMARY")
    print(f"{'='*80}")
    print(f"Test database: {db_count:,} clusters")
    print(f"Test dataset: {TEST_SIZE:,} entries")
    print(f"Result: {'✓ PASSED' if success else '✗ FAILED'}")

    if success:
        print("\n✓ Pipeline is working correctly!")
        print("You can now run the full augmentation when the complete XML download finishes.")
        print("\nNext steps:")
        print("  1. Wait for build_cluster_mappings.py to complete (check: tail -f build_mappings.log)")
        print("  2. Run: python augment_hf_dataset.py --test")
        print("  3. If test passes, run: python augment_hf_dataset.py")
    else:
        print("\n✗ Pipeline test failed. Please review errors above.")

    print(f"\nCompleted at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()

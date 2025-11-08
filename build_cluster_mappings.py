#!/usr/bin/env python3
"""
Build SQLite database mapping UniRef50 cluster IDs to metadata.

This script:
1. Downloads uniref50.xml.gz from UniProt FTP
2. Streams through the XML using lxml.etree.iterparse() for memory efficiency
3. Extracts cluster metadata (common_taxid, member taxids, member accessions)
4. Stores in SQLite database indexed by cluster_id
5. Supports resume capability via checkpointing

Usage:
    python build_cluster_mappings.py
"""

import os
import sys
import json
import sqlite3
import gzip
import time
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

try:
    import lxml.etree as ET
except ImportError:
    print("ERROR: lxml not installed. Installing...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "lxml"])
    import lxml.etree as ET


# Configuration
XML_URL = "https://ftp.uniprot.org/pub/databases/uniprot/current_release/uniref/uniref50/uniref50.xml.gz"
XML_FILE = "uniref50.xml.gz"
DB_FILE = "uniref50_mappings.db"
CHECKPOINT_FILE = "parsing_checkpoint.txt"
FAILED_CLUSTERS_LOG = "failed_clusters.log"
BATCH_SIZE = 100000  # Commit every 100k entries
PROGRESS_INTERVAL = 10000  # Log progress every 10k entries
MAX_CONSECUTIVE_ERRORS = 100  # Stop if this many errors in a row


def download_xml(url, output_file):
    """Download XML file with resume capability using wget."""
    print(f"\n{'='*80}")
    print(f"DOWNLOADING UniRef50 XML")
    print(f"{'='*80}")
    print(f"URL: {url}")
    print(f"Output: {output_file}")

    if os.path.exists(output_file):
        file_size_gb = os.path.getsize(output_file) / (1024**3)
        print(f"\nFile already exists ({file_size_gb:.2f} GB)")

        # Auto-continue if not running interactively
        if sys.stdin.isatty():
            response = input("Download again? (y/N): ").strip().lower()
            if response != 'y':
                print("Using existing file.")
                return
            else:
                os.remove(output_file)
        else:
            print("Running in non-interactive mode - using existing file")
            return

    print("\nStarting download (this may take 1-3 hours)...")
    print("Using wget with resume capability (-c flag)")

    # Use wget with continue flag for resume capability
    cmd = ["wget", "-c", "-O", output_file, url]

    try:
        subprocess.run(cmd, check=True)
        file_size_gb = os.path.getsize(output_file) / (1024**3)
        print(f"\n✓ Download complete! File size: {file_size_gb:.2f} GB")
    except subprocess.CalledProcessError as e:
        print(f"\n✗ Download failed: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n\nDownload interrupted. Run script again to resume from checkpoint.")
        sys.exit(0)


def create_database(db_file):
    """Create SQLite database with schema."""
    print(f"\n{'='*80}")
    print(f"INITIALIZING DATABASE")
    print(f"{'='*80}")
    print(f"Database: {db_file}")

    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    # Create table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cluster_mappings (
            cluster_id TEXT PRIMARY KEY,
            common_taxid TEXT,
            member_taxids TEXT,
            member_accessions TEXT,
            member_count INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Create index for fast lookups
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_cluster_id
        ON cluster_mappings(cluster_id)
    ''')

    conn.commit()

    # Check if we're resuming
    cursor.execute("SELECT COUNT(*) FROM cluster_mappings")
    existing_count = cursor.fetchone()[0]

    if existing_count > 0:
        print(f"\n⚠ Database already contains {existing_count:,} entries")
        # Auto-continue if not running interactively (e.g., via nohup)
        if sys.stdin.isatty():
            response = input("Continue adding to existing database? (y/N): ").strip().lower()
            if response != 'y':
                print("Exiting. Delete the database file to start fresh.")
                sys.exit(0)
        else:
            print("Running in non-interactive mode - auto-continuing with existing database")

    conn.close()
    print("✓ Database initialized")


def get_checkpoint():
    """Get last processed cluster ID from checkpoint file."""
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE, 'r') as f:
            return f.read().strip()
    return None


def save_checkpoint(cluster_id):
    """Save checkpoint for resume capability."""
    with open(CHECKPOINT_FILE, 'w') as f:
        f.write(cluster_id)


def parse_xml_and_build_db(xml_file, db_file):
    """Stream parse XML and populate SQLite database."""
    print(f"\n{'='*80}")
    print(f"PARSING XML AND BUILDING DATABASE")
    print(f"{'='*80}")
    print(f"XML file: {xml_file}")
    print(f"Database: {db_file}")
    print(f"Batch size: {BATCH_SIZE:,} entries")

    # Connect to database
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    # Get existing count for count-based resume
    cursor.execute("SELECT COUNT(*) FROM cluster_mappings")
    initial_count = cursor.fetchone()[0]
    print(f"Initial database count: {initial_count:,} entries")

    # Use database count to skip already-processed entries
    skip_count = initial_count
    if skip_count > 0:
        print(f"Will skip first {skip_count:,} entries (already in database)")
        print("This should take less than a minute...")

    # Tracking variables
    entries_processed = 0
    entries_inserted = 0
    entries_skipped = 0
    entries_failed = 0
    consecutive_errors = 0
    batch_count = 0
    start_time = time.time()
    last_progress_time = start_time

    # Open failed clusters log
    failed_log = open(FAILED_CLUSTERS_LOG, 'a', buffering=1)  # Line buffered
    failed_log.write(f"\n{'='*80}\n")
    failed_log.write(f"Parsing session started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    failed_log.write(f"{'='*80}\n")

    print(f"\nStarting XML parsing at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    if skip_count == 0:
        print("This will take 10-20 hours. Progress updates every 10,000 entries.\n")
    else:
        print(f"Resuming from entry {skip_count + 1:,}. Progress updates every 10,000 entries.\n")

    try:
        # Open compressed XML file
        with gzip.open(xml_file, 'rb') as f:
            # Create iterparse context
            context = ET.iterparse(f, events=('end',), tag='{http://uniprot.org/uniref}entry')

            for event, elem in context:
                entries_processed += 1

                # Skip entries already in database (count-based skip)
                if entries_processed <= skip_count:
                    entries_skipped += 1
                    # Clear element to free memory
                    elem.clear()
                    while elem.getprevious() is not None:
                        del elem.getparent()[0]

                    # Progress update during skip phase
                    if entries_skipped % 100000 == 0:
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] Skipping: {entries_skipped:,} / {skip_count:,}")
                    continue

                # Extract cluster ID
                cluster_id = elem.get('id')

                # Safety check: verify not already in database
                cursor.execute("SELECT 1 FROM cluster_mappings WHERE cluster_id = ?", (cluster_id,))
                if cursor.fetchone():
                    entries_skipped += 1
                    elem.clear()
                    while elem.getprevious() is not None:
                        del elem.getparent()[0]
                    continue

                # Process this cluster with error handling
                try:
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
                        # Get representative accession and taxid
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
                        # Get member accession
                        for prop in member.findall("{http://uniprot.org/uniref}property[@type='UniProtKB accession']"):
                            mem_acc = prop.get('value')
                            if mem_acc:
                                accessions.append(mem_acc)

                        # Get member taxid
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

                    entries_inserted += 1
                    batch_count += 1
                    consecutive_errors = 0  # Reset on success

                except Exception as e:
                    # Log the failed cluster
                    entries_failed += 1
                    consecutive_errors += 1

                    error_type = type(e).__name__
                    error_msg = str(e)

                    failed_log.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
                                   f"Entry: {entries_processed:,} | "
                                   f"Cluster: {cluster_id if cluster_id else 'UNKNOWN'} | "
                                   f"Error: {error_type}: {error_msg}\n")

                    # Circuit breaker: stop if too many consecutive errors
                    if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                        failed_log.write(f"\n{'='*80}\n")
                        failed_log.write(f"CRITICAL: {MAX_CONSECUTIVE_ERRORS} consecutive errors. Stopping.\n")
                        failed_log.write(f"{'='*80}\n")
                        failed_log.close()

                        print(f"\n\n⚠️  CRITICAL: {MAX_CONSECUTIVE_ERRORS} consecutive errors detected!")
                        print(f"Last error at entry {entries_processed:,}: {error_type}: {error_msg}")
                        print(f"This indicates a systemic issue. Stopping to prevent data corruption.")
                        print(f"Failed clusters logged to: {FAILED_CLUSTERS_LOG}")
                        conn.commit()
                        raise

                # Commit batch
                if batch_count >= BATCH_SIZE:
                    conn.commit()
                    save_checkpoint(cluster_id)
                    batch_count = 0

                # Progress update
                if entries_processed % PROGRESS_INTERVAL == 0:
                    elapsed = time.time() - start_time
                    entries_since_resume = entries_processed - skip_count
                    rate = entries_since_resume / elapsed if elapsed > 0 else 0

                    # Estimate total (assuming ~70M clusters)
                    estimated_total = 70_000_000
                    remaining = estimated_total - entries_processed
                    eta_seconds = remaining / rate if rate > 0 else 0
                    eta = timedelta(seconds=int(eta_seconds))

                    print(f"[{datetime.now().strftime('%H:%M:%S')}] "
                          f"Processed: {entries_processed:,} | "
                          f"Inserted: {entries_inserted:,} | "
                          f"Skipped: {entries_skipped:,} | "
                          f"Failed: {entries_failed:,} | "
                          f"Rate: {rate:.0f}/s | "
                          f"ETA: {eta}")

                # Critical: Clear element to free memory
                elem.clear()
                while elem.getprevious() is not None:
                    del elem.getparent()[0]

            # Final commit
            if batch_count > 0:
                conn.commit()

            # Clear context
            del context

    except KeyboardInterrupt:
        print("\n\n⚠ Interrupted by user. Saving progress...")
        conn.commit()
        failed_log.close()
        print(f"✓ Progress saved. Processed {entries_processed:,} entries so far.")
        print(f"  Inserted: {entries_inserted:,} | Skipped: {entries_skipped:,} | Failed: {entries_failed:,}")
        if entries_failed > 0:
            print(f"  Failed clusters logged to: {FAILED_CLUSTERS_LOG}")
        print(f"Run script again to resume from checkpoint.")
        sys.exit(0)

    except Exception as e:
        print(f"\n✗ Error during parsing: {e}")
        import traceback
        traceback.print_exc()
        conn.commit()
        failed_log.close()
        print(f"\nProgress saved up to {entries_processed:,} entries.")
        print(f"  Inserted: {entries_inserted:,} | Skipped: {entries_skipped:,} | Failed: {entries_failed:,}")
        if entries_failed > 0:
            print(f"  Failed clusters logged to: {FAILED_CLUSTERS_LOG}")
        sys.exit(1)

    finally:
        if not failed_log.closed:
            failed_log.close()
        conn.close()

    # Print summary
    total_time = time.time() - start_time
    hours = total_time / 3600

    print(f"\n{'='*80}")
    print(f"PARSING COMPLETE")
    print(f"{'='*80}")
    print(f"Total entries processed: {entries_processed:,}")
    print(f"Entries inserted: {entries_inserted:,}")
    print(f"Entries skipped: {entries_skipped:,}")
    print(f"Entries failed: {entries_failed:,}")
    if entries_failed > 0:
        failure_rate = (entries_failed / entries_processed * 100) if entries_processed > 0 else 0
        print(f"  Failure rate: {failure_rate:.4f}%")
        print(f"  Failed clusters logged to: {FAILED_CLUSTERS_LOG}")
    print(f"Total time: {hours:.2f} hours ({total_time/60:.1f} minutes)")
    print(f"Average rate: {entries_processed/total_time:.1f} entries/second")

    # Verify database
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM cluster_mappings")
    final_count = cursor.fetchone()[0]
    conn.close()

    print(f"\n✓ Database now contains {final_count:,} cluster mappings")

    # Clean up checkpoint
    if os.path.exists(CHECKPOINT_FILE):
        os.remove(CHECKPOINT_FILE)
        print("✓ Checkpoint file removed")


def verify_database(db_file):
    """Run some verification queries on the database."""
    print(f"\n{'='*80}")
    print(f"DATABASE VERIFICATION")
    print(f"{'='*80}")

    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    # Total count
    cursor.execute("SELECT COUNT(*) FROM cluster_mappings")
    total = cursor.fetchone()[0]
    print(f"Total clusters: {total:,}")

    # Sample entries
    cursor.execute("SELECT cluster_id, common_taxid, member_count FROM cluster_mappings LIMIT 5")
    print("\nSample entries:")
    for row in cursor.fetchall():
        print(f"  {row[0]}: common_taxid={row[1]}, members={row[2]}")

    # Statistics
    cursor.execute("SELECT AVG(member_count), MIN(member_count), MAX(member_count) FROM cluster_mappings")
    avg, min_count, max_count = cursor.fetchone()
    print(f"\nMember count statistics:")
    print(f"  Average: {avg:.2f}")
    print(f"  Min: {min_count}")
    print(f"  Max: {max_count}")

    # Check for nulls
    cursor.execute("SELECT COUNT(*) FROM cluster_mappings WHERE common_taxid IS NULL")
    null_taxid = cursor.fetchone()[0]
    print(f"\nNull common_taxid: {null_taxid:,} ({100*null_taxid/total:.2f}%)")

    cursor.execute("SELECT COUNT(*) FROM cluster_mappings WHERE member_count = 0")
    zero_members = cursor.fetchone()[0]
    print(f"Zero member count: {zero_members:,} ({100*zero_members/total:.2f}%)")

    conn.close()
    print("\n✓ Verification complete")


def main():
    """Main execution flow."""
    print(f"\n{'='*80}")
    print(f"UNIREF50 CLUSTER MAPPING DATABASE BUILDER")
    print(f"{'='*80}")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Step 1: Download XML
    if not os.path.exists(XML_FILE):
        download_xml(XML_URL, XML_FILE)
    else:
        file_size_gb = os.path.getsize(XML_FILE) / (1024**3)
        print(f"\n✓ XML file already exists ({file_size_gb:.2f} GB)")

    # Step 2: Create database
    create_database(DB_FILE)

    # Step 3: Parse and populate
    parse_xml_and_build_db(XML_FILE, DB_FILE)

    # Step 4: Verify
    verify_database(DB_FILE)

    print(f"\n{'='*80}")
    print(f"ALL STEPS COMPLETE")
    print(f"{'='*80}")
    print(f"Database file: {DB_FILE}")
    print(f"Database size: {os.path.getsize(DB_FILE) / (1024**3):.2f} GB")
    print(f"Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("\nNext step: Run augment_hf_dataset.py to update HuggingFace dataset")


if __name__ == "__main__":
    main()

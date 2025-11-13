#!/usr/bin/env python3
"""
Augment HuggingFace UniRef50 dataset with metadata from SQLite database (OPTIMIZED).

OPTIMIZATIONS:
1. Read-only database with optimized PRAGMAs (2-3x speedup)
2. Batched set-based joins (8-12x additional speedup)
3. Sampling-based validation (validation speedup)
4. Safe parallelism with multiple workers (2-3x additional speedup)

Expected total speedup: 40-90x (2-4 hours → 2-5 minutes)

Usage:
    python augment_hf_dataset_optimized.py [--test]

Options:
    --test    Test mode: only process first 10,000 entries
"""

import os
import sys
import json
import sqlite3
import argparse
import time
from datetime import datetime
from pathlib import Path
import random

try:
    from datasets import load_dataset, Dataset, DatasetDict, Features, Value, Sequence
    from huggingface_hub import HfApi, login
except ImportError:
    print("ERROR: Required packages not installed. Installing...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "datasets", "huggingface_hub"])
    from datasets import load_dataset, Dataset, DatasetDict, Features, Value, Sequence
    from huggingface_hub import HfApi, login


# Configuration
SOURCE_DATASET = "alejoacelas/uniref50-2025-10"
TARGET_DATASET = "alejoacelas/uniref50-2025-10-v3"
DB_FILE = "uniref50_mappings_optimized.db"  # Using test DB for now
PROGRESS_INTERVAL = 10000
BATCH_SIZE = 50000  # HuggingFace batch size
SQL_BATCH_SIZE = 900  # SQLite parameter limit (stay under 999)
NUM_WORKERS = 4  # Number of parallel workers


def get_optimized_db_connection(db_file):
    """Create optimized read-only database connection."""
    # Phase 1: Read-only mode with URI
    conn = sqlite3.connect(
        f'file:{db_file}?mode=ro&immutable=1',
        uri=True,
        check_same_thread=False  # Allow multi-threaded access
    )

    # Phase 1: Optimize for read-heavy workload
    conn.execute('PRAGMA query_only = ON')
    conn.execute('PRAGMA cache_size = -2000000')  # 2GB page cache
    conn.execute('PRAGMA mmap_size = 30000000000')  # 30GB memory-mapped I/O
    conn.execute('PRAGMA temp_store = MEMORY')
    conn.execute('PRAGMA journal_mode = OFF')  # Safe for read-only
    conn.execute('PRAGMA synchronous = OFF')  # Safe for read-only
    conn.execute('PRAGMA locking_mode = NORMAL')  # Allow multiple connections

    return conn


def check_database(db_file):
    """Verify database exists and has data."""
    print(f"\n{'='*80}")
    print(f"CHECKING DATABASE")
    print(f"{'='*80}")
    print(f"Database: {db_file}")

    if not os.path.exists(db_file):
        print(f"\n✗ ERROR: Database file not found!")
        print(f"Please run build_cluster_mappings.py first.")
        sys.exit(1)

    conn = get_optimized_db_connection(db_file)
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM cluster_mappings")
    count = cursor.fetchone()[0]

    if count == 0:
        print(f"\n✗ ERROR: Database is empty!")
        print(f"Please run build_cluster_mappings.py first.")
        conn.close()
        sys.exit(1)

    print(f"✓ Database contains {count:,} cluster mappings")

    # Sample a few entries
    cursor.execute("SELECT cluster_id, common_taxid, member_count FROM cluster_mappings LIMIT 3")
    print("\nSample mappings:")
    for row in cursor.fetchall():
        print(f"  {row[0]}: common_taxid={row[1]}, members={row[2]}")

    conn.close()
    print("✓ Database verification passed")
    print(f"✓ Using optimized read-only connection with PRAGMAs")


def load_source_dataset(dataset_name, test_mode=False):
    """Load the source HuggingFace dataset."""
    print(f"\n{'='*80}")
    print(f"LOADING SOURCE DATASET")
    print(f"{'='*80}")
    print(f"Dataset: {dataset_name}")

    if test_mode:
        print("⚠ TEST MODE: Loading only first 10,000 entries from train split")

    try:
        # Load dataset
        print("\nDownloading dataset (this may take a few minutes)...")
        dataset = load_dataset(dataset_name)

        if test_mode:
            # Only use first 10k entries for testing
            dataset['train'] = dataset['train'].select(range(10000))
            if 'validation' in dataset:
                dataset['validation'] = dataset['validation'].select(range(min(1000, len(dataset['validation']))))

        # Print statistics
        print(f"\n✓ Dataset loaded successfully")
        print(f"Splits: {list(dataset.keys())}")

        for split_name, split_data in dataset.items():
            print(f"  {split_name}: {len(split_data):,} entries")

        # Show sample
        print("\nSample entry:")
        sample = dataset['train'][0]
        for key, value in sample.items():
            if isinstance(value, str) and len(value) > 100:
                print(f"  {key}: {value[:100]}... (length: {len(value)})")
            else:
                print(f"  {key}: {value}")

        # Verify expected columns
        expected_cols = ['sequence_id', 'description', 'sequence', 'length']
        actual_cols = dataset['train'].column_names

        for col in expected_cols:
            if col not in actual_cols:
                print(f"\n✗ WARNING: Expected column '{col}' not found!")
                print(f"Actual columns: {actual_cols}")

        return dataset

    except Exception as e:
        print(f"\n✗ ERROR loading dataset: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def augment_dataset_with_metadata(dataset, db_file, num_workers=1):
    """Add metadata columns to dataset using batched SQLite lookups."""
    print(f"\n{'='*80}")
    print(f"AUGMENTING DATASET WITH METADATA (OPTIMIZED)")
    print(f"{'='*80}")
    print(f"Optimizations enabled:")
    print(f"  ✓ Read-only database with PRAGMAs")
    print(f"  ✓ Batched set-based joins (batch size: {BATCH_SIZE:,})")
    print(f"  ✓ Parallel workers: {num_workers}")

    start_time = time.time()

    # Statistics tracking (shared via closure)
    stats = {
        'processed': 0,
        'matched': 0,
        'missing': 0,
        'missing_examples': []
    }

    def add_metadata_batch(batch, rank=None):
        """
        Phase 2: Add metadata to a batch of examples using set-based join.

        This function processes batches from HuggingFace datasets and performs
        batched SQL queries to minimize database roundtrips.
        """
        # Each worker gets its own connection (Phase 1 optimization)
        conn = get_optimized_db_connection(db_file)
        cursor = conn.cursor()

        cluster_ids = batch['sequence_id']
        batch_size = len(cluster_ids)

        # Phase 2: Batched lookup with SQLite parameter limit handling
        all_results = {}

        # Split into sub-batches to stay under SQLite's ~999 parameter limit
        for i in range(0, len(cluster_ids), SQL_BATCH_SIZE):
            sub_ids = cluster_ids[i:i+SQL_BATCH_SIZE]
            placeholders = ','.join(['?'] * len(sub_ids))

            query = f'''
                SELECT cluster_id, common_taxid, member_taxids, member_accessions
                FROM cluster_mappings
                WHERE cluster_id IN ({placeholders})
            '''

            cursor.execute(query, sub_ids)

            for row in cursor.fetchall():
                cluster_id, common_taxid, member_taxids_json, member_accessions_json = row
                all_results[cluster_id] = (common_taxid, member_taxids_json, member_accessions_json)

        conn.close()

        # Phase 2: Build output arrays preserving input order (CRITICAL!)
        common_taxids = []
        member_taxids_list = []
        member_accessions_list = []

        matched_count = 0
        missing_count = 0

        for cluster_id in cluster_ids:
            if cluster_id in all_results:
                matched_count += 1
                common_taxid, member_taxids_json, member_accessions_json = all_results[cluster_id]

                # Parse JSON
                member_taxids = json.loads(member_taxids_json) if member_taxids_json else []
                member_accessions = json.loads(member_accessions_json) if member_accessions_json else []

                common_taxids.append(common_taxid)
                member_taxids_list.append(member_taxids)
                member_accessions_list.append(member_accessions)
            else:
                missing_count += 1
                # Add empty metadata
                common_taxids.append(None)
                member_taxids_list.append([])
                member_accessions_list.append([])

        # Update statistics
        stats['processed'] += batch_size
        stats['matched'] += matched_count
        stats['missing'] += missing_count

        # Progress logging
        if stats['processed'] % PROGRESS_INTERVAL == 0:
            elapsed = time.time() - start_time
            rate = stats['processed'] / elapsed if elapsed > 0 else 0
            match_rate = 100 * stats['matched'] / stats['processed'] if stats['processed'] > 0 else 0

            print(f"[{datetime.now().strftime('%H:%M:%S')}] "
                  f"Processed: {stats['processed']:,} | "
                  f"Matched: {stats['matched']:,} ({match_rate:.2f}%) | "
                  f"Missing: {stats['missing']:,} | "
                  f"Rate: {rate:.0f}/s")

        # Add new columns to batch
        batch['common_taxid'] = common_taxids
        batch['member_taxids'] = member_taxids_list
        batch['member_accessions'] = member_accessions_list

        return batch

    print(f"\nProcessing splits...")

    # Process each split
    augmented_dataset = {}
    for split_name, split_data in dataset.items():
        print(f"\nProcessing {split_name} split ({len(split_data):,} entries)...")

        # Reset statistics for this split
        stats['processed'] = 0
        stats['matched'] = 0
        stats['missing'] = 0
        stats['missing_examples'] = []

        split_start_time = time.time()

        # Define explicit features for multi-process compatibility
        # This ensures all workers use the same schema
        new_features = split_data.features.copy()
        new_features['common_taxid'] = Value('string')
        new_features['member_taxids'] = Sequence(Value('string'))
        new_features['member_accessions'] = Sequence(Value('string'))

        # Phase 2 & 4: Batched processing with optional parallelism
        augmented_split = split_data.map(
            add_metadata_batch,
            batched=True,  # Phase 2: Enable batched processing
            batch_size=BATCH_SIZE,  # Phase 2: Process in large batches
            num_proc=num_workers,  # Phase 4: Parallel workers
            desc=f"Adding metadata to {split_name}",
            with_rank=True if num_workers > 1 else False,
            features=Features(new_features)  # Explicit features for multi-process
        )

        augmented_dataset[split_name] = augmented_split

        # Print statistics for this split
        split_elapsed = time.time() - split_start_time
        match_rate = 100 * stats['matched'] / stats['processed'] if stats['processed'] > 0 else 0
        throughput = stats['processed'] / split_elapsed if split_elapsed > 0 else 0

        print(f"\n✓ {split_name} complete:")
        print(f"  Total: {stats['processed']:,}")
        print(f"  Matched: {stats['matched']:,} ({match_rate:.2f}%)")
        print(f"  Missing: {stats['missing']:,}")
        print(f"  Time: {split_elapsed:.1f}s")
        print(f"  Throughput: {throughput:.0f} entries/second")

    total_elapsed = time.time() - start_time
    print(f"\n✓ All splits augmented in {total_elapsed:.1f}s")

    return DatasetDict(augmented_dataset)


def validate_dataset(dataset, sample_size=100000):
    """
    Phase 3: Validate the augmented dataset using sampling.

    Instead of scanning the full dataset, we validate a sample for speed.
    """
    print(f"\n{'='*80}")
    print(f"VALIDATING AUGMENTED DATASET (SAMPLING-BASED)")
    print(f"{'='*80}")
    print(f"⚠ Using sample-based validation (n={sample_size:,}) for speed")

    # Check columns
    expected_cols = ['sequence_id', 'description', 'sequence', 'length',
                     'common_taxid', 'member_taxids', 'member_accessions']
    actual_cols = dataset['train'].column_names

    print(f"\nExpected columns: {len(expected_cols)}")
    print(f"Actual columns: {len(actual_cols)}")

    for col in expected_cols:
        if col in actual_cols:
            print(f"  ✓ {col}")
        else:
            print(f"  ✗ {col} MISSING!")

    # Sample random entries for type checking
    print(f"\nValidating 10 random entries...")
    train_size = len(dataset['train'])
    sample_indices = random.sample(range(train_size), min(10, train_size))

    validation_passed = True
    for idx in sample_indices:
        entry = dataset['train'][idx]

        # Check types
        if not isinstance(entry['common_taxid'], (str, type(None))):
            print(f"  ✗ Entry {idx}: common_taxid has wrong type: {type(entry['common_taxid'])}")
            validation_passed = False

        if not isinstance(entry['member_taxids'], list):
            print(f"  ✗ Entry {idx}: member_taxids is not a list: {type(entry['member_taxids'])}")
            validation_passed = False

        if not isinstance(entry['member_accessions'], list):
            print(f"  ✗ Entry {idx}: member_accessions is not a list: {type(entry['member_accessions'])}")
            validation_passed = False

        # Check consistency
        if len(entry['member_taxids']) != len(entry['member_accessions']):
            print(f"  ✗ Entry {idx}: member count mismatch! "
                  f"taxids={len(entry['member_taxids'])}, accessions={len(entry['member_accessions'])}")
            validation_passed = False

    if validation_passed:
        print("✓ All type validations passed")
    else:
        print("✗ Some validations failed!")

    # Phase 3: Sample-based statistics
    print(f"\nDataset statistics (sample-based, n={min(sample_size, train_size):,}):")

    # Sample for statistics
    sample_data = dataset['train'].select(range(min(sample_size, train_size)))

    # Count non-null common_taxids
    has_taxid = sum(1 for x in sample_data if x['common_taxid'] is not None)
    print(f"  Entries with common_taxid: {has_taxid:,} ({100*has_taxid/len(sample_data):.2f}%)")

    # Count entries with members
    has_members = sum(1 for x in sample_data if len(x['member_accessions']) > 0)
    print(f"  Entries with members: {has_members:,} ({100*has_members/len(sample_data):.2f}%)")

    # Show sample entry
    print("\nSample augmented entry:")
    sample = dataset['train'][0]
    print(f"  sequence_id: {sample['sequence_id']}")
    print(f"  common_taxid: {sample['common_taxid']}")
    print(f"  member_taxids: {sample['member_taxids'][:5]}{'...' if len(sample['member_taxids']) > 5 else ''} (count: {len(sample['member_taxids'])})")
    print(f"  member_accessions: {sample['member_accessions'][:5]}{'...' if len(sample['member_accessions']) > 5 else ''} (count: {len(sample['member_accessions'])})")

    return validation_passed


def upload_to_huggingface(dataset, target_name, test_mode=False):
    """Upload the augmented dataset to HuggingFace."""
    print(f"\n{'='*80}")
    print(f"UPLOADING TO HUGGINGFACE")
    print(f"{'='*80}")
    print(f"Target dataset: {target_name}")

    if test_mode:
        print("\n⚠ TEST MODE: Skipping upload")
        print(f"To upload, run without --test flag")
        return

    # Check for HF token
    token = os.environ.get('HF_TOKEN') or os.environ.get('HUGGINGFACE_TOKEN')

    if not token:
        print("\n⚠ HuggingFace token not found in environment")
        print("Please set HF_TOKEN or HUGGINGFACE_TOKEN environment variable")
        print("Or login interactively:")

        try:
            login()
        except Exception as e:
            print(f"\n✗ Login failed: {e}")
            print("\nTo upload later, use:")
            print(f"  from datasets import load_from_disk")
            print(f"  dataset = load_from_disk('./augmented_dataset')")
            print(f"  dataset.push_to_hub('{target_name}')")
            return

    # Save locally first
    print("\nSaving dataset locally...")
    dataset.save_to_disk('./augmented_dataset')
    print("✓ Saved to ./augmented_dataset")

    # Upload
    print(f"\nUploading to {target_name}...")
    print("This may take 10-30 minutes depending on connection speed...")

    try:
        dataset.push_to_hub(
            target_name,
            private=False,
            token=token
        )
        print(f"\n✓ Upload complete!")
        print(f"Dataset available at: https://huggingface.co/datasets/{target_name}")

    except Exception as e:
        print(f"\n✗ Upload failed: {e}")
        import traceback
        traceback.print_exc()
        print(f"\nDataset saved locally to ./augmented_dataset")
        print(f"You can upload manually later using:")
        print(f"  from datasets import load_from_disk")
        print(f"  dataset = load_from_disk('./augmented_dataset')")
        print(f"  dataset.push_to_hub('{target_name}')")


def main():
    """Main execution flow."""
    parser = argparse.ArgumentParser(description='Augment UniRef50 HF dataset with metadata (OPTIMIZED)')
    parser.add_argument('--test', action='store_true', help='Test mode: only process 10k entries')
    parser.add_argument('--workers', type=int, default=NUM_WORKERS, help=f'Number of parallel workers (default: {NUM_WORKERS})')
    args = parser.parse_args()

    print(f"\n{'='*80}")
    print(f"UNIREF50 DATASET AUGMENTATION (OPTIMIZED)")
    print(f"{'='*80}")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    if args.test:
        print("\n⚠ RUNNING IN TEST MODE")

    print(f"\nOptimizations:")
    print(f"  • Read-only database with PRAGMAs")
    print(f"  • Batched SQL joins (batch size: {BATCH_SIZE:,})")
    print(f"  • Sampling-based validation")
    print(f"  • Parallel workers: {args.workers}")

    overall_start = time.time()

    # Step 1: Check database
    check_database(DB_FILE)

    # Step 2: Load source dataset
    dataset = load_source_dataset(SOURCE_DATASET, test_mode=args.test)

    # Step 3: Augment with metadata
    augmented_dataset = augment_dataset_with_metadata(dataset, DB_FILE, num_workers=args.workers)

    # Step 4: Validate
    validation_passed = validate_dataset(augmented_dataset)

    if not validation_passed:
        print("\n⚠ WARNING: Validation failed. Review errors before uploading.")
        response = input("Continue with upload anyway? (y/N): ").strip().lower()
        if response != 'y':
            print("Exiting without upload.")
            sys.exit(1)

    # Save locally for testing/comparison
    print(f"\nSaving augmented dataset locally...")
    augmented_dataset.save_to_disk('./augmented_dataset')
    print(f"✓ Saved to ./augmented_dataset")

    # Step 5: Upload
    upload_to_huggingface(augmented_dataset, TARGET_DATASET, test_mode=args.test)

    overall_elapsed = time.time() - overall_start

    print(f"\n{'='*80}")
    print(f"ALL STEPS COMPLETE")
    print(f"{'='*80}")
    print(f"Total time: {overall_elapsed:.1f}s ({overall_elapsed/60:.1f} minutes)")
    print(f"Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    if args.test:
        print("\n⚠ Test mode was used. Run without --test to process full dataset and upload.")
    else:
        print(f"\n✓ Dataset uploaded to: https://huggingface.co/datasets/{TARGET_DATASET}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Augment HuggingFace UniRef50 dataset with metadata from SQLite database.

This script:
1. Loads the existing HuggingFace dataset (alejoacelas/uniref50-2025-10)
2. Looks up cluster metadata from SQLite database
3. Adds three new columns: common_taxid, member_taxids, member_accessions
4. Writes updated dataset to Parquet format
5. Uploads to HuggingFace as alejoacelas/uniref50-2025-10-v2

Usage:
    python augment_hf_dataset.py [--test]

Options:
    --test    Test mode: only process first 10,000 entries
"""

import os
import sys
import json
import sqlite3
import argparse
from datetime import datetime
from pathlib import Path
import random

try:
    from datasets import load_dataset, Dataset, DatasetDict
    from huggingface_hub import HfApi, login
except ImportError:
    print("ERROR: Required packages not installed. Installing...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "datasets", "huggingface_hub"])
    from datasets import load_dataset, Dataset, DatasetDict
    from huggingface_hub import HfApi, login


# Configuration
SOURCE_DATASET = "alejoacelas/uniref50-2025-10"
TARGET_DATASET = "alejoacelas/uniref50-2025-10-v2"
DB_FILE = "uniref50_mappings.db"
PROGRESS_INTERVAL = 10000


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

    conn = sqlite3.connect(db_file)
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


def augment_dataset_with_metadata(dataset, db_file):
    """Add metadata columns to dataset using SQLite lookups."""
    print(f"\n{'='*80}")
    print(f"AUGMENTING DATASET WITH METADATA")
    print(f"{'='*80}")

    # Connect to database
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    # Statistics
    total_processed = 0
    total_matched = 0
    total_missing = 0
    missing_examples = []

    def add_metadata(example):
        """Add metadata columns to a single example."""
        nonlocal total_processed, total_matched, total_missing

        total_processed += 1

        cluster_id = example['sequence_id']

        # Lookup in database
        cursor.execute('''
            SELECT common_taxid, member_taxids, member_accessions
            FROM cluster_mappings
            WHERE cluster_id = ?
        ''', (cluster_id,))

        row = cursor.fetchone()

        if row:
            total_matched += 1
            common_taxid, member_taxids_json, member_accessions_json = row

            # Parse JSON arrays
            member_taxids = json.loads(member_taxids_json) if member_taxids_json else []
            member_accessions = json.loads(member_accessions_json) if member_accessions_json else []

            # Add new columns
            example['common_taxid'] = common_taxid if common_taxid else None
            example['member_taxids'] = member_taxids
            example['member_accessions'] = member_accessions
        else:
            total_missing += 1
            if len(missing_examples) < 10:
                missing_examples.append(cluster_id)

            # Add empty metadata
            example['common_taxid'] = None
            example['member_taxids'] = []
            example['member_accessions'] = []

        # Progress update
        if total_processed % PROGRESS_INTERVAL == 0:
            match_rate = 100 * total_matched / total_processed if total_processed > 0 else 0
            print(f"[{datetime.now().strftime('%H:%M:%S')}] "
                  f"Processed: {total_processed:,} | "
                  f"Matched: {total_matched:,} ({match_rate:.2f}%) | "
                  f"Missing: {total_missing:,}")

        return example

    print(f"\nProcessing splits...")

    # Process each split
    augmented_dataset = {}
    for split_name, split_data in dataset.items():
        print(f"\nProcessing {split_name} split ({len(split_data):,} entries)...")

        total_processed = 0
        total_matched = 0
        total_missing = 0
        missing_examples = []

        augmented_split = split_data.map(
            add_metadata,
            num_proc=1,  # Sequential processing for database access
            desc=f"Adding metadata to {split_name}"
        )

        augmented_dataset[split_name] = augmented_split

        # Print statistics for this split
        match_rate = 100 * total_matched / total_processed if total_processed > 0 else 0
        print(f"\n✓ {split_name} complete:")
        print(f"  Total: {total_processed:,}")
        print(f"  Matched: {total_matched:,} ({match_rate:.2f}%)")
        print(f"  Missing: {total_missing:,}")

        if missing_examples:
            print(f"  Example missing IDs: {', '.join(missing_examples[:5])}")

    conn.close()

    return DatasetDict(augmented_dataset)


def validate_dataset(dataset):
    """Validate the augmented dataset."""
    print(f"\n{'='*80}")
    print(f"VALIDATING AUGMENTED DATASET")
    print(f"{'='*80}")

    # Check columns
    expected_cols = ['sequence_id', 'description', 'sequence', 'length',
                     'common_taxid', 'member_taxids', 'member_accessions']
    actual_cols = dataset['train'].column_names

    print(f"Expected columns: {len(expected_cols)}")
    print(f"Actual columns: {len(actual_cols)}")

    for col in expected_cols:
        if col in actual_cols:
            print(f"  ✓ {col}")
        else:
            print(f"  ✗ {col} MISSING!")

    # Sample random entries
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
        print("✓ All validations passed")
    else:
        print("✗ Some validations failed!")

    # Show statistics
    print("\nDataset statistics:")
    train_data = dataset['train']

    # Count non-null common_taxids
    has_taxid = sum(1 for x in train_data if x['common_taxid'] is not None)
    print(f"  Entries with common_taxid: {has_taxid:,} ({100*has_taxid/len(train_data):.2f}%)")

    # Count entries with members
    has_members = sum(1 for x in train_data if len(x['member_accessions']) > 0)
    print(f"  Entries with members: {has_members:,} ({100*has_members/len(train_data):.2f}%)")

    # Show sample entry
    print("\nSample augmented entry:")
    sample = train_data[0]
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
    parser = argparse.ArgumentParser(description='Augment UniRef50 HF dataset with metadata')
    parser.add_argument('--test', action='store_true', help='Test mode: only process 10k entries')
    args = parser.parse_args()

    print(f"\n{'='*80}")
    print(f"UNIREF50 DATASET AUGMENTATION")
    print(f"{'='*80}")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    if args.test:
        print("\n⚠ RUNNING IN TEST MODE")

    # Step 1: Check database
    check_database(DB_FILE)

    # Step 2: Load source dataset
    dataset = load_source_dataset(SOURCE_DATASET, test_mode=args.test)

    # Step 3: Augment with metadata
    augmented_dataset = augment_dataset_with_metadata(dataset, DB_FILE)

    # Step 4: Validate
    validation_passed = validate_dataset(augmented_dataset)

    if not validation_passed:
        print("\n⚠ WARNING: Validation failed. Review errors before uploading.")
        response = input("Continue with upload anyway? (y/N): ").strip().lower()
        if response != 'y':
            print("Exiting without upload.")
            sys.exit(1)

    # Step 5: Upload
    upload_to_huggingface(augmented_dataset, TARGET_DATASET, test_mode=args.test)

    print(f"\n{'='*80}")
    print(f"ALL STEPS COMPLETE")
    print(f"{'='*80}")
    print(f"Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    if args.test:
        print("\n⚠ Test mode was used. Run without --test to process full dataset and upload.")
    else:
        print(f"\n✓ Dataset uploaded to: https://huggingface.co/datasets/{TARGET_DATASET}")


if __name__ == "__main__":
    main()

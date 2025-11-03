#!/usr/bin/env python3
"""
UniRef50 Dataset Preparation Pipeline for Protein Language Model Training

This script:
1. Loads and filters UniRef50 FASTA (removes synthetic constructs)
2. Creates validation split (0.5% random selection)
3. Uses MMseqs2 to find train sequences similar to validation
4. Removes train sequences with ≥50% identity to validation
5. Creates HuggingFace dataset and uploads to Hub
"""

import os
import gzip
import random
import subprocess
import tempfile
import shutil
import time
import multiprocessing
from pathlib import Path
from typing import Dict, List, Tuple
from collections import defaultdict
from datetime import timedelta
import argparse

from datasets import Dataset, DatasetDict, concatenate_datasets
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def format_time(seconds: float) -> str:
    """Format seconds into human-readable time string."""
    return str(timedelta(seconds=int(seconds)))


def parse_fasta(fasta_path: str, max_sequences: int = None) -> List[Dict]:
    """
    Parse FASTA file and return list of sequence dictionaries.

    Args:
        fasta_path: Path to FASTA file (can be .gz)
        max_sequences: Maximum number of sequences to load (for testing)

    Returns:
        List of dicts with keys: sequence_id, description, sequence, length
    """
    sequences = []

    open_func = gzip.open if fasta_path.endswith('.gz') else open

    with open_func(fasta_path, 'rt') as f:
        current_header = None
        current_seq = []

        for line in f:
            line = line.strip()

            if line.startswith('>'):
                # Save previous sequence
                if current_header is not None:
                    seq_str = ''.join(current_seq)
                    # Parse header: >UniRef50_ID Description n=X Tax=Y TaxID=Z RepID=R
                    parts = current_header[1:].split(None, 1)
                    seq_id = parts[0]
                    description = parts[1] if len(parts) > 1 else ""

                    sequences.append({
                        'sequence_id': seq_id,
                        'description': description,
                        'sequence': seq_str,
                        'length': len(seq_str)
                    })

                    if max_sequences and len(sequences) >= max_sequences:
                        break

                # Start new sequence
                current_header = line
                current_seq = []
            else:
                current_seq.append(line)

        # Don't forget the last sequence
        if current_header is not None and (not max_sequences or len(sequences) < max_sequences):
            seq_str = ''.join(current_seq)
            parts = current_header[1:].split(None, 1)
            seq_id = parts[0]
            description = parts[1] if len(parts) > 1 else ""

            sequences.append({
                'sequence_id': seq_id,
                'description': description,
                'sequence': seq_str,
                'length': len(seq_str)
            })

    return sequences


def filter_synthetic_constructs(sequences: List[Dict]) -> Tuple[List[Dict], int]:
    """
    Remove sequences with 'Tax=synthetic construct' in description.

    Returns:
        (filtered_sequences, count_removed)
    """
    filtered = []
    removed_count = 0

    for seq in sequences:
        if "Tax=synthetic construct" in seq['description']:
            removed_count += 1
        else:
            filtered.append(seq)

    return filtered, removed_count


def create_validation_split(sequences: List[Dict], val_fraction: float = 0.005,
                           random_seed: int = 42) -> Tuple[List[Dict], List[Dict]]:
    """
    Randomly split sequences into train and validation sets.

    Args:
        sequences: List of sequence dicts
        val_fraction: Fraction for validation (default 0.005 = 0.5%)
        random_seed: Random seed for reproducibility

    Returns:
        (train_sequences, val_sequences)
    """
    random.seed(random_seed)

    # Shuffle and split
    shuffled = sequences.copy()
    random.shuffle(shuffled)

    val_size = int(len(shuffled) * val_fraction)
    val_sequences = shuffled[:val_size]
    train_sequences = shuffled[val_size:]

    return train_sequences, val_sequences


def write_fasta(sequences: List[Dict], output_path: str):
    """Write sequences to FASTA file."""
    with open(output_path, 'w') as f:
        for seq in sequences:
            f.write(f">{seq['sequence_id']} {seq['description']}\n")
            # Write sequence in lines of 80 characters
            seq_str = seq['sequence']
            for i in range(0, len(seq_str), 80):
                f.write(seq_str[i:i+80] + '\n')


def run_mmseqs2_search(train_fasta: str, val_fasta: str, output_dir: str,
                       threads: int = None) -> Tuple[str, Dict[str, float]]:
    """
    Run MMseqs2 similarity search between train and validation sets.

    Args:
        train_fasta: Path to train FASTA file
        val_fasta: Path to validation FASTA file
        output_dir: Directory for MMseqs2 outputs
        threads: Number of threads to use (default: all available CPUs)

    Returns:
        Tuple of (path to results TSV file, timing dict)
    """
    timings = {}

    print("\n=== Running MMseqs2 similarity search ===")

    # Determine number of threads
    if threads is None:
        threads = multiprocessing.cpu_count()
    print(f"Using {threads} threads")

    # Create MMseqs2 databases
    train_db = os.path.join(output_dir, "train_db")
    val_db = os.path.join(output_dir, "val_db")
    result_db = os.path.join(output_dir, "result_db")
    tmp_dir = os.path.join(output_dir, "tmp")

    os.makedirs(tmp_dir, exist_ok=True)

    # Create train database
    print("Creating train database...")
    start = time.time()
    subprocess.run([
        "mmseqs", "createdb", train_fasta, train_db, "-v", "1"
    ], check=True)
    timings['createdb_train'] = time.time() - start
    print(f"  ✓ Completed in {format_time(timings['createdb_train'])}")

    # Create validation database
    print("Creating validation database...")
    start = time.time()
    subprocess.run([
        "mmseqs", "createdb", val_fasta, val_db, "-v", "1"
    ], check=True)
    timings['createdb_val'] = time.time() - start
    print(f"  ✓ Completed in {format_time(timings['createdb_val'])}")

    # Run search with exact parameters from instructions + threading
    print("Running similarity search (this may take a while)...")
    print(f"  Parameters: min-seq-id=0.5, alignment-mode=3, sensitivity=7, coverage=0.8")
    start = time.time()
    subprocess.run([
        "mmseqs", "search",
        train_db, val_db, result_db, tmp_dir,
        "--min-seq-id", "0.5",
        "--alignment-mode", "3",
        "--max-seqs", "300",
        "-s", "7",
        "-c", "0.8",
        "--cov-mode", "0",
        "--threads", str(threads),
        "-v", "2"  # Verbosity level 2 for progress
    ], check=True)
    timings['search'] = time.time() - start
    print(f"  ✓ Search completed in {format_time(timings['search'])}")

    # Convert results to TSV
    result_tsv = os.path.join(output_dir, "results.tsv")
    print("Converting results to TSV...")
    start = time.time()
    subprocess.run([
        "mmseqs", "convertalis",
        train_db, val_db, result_db, result_tsv,
        "--threads", str(threads),
        "-v", "1"
    ], check=True)
    timings['convertalis'] = time.time() - start
    print(f"  ✓ Conversion completed in {format_time(timings['convertalis'])}")

    # Clean up tmp directory
    print("Cleaning up temporary files...")
    start = time.time()
    if os.path.exists(tmp_dir):
        shutil.rmtree(tmp_dir)
    timings['cleanup'] = time.time() - start
    print(f"  ✓ Cleanup completed in {format_time(timings['cleanup'])}")

    return result_tsv, timings


def parse_mmseqs2_results(tsv_path: str) -> set:
    """
    Parse MMseqs2 results and return set of train sequence IDs that match validation.

    Returns:
        Set of train sequence IDs to remove
    """
    train_ids_to_remove = set()

    if not os.path.exists(tsv_path):
        print(f"Warning: Results file {tsv_path} not found")
        return train_ids_to_remove

    with open(tsv_path, 'r') as f:
        for line in f:
            parts = line.strip().split('\t')
            if len(parts) >= 2:
                train_id = parts[0]  # Query (train sequence)
                train_ids_to_remove.add(train_id)

    return train_ids_to_remove


def remove_similar_sequences(train_sequences: List[Dict],
                            ids_to_remove: set) -> Tuple[List[Dict], int]:
    """
    Remove train sequences that are similar to validation set.

    Returns:
        (filtered_train_sequences, count_removed)
    """
    filtered = []
    removed_count = 0

    for seq in train_sequences:
        if seq['sequence_id'] in ids_to_remove:
            removed_count += 1
        else:
            filtered.append(seq)

    return filtered, removed_count


def create_huggingface_dataset(train_sequences: List[Dict],
                               val_sequences: List[Dict],
                               chunk_size: int = 1000000) -> DatasetDict:
    """
    Create HuggingFace DatasetDict from sequences using chunked processing.

    Args:
        train_sequences: List of train sequence dicts
        val_sequences: List of validation sequence dicts
        chunk_size: Number of sequences to process per chunk (default 1M)

    Returns:
        DatasetDict with train and validation splits
    """
    # Process train sequences in chunks to reduce peak memory
    print(f"           Creating train dataset in chunks of {chunk_size:,} sequences...")
    train_chunks = []
    
    for i in range(0, len(train_sequences), chunk_size):
        chunk = train_sequences[i:i + chunk_size]
        chunk_dataset = Dataset.from_list(chunk)
        train_chunks.append(chunk_dataset)
        print(f"           Processed chunk {len(train_chunks)} ({len(chunk):,} sequences)")
    
    # Concatenate all train chunks
    if len(train_chunks) > 1:
        train_dataset = concatenate_datasets(train_chunks)
    else:
        train_dataset = train_chunks[0] if train_chunks else Dataset.from_list([])
    
    # Validation set is small, process normally
    val_dataset = Dataset.from_list(val_sequences)

    dataset_dict = DatasetDict({
        'train': train_dataset,
        'validation': val_dataset
    })

    return dataset_dict


def main():
    parser = argparse.ArgumentParser(description='Prepare UniRef50 dataset for pLM training')
    parser.add_argument('--fasta', type=str, required=True,
                       help='Path to UniRef50 FASTA file (.fasta or .fasta.gz)')
    parser.add_argument('--max-sequences', type=int, default=None,
                       help='Maximum sequences to process (for testing)')
    parser.add_argument('--output-dir', type=str, default='./output',
                       help='Output directory for intermediate files')
    parser.add_argument('--hf-dataset-name', type=str, default='alejoacelas/uniref50-2025-3',
                       help='HuggingFace dataset name (username/dataset)')
    parser.add_argument('--upload', action='store_true',
                       help='Upload to HuggingFace Hub')
    parser.add_argument('--public', action='store_true', default=True,
                       help='Make dataset public on HuggingFace Hub')
    parser.add_argument('--threads', type=int, default=None,
                       help='Number of threads for MMseqs2 (default: all available CPUs)')

    args = parser.parse_args()

    # Track overall timing
    pipeline_start = time.time()
    step_timings = {}

    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("="*80)
    print("UniRef50 Dataset Preparation Pipeline")
    print("="*80)
    print(f"Start time: {time.strftime('%Y-%m-%d %H:%M:%S')}")

    # Step 1: Load and parse FASTA
    print(f"\n[Step 1/6] Loading FASTA file: {args.fasta}")
    if args.max_sequences:
        print(f"           (limiting to {args.max_sequences} sequences for testing)")

    step_start = time.time()
    sequences = parse_fasta(args.fasta, max_sequences=args.max_sequences)
    step_timings['load_fasta'] = time.time() - step_start
    print(f"           Loaded {len(sequences):,} sequences")
    print(f"           ⏱  Time: {format_time(step_timings['load_fasta'])}")

    # Step 2: Filter synthetic constructs
    print(f"\n[Step 2/6] Filtering synthetic constructs...")
    step_start = time.time()
    filtered_sequences, synthetic_removed = filter_synthetic_constructs(sequences)
    step_timings['filter_synthetic'] = time.time() - step_start
    print(f"           Removed {synthetic_removed:,} synthetic constructs")
    print(f"           Remaining: {len(filtered_sequences):,} sequences")
    print(f"           ⏱  Time: {format_time(step_timings['filter_synthetic'])}")

    # Step 3: Create validation split
    print(f"\n[Step 3/6] Creating validation split (0.5%)...")
    step_start = time.time()
    train_sequences, val_sequences = create_validation_split(filtered_sequences)
    print(f"           Train set: {len(train_sequences):,} sequences")
    print(f"           Validation set: {len(val_sequences):,} sequences")

    # Write FASTA files for MMseqs2
    train_fasta = output_dir / "train.fasta"
    val_fasta = output_dir / "validation.fasta"

    print(f"\n           Writing temporary FASTA files...")
    write_fasta(train_sequences, str(train_fasta))
    write_fasta(val_sequences, str(val_fasta))
    step_timings['create_split'] = time.time() - step_start
    print(f"           ⏱  Time: {format_time(step_timings['create_split'])}")

    # Step 4: Run MMseqs2 similarity search
    print(f"\n[Step 4/6] Running MMseqs2 similarity search...")
    mmseqs_output_dir = output_dir / "mmseqs2"
    mmseqs_output_dir.mkdir(exist_ok=True)

    step_start = time.time()
    results_tsv, mmseqs_timings = run_mmseqs2_search(
        str(train_fasta),
        str(val_fasta),
        str(mmseqs_output_dir),
        threads=args.threads
    )
    step_timings['mmseqs2_total'] = time.time() - step_start
    step_timings['mmseqs2_breakdown'] = mmseqs_timings

    # Step 5: Parse results and remove similar sequences
    print(f"\n[Step 5/6] Removing similar sequences from train set...")
    step_start = time.time()
    ids_to_remove = parse_mmseqs2_results(results_tsv)
    print(f"           Found {len(ids_to_remove):,} train sequences similar to validation")

    final_train_sequences, removed_count = remove_similar_sequences(
        train_sequences, ids_to_remove
    )
    step_timings['remove_similar'] = time.time() - step_start
    print(f"           Removed {removed_count:,} sequences from train set")
    print(f"           Final train set: {len(final_train_sequences):,} sequences")
    print(f"           ⏱  Time: {format_time(step_timings['remove_similar'])}")

    # Step 6: Create HuggingFace dataset
    print(f"\n[Step 6/6] Creating HuggingFace dataset...")
    step_start = time.time()
    dataset = create_huggingface_dataset(final_train_sequences, val_sequences)

    print(f"\n{dataset}")

    # Save locally
    local_dataset_path = output_dir / "dataset"
    print(f"\n           Saving dataset locally to {local_dataset_path}...")
    dataset.save_to_disk(str(local_dataset_path))
    step_timings['create_dataset'] = time.time() - step_start
    print(f"           ⏱  Time: {format_time(step_timings['create_dataset'])}")

    # Upload to HuggingFace Hub
    if args.upload:
        print(f"\n           Uploading to HuggingFace Hub: {args.hf_dataset_name}...")

        hf_token = os.getenv('HF_TOKEN')
        if not hf_token:
            print("           ERROR: HF_TOKEN not found in environment!")
            print("           Dataset saved locally but not uploaded.")
        else:
            # Create dataset card
            card_content = f"""---
license: cc-by-4.0
task_categories:
- fill-mask
language:
- en
tags:
- protein
- biology
- protein-language-model
- uniref50
size_categories:
- {len(final_train_sequences) + len(val_sequences)}
---

# UniRef50 Dataset for Protein Language Model Training

This dataset is derived from UniRef50 (Release 2025_03) and prepared for protein language model pre-training.

## Dataset Statistics

- **Original UniRef50 sequences**: {len(sequences):,}
- **Synthetic constructs removed**: {synthetic_removed:,}
- **Validation set size**: {len(val_sequences):,} ({0.5}%)
- **Initial train set size**: {len(train_sequences):,}
- **Sequences removed by similarity filter (≥50% identity)**: {removed_count:,}
- **Final train set size**: {len(final_train_sequences):,}
- **Total sequences in dataset**: {len(final_train_sequences) + len(val_sequences):,}

## Processing Details

- **Processing date**: 2025-11-03
- **MMseqs2 version**: 13-45111+ds-2
- **Similarity threshold**: 50% sequence identity
- **Coverage threshold**: 80%
- **Alignment mode**: 3
- **Sensitivity**: 7

## Data Fields

- `sequence`: Amino acid sequence (string)
- `sequence_id`: UniRef50 cluster ID (string)
- `description`: Full description including taxonomy info (string)
- `length`: Sequence length in amino acids (integer)

## Intended Use

This dataset is intended for pre-training protein language models, following similar procedures as used for ESM models.

## Citation

If you use this dataset, please cite UniProt:

```
UniProt Consortium. "UniProt: the Universal Protein Knowledgebase in 2025."
Nucleic Acids Research (2025).
```
"""

            # Save card
            card_path = output_dir / "README.md"
            with open(card_path, 'w') as f:
                f.write(card_content)

            # Upload
            try:
                dataset.push_to_hub(
                    args.hf_dataset_name,
                    private=not args.public,
                    token=hf_token
                )
                print(f"\n           ✓ Successfully uploaded to: https://huggingface.co/datasets/{args.hf_dataset_name}")
            except Exception as e:
                print(f"\n           ERROR during upload: {e}")
                print("           Dataset saved locally but not uploaded.")

    # Calculate total time
    total_time = time.time() - pipeline_start

    # Print final summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"Total UniRef50 sequences processed: {len(sequences):,}")
    print(f"Synthetic constructs filtered: {synthetic_removed:,}")
    print(f"Validation set size: {len(val_sequences):,} ({0.5}%)")
    print(f"Train sequences removed (≥50% identity to val): {removed_count:,}")
    print(f"Final train set size: {len(final_train_sequences):,}")
    print(f"Final validation set size: {len(val_sequences):,}")
    print("="*80)

    # Print timing breakdown
    print("\n" + "="*80)
    print("TIMING BREAKDOWN")
    print("="*80)
    print(f"Step 1 - Load FASTA:              {format_time(step_timings['load_fasta']):>12}")
    print(f"Step 2 - Filter synthetic:        {format_time(step_timings['filter_synthetic']):>12}")
    print(f"Step 3 - Create splits & FASTA:   {format_time(step_timings['create_split']):>12}")
    print(f"Step 4 - MMseqs2 similarity:")
    if 'mmseqs2_breakdown' in step_timings:
        for key, val in step_timings['mmseqs2_breakdown'].items():
            print(f"         - {key:20s}    {format_time(val):>12}")
    print(f"         Total MMseqs2:           {format_time(step_timings['mmseqs2_total']):>12}")
    print(f"Step 5 - Remove similar:          {format_time(step_timings['remove_similar']):>12}")
    print(f"Step 6 - Create HF dataset:       {format_time(step_timings['create_dataset']):>12}")
    print(f"\n{'='*80}")
    print(f"TOTAL PIPELINE TIME:              {format_time(total_time):>12}")
    print(f"End time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)

    # Save timing log
    timing_log = output_dir / "timing_log.txt"
    with open(timing_log, 'w') as f:
        f.write("UniRef50 Dataset Preparation - Timing Log\n")
        f.write("="*80 + "\n\n")
        f.write(f"Sequences processed: {len(sequences):,}\n")
        f.write(f"Threads used: {args.threads if args.threads else multiprocessing.cpu_count()}\n\n")
        f.write("Step timings:\n")
        f.write(f"  Load FASTA: {format_time(step_timings['load_fasta'])}\n")
        f.write(f"  Filter synthetic: {format_time(step_timings['filter_synthetic'])}\n")
        f.write(f"  Create splits: {format_time(step_timings['create_split'])}\n")
        f.write(f"  MMseqs2 total: {format_time(step_timings['mmseqs2_total'])}\n")
        if 'mmseqs2_breakdown' in step_timings:
            for key, val in step_timings['mmseqs2_breakdown'].items():
                f.write(f"    - {key}: {format_time(val)}\n")
        f.write(f"  Remove similar: {format_time(step_timings['remove_similar'])}\n")
        f.write(f"  Create dataset: {format_time(step_timings['create_dataset'])}\n")
        f.write(f"\nTotal time: {format_time(total_time)}\n")

    print(f"\n✓ Timing log saved to: {timing_log}")


if __name__ == "__main__":
    main()

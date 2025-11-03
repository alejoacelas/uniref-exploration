#!/usr/bin/env python3
"""
Filter MMseqs2 clustering results by similarity threshold.

This script demonstrates how to:
1. Parse MMseqs2 clustering TSV output
2. Re-align sequences with detailed metrics
3. Filter by sequence identity and coverage thresholds
4. Export filtered results

Usage:
    python filter_by_similarity.py <input_tsv> <output_tsv> --min-identity 0.7 --min-coverage 0.9
"""

import argparse
import subprocess
import sys
from pathlib import Path


def parse_clusters(tsv_file):
    """Parse MMseqs2 clustering TSV into dictionary."""
    clusters = {}
    with open(tsv_file, 'r') as f:
        for line in f:
            rep, member = line.strip().split('\t')
            if rep not in clusters:
                clusters[rep] = []
            clusters[rep].append(member)
    return clusters


def create_alignment_db(db_prefix, clu_db, min_identity, min_coverage):
    """Re-align cluster members with detailed similarity metrics."""
    aln_db = f"{clu_db}_aln"

    cmd = [
        'mmseqs', 'align',
        f'{db_prefix}', f'{db_prefix}',
        clu_db, aln_db,
        '--min-seq-id', str(min_identity),
        '-c', str(min_coverage),
        '--alignment-mode', '3',  # Smith-Waterman
        '-v', '3'
    ]

    print(f"Running alignment: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"Error running alignment: {result.stderr}")
        sys.exit(1)

    return aln_db


def convert_to_tsv_with_metrics(db_prefix, aln_db, output_tsv):
    """Convert alignment DB to TSV with similarity metrics."""
    cmd = [
        'mmseqs', 'convertalis',
        f'{db_prefix}', f'{db_prefix}',
        aln_db, output_tsv,
        '--format-output', 'query,target,pident,qcov,tcov,alnlen,qlen,tlen,evalue,bits'
    ]

    print(f"Converting to TSV: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"Error converting to TSV: {result.stderr}")
        sys.exit(1)


def filter_alignments(aln_tsv, output_tsv, min_identity, min_coverage, bidirectional=True):
    """
    Filter alignments by identity and coverage thresholds.

    Args:
        aln_tsv: Input alignment TSV with metrics
        output_tsv: Output filtered TSV
        min_identity: Minimum sequence identity (0-1)
        min_coverage: Minimum coverage (0-1)
        bidirectional: If True, require both query and target coverage >= threshold
    """
    kept = 0
    total = 0

    with open(aln_tsv, 'r') as f, open(output_tsv, 'w') as out:
        # Write header
        out.write("query\ttarget\tpident\tqcov\ttcov\talnlen\tqlen\ttlen\tevalue\tbits\n")

        for line in f:
            total += 1
            parts = line.strip().split('\t')

            if len(parts) < 5:
                continue

            query, target, pident, qcov, tcov = parts[:5]
            pident = float(pident)
            qcov = float(qcov)
            tcov = float(tcov)

            # Apply filters
            identity_pass = pident >= min_identity * 100  # convertalis outputs 0-100
            if bidirectional:
                coverage_pass = qcov >= min_coverage and tcov >= min_coverage
            else:
                coverage_pass = qcov >= min_coverage or tcov >= min_coverage

            if identity_pass and coverage_pass:
                out.write(line)
                kept += 1

    print(f"Filtered {total} alignments -> kept {kept} ({100*kept/total:.1f}%)")
    return kept


def create_filtered_cluster_tsv(filtered_aln_tsv, output_tsv):
    """Create standard cluster TSV from filtered alignments."""
    # Read alignments and group by query (representative)
    clusters = {}

    with open(filtered_aln_tsv, 'r') as f:
        next(f)  # Skip header
        for line in f:
            query, target = line.strip().split('\t')[:2]
            if query not in clusters:
                clusters[query] = set([query])  # Include rep as member
            clusters[query].add(target)

    # Write cluster TSV
    with open(output_tsv, 'w') as out:
        for rep in sorted(clusters.keys()):
            for member in sorted(clusters[rep]):
                out.write(f"{rep}\t{member}\n")

    print(f"Created cluster TSV with {len(clusters)} clusters")


def main():
    parser = argparse.ArgumentParser(
        description='Filter MMseqs2 clusters by similarity threshold',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Filter to keep only pairs with >=80% identity and >=90% coverage
  python filter_by_similarity.py DB_clu.tsv filtered_clu.tsv -i 0.8 -c 0.9

  # More lenient filtering (70% identity, 80% coverage)
  python filter_by_similarity.py DB_clu.tsv filtered_clu.tsv -i 0.7 -c 0.8

  # Require only query coverage (faster, less strict)
  python filter_by_similarity.py DB_clu.tsv filtered_clu.tsv -i 0.8 -c 0.9 --no-bidirectional
        """
    )

    parser.add_argument('input_tsv', help='Input MMseqs2 cluster TSV')
    parser.add_argument('output_tsv', help='Output filtered cluster TSV')
    parser.add_argument('-i', '--min-identity', type=float, default=0.7,
                       help='Minimum sequence identity (0-1, default: 0.7)')
    parser.add_argument('-c', '--min-coverage', type=float, default=0.9,
                       help='Minimum coverage (0-1, default: 0.9)')
    parser.add_argument('--no-bidirectional', action='store_true',
                       help='Do not require bidirectional coverage (query OR target >= threshold)')
    parser.add_argument('--db-prefix', default='DB',
                       help='MMseqs2 database prefix (default: DB)')
    parser.add_argument('--keep-intermediate', action='store_true',
                       help='Keep intermediate alignment files')

    args = parser.parse_args()

    # Validate inputs
    if not Path(args.input_tsv).exists():
        print(f"Error: Input file {args.input_tsv} not found")
        sys.exit(1)

    if not (0 <= args.min_identity <= 1):
        print("Error: min-identity must be between 0 and 1")
        sys.exit(1)

    if not (0 <= args.min_coverage <= 1):
        print("Error: min-coverage must be between 0 and 1")
        sys.exit(1)

    print("="*60)
    print("MMseqs2 Clustering Filter by Similarity")
    print("="*60)
    print(f"Input: {args.input_tsv}")
    print(f"Output: {args.output_tsv}")
    print(f"Min identity: {args.min_identity:.2f} ({args.min_identity*100:.0f}%)")
    print(f"Min coverage: {args.min_coverage:.2f} ({args.min_coverage*100:.0f}%)")
    print(f"Bidirectional: {not args.no_bidirectional}")
    print("="*60)

    # Step 1: Parse input clusters
    print("\n[1/5] Parsing input clusters...")
    clusters = parse_clusters(args.input_tsv)
    print(f"Found {len(clusters)} clusters with {sum(len(m) for m in clusters.values())} total sequences")

    # Step 2: Derive cluster DB name from input TSV
    clu_db = args.input_tsv.replace('.tsv', '')
    if not Path(f"{clu_db}.index").exists():
        print(f"Error: Cluster database {clu_db} not found")
        print(f"Expected files: {clu_db}.index, {clu_db}.dbtype, etc.")
        sys.exit(1)

    # Step 3: Create alignment with metrics
    print("\n[2/5] Re-aligning sequences with detailed metrics...")
    aln_db = create_alignment_db(args.db_prefix, clu_db, args.min_identity, args.min_coverage)

    # Step 4: Convert to TSV with metrics
    print("\n[3/5] Converting alignments to TSV...")
    aln_tsv = f"{aln_db}_metrics.tsv"
    convert_to_tsv_with_metrics(args.db_prefix, aln_db, aln_tsv)

    # Step 5: Filter by thresholds
    print("\n[4/5] Filtering by similarity thresholds...")
    filtered_aln_tsv = f"{aln_db}_filtered.tsv"
    kept = filter_alignments(
        aln_tsv, filtered_aln_tsv,
        args.min_identity, args.min_coverage,
        bidirectional=not args.no_bidirectional
    )

    if kept == 0:
        print("\nWarning: No alignments passed the filters!")
        print("Consider lowering --min-identity or --min-coverage")
        sys.exit(1)

    # Step 6: Create filtered cluster TSV
    print("\n[5/5] Creating filtered cluster TSV...")
    create_filtered_cluster_tsv(filtered_aln_tsv, args.output_tsv)

    # Cleanup
    if not args.keep_intermediate:
        print("\nCleaning up intermediate files...")
        for f in [aln_tsv, filtered_aln_tsv]:
            Path(f).unlink(missing_ok=True)
        # Remove alignment DB files
        for f in Path('.').glob(f"{aln_db}*"):
            f.unlink()

    print("\n" + "="*60)
    print("COMPLETE!")
    print("="*60)
    print(f"Filtered clusters written to: {args.output_tsv}")
    print(f"Use this file for downstream analysis")


if __name__ == '__main__':
    main()

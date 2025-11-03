#!/bin/bash
# MMseqs2 clustering script for full uniref50 dataset
# Based on successful test with 200 sequences

set -e  # Exit on error
set -u  # Exit on undefined variable

# Configuration
INPUT_FASTA="$1"  # Path to uniref50.fasta or uniref50.fasta.gz
OUTPUT_PREFIX="${2:-uniref50_clustered}"  # Output prefix, default: uniref50_clustered
THREADS="${3:-192}"  # Number of threads, default: 192
TMP_DIR="${4:-./tmp}"  # Temporary directory

# Parameters (as specified)
MIN_SEQ_ID="0.5"
ALIGNMENT_MODE="3"
MAX_SEQS="300"
SENSITIVITY="7"
COVERAGE="0.8"
COV_MODE="0"

echo "=================================================="
echo "MMseqs2 Clustering for UniRef50"
echo "=================================================="
echo "Input:       $INPUT_FASTA"
echo "Output:      ${OUTPUT_PREFIX}"
echo "Threads:     $THREADS"
echo "Tmp dir:     $TMP_DIR"
echo ""
echo "Parameters:"
echo "  --min-seq-id:     $MIN_SEQ_ID"
echo "  --alignment-mode: $ALIGNMENT_MODE"
echo "  --max-seqs:       $MAX_SEQS"
echo "  -s (sensitivity): $SENSITIVITY"
echo "  -c (coverage):    $COVERAGE"
echo "  --cov-mode:       $COV_MODE"
echo "=================================================="
echo ""

# Check if input exists
if [ ! -f "$INPUT_FASTA" ]; then
    echo "ERROR: Input file $INPUT_FASTA not found!"
    exit 1
fi

# Create output directory
mkdir -p "$(dirname "$OUTPUT_PREFIX")"

# Step 1: Create database
echo "[$(date)] Step 1/3: Creating MMseqs2 database..."
mmseqs createdb "$INPUT_FASTA" "${OUTPUT_PREFIX}_DB" \
    --threads "$THREADS" \
    -v 3

# Step 2: Cluster
echo "[$(date)] Step 2/3: Running clustering..."
mmseqs cluster "${OUTPUT_PREFIX}_DB" "${OUTPUT_PREFIX}_clu" "$TMP_DIR" \
    --min-seq-id "$MIN_SEQ_ID" \
    --alignment-mode "$ALIGNMENT_MODE" \
    --max-seqs "$MAX_SEQS" \
    -s "$SENSITIVITY" \
    -c "$COVERAGE" \
    --cov-mode "$COV_MODE" \
    --threads "$THREADS" \
    --remove-tmp-files 1 \
    -v 3

# Step 3: Create TSV output
echo "[$(date)] Step 3/3: Creating TSV output..."
mmseqs createtsv "${OUTPUT_PREFIX}_DB" "${OUTPUT_PREFIX}_DB" "${OUTPUT_PREFIX}_clu" "${OUTPUT_PREFIX}_clu.tsv" \
    --threads "$THREADS" \
    -v 3

# Generate summary statistics
echo "[$(date)] Generating summary statistics..."
python3 << 'EOF'
import sys

clusters = {}
with open("${OUTPUT_PREFIX}_clu.tsv", 'r') as f:
    for line in f:
        rep, member = line.strip().split('\t')
        if rep not in clusters:
            clusters[rep] = []
        clusters[rep].append(member)

total_sequences = sum(len(members) for members in clusters.values())
num_clusters = len(clusters)
singleton_clusters = sum(1 for members in clusters.values() if len(members) == 1)
max_cluster_size = max(len(members) for members in clusters.values())
avg_cluster_size = total_sequences / num_clusters

print("\n" + "="*60)
print("CLUSTERING SUMMARY")
print("="*60)
print(f"Total sequences:        {total_sequences:,}")
print(f"Total clusters:         {num_clusters:,}")
print(f"Singleton clusters:     {singleton_clusters:,} ({100*singleton_clusters/num_clusters:.1f}%)")
print(f"Multi-member clusters:  {num_clusters - singleton_clusters:,} ({100*(num_clusters - singleton_clusters)/num_clusters:.1f}%)")
print(f"Largest cluster size:   {max_cluster_size:,}")
print(f"Average cluster size:   {avg_cluster_size:.2f}")
print(f"Reduction rate:         {100*(1 - num_clusters/total_sequences):.1f}%")
print("="*60)

# Write summary to file
with open("${OUTPUT_PREFIX}_summary.txt", 'w') as out:
    out.write(f"Total sequences: {total_sequences}\n")
    out.write(f"Total clusters: {num_clusters}\n")
    out.write(f"Singleton clusters: {singleton_clusters}\n")
    out.write(f"Reduction rate: {100*(1 - num_clusters/total_sequences):.2f}%\n")
    out.write(f"Largest cluster: {max_cluster_size}\n")
    out.write(f"Average cluster size: {avg_cluster_size:.2f}\n")
EOF

echo ""
echo "[$(date)] Clustering complete!"
echo ""
echo "Output files:"
echo "  - ${OUTPUT_PREFIX}_clu.tsv      (clustering results)"
echo "  - ${OUTPUT_PREFIX}_summary.txt  (summary statistics)"
echo "  - ${OUTPUT_PREFIX}_DB*          (database files)"
echo "  - ${OUTPUT_PREFIX}_clu*         (cluster database)"
echo ""

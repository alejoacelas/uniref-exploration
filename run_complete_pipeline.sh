#!/bin/bash
set -euo pipefail

# Complete MMseqs2 filtering pipeline for development/testing
# Runs from scratch starting with FASTA files in data/ directory
WORKDIR="/workspace/filtering"
cd "$WORKDIR"

echo "=== MMseqs2 Filtering Pipeline ==="
echo "Working directory: $WORKDIR"
echo

# Check for required input files
if [ ! -f "data/query.fasta" ] || [ ! -f "data/target.fasta" ]; then
    echo "ERROR: Required FASTA files not found!"
    echo "Please ensure data/query.fasta and data/target.fasta exist"
    exit 1
fi

echo "Input files:"
echo "  - Queries: $(grep -c '^>' data/query.fasta) sequences in data/query.fasta"
echo "  - Targets: $(grep -c '^>' data/target.fasta) sequences in data/target.fasta"
echo

# Step 0: Database creation and splitting
echo "Step 0: Creating MMseqs2 databases and splitting targets..."

# Create directories if they don't exist
mkdir -p mmseqs_db/target_chunks tmp results/{tsv_chunks,per_target,thresholds,final} logs

# Create query database
if [ ! -f "mmseqs_db/queryDB" ]; then
    echo "  Creating query database..."
    mmseqs createdb data/query.fasta mmseqs_db/queryDB
else
    echo "  Query database already exists, skipping..."
fi

# Create target database
if [ ! -f "mmseqs_db/targetDB" ]; then
    echo "  Creating target database..."
    mmseqs createdb data/target.fasta mmseqs_db/targetDB
else
    echo "  Target database already exists, skipping..."
fi

# Split target database into chunks
N_SPLITS=4  # Adjust for production (e.g., 128 for large datasets)
if [ ! -f "mmseqs_db/target_chunks/target_split_0_${N_SPLITS}" ]; then
    echo "  Splitting target database into $N_SPLITS chunks..."
    mmseqs splitdb mmseqs_db/targetDB mmseqs_db/target_chunks/target_split --split $N_SPLITS
else
    echo "  Target database already split, skipping..."
fi

echo "  Database setup complete!"
echo

# Step 1: Run MMseqs searches and per-target scoring on all chunks
echo "Step 1: Running MMseqs searches and per-target scoring..."

# ============================================================================
# PARALLEL EXECUTION SECTION
#
# To run chunks in parallel instead of sequentially, replace the sequential
# loop below with one of these parallel approaches:
#
# Slurm job array (for cluster environments)
# Create a separate slurm script that calls: ./run_search.sh $SLURM_ARRAY_TASK_ID $N_SPLITS
# Then submit with: sbatch --array=0-$((N_SPLITS-1)) your_slurm_script.sh
#
# wait  # Wait for all background jobs to complete
# ============================================================================

# SEQUENTIAL EXECUTION (current default)
echo "  Processing $N_SPLITS chunks sequentially..."
for chunk_id in $(seq 0 $((N_SPLITS-1))); do
    ./run_search.sh $chunk_id $N_SPLITS
done

echo "  All chunks processed!"
echo

# Step 2: Compute threshold and generate final flags
echo "Step 2: Computing threshold and generating exclusion flags..."
python3 compute_threshold_and_flags.py
echo

# Step 3: Show summary
echo "=== Pipeline Complete ==="
echo "Results:"
echo "  - Raw TSV chunks: results/tsv_chunks/"
echo "  - Per-target scores: results/per_target/"
echo "  - Final output: results/final/target_scores_and_flags.tsv"
echo "  - Threshold log: results/thresholds/threshold_log.txt"
echo

if [ -f "results/final/target_scores_and_flags.tsv" ]; then
    echo "Final results summary:"
    echo "  Total records: $(tail -n +2 results/final/target_scores_and_flags.tsv | wc -l)"
    echo "  Excluded records: $(tail -n +2 results/final/target_scores_and_flags.tsv | cut -f4 | grep -c True || echo 0)"
    echo
    echo "Threshold log:"
    cat results/thresholds/threshold_log.txt
fi
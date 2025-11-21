#!/bin/bash
set -euo pipefail

# Single chunk MMseqs search and reduction pipeline
# Usage: ./run_search.sh <chunk_id> [n_splits]
# Example: ./run_search.sh 0 4

if [ $# -lt 1 ]; then
    echo "Usage: $0 <chunk_id> [n_splits]"
    echo "Example: $0 0 4"
    exit 1
fi

CHUNK_ID=$1
N_SPLITS=${2:-4}

WORKDIR="/workspace/filtering"
cd "$WORKDIR"

CHUNK_NAME="target_split_${CHUNK_ID}_${N_SPLITS}"
QUERY_DB="$WORKDIR/mmseqs_db/queryDB"
TARGET_CHUNK_DB="$WORKDIR/mmseqs_db/target_chunks/${CHUNK_NAME}"
RESULT_DB="$WORKDIR/mmseqs_db/target_chunks/${CHUNK_NAME}_res"
TMP_DIR="$WORKDIR/tmp/${CHUNK_NAME}"
TSV_OUT="$WORKDIR/results/tsv_chunks/${CHUNK_NAME}.tsv"
SCORE_OUT="$WORKDIR/results/per_target/${CHUNK_NAME}.tsv"

echo "Processing chunk $CHUNK_ID/$((N_SPLITS-1)): $CHUNK_NAME"

# Check if chunk database exists
if [ ! -f "$TARGET_CHUNK_DB" ]; then
    echo "ERROR: Target chunk database not found: $TARGET_CHUNK_DB"
    echo "Make sure the database has been split properly."
    exit 1
fi

mkdir -p "$TMP_DIR"
mkdir -p "$(dirname "$TSV_OUT")"
mkdir -p "$(dirname "$SCORE_OUT")"

echo "  Step 1: Running MMseqs2 search..."
# Run search: queries vs this target chunk
mmseqs search "$QUERY_DB" "$TARGET_CHUNK_DB" "$RESULT_DB" "$TMP_DIR" \
  --alignment-mode 3 \
  -s 7.0 \
  -e 1e5 \
  --min-seq-id 0.0 \
  --cov-mode 0 -c 0.3 \
  --max-seqs 200 \

echo "  Step 2: Converting alignments to TSV..."
# Convert alignments to TSV with continuous metrics
mmseqs convertalis "$QUERY_DB" "$TARGET_CHUNK_DB" "$RESULT_DB" "$TSV_OUT" \
  --format-mode 4 \
  --format-output "query,target,fident,qcov,tcov,alnlen,bits"

echo "  Step 3: Computing per-target scores..."
# Reduce TSV to per-target scores using modified script
python3 reduce_chunk_to_per_target.py "$TSV_OUT" "$SCORE_OUT"

echo "  Step 4: Cleaning up intermediate files..."
# Clean up intermediate files to save space
rm -rf "$RESULT_DB"* "$TMP_DIR"

echo "  Completed chunk $CHUNK_ID"
echo "  - TSV output: $TSV_OUT"
echo "  - Score output: $SCORE_OUT"
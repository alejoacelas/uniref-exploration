#!/bin/bash
set -e  # Exit on error

echo "╔══════════════════════════════════════════════════════════════════════════╗"
echo "║         UniRef50 2025_03 Dataset Preparation - Full Pipeline            ║"
echo "╚══════════════════════════════════════════════════════════════════════════╝"
echo ""

# Configuration
RELEASE="2025_03"
ARCHIVE_URL="https://ftp.uniprot.org/pub/databases/uniprot/previous_releases/release-${RELEASE}/uniref/uniref${RELEASE}.tar.gz"
ARCHIVE_FILE="uniref${RELEASE}.tar.gz"
FASTA_FILE="uniref50.fasta.gz"
OUTPUT_DIR="./uniref50_output"
HF_DATASET="alejoacelas/uniref50-2025-3"
THREADS=${THREADS:-$(nproc)}  # Use all CPUs by default
LOG_FILE="full_pipeline_$(date +%Y%m%d_%H%M%S).log"

echo "Configuration:"
echo "  Release: $RELEASE"
echo "  Output dir: $OUTPUT_DIR"
echo "  Threads: $THREADS"
echo "  HF dataset: $HF_DATASET"
echo "  Log file: $LOG_FILE"
echo ""

# Check disk space (need ~500GB)
AVAILABLE=$(df -BG . | tail -1 | awk '{print $4}' | sed 's/G//')
if [ "$AVAILABLE" -lt 500 ]; then
    echo "⚠️  Warning: Only ${AVAILABLE}GB available. Need at least 500GB."
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    [[ ! $REPLY =~ ^[Yy]$ ]] && exit 1
fi

# Download and extract UniRef50 2025_03 if not exists
if [ ! -f "$FASTA_FILE" ]; then
    echo "📥 Downloading UniRef 2025_03 archive (~254GB, may take several hours)..."
    echo "   This contains UniRef50, UniRef90, and UniRef100"

    if [ ! -f "$ARCHIVE_FILE" ]; then
        wget -c "$ARCHIVE_URL" || { echo "❌ Download failed"; exit 1; }
        echo "✓ Archive downloaded"
    else
        echo "✓ Using existing archive: $ARCHIVE_FILE"
    fi

    echo ""
    echo "📦 Extracting UniRef50 from archive..."
    tar -xzf "$ARCHIVE_FILE" uniref50.tar || { echo "❌ Extraction failed"; exit 1; }
    echo "✓ Extracted uniref50.tar"

    echo ""
    echo "📦 Extracting FASTA file..."
    tar -xf uniref50.tar uniref50.fasta.gz || { echo "❌ Extraction failed"; exit 1; }
    echo "✓ Extracted $FASTA_FILE"

    # Cleanup intermediate tar file
    rm -f uniref50.tar
    echo "✓ Cleaned up intermediate tar file"
else
    echo "✓ Using existing $FASTA_FILE"
fi
echo ""

# Check HF token
if [ -z "$HF_TOKEN" ] && [ ! -f .env ]; then
    echo "⚠️  Warning: HF_TOKEN not set. Dataset will not be uploaded."
    echo "   Set HF_TOKEN in .env or export HF_TOKEN=your_token"
fi
echo ""

# Run pipeline
echo "🚀 Starting pipeline (estimated 6-12 hours)..."
echo "   Monitor progress: tail -f $LOG_FILE"
echo ""

python3 prepare_uniref50_dataset.py \
    --fasta "$FASTA_FILE" \
    --output-dir "$OUTPUT_DIR" \
    --hf-dataset-name "$HF_DATASET" \
    --upload \
    --public \
    --threads "$THREADS" \
    2>&1 | tee "$LOG_FILE"

# Summary
if [ $? -eq 0 ]; then
    echo ""
    echo "╔══════════════════════════════════════════════════════════════════════════╗"
    echo "║                         ✓ PIPELINE COMPLETED                             ║"
    echo "╚══════════════════════════════════════════════════════════════════════════╝"
    echo ""
    echo "📊 Results:"
    echo "   Dataset: $OUTPUT_DIR/dataset/"
    echo "   Timing:  $OUTPUT_DIR/timing_log.txt"
    echo "   Log:     $LOG_FILE"
    echo ""

    # Cleanup prompt
    read -p "Delete intermediate files to save ~450GB? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "🧹 Cleaning up..."
        rm -rf "$OUTPUT_DIR/mmseqs2" "$OUTPUT_DIR"/*.fasta
        rm -f "$ARCHIVE_FILE"  # Remove the large archive
        echo "✓ Cleanup complete (saved ~450GB)"
    fi
else
    echo ""
    echo "❌ Pipeline failed. Check $LOG_FILE for errors."
    exit 1
fi

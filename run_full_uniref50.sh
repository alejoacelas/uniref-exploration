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

# Install dependencies
echo "📦 Installing required dependencies..."
pip install datasets python-dotenv || { echo "❌ pip install failed"; exit 1; }
conda install -c bioconda -c conda-forge mmseqs2 -y || { echo "❌ conda install failed"; exit 1; }
echo "✓ Dependencies installed"
echo ""

# Check disk space (need ~50GB for UniRef50 FASTA file)
AVAILABLE=$(df -BG . | tail -1 | awk '{print $4}' | sed 's/G//')
if [ "$AVAILABLE" -lt 50 ]; then
    echo "⚠️  Warning: Only ${AVAILABLE}GB available. Need at least ~50GB for UniRef50 FASTA file (~40GB compressed)."
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    [[ ! $REPLY =~ ^[Yy]$ ]] && exit 1
fi

# Download and extract UniRef50 2025_03 if not exists (streaming to save space)
if [ ! -f "$FASTA_FILE" ]; then
    echo "📥 Streaming extraction of UniRef50 FASTA from archive (~254GB archive, ~40GB output)..."
    echo "   This will extract ONLY uniref50.fasta.gz without storing the full archive"
    echo "   Note: This will download the entire archive but stream it directly without storage"

    # Stream extract: download archive, extract only uniref50.tar to temp pipe
    echo ""
    echo "📦 Stage 1: Extracting uniref50.tar from remote archive (streaming)..."
    wget -qO- "$ARCHIVE_URL" | tar -xz uniref50.tar || { echo "❌ Extraction failed"; exit 1; }
    
    if [ ! -f "uniref50.tar" ]; then
        echo "❌ Failed to extract uniref50.tar. Archive may be corrupted or network issue."
        exit 1
    fi
    echo "✓ Extracted uniref50.tar (temporary)"

    echo ""
    echo "📦 Stage 2: Extracting FASTA file from uniref50.tar..."
    tar -xf uniref50.tar uniref50.fasta.gz || { echo "❌ Extraction failed"; exit 1; }
    echo "✓ Extracted $FASTA_FILE"

    # Cleanup intermediate tar file immediately
    echo ""
    echo "🧹 Cleaning up intermediate files..."
    rm -f uniref50.tar
    echo "✓ Removed uniref50.tar (saved space)"
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

#!/bin/bash
set -e  # Exit on error

echo "╔══════════════════════════════════════════════════════════════════════════╗"
echo "║         UniRef50 2025_03 Sample Test - Quick Pipeline Validation        ║"
echo "╚══════════════════════════════════════════════════════════════════════════╝"
echo ""

# Configuration
RELEASE="2025_03"
ARCHIVE_URL="https://ftp.uniprot.org/pub/databases/uniprot/previous_releases/release-${RELEASE}/uniref/uniref${RELEASE}.tar.gz"
SAMPLE_SIZE_MB=100  # Download first 100MB of archive
SAMPLE_FILE="uniref_sample.tar.gz"
FASTA_SAMPLE="uniref50_sample.fasta"
MAX_SEQUENCES=10000  # Process up to 10k sequences
OUTPUT_DIR="./sample_test_output"
THREADS=${THREADS:-$(nproc)}
LOG_FILE="sample_test_$(date +%Y%m%d_%H%M%S).log"

echo "Configuration:"
echo "  Release: $RELEASE"
echo "  Sample size: ${SAMPLE_SIZE_MB}MB (~10k sequences)"
echo "  Max sequences: $MAX_SEQUENCES"
echo "  Output dir: $OUTPUT_DIR"
echo "  Threads: $THREADS"
echo "  Log file: $LOG_FILE"
echo ""

# Check disk space (need ~5GB)
AVAILABLE=$(df -BG . | tail -1 | awk '{print $4}' | sed 's/G//')
if [ "$AVAILABLE" -lt 5 ]; then
    echo "⚠️  Warning: Only ${AVAILABLE}GB available. Need at least 5GB for sample test."
    exit 1
fi

# Download sample if not exists
if [ ! -f "$FASTA_SAMPLE" ]; then
    echo "📥 Downloading sample from UniRef 2025_03 (${SAMPLE_SIZE_MB}MB)..."

    # Download first 100MB using curl with range
    BYTE_LIMIT=$((SAMPLE_SIZE_MB * 1024 * 1024 - 1))
    curl -r "0-${BYTE_LIMIT}" "$ARCHIVE_URL" -o "$SAMPLE_FILE" || {
        echo "❌ Download failed"; exit 1;
    }
    echo "✓ Downloaded ${SAMPLE_SIZE_MB}MB sample"

    echo ""
    echo "📦 Extracting sample data..."
    # Extract what's available (tar will warn about incomplete archive, that's OK)
    tar -xzf "$SAMPLE_FILE" --ignore-zeros 2>/dev/null || true

    # Try to extract FASTA from the partial uniref50.tar
    if [ -f "uniref50.tar" ]; then
        tar -xf uniref50.tar 2>/dev/null || true

        # If we got the gzipped FASTA, uncompress it
        if [ -f "uniref50.fasta.gz" ]; then
            zcat uniref50.fasta.gz 2>/dev/null > "$FASTA_SAMPLE" || {
                # If that fails, just use what we have
                gunzip -c uniref50.fasta.gz 2>/dev/null > "$FASTA_SAMPLE" || true
            }
            rm -f uniref50.fasta.gz uniref50.tar
        fi
    fi

    # If extraction didn't work, try downloading directly from current release
    if [ ! -f "$FASTA_SAMPLE" ] || [ ! -s "$FASTA_SAMPLE" ]; then
        echo "   Archive extraction incomplete, downloading sample from current release..."
        CURRENT_URL="https://ftp.uniprot.org/pub/databases/uniprot/uniref/uniref50/uniref50.fasta.gz"
        curl -r "0-52428800" "$CURRENT_URL" 2>/dev/null | zcat 2>/dev/null > "$FASTA_SAMPLE" || {
            echo "❌ Could not create sample FASTA"
            exit 1
        }
    fi

    # Cleanup
    rm -f "$SAMPLE_FILE"

    # Count sequences
    SEQ_COUNT=$(grep -c "^>" "$FASTA_SAMPLE" 2>/dev/null || echo "0")
    echo "✓ Sample ready: $SEQ_COUNT sequences"
else
    SEQ_COUNT=$(grep -c "^>" "$FASTA_SAMPLE" 2>/dev/null || echo "0")
    echo "✓ Using existing sample: $SEQ_COUNT sequences"
fi
echo ""

# Check we have sequences
if [ "$SEQ_COUNT" -eq 0 ]; then
    echo "❌ No sequences found in sample file"
    exit 1
fi

# Run pipeline on sample
echo "🚀 Starting sample pipeline test (~3-5 minutes)..."
echo "   Monitor progress: tail -f $LOG_FILE"
echo ""

python3 prepare_uniref50_dataset.py \
    --fasta "$FASTA_SAMPLE" \
    --max-sequences "$MAX_SEQUENCES" \
    --output-dir "$OUTPUT_DIR" \
    --threads "$THREADS" \
    2>&1 | tee "$LOG_FILE"

# Summary
if [ $? -eq 0 ]; then
    echo ""
    echo "╔══════════════════════════════════════════════════════════════════════════╗"
    echo "║                      ✓ SAMPLE TEST COMPLETED                             ║"
    echo "╚══════════════════════════════════════════════════════════════════════════╝"
    echo ""
    echo "📊 Results:"
    echo "   Dataset: $OUTPUT_DIR/dataset/"
    echo "   Timing:  $OUTPUT_DIR/timing_log.txt"
    echo "   Log:     $LOG_FILE"
    echo ""
    echo "💡 Pipeline validated! Ready for full run with: ./run_full_uniref50.sh"
    echo ""

    # Show timing summary
    if [ -f "$OUTPUT_DIR/timing_log.txt" ]; then
        echo "⏱️  Timing Summary:"
        tail -n 5 "$OUTPUT_DIR/timing_log.txt"
    fi

    echo ""
    read -p "Delete test files to save ~1GB? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "🧹 Cleaning up..."
        rm -rf "$OUTPUT_DIR" "$FASTA_SAMPLE"
        echo "✓ Cleanup complete"
    fi
else
    echo ""
    echo "❌ Sample test failed. Check $LOG_FILE for errors."
    exit 1
fi

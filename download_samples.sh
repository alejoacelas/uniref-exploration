#!/bin/bash
# Download 1010 sample FASTA sequences using curl

set -euo pipefail

OUTPUT_FILE="${1:-sample_sequences.fasta}"
NUM_SEQUENCES=1010

echo "Downloading $NUM_SEQUENCES sample sequences from UniProt..."

# Use UniProt's stream API with a query that returns many sequences
# Download directly in FASTA format
curl -s "https://rest.uniprot.org/uniprotkb/stream?format=fasta&query=reviewed:true&size=$NUM_SEQUENCES" > "$OUTPUT_FILE"

# If we didn't get enough, try a broader query
SEQUENCE_COUNT=$(grep -c "^>" "$OUTPUT_FILE" 2>/dev/null || echo "0")

if [ "$SEQUENCE_COUNT" -lt "$NUM_SEQUENCES" ]; then
    echo "Got $SEQUENCE_COUNT sequences, fetching more with broader query..."
    curl -s "https://rest.uniprot.org/uniprotkb/stream?format=fasta&query=*&size=$NUM_SEQUENCES" > "$OUTPUT_FILE"
    SEQUENCE_COUNT=$(grep -c "^>" "$OUTPUT_FILE" 2>/dev/null || echo "0")
fi

# Verify download
if [ -s "$OUTPUT_FILE" ]; then
    echo "Successfully downloaded $SEQUENCE_COUNT sequences to $OUTPUT_FILE"
    FILE_SIZE=$(du -h "$OUTPUT_FILE" | cut -f1)
    echo "File size: $FILE_SIZE"
    
    # Show first few lines as preview
    echo ""
    echo "First 5 lines:"
    head -n 5 "$OUTPUT_FILE"
else
    echo "Error: Download failed or file is empty"
    exit 1
fi

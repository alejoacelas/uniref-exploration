#!/bin/bash
################################################################################
# Continue Database Build
#
# Simple script to continue building the database from the checkpoint.
# Use this when you only want to complete Step 1 (database building).
################################################################################

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo "================================================================================"
echo "  Continue Database Build - Resume from Checkpoint"
echo "================================================================================"
echo ""

# Check current status
if [ -f "uniref50_mappings_optimized.db" ]; then
    db_count=$(python3 -c "import sqlite3; conn=sqlite3.connect('uniref50_mappings_optimized.db'); print(conn.execute('SELECT COUNT(*) FROM cluster_mappings').fetchone()[0]); conn.close()" 2>/dev/null || echo "0")
    echo -e "${GREEN}Database found: ${db_count} entries${NC}"

    if [ "$db_count" -ge 60000000 ]; then
        echo -e "${GREEN}✓ Database appears complete!${NC}"
        echo "  (>= 60M entries, target is ~70M)"
        echo ""
        echo "If you want to rebuild, delete the database first:"
        echo "  rm uniref50_mappings_optimized.db"
        exit 0
    else
        echo -e "${YELLOW}Database incomplete: ${db_count} / ~70,000,000 entries${NC}"
        remaining=$((70000000 - db_count))
        echo "  Remaining: ~${remaining} entries"
    fi
else
    echo -e "${YELLOW}No database found - will start fresh${NC}"
fi

echo ""
echo "This will:"
echo "  1. Resume building the cluster mappings database"
echo "  2. Use optimized settings (500K batch size)"
echo "  3. Commit every ~9 minutes"
echo "  4. Show progress updates regularly"
echo ""

# Check if running interactively
if [ -t 0 ]; then
    read -p "Continue? (y/N) " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Cancelled."
        exit 0
    fi
fi

echo ""
echo "================================================================================"
echo "  Starting Database Build"
echo "================================================================================"
echo ""

# Run the optimized builder directly (unbuffered for real-time output)
python3 -u build_cluster_mappings_optimized.py

echo ""
echo "================================================================================"
echo "  Database Build Complete!"
echo "================================================================================"
echo ""

# Show final count
if [ -f "uniref50_mappings_optimized.db" ]; then
    final_count=$(python3 -c "import sqlite3; conn=sqlite3.connect('uniref50_mappings_optimized.db'); print(conn.execute('SELECT COUNT(*) FROM cluster_mappings').fetchone()[0]); conn.close()")
    db_size=$(du -h uniref50_mappings_optimized.db | cut -f1)

    echo -e "${GREEN}✓ Final database:${NC}"
    echo "  Entries: ${final_count}"
    echo "  Size: ${db_size}"
    echo ""

    if [ "$final_count" -ge 60000000 ]; then
        echo -e "${GREEN}✓ Database is complete!${NC}"
        echo ""
        echo "Next step: Run the full pipeline to augment HF dataset:"
        echo "  ./run_full_pipeline.sh"
    else
        echo -e "${YELLOW}⚠ Database may be incomplete${NC}"
        echo "  Expected ~70M entries, got ${final_count}"
    fi
fi

echo ""
echo "================================================================================"

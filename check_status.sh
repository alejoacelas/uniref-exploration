#!/bin/bash
################################################################################
# Quick Status Check
################################################################################

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo "================================================================================"
echo "  Quick Status Check - $(date +'%Y-%m-%d %H:%M:%S')"
echo "================================================================================"
echo ""

# 1. BGZF Conversion Status
echo -e "${BLUE}1. BGZF Conversion${NC}"
if [ -f "uniref50.xml.bgz" ]; then
    bgzf_size_gb=$(du -h uniref50.xml.bgz | cut -f1)
    echo "   Status: In progress"
    echo "   Current size: $bgzf_size_gb"

    if pgrep -f "bgzip -c" > /dev/null; then
        echo -e "   ${GREEN}✓ Process running${NC}"
    else
        echo -e "   ${GREEN}✓ Conversion complete!${NC}"
        echo "   Ready to launch workers: ./run_parallel_workers.sh"
    fi

    # Show last log line
    if [ -f "bgzf_conversion.log" ]; then
        echo "   Last log: $(tail -1 bgzf_conversion.log)"
    fi
else
    echo "   Status: Not started or file not found"
fi
echo ""

# 2. Database Status
echo -e "${BLUE}2. Database Status${NC}"
if [ -f "uniref50_mappings_optimized.db" ]; then
    db_count=$(python3 -c "import sqlite3; conn=sqlite3.connect('uniref50_mappings_optimized.db'); print(conn.execute('SELECT COUNT(*) FROM cluster_mappings').fetchone()[0]); conn.close()" 2>/dev/null)
    db_size=$(du -h uniref50_mappings_optimized.db | cut -f1)

    echo "   Entries: $db_count"
    echo "   Size: $db_size"

    if [ "$db_count" -ge 60000000 ]; then
        echo -e "   ${GREEN}✓ COMPLETE (>= 60M entries)${NC}"
    else
        remaining=$((70000000 - db_count))
        percent=$((db_count * 100 / 70000000))
        echo "   Progress: ${percent}% (~${remaining} remaining)"
    fi
else
    echo "   Database not found"
fi
echo ""

# 3. Worker Status
echo -e "${BLUE}3. Workers${NC}"
worker_count=$(ps aux | grep "parallel_worker.py" | grep -v grep | wc -l)
if [ "$worker_count" -gt 0 ]; then
    echo -e "   ${GREEN}✓ $worker_count worker(s) running${NC}"
    ps aux | grep "parallel_worker.py" | grep -v grep | awk '{print "   - PID " $2 ": " $12}'
    echo ""
    echo "   Monitor with: ./monitor_workers.sh"
else
    echo "   No workers currently running"

    if [ -f "uniref50.xml.bgz" ] && ! pgrep -f "bgzip -c" > /dev/null; then
        echo -e "   ${YELLOW}→ Ready to launch: ./run_parallel_workers.sh${NC}"
    fi
fi
echo ""

# 4. Completed Workers
if [ -f "worker_progress.csv" ] && [ $(wc -l < worker_progress.csv) -gt 1 ]; then
    echo -e "${BLUE}4. Completed Workers${NC}"
    tail -n +2 worker_progress.csv | while IFS=',' read -r worker_id percent start_byte first_cluster rows_proc rows_ins rows_fail duration status timestamp; do
        duration_min=$(echo "scale=1; $duration / 60" | bc 2>/dev/null || echo "?")
        echo "   $worker_id ($percent%): $rows_ins rows in ${duration_min}min"
    done
    echo ""
fi

# 5. Next Steps
echo -e "${BLUE}Next Steps${NC}"
if pgrep -f "bgzip -c" > /dev/null; then
    echo "   1. Wait for BGZF conversion to complete (~2 hours from start)"
    echo "   2. Check status again: ./check_status.sh"
elif [ ! -f "uniref50.xml.bgz" ]; then
    echo "   1. BGZF file not found - start conversion?"
    echo "      pigz -dc uniref50.xml.gz | bgzip -c > uniref50.xml.bgz"
elif [ "$worker_count" -gt 0 ]; then
    echo "   1. Workers are running - monitor progress"
    echo "      ./monitor_workers.sh"
elif [ -f "uniref50.xml.bgz" ]; then
    echo -e "   ${GREEN}1. BGZF ready - launch workers:${NC}"
    echo "      ./run_parallel_workers.sh"
fi

echo ""
echo "================================================================================"
echo "Full documentation: PARALLEL_WORKERS_README.md"
echo "Setup summary: SETUP_COMPLETE.md"
echo "================================================================================"

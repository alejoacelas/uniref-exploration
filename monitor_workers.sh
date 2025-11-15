#!/bin/bash
################################################################################
# Monitor Parallel Workers
#
# Real-time dashboard showing all worker progress
################################################################################

BGZF_FILE="uniref50.xml.bgz"
DB_FILE="uniref50_mappings_optimized.db"
CSV_LOG="worker_progress.csv"

while true; do
    clear
    echo "================================================================================"
    echo "  Parallel Workers - Live Monitor"
    echo "  $(date +'%Y-%m-%d %H:%M:%S')"
    echo "================================================================================"
    echo ""

    # BGZF file status
    if [ -f "$BGZF_FILE" ]; then
        bgzf_size=$(du -h "$BGZF_FILE" | cut -f1)
        echo "BGZF File: $BGZF_FILE ($bgzf_size)"
    else
        echo "BGZF File: NOT FOUND (still converting?)"
    fi
    echo ""

    # Database status
    if [ -f "$DB_FILE" ]; then
        db_count=$(python3 -c "import sqlite3; conn=sqlite3.connect('$DB_FILE'); print(conn.execute('SELECT COUNT(*) FROM cluster_mappings').fetchone()[0]); conn.close()" 2>/dev/null || echo "ERROR")
        db_size=$(du -h "$DB_FILE" | cut -f1)
        echo "Database: $DB_FILE"
        echo "  Count: $db_count entries"
        echo "  Size: $db_size"

        if [ "$db_count" != "ERROR" ] && [ "$db_count" -ge 60000000 ]; then
            echo "  Status: ✓ COMPLETE (>= 60M)"
        else
            remaining=$((70000000 - db_count))
            echo "  Status: In progress (~$remaining remaining)"
        fi
    else
        echo "Database: NOT FOUND"
    fi
    echo ""

    # Running workers
    echo "Active Workers:"
    worker_pids=$(ps aux | grep "parallel_worker.py" | grep -v grep | awk '{print $2, $11, $12}' || echo "")
    if [ -z "$worker_pids" ]; then
        echo "  No workers currently running"
    else
        echo "$worker_pids" | while read pid script worker_id; do
            echo "  PID $pid: $worker_id"
        done
    fi
    echo ""

    # Worker logs - last line from each
    echo "Worker Progress (last update from each log):"
    if [ -d "worker_logs" ]; then
        for log in worker_logs/worker_*.log; do
            if [ -f "$log" ]; then
                worker=$(basename "$log" .log)
                # Get last line that shows progress
                last_progress=$(grep -E "Processed:|Inserted:|Progress:" "$log" | tail -1 | sed 's/.*] //' || echo "Starting...")
                echo "  $worker: $last_progress"
            fi
        done

        if ! ls worker_logs/worker_*.log 1> /dev/null 2>&1; then
            echo "  No worker logs yet"
        fi
    else
        echo "  worker_logs/ directory not found"
    fi
    echo ""

    # CSV summary
    if [ -f "$CSV_LOG" ]; then
        echo "Completed Workers (from CSV):"
        tail -n +2 "$CSV_LOG" 2>/dev/null | while IFS=',' read -r worker_id percent start_byte first_cluster rows_proc rows_ins rows_fail duration status timestamp; do
            duration_min=$(echo "scale=1; $duration / 60" | bc 2>/dev/null || echo "?")
            echo "  $worker_id ($percent%): $rows_ins inserted in ${duration_min}min - $status"
        done

        if [ $(wc -l < "$CSV_LOG") -le 1 ]; then
            echo "  No completed workers yet"
        fi
    else
        echo "CSV Log: Not found (workers haven't completed yet)"
    fi
    echo ""

    echo "================================================================================"
    echo "Press Ctrl+C to exit | Refreshing in 30 seconds..."
    echo "================================================================================"

    sleep 30
done

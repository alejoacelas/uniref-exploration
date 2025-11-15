#!/bin/bash
################################################################################
# Run Parallel BGZF Workers
#
# Launches multiple workers that seek to different positions in the BGZF file
# and process in parallel. Uses INSERT OR IGNORE for safe deduplication.
################################################################################

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

BGZF_FILE="uniref50.xml.bgz"
DB_FILE="uniref50_mappings_optimized.db"
CSV_LOG="worker_progress.csv"

log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} ✓ $1"
}

log_warning() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} ⚠ $1"
}

log_error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} ✗ $1"
}

echo "================================================================================"
echo "  Parallel BGZF Worker Orchestration"
echo "================================================================================"
echo ""

# Check prerequisites
log "Checking prerequisites..."

if [ ! -f "$BGZF_FILE" ]; then
    log_error "BGZF file not found: $BGZF_FILE"
    echo ""
    echo "Please run the BGZF conversion first:"
    echo "  pigz -dc uniref50.xml.gz | bgzip -c > uniref50.xml.bgz"
    exit 1
fi

if [ ! -f "$DB_FILE" ]; then
    log_error "Database file not found: $DB_FILE"
    exit 1
fi

if [ ! -f "parallel_worker.py" ]; then
    log_error "Worker script not found: parallel_worker.py"
    exit 1
fi

log_success "All prerequisites satisfied"
echo ""

# Check current database status
log "Checking current database status..."
db_count=$(python3 -c "import sqlite3; conn=sqlite3.connect('$DB_FILE'); print(conn.execute('SELECT COUNT(*) FROM cluster_mappings').fetchone()[0]); conn.close()")
log "Current database count: ${db_count}"
echo ""

# Show BGZF file info
log "BGZF file info:"
ls -lh "$BGZF_FILE"
echo ""

# Confirm start
if [ -t 0 ]; then
    echo "This will launch parallel workers at the following positions:"
    echo "  - Worker 1: 55% (just past last known crash)"
    echo "  - Worker 2: 75% (mid-to-late portion)"
    echo "  - Worker 3: 90% (last 10%)"
    echo ""
    echo "Workers will run in parallel and use INSERT OR IGNORE for safety."
    echo "Progress will be logged to: $CSV_LOG"
    echo ""
    read -p "Continue? (y/N) " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Cancelled."
        exit 0
    fi
fi

echo ""
echo "================================================================================"
echo "  Launching Workers"
echo "================================================================================"
echo ""

# Create log directory for individual worker logs
mkdir -p worker_logs

# Launch workers in background
WORKERS=()
PERCENTAGES=(55 75 90)

for pct in "${PERCENTAGES[@]}"; do
    worker_id="worker_${pct}"
    log_file="worker_logs/${worker_id}.log"

    log "Launching ${worker_id} at ${pct}%..."

    nohup python3 -u parallel_worker.py "$worker_id" "$pct" "$BGZF_FILE" "$DB_FILE" > "$log_file" 2>&1 &
    worker_pid=$!
    WORKERS+=("$worker_pid:$worker_id:$pct")

    log_success "Worker ${worker_id} started (PID: $worker_pid)"
    log "  Log file: $log_file"
    echo ""

    # Small delay between launches
    sleep 2
done

echo ""
echo "================================================================================"
echo "  Monitoring Workers"
echo "================================================================================"
echo ""

log_success "All ${#PERCENTAGES[@]} workers launched!"
echo ""
echo "Worker PIDs:"
for worker_info in "${WORKERS[@]}"; do
    IFS=':' read -r pid worker_id pct <<< "$worker_info"
    echo "  $worker_id (${pct}%): PID $pid"
done
echo ""

echo "Monitor individual workers:"
for pct in "${PERCENTAGES[@]}"; do
    echo "  tail -f worker_logs/worker_${pct}.log"
done
echo ""

echo "View consolidated progress:"
echo "  watch -n 30 'cat $CSV_LOG'"
echo ""

echo "Check database count:"
echo "  watch -n 60 'python3 -c \"import sqlite3; conn=sqlite3.connect(\\\"$DB_FILE\\\"); print(f\\\"{conn.execute(\\\"SELECT COUNT(*) FROM cluster_mappings\\\").fetchone()[0]:,} entries\\\"); conn.close()\"'"
echo ""

# Monitoring loop
log "Entering monitoring loop (press Ctrl+C to exit monitoring, workers will continue)..."
echo ""

while true; do
    sleep 60

    # Check if all workers are done
    all_done=true
    for worker_info in "${WORKERS[@]}"; do
        IFS=':' read -r pid worker_id pct <<< "$worker_info"
        if ps -p "$pid" > /dev/null 2>&1; then
            all_done=false
        fi
    done

    # Show current status
    current_count=$(python3 -c "import sqlite3; conn=sqlite3.connect('$DB_FILE'); print(conn.execute('SELECT COUNT(*) FROM cluster_mappings').fetchone()[0]); conn.close()")
    gained=$((current_count - db_count))
    log "Current DB count: ${current_count} (+${gained} since start)"

    # Check CSV log
    if [ -f "$CSV_LOG" ]; then
        completed=$(tail -n +2 "$CSV_LOG" 2>/dev/null | grep -c "completed" || echo "0")
        log "Workers completed: ${completed}/${#PERCENTAGES[@]}"
    fi

    # Show active workers
    echo "  Active workers:"
    for worker_info in "${WORKERS[@]}"; do
        IFS=':' read -r pid worker_id pct <<< "$worker_info"
        if ps -p "$pid" > /dev/null 2>&1; then
            # Get last line from worker log
            last_line=$(tail -1 "worker_logs/${worker_id}.log" 2>/dev/null | cut -c 1-80 || echo "No output yet")
            echo "    $worker_id: RUNNING - $last_line"
        else
            echo "    $worker_id: COMPLETED"
        fi
    done
    echo ""

    if [ "$all_done" = true ]; then
        log_success "All workers completed!"
        break
    fi
done

echo ""
echo "================================================================================"
echo "  Workers Complete - Final Summary"
echo "================================================================================"
echo ""

# Show final CSV results
if [ -f "$CSV_LOG" ]; then
    log "Worker results:"
    echo ""
    column -t -s ',' "$CSV_LOG"
    echo ""
fi

# Show final database count
final_count=$(python3 -c "import sqlite3; conn=sqlite3.connect('$DB_FILE'); print(conn.execute('SELECT COUNT(*) FROM cluster_mappings').fetchone()[0]); conn.close()")
total_gained=$((final_count - db_count))

log_success "Final database count: ${final_count}"
log "Total entries added: ${total_gained}"
echo ""

# Check if we need a 4th worker
if [ "$final_count" -lt 60000000 ]; then
    remaining=$((70000000 - final_count))
    log_warning "Database still incomplete (< 60M entries)"
    log "Remaining: ~${remaining} entries"
    echo ""
    echo "Consider launching a 4th worker at 40%:"
    echo "  python3 -u parallel_worker.py worker_40 40 $BGZF_FILE $DB_FILE > worker_logs/worker_40.log 2>&1 &"
    echo ""
else
    log_success "Database appears complete (>= 60M entries)!"
fi

echo "Individual worker logs available in: worker_logs/"
echo ""

echo "================================================================================"
echo "  Next Steps"
echo "================================================================================"
echo ""

if [ "$final_count" -ge 60000000 ]; then
    echo "Database is complete! You can now:"
    echo "  1. Run the full pipeline to augment HF dataset:"
    echo "     ./run_full_pipeline.sh"
    echo ""
    echo "  2. Or continue with HF augmentation directly"
else
    echo "If count is still short, launch additional worker(s):"
    echo "  python3 -u parallel_worker.py worker_40 40 > worker_logs/worker_40.log 2>&1 &"
    echo ""
    echo "Or run at a different percentage (e.g., 35%, 65%):"
    echo "  python3 -u parallel_worker.py worker_35 35 > worker_logs/worker_35.log 2>&1 &"
fi

echo ""
echo "================================================================================"

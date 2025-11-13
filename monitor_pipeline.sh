#!/bin/bash
################################################################################
# Pipeline Monitor - Real-time progress tracking
#
# Usage:
#   ./monitor_pipeline.sh [log_file]
#
# Features:
# - Color-coded log output
# - Progress estimation
# - Live statistics
# - Error highlighting
################################################################################

# Default to latest log file if not specified
LOG_FILE="${1:-$(ls -t pipeline_*.log 2>/dev/null | head -1)}"

if [ -z "$LOG_FILE" ] || [ ! -f "$LOG_FILE" ]; then
    echo "Error: No log file found"
    echo "Usage: $0 [log_file]"
    echo ""
    echo "Available log files:"
    ls -1t pipeline_*.log 2>/dev/null || echo "  None found"
    exit 1
fi

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m' # No Color

# Clear screen and print header
clear
echo "================================================================================"
echo "  UniRef50 Pipeline Monitor"
echo "================================================================================"
echo "  Log file: $LOG_FILE"
echo "  Started:  $(head -1 "$LOG_FILE" 2>/dev/null | cut -d: -f2-)"
echo "  Monitoring... (Ctrl+C to exit)"
echo "================================================================================"
echo ""

# Function to colorize log lines
colorize_line() {
    local line="$1"

    # Color by log level
    if [[ "$line" =~ \[ERROR\] ]]; then
        echo -e "${RED}${line}${NC}"
    elif [[ "$line" =~ \[WARNING\] ]]; then
        echo -e "${YELLOW}${line}${NC}"
    elif [[ "$line" =~ \[SUCCESS\] ]]; then
        echo -e "${GREEN}${line}${NC}"
    elif [[ "$line" =~ \[INFO\] ]]; then
        echo -e "${BLUE}${line}${NC}"
    # Highlight progress lines
    elif [[ "$line" =~ "Processed:" ]]; then
        echo -e "${CYAN}${line}${NC}"
    elif [[ "$line" =~ "Rate:" ]]; then
        echo -e "${CYAN}${line}${NC}"
    # Highlight important milestones
    elif [[ "$line" =~ "STEP" ]] || [[ "$line" =~ "=====" ]]; then
        echo -e "${MAGENTA}${line}${NC}"
    else
        echo "$line"
    fi
}

# Function to extract and show current stats
show_stats() {
    local log="$1"

    echo ""
    echo -e "${MAGENTA}════════════════════════════════════════════════════════════════════════════════${NC}"
    echo -e "${MAGENTA}  CURRENT STATISTICS${NC}"
    echo -e "${MAGENTA}════════════════════════════════════════════════════════════════════════════════${NC}"

    # Pipeline start time
    local start_time=$(head -1 "$log" | cut -d: -f2- | xargs)
    if [ -n "$start_time" ]; then
        echo -e "${BLUE}Pipeline Start:${NC} $start_time"
    fi

    # Current step
    local current_step=$(grep -E "STEP [0-9]:" "$log" | tail -1)
    if [ -n "$current_step" ]; then
        echo -e "${BLUE}Current Step:${NC} $(echo $current_step | sed 's/.*STEP /STEP /')"
    fi

    # Latest progress
    local latest_progress=$(grep "Processed:" "$log" | tail -1)
    if [ -n "$latest_progress" ]; then
        echo -e "${CYAN}Latest Progress:${NC} $latest_progress"
    fi

    # Database info
    if [ -f "uniref50_mappings_optimized.db" ]; then
        local db_size=$(du -h uniref50_mappings_optimized.db | cut -f1)
        echo -e "${GREEN}Database Size:${NC} $db_size"
    fi

    # Augmented dataset info
    if [ -d "augmented_dataset" ]; then
        local ds_size=$(du -sh augmented_dataset 2>/dev/null | cut -f1)
        echo -e "${GREEN}Dataset Size:${NC} $ds_size"
    fi

    # Error count
    local error_count=$(grep -c "\[ERROR\]" "$log" 2>/dev/null || echo 0)
    if [ "$error_count" -gt 0 ]; then
        echo -e "${RED}Errors:${NC} $error_count"
    fi

    # Warning count
    local warning_count=$(grep -c "\[WARNING\]" "$log" 2>/dev/null || echo 0)
    if [ "$warning_count" -gt 0 ]; then
        echo -e "${YELLOW}Warnings:${NC} $warning_count"
    fi

    # Runtime
    local start_epoch=$(date -d "$(head -1 "$log" | cut -d: -f2- | xargs)" +%s 2>/dev/null || echo 0)
    local current_epoch=$(date +%s)
    local runtime=$((current_epoch - start_epoch))
    if [ "$runtime" -gt 0 ]; then
        local hours=$((runtime / 3600))
        local minutes=$(((runtime % 3600) / 60))
        echo -e "${BLUE}Runtime:${NC} ${hours}h ${minutes}m"
    fi

    echo -e "${MAGENTA}════════════════════════════════════════════════════════════════════════════════${NC}"
    echo ""
}

# Show initial stats
show_stats "$LOG_FILE"

# Follow log file with colorization
echo "Recent activity:"
echo "----------------"

# Show last 20 lines, then follow
tail -20 "$LOG_FILE" | while IFS= read -r line; do
    colorize_line "$line"
done

# Follow new lines
tail -f "$LOG_FILE" | while IFS= read -r line; do
    colorize_line "$line"

    # Update stats periodically (every 100 lines with progress info)
    if [[ "$line" =~ "Processed:" ]]; then
        # Clear screen and refresh stats every 10th progress update
        if [ $((RANDOM % 10)) -eq 0 ]; then
            clear
            show_stats "$LOG_FILE"
            echo "Recent activity:"
            echo "----------------"
        fi
    fi
done

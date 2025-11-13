#!/bin/bash
################################################################################
# UniRef50 Full Pipeline Runner
#
# This script runs the complete pipeline:
# 1. Build cluster mappings database from XML
# 2. Augment HuggingFace dataset with metadata
# 3. Upload to HuggingFace as uniref50-2025-10-v3
#
# All output is logged to pipeline.log with timestamps
# You can monitor progress in real-time with: tail -f pipeline.log
################################################################################

set -e  # Exit on error
set -o pipefail  # Pipe failures propagate

# Configuration
LOG_FILE="pipeline_$(date +%Y%m%d_%H%M%S).log"
TARGET_DATASET="alejoacelas/uniref50-2025-10-v3"

# Colors for terminal output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function with timestamps
log() {
    local level=$1
    shift
    local message="$@"
    local timestamp=$(date "+%Y-%m-%d %H:%M:%S")

    case $level in
        INFO)
            echo -e "${BLUE}[INFO]${NC} ${timestamp} - ${message}" | tee -a "$LOG_FILE"
            ;;
        SUCCESS)
            echo -e "${GREEN}[SUCCESS]${NC} ${timestamp} - ${message}" | tee -a "$LOG_FILE"
            ;;
        WARNING)
            echo -e "${YELLOW}[WARNING]${NC} ${timestamp} - ${message}" | tee -a "$LOG_FILE"
            ;;
        ERROR)
            echo -e "${RED}[ERROR]${NC} ${timestamp} - ${message}" | tee -a "$LOG_FILE"
            ;;
        *)
            echo "${timestamp} - ${message}" | tee -a "$LOG_FILE"
            ;;
    esac
}

# Print banner
print_banner() {
    local text="$1"
    echo "" | tee -a "$LOG_FILE"
    echo "================================================================================" | tee -a "$LOG_FILE"
    echo "  $text" | tee -a "$LOG_FILE"
    echo "================================================================================" | tee -a "$LOG_FILE"
    echo "" | tee -a "$LOG_FILE"
}

# Check if a command exists
check_command() {
    if ! command -v $1 &> /dev/null; then
        log ERROR "Required command '$1' not found"
        return 1
    fi
    return 0
}

# Check prerequisites
check_prerequisites() {
    log INFO "Checking prerequisites..."

    local missing=0

    if ! check_command python3; then
        missing=$((missing + 1))
    fi

    if ! check_command wget; then
        log WARNING "wget not found - will be needed for XML download"
    fi

    # Check Python scripts exist
    if [ ! -f "build_cluster_mappings_optimized.py" ]; then
        log ERROR "build_cluster_mappings_optimized.py not found"
        missing=$((missing + 1))
    fi

    if [ ! -f "augment_hf_dataset_optimized.py" ]; then
        log ERROR "augment_hf_dataset_optimized.py not found"
        missing=$((missing + 1))
    fi

    if [ $missing -gt 0 ]; then
        log ERROR "$missing prerequisite(s) missing. Exiting."
        exit 1
    fi

    log SUCCESS "All prerequisites satisfied"
}

# Check HuggingFace token
check_hf_token() {
    log INFO "Checking HuggingFace authentication..."

    if [ -z "$HF_TOKEN" ] && [ -z "$HUGGINGFACE_TOKEN" ]; then
        log WARNING "No HuggingFace token found in environment"
        log WARNING "Set HF_TOKEN or HUGGINGFACE_TOKEN before running"
        log WARNING "Or the script will prompt for interactive login"

        echo ""
        read -p "Continue anyway? (y/N) " -n 1 -r
        echo ""
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log INFO "Exiting. Set HF_TOKEN and run again."
            exit 0
        fi
    else
        log SUCCESS "HuggingFace token found"
    fi
}

# Check disk space
check_disk_space() {
    log INFO "Checking available disk space..."

    # Get available space in GB
    local available_gb=$(df -BG . | awk 'NR==2 {print $4}' | sed 's/G//')

    log INFO "Available disk space: ${available_gb} GB"

    if [ "$available_gb" -lt 300 ]; then
        log WARNING "Less than 300 GB available. Recommended: 500 GB"
        log WARNING "Pipeline may fail if space runs out"

        echo ""
        read -p "Continue anyway? (y/N) " -n 1 -r
        echo ""
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log INFO "Exiting. Free up disk space and run again."
            exit 0
        fi
    else
        log SUCCESS "Sufficient disk space available"
    fi
}

# Step 1: Build cluster mappings database
build_cluster_mappings() {
    print_banner "STEP 1: Building Cluster Mappings Database"

    log INFO "Starting cluster mapping build..."
    log INFO "This will take 6-12 hours for the full dataset"
    log INFO "Output logged to: $LOG_FILE"

    local start_time=$(date +%s)

    # Run with output to both terminal and log
    if python3 build_cluster_mappings_optimized.py 2>&1 | tee -a "$LOG_FILE"; then
        local end_time=$(date +%s)
        local duration=$((end_time - start_time))
        local hours=$((duration / 3600))
        local minutes=$(((duration % 3600) / 60))

        log SUCCESS "Cluster mappings database built successfully"
        log INFO "Duration: ${hours}h ${minutes}m"

        # Check database size
        if [ -f "uniref50_mappings_optimized.db" ]; then
            local db_size=$(du -h uniref50_mappings_optimized.db | cut -f1)
            log INFO "Database size: $db_size"
        fi

        return 0
    else
        log ERROR "Cluster mapping build failed"
        log ERROR "Check $LOG_FILE for details"
        return 1
    fi
}

# Step 2: Augment HuggingFace dataset
augment_hf_dataset() {
    print_banner "STEP 2: Augmenting HuggingFace Dataset"

    log INFO "Starting dataset augmentation..."
    log INFO "This will take 2-5 hours depending on download speed"
    log INFO "Target dataset: $TARGET_DATASET"

    local start_time=$(date +%s)

    # Update the target dataset in the augment script
    log INFO "Updating target dataset name..."
    sed -i "s|TARGET_DATASET = \".*\"|TARGET_DATASET = \"$TARGET_DATASET\"|" augment_hf_dataset_optimized.py

    # Update database file path to use the optimized version
    sed -i 's|DB_FILE = "uniref50_mappings.db"|DB_FILE = "uniref50_mappings_optimized.db"|' augment_hf_dataset_optimized.py

    # Run augmentation (NOT in test mode)
    if python3 augment_hf_dataset_optimized.py --workers 4 2>&1 | tee -a "$LOG_FILE"; then
        local end_time=$(date +%s)
        local duration=$((end_time - start_time))
        local hours=$((duration / 3600))
        local minutes=$(((duration % 3600) / 60))

        log SUCCESS "Dataset augmentation completed successfully"
        log INFO "Duration: ${hours}h ${minutes}m"

        # Check output directory
        if [ -d "augmented_dataset" ]; then
            local dataset_size=$(du -sh augmented_dataset | cut -f1)
            log INFO "Augmented dataset size: $dataset_size"
        fi

        return 0
    else
        log ERROR "Dataset augmentation failed"
        log ERROR "Check $LOG_FILE for details"
        return 1
    fi
}

# Print summary
print_summary() {
    print_banner "PIPELINE SUMMARY"

    log INFO "Full pipeline completed successfully!"
    log INFO "Log file: $LOG_FILE"

    echo "" | tee -a "$LOG_FILE"
    log INFO "Outputs:"
    log INFO "  • Database: uniref50_mappings_optimized.db"
    log INFO "  • Local dataset: ./augmented_dataset/"
    log INFO "  • HuggingFace: https://huggingface.co/datasets/$TARGET_DATASET"

    echo "" | tee -a "$LOG_FILE"
    log INFO "Next steps:"
    log INFO "  1. Verify dataset at: https://huggingface.co/datasets/$TARGET_DATASET"
    log INFO "  2. Test loading: from datasets import load_dataset; ds = load_dataset('$TARGET_DATASET')"
    log INFO "  3. Archive log file: $LOG_FILE"
}

# Cleanup on error
cleanup_on_error() {
    log ERROR "Pipeline failed. Cleaning up..."
    log INFO "Partial results may be available:"

    if [ -f "uniref50_mappings_optimized.db" ]; then
        log INFO "  • Cluster mappings database exists (can resume)"
    fi

    if [ -d "augmented_dataset" ]; then
        log INFO "  • Augmented dataset directory exists (partial)"
    fi

    log INFO "Check log file for details: $LOG_FILE"
    log INFO "To resume: re-run this script (will skip completed steps)"
}

# Trap errors
trap cleanup_on_error ERR

################################################################################
# MAIN EXECUTION
################################################################################

# Print start banner
echo ""
echo "################################################################################"
echo "#                                                                              #"
echo "#                    UniRef50 Full Pipeline Runner                            #"
echo "#                                                                              #"
echo "################################################################################"
echo ""
echo "Started at: $(date '+%Y-%m-%d %H:%M:%S')"
echo "Log file: $LOG_FILE"
echo ""
echo "Monitor progress in real-time:"
echo "  tail -f $LOG_FILE"
echo ""
echo "This pipeline will:"
echo "  1. Build cluster mappings database (~6-12 hours)"
echo "  2. Augment HuggingFace dataset (~2-5 hours)"
echo "  3. Upload to HuggingFace as $TARGET_DATASET"
echo ""
echo "Total estimated time: 8-17 hours"
echo ""

# Ask for confirmation
read -p "Continue? (y/N) " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    log INFO "Pipeline cancelled by user"
    exit 0
fi

# Initialize log file
echo "Pipeline started at: $(date '+%Y-%m-%d %H:%M:%S')" > "$LOG_FILE"
echo "Target dataset: $TARGET_DATASET" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"

# Run prerequisite checks
check_prerequisites
check_hf_token
check_disk_space

# Track overall time
PIPELINE_START=$(date +%s)

# Run pipeline steps
log INFO "Starting pipeline execution..."

# Step 1: Build cluster mappings (skip if database is COMPLETE)
if [ -f "uniref50_mappings_optimized.db" ]; then
    # Check if database is complete (should have ~70M entries)
    db_count=$(python3 -c "import sqlite3; conn=sqlite3.connect('uniref50_mappings_optimized.db'); print(conn.execute('SELECT COUNT(*) FROM cluster_mappings').fetchone()[0]); conn.close()" 2>/dev/null || echo "0")

    if [ "$db_count" -ge 60000000 ]; then
        # Database appears complete (>= 60M entries)
        log SUCCESS "Database already complete: ${db_count} entries"
        log INFO "Skipping Step 1 (cluster mapping build)"
    else
        # Database exists but incomplete
        log WARNING "Database exists but incomplete: ${db_count} entries (expected ~70M)"
        log INFO "Continuing Step 1 to complete the build..."
        if ! build_cluster_mappings; then
            log ERROR "Step 1 failed. Exiting."
            exit 1
        fi
    fi
else
    # No database, start fresh
    if ! build_cluster_mappings; then
        log ERROR "Step 1 failed. Exiting."
        exit 1
    fi
fi

# Step 2: Augment HuggingFace dataset
if ! augment_hf_dataset; then
    log ERROR "Step 2 failed. Exiting."
    exit 1
fi

# Calculate total duration
PIPELINE_END=$(date +%s)
TOTAL_DURATION=$((PIPELINE_END - PIPELINE_START))
TOTAL_HOURS=$((TOTAL_DURATION / 3600))
TOTAL_MINUTES=$(((TOTAL_DURATION % 3600) / 60))

# Print summary
print_summary

echo "" | tee -a "$LOG_FILE"
log SUCCESS "Total pipeline duration: ${TOTAL_HOURS}h ${TOTAL_MINUTES}m"
log SUCCESS "Completed at: $(date '+%Y-%m-%d %H:%M:%S')"

echo ""
echo "################################################################################"
echo "#                          PIPELINE COMPLETE                                   #"
echo "################################################################################"
echo ""

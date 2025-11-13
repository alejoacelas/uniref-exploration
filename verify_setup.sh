#!/bin/bash
################################################################################
# Setup Verification Script
# Run this before starting the full pipeline
################################################################################

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo "================================================================================"
echo "  UniRef50 Pipeline - Setup Verification"
echo "================================================================================"
echo ""

# Check 1: Disk Space
echo -e "${BLUE}[1/5] Checking disk space...${NC}"
available_gb=$(df -BG . | awk 'NR==2 {print $4}' | sed 's/G//')
echo "  Available: ${available_gb} GB"

if [ "$available_gb" -lt 250 ]; then
    echo -e "  ${RED}✗ INSUFFICIENT SPACE${NC}"
    echo "  Minimum required: 250 GB"
    echo "  Recommended: 500 GB"
    exit 1
elif [ "$available_gb" -lt 400 ]; then
    echo -e "  ${YELLOW}⚠ MARGINAL SPACE${NC}"
    echo "  You have enough for the pipeline, but not much margin"
else
    echo -e "  ${GREEN}✓ SUFFICIENT SPACE${NC}"
fi
echo ""

# Check 2: Required Files
echo -e "${BLUE}[2/5] Checking required files...${NC}"
required_files=(
    "run_full_pipeline.sh"
    "build_cluster_mappings_optimized.py"
    "augment_hf_dataset_optimized.py"
    "monitor_pipeline.sh"
)

all_present=true
for file in "${required_files[@]}"; do
    if [ -f "$file" ]; then
        echo -e "  ${GREEN}✓${NC} $file"
    else
        echo -e "  ${RED}✗${NC} $file (MISSING)"
        all_present=false
    fi
done

if [ "$all_present" = false ]; then
    echo -e "${RED}ERROR: Some required files are missing${NC}"
    exit 1
fi
echo ""

# Check 3: HuggingFace Token
echo -e "${BLUE}[3/5] Checking HuggingFace token...${NC}"
if [ -n "$HF_TOKEN" ] || [ -n "$HUGGINGFACE_TOKEN" ]; then
    echo -e "  ${GREEN}✓ Token found in environment${NC}"
else
    echo -e "  ${YELLOW}⚠ No token found${NC}"
    echo "  Set it with: export HF_TOKEN='your_token'"
    echo "  Get token from: https://huggingface.co/settings/tokens"
    echo ""
    echo "  Pipeline will prompt for login if needed"
fi
echo ""

# Check 4: Verify NO old files exist
echo -e "${BLUE}[4/5] Checking for old/incomplete files...${NC}"
old_files_exist=false

if [ -f "uniref50.xml.gz" ]; then
    file_size=$(du -h uniref50.xml.gz | cut -f1)
    echo -e "  ${YELLOW}⚠${NC} uniref50.xml.gz exists (${file_size})"

    # Check if it's the full file (should be ~150GB)
    size_bytes=$(stat -c%s uniref50.xml.gz 2>/dev/null || stat -f%z uniref50.xml.gz 2>/dev/null)
    size_gb=$((size_bytes / 1024 / 1024 / 1024))

    if [ "$size_gb" -lt 100 ]; then
        echo -e "    ${RED}This looks incomplete (< 100 GB)${NC}"
        echo "    The full file should be ~150 GB"
        old_files_exist=true
    else
        echo -e "    ${GREEN}Size looks correct (>= 100 GB)${NC}"
        echo "    Pipeline will reuse this file"
    fi
fi

if [ -f "uniref50_mappings_optimized.db" ]; then
    db_size=$(du -h uniref50_mappings_optimized.db | cut -f1)
    row_count=$(sqlite3 uniref50_mappings_optimized.db "SELECT COUNT(*) FROM cluster_mappings" 2>/dev/null || echo "?")
    echo -e "  ${YELLOW}⚠${NC} uniref50_mappings_optimized.db exists (${db_size}, ${row_count} rows)"
    echo "    Pipeline will resume from this point"
fi

if [ "$old_files_exist" = true ]; then
    echo ""
    echo -e "  ${YELLOW}RECOMMENDATION: Delete incomplete files before starting${NC}"
    echo "  Run: rm -f uniref50.xml.gz uniref50_mappings_optimized.db"
else
    echo -e "  ${GREEN}✓ No problematic old files found${NC}"
fi
echo ""

# Check 5: System Info
echo -e "${BLUE}[5/5] System information...${NC}"
echo "  CPU cores: $(nproc)"
echo "  RAM: $(free -h | awk '/^Mem:/ {print $2}')"
echo "  Python: $(python3 --version 2>&1)"

# Check if pigz/bgzip will be available
if command -v pigz &> /dev/null; then
    echo -e "  ${GREEN}✓${NC} pigz (parallel gzip) available"
else
    echo -e "  ${YELLOW}⚠${NC} pigz not installed (will auto-install)"
fi

if command -v bgzip &> /dev/null; then
    echo -e "  ${GREEN}✓${NC} bgzip available"
else
    echo -e "  ${YELLOW}⚠${NC} bgzip not installed (will auto-install)"
fi
echo ""

# Summary
echo "================================================================================"
echo "  Summary"
echo "================================================================================"
echo ""

if [ "$available_gb" -ge 400 ] && [ "$all_present" = true ] && [ "$old_files_exist" = false ]; then
    echo -e "${GREEN}✓ SYSTEM READY FOR FULL PIPELINE${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. Set HF_TOKEN (if not already set):"
    echo "     export HF_TOKEN='your_token_here'"
    echo ""
    echo "  2. Start the pipeline:"
    echo "     ./run_full_pipeline.sh"
    echo ""
    echo "  3. Monitor progress (in another terminal):"
    echo "     ./monitor_pipeline.sh"
    echo ""
    echo "Expected timeline:"
    echo "  • XML download: 1-3 hours (150 GB)"
    echo "  • Database build: 5-9 hours (70M entries)"
    echo "  • Dataset augment: 2-5 hours"
    echo "  • Total: 8-17 hours"
    echo ""
else
    echo -e "${YELLOW}⚠ SETUP HAS ISSUES (see above)${NC}"
    echo ""
    echo "Please fix the issues before running the pipeline"

    if [ "$old_files_exist" = true ]; then
        echo ""
        echo -e "${YELLOW}Recommended: Clean up incomplete files${NC}"
        echo "  rm -f uniref50.xml.gz uniref50_mappings_optimized.db"
    fi
fi

echo ""
echo "================================================================================"

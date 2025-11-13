# UniRef50 Full Pipeline - Usage Guide

## Quick Start

```bash
# 1. Set your HuggingFace token
export HF_TOKEN="your_token_here"

# 2. Run the full pipeline
./run_full_pipeline.sh

# 3. Monitor progress in another terminal
./monitor_pipeline.sh
```

---

## Overview

The full pipeline processes the complete UniRef50 dataset:
1. **Build Database** (~6-12 hours): Parse 150GB XML, create SQLite mappings
2. **Augment Dataset** (~2-5 hours): Add metadata to HuggingFace dataset
3. **Upload** (~20-40 min): Push to HuggingFace as `uniref50-2025-10-v3`

**Total time: 8-17 hours** (can run unattended)

---

## Prerequisites

### System Requirements
- **Disk space**: 500 GB free (recommended)
  - XML file: ~150 GB
  - Database: ~10 GB
  - Dataset cache: ~25 GB
  - Working space: ~50 GB
- **RAM**: 8 GB minimum, 16 GB recommended
- **CPU**: Multi-core (optimizations use parallel processing)
- **Internet**: Stable connection for download/upload

### Software
- Python 3.7+
- wget (for XML download)
- Standard Unix tools (bash, tee, tail)

Auto-installed if missing:
- pigz (parallel gzip)
- bgzip (seekable compression)
- Python packages (lxml, datasets, huggingface_hub)

### HuggingFace Token
Required for uploading the final dataset.

Get token from: https://huggingface.co/settings/tokens

```bash
export HF_TOKEN="hf_xxxxxxxxxxxxxxxxxxxxx"
```

Or set in your shell profile (`~/.bashrc` or `~/.zshrc`):
```bash
echo 'export HF_TOKEN="hf_xxxxxxxxxxxxxxxxxxxxx"' >> ~/.bashrc
source ~/.bashrc
```

---

## Running the Pipeline

### Option 1: Full Automatic Pipeline

```bash
./run_full_pipeline.sh
```

This script:
- ✅ Checks prerequisites (disk space, tools, token)
- ✅ Runs both steps sequentially
- ✅ Handles errors and resume
- ✅ Logs everything to timestamped file
- ✅ Uploads to HuggingFace automatically

**Output:**
- `pipeline_YYYYMMDD_HHMMSS.log` - Complete execution log
- `uniref50_mappings_optimized.db` - Cluster mappings database
- `augmented_dataset/` - Local copy of augmented dataset
- HuggingFace: `alejoacelas/uniref50-2025-10-v3`

### Option 2: Manual Step-by-Step

#### Step 1: Build Cluster Mappings
```bash
python build_cluster_mappings_optimized.py
```

**Duration:** 6-12 hours
**Output:** `uniref50_mappings_optimized.db` (~10 GB)

Features:
- Downloads XML if not present
- Resume capability (can restart after crash)
- Progress updates every 10K entries
- Checkpoints every 5M entries

#### Step 2: Augment HuggingFace Dataset
```bash
python augment_hf_dataset_optimized.py --workers 4
```

**Duration:** 2-5 hours
**Output:** `augmented_dataset/` + HuggingFace upload

Features:
- Batched SQL queries
- Parallel workers (4 by default)
- Automatic upload to HuggingFace
- Validation checks

---

## Monitoring Progress

### Real-time Monitor (Recommended)

In a separate terminal:
```bash
./monitor_pipeline.sh
```

Features:
- 🎨 Color-coded output (errors, warnings, progress)
- 📊 Live statistics (processed count, rate, errors)
- 📈 Runtime tracking
- 🔄 Auto-refreshes every 10 progress updates

### Basic Log Tailing

```bash
# Follow latest log
tail -f pipeline_*.log

# Follow specific log
tail -f pipeline_20251113_153000.log

# Search for errors
grep ERROR pipeline_*.log

# Search for progress
grep "Processed:" pipeline_*.log | tail -20
```

### Progress Indicators

**Step 1 - Building Database:**
```
[15:38:26] Processed: 1,230,000 | Inserted: 1,230,000 | Rate: 1000/s | ETA: 15:30:00
```

**Step 2 - Augmenting Dataset:**
```
[16:45:12] Processed: 45,000,000 | Matched: 44,500,000 (98.89%) | Rate: 5000/s
```

---

## Handling Interruptions

### Resume After Crash

The pipeline is **crash-safe** and can resume from checkpoints:

**If Step 1 crashes:**
```bash
# Just re-run the pipeline
./run_full_pipeline.sh

# Script detects existing database and resumes
# Uses INSERT OR IGNORE for idempotent inserts
```

**If Step 2 crashes:**
```bash
# Re-run from Step 2 only
python augment_hf_dataset_optimized.py --workers 4

# HuggingFace dataset loads from cache
# Metadata addition is idempotent
```

### Manual Checkpoint Management

```bash
# Check current progress
sqlite3 uniref50_mappings_optimized.db "SELECT COUNT(*) FROM cluster_mappings"

# View checkpoint info
cat parsing_checkpoint_optimized.json

# Force restart from scratch
rm uniref50_mappings_optimized.db parsing_checkpoint_optimized.json
./run_full_pipeline.sh
```

---

## Troubleshooting

### Out of Disk Space

**Symptoms:**
- "No space left on device"
- Pipeline crashes during XML download

**Solutions:**
```bash
# Check available space
df -h .

# Clean up old files
rm -rf augmented_dataset/  # Can re-download from HF
rm uniref50.xml.gz          # Can re-download
rm pipeline_*.log           # Old logs

# Use external storage
export TMPDIR=/mnt/large_disk
./run_full_pipeline.sh
```

### Download Interrupted

**Symptoms:**
- XML download fails mid-way

**Solution:**
```bash
# wget resumes automatically with -c flag
# Just re-run the script
./run_full_pipeline.sh
```

### Database Corruption

**Symptoms:**
- "database disk image is malformed"
- SQLite errors

**Solution:**
```bash
# Try to repair
sqlite3 uniref50_mappings_optimized.db "PRAGMA integrity_check"

# If repair fails, start fresh
rm uniref50_mappings_optimized.db
./run_full_pipeline.sh
```

### HuggingFace Upload Fails

**Symptoms:**
- Upload timeout
- Network errors
- Authentication errors

**Solution:**
```bash
# Dataset is saved locally - upload manually
python << EOF
from datasets import load_from_disk
dataset = load_from_disk('./augmented_dataset')
dataset.push_to_hub('alejoacelas/uniref50-2025-10-v3', token='YOUR_TOKEN')
EOF
```

### Slow Performance

**Symptoms:**
- Processing rate < 500 entries/second
- High CPU but low throughput

**Solutions:**
```bash
# Reduce parallel workers (if I/O bound)
python augment_hf_dataset_optimized.py --workers 2

# Check for other processes
top
htop

# Check if pigz is installed
which pigz  # Should return /usr/bin/pigz

# Monitor I/O
iostat -x 5
```

---

## Testing Before Full Run

### Test Mode (10K Entries Only)

```bash
# Test Step 1 (build database)
python build_cluster_mappings_optimized.py test_sample_100k.xml.gz

# Test Step 2 (augment dataset)
python augment_hf_dataset_optimized.py --test

# Both complete in < 5 minutes
```

### Verify Output

```bash
# Check database
sqlite3 uniref50_mappings_optimized.db << EOF
SELECT COUNT(*) as total_clusters FROM cluster_mappings;
SELECT cluster_id, common_taxid, member_count FROM cluster_mappings LIMIT 5;
.quit
EOF

# Check augmented dataset
python << EOF
from datasets import load_from_disk
ds = load_from_disk('./augmented_dataset')
print(f"Splits: {list(ds.keys())}")
print(f"Train size: {len(ds['train']):,}")
print(f"Columns: {ds['train'].column_names}")
print(f"Sample: {ds['train'][0]}")
EOF
```

---

## Performance Tuning

### Adjust Workers

```bash
# More workers (if CPU-bound)
python augment_hf_dataset_optimized.py --workers 8

# Fewer workers (if I/O-bound)
python augment_hf_dataset_optimized.py --workers 2
```

### Adjust Batch Sizes

Edit `build_cluster_mappings_optimized.py`:
```python
LARGE_BATCH_SIZE = 5_000_000  # Increase for faster, riskier inserts
QUEUE_SIZE = 10000            # Increase if producer waits
```

Edit `augment_hf_dataset_optimized.py`:
```python
BATCH_SIZE = 50000      # Increase for faster SQL queries
NUM_WORKERS = 4         # Adjust based on CPU cores
```

---

## Expected Timings

Based on typical hardware (16-core, SSD, 32GB RAM, 1Gbps network):

| Stage | Duration | Bottleneck | Notes |
|-------|----------|------------|-------|
| XML Download | 1-3 hours | Network | wget auto-resumes |
| XML Parsing | 5-8 hours | CPU + I/O | Parallel decompression helps |
| Database Build | 1-2 hours | Disk I/O | SSD much faster than HDD |
| **Step 1 Total** | **6-12 hours** | I/O-bound | Can run overnight |
| Dataset Download | 5-10 min | Network | Cached after first time |
| Metadata Lookup | 2-4 hours | Disk I/O | Parallel workers help |
| Dataset Upload | 20-40 min | Network | Depends on connection |
| **Step 2 Total** | **2-5 hours** | Network + I/O | - |
| **PIPELINE TOTAL** | **8-17 hours** | Varies | Unattended operation |

---

## Output Files

### Generated Files

```
workspace/
├── uniref50.xml.gz                      # 150 GB - Downloaded XML
├── uniref50_mappings_optimized.db       # 10 GB - Cluster mappings
├── augmented_dataset/                   # 25 GB - Augmented HF dataset
│   ├── train/
│   ├── validation/
│   └── dataset_info.json
├── pipeline_20251113_153000.log         # Complete execution log
├── parsing_checkpoint_optimized.json    # Resume checkpoint
└── failed_clusters_optimized.log        # Error log (if any)
```

### Cleanup After Success

Once uploaded to HuggingFace, you can safely delete:

```bash
# Archive the log
gzip pipeline_*.log

# Delete large files (can re-download/regenerate)
rm uniref50.xml.gz                    # 150 GB
rm -rf augmented_dataset/             # 25 GB (backed up on HF)

# Keep these for future use
# uniref50_mappings_optimized.db      # 10 GB - keep for queries
# pipeline_*.log.gz                   # Archive for records
```

---

## Advanced Usage

### Custom Target Dataset

```bash
# Edit run_full_pipeline.sh before running
TARGET_DATASET="your_username/your_dataset_name"
```

Or edit `augment_hf_dataset_optimized.py`:
```python
TARGET_DATASET = "your_username/your_dataset_name"
```

### Use Existing Database

```bash
# Skip Step 1, run Step 2 only
python augment_hf_dataset_optimized.py \
    --workers 4

# Uses existing uniref50_mappings_optimized.db
```

### Process Subset of Data

```bash
# Generate smaller test XML
python generate_test_xml.py 1000000  # 1M entries

# Build database from test XML
python build_cluster_mappings_optimized.py test_sample_1000.xml.gz

# Test augmentation
python augment_hf_dataset_optimized.py --test
```

---

## FAQ

**Q: How long does the full pipeline take?**
A: 8-17 hours typically. Step 1 (database) takes 6-12 hours, Step 2 (augmentation) takes 2-5 hours.

**Q: Can I run this on a laptop?**
A: Not recommended. You need 500GB disk, stable internet, and can't sleep the machine for 8-17 hours. Use a server or cloud instance.

**Q: What if my SSH connection drops?**
A: Use `screen` or `tmux` to run in a persistent session:
```bash
screen -S uniref_pipeline
./run_full_pipeline.sh
# Press Ctrl+A then D to detach
# Reconnect later with: screen -r uniref_pipeline
```

**Q: Can I pause and resume?**
A: Not mid-batch, but each batch (5M entries) is a checkpoint. Kill and restart safely.

**Q: How much does this cost on cloud?**
A: AWS c5.4xlarge (16 vCPU, 32GB RAM): ~$0.68/hr × 12 hours = ~$8
Plus storage: 500GB EBS SSD ~$50/month (prorated)
Total: ~$15-20 for one-time run

**Q: Why is my processing rate slow?**
A: Common causes:
- HDD instead of SSD (use SSD for 5-10x speedup)
- Network I/O (HuggingFace dataset download)
- Too many workers (thrashing)
- Background processes (check with `htop`)

**Q: Can I run multiple pipelines in parallel?**
A: Not recommended. Each pipeline needs full system resources. Run serially.

---

## Support

For issues or questions:
1. Check the log file: `pipeline_*.log`
2. Search for common errors in TROUBLESHOOTING section above
3. Check GitHub issues: https://github.com/alejoacelas/uniref-exploration/issues
4. Open new issue with log excerpt and error message

---

## Summary Commands

```bash
# Setup
export HF_TOKEN="your_token_here"

# Run full pipeline
./run_full_pipeline.sh &

# Monitor in another terminal
./monitor_pipeline.sh

# Check progress
tail -f pipeline_*.log | grep "Processed:"

# After completion
ls -lh uniref50_mappings_optimized.db
ls -lh augmented_dataset/
```

Good luck! The pipeline is designed to run unattended overnight.

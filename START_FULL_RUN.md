# 🚀 START THE FULL UNIREF50 PIPELINE

## ✅ Setup Complete!

Your system is ready for the full 70M entry UniRef50 pipeline run.

---

## Quick Start (3 Commands)

### 1️⃣ Verify Setup (Optional but Recommended)
```bash
./verify_setup.sh
```
This checks disk space, required files, and system readiness.

### 2️⃣ Start the Pipeline
```bash
./run_full_pipeline.sh
```
**This will:**
- Download 150 GB XML file (1-3 hours)
- Build SQLite database with 70M entries (5-9 hours)
- Augment HuggingFace dataset (2-5 hours)
- Upload to HuggingFace as `alejoacelas/uniref50-2025-10-v3`

**Total time: 8-17 hours** (runs unattended)

### 3️⃣ Monitor Progress (Separate Terminal)
```bash
./monitor_pipeline.sh
```
Real-time color-coded progress dashboard.

---

## Expected Timeline

| Phase | Duration | What Happens |
|-------|----------|--------------|
| **Download** | 1-3 hours | wget downloads 150GB XML |
| **Parse & Build** | 5-9 hours | 70M entries → SQLite |
| **Augment** | 2-5 hours | Add metadata to HF dataset |
| **Upload** | 20-40 min | Push to HuggingFace |
| **TOTAL** | **8-17 hours** | Fully automated |

---

## What You'll See

### Download Phase
```
[INFO] Starting cluster mapping build...
[INFO] Starting download (this may take 1-3 hours)...
uniref50.xml.gz    5%[=>    ] 7.5G  25.3MB/s  eta 1h 45m
```

### Build Phase
```
[15:42:13] Processed: 5,230,000 | Inserted: 5,230,000 | Rate: 850/s | ETA: 7:23:00
```

### Augment Phase
```
[16:45:12] Processed: 45,000,000 | Matched: 44,500,000 (98.89%) | Rate: 4500/s
```

---

## Files Created

```
uniref50.xml.gz                     # 150 GB - Downloaded XML
uniref50_mappings_optimized.db      # ~10 GB - Cluster mappings
augmented_dataset/                  # ~25 GB - Augmented HF dataset
pipeline_YYYYMMDD_HHMMSS.log        # Complete log
```

**HuggingFace Dataset:** https://huggingface.co/datasets/alejoacelas/uniref50-2025-10-v3

---

## System Status

✅ **Disk Space:** 429 GB available (plenty!)
✅ **CPU:** 32 cores (excellent for parallel processing)
✅ **RAM:** 251 GB (more than enough)
✅ **HF Token:** Configured
✅ **Tools:** pigz & bgzip installed
✅ **No incomplete files:** Clean slate

---

## Using screen/tmux (Recommended)

Since this runs for 8-17 hours, use `screen` or `tmux` for a persistent session:

```bash
# Start screen session
screen -S uniref

# Inside screen, run pipeline
./run_full_pipeline.sh

# Detach: Press Ctrl+A then D

# Reattach later
screen -r uniref

# Monitor in another screen window
# Press Ctrl+A then C (create new window)
./monitor_pipeline.sh

# Switch between windows: Ctrl+A then N (next)
```

---

## If Something Goes Wrong

### Pipeline Crashes?
```bash
# Just restart - it will resume automatically
./run_full_pipeline.sh
```

The pipeline has checkpoint recovery. It will:
- Skip already-downloaded XML
- Resume database from last checkpoint
- Use INSERT OR IGNORE for safety

### Monitor the Log
```bash
# Real-time monitoring
tail -f pipeline_*.log

# Search for errors
grep ERROR pipeline_*.log

# Check progress
grep "Processed:" pipeline_*.log | tail -20
```

### Manual Cleanup (if needed)
```bash
# Remove incomplete files and start fresh
rm -f uniref50.xml.gz uniref50_mappings_optimized.db
./run_full_pipeline.sh
```

---

## Ready to Start?

```bash
# Run this command to start the full pipeline:
./run_full_pipeline.sh
```

The pipeline will:
1. ✅ Auto-detect and resume from checkpoints
2. ✅ Handle interruptions gracefully
3. ✅ Log everything with timestamps
4. ✅ Upload to HuggingFace automatically
5. ✅ Create local backups

**You can safely leave it running overnight!** 🌙

---

## Quick Reference

| Command | Purpose |
|---------|---------|
| `./verify_setup.sh` | Check system readiness |
| `./run_full_pipeline.sh` | Start full pipeline |
| `./monitor_pipeline.sh` | Watch progress |
| `tail -f pipeline_*.log` | View raw log |
| `screen -S uniref` | Persistent session |
| `Ctrl+A, D` | Detach from screen |
| `screen -r uniref` | Reattach to screen |

---

## After Completion

The pipeline will print:
```
================================================================================
                          PIPELINE COMPLETE
================================================================================

Dataset uploaded to: https://huggingface.co/datasets/alejoacelas/uniref50-2025-10-v3
Total pipeline duration: 12h 34m
```

Then you can:
1. ✅ Verify dataset on HuggingFace
2. ✅ Test loading: `from datasets import load_dataset; ds = load_dataset('alejoacelas/uniref50-2025-10-v3')`
3. ✅ Archive log file
4. ✅ Optional: Clean up large files (XML, local dataset) to save space

---

**System is ready. Good luck! 🚀**

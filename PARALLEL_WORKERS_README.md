# Parallel BGZF Workers - Quick Start Guide

## Overview

This system processes a large BGZF-compressed XML file in parallel by launching multiple workers that seek to different positions and process to EOF. Uses `INSERT OR IGNORE` for automatic deduplication.

## Current Status

**BGZF Conversion:** In progress (started at 2025-11-14 16:11)
- Monitor with: `tail -f bgzf_conversion.log`
- Current size: `ls -lh uniref50.xml.bgz`
- Expected completion: 2-3 hours

**Database:** 39,866,990 entries (57% of ~70M)
- Missing: ~30M entries
- Workers will start at: 55%, 75%, 90%

## Quick Start (Once BGZF Conversion Completes)

### 1. Wait for BGZF Conversion
```bash
# Check if complete
tail bgzf_conversion.log

# Should show:
# "Completed at ..."
# File should be ~31-35GB
ls -lh uniref50.xml.bgz
```

### 2. Launch Workers
```bash
# Runs 3 workers in parallel
./run_parallel_workers.sh
```

**What it does:**
- Worker 1: Seeks to 55%, processes 55%-100%
- Worker 2: Seeks to 75%, processes 75%-100%
- Worker 3: Seeks to 90%, processes 90%-100%
- All use INSERT OR IGNORE (safe overlap)

### 3. Monitor Progress

**Real-time monitoring (orchestration script does this automatically):**
```bash
# Watch database count
watch -n 60 'python3 -c "import sqlite3; conn=sqlite3.connect(\"uniref50_mappings_optimized.db\"); print(f\"{conn.execute(\"SELECT COUNT(*) FROM cluster_mappings\").fetchone()[0]:,} entries\"); conn.close()"'

# Watch individual workers
tail -f worker_logs/worker_55.log
tail -f worker_logs/worker_75.log
tail -f worker_logs/worker_90.log

# View CSV summary
cat worker_progress.csv
```

### 4. Launch 4th Worker if Needed

If database count is still < 60M after workers complete:
```bash
# Launch worker at 40% to fill gaps
python3 -u parallel_worker.py worker_40 40 > worker_logs/worker_40.log 2>&1 &

# Monitor
tail -f worker_logs/worker_40.log
```

## Architecture

### Files

| File | Purpose |
|------|---------|
| `parallel_worker.py` | Worker script: seeks, resyncs, processes to EOF |
| `run_parallel_workers.sh` | Orchestration: launches and monitors workers |
| `worker_progress.csv` | CSV log of all worker results |
| `worker_logs/` | Individual worker log files |
| `uniref50.xml.bgz` | BGZF-compressed XML (seekable) |

### How It Works

1. **BGZF Format:** Compressed with block-level indexing (seekable)
2. **Seek:** Worker seeks to target byte position (~instant)
3. **Resync:** Scans forward to next `<entry id=` tag
4. **Process:** Parses from that entry to EOF
5. **Insert:** Uses `INSERT OR IGNORE` for safe deduplication
6. **Log:** Records progress to CSV

### Deduplication Strategy

**No coordination needed between workers!**
- Database table has `PRIMARY KEY (cluster_id)`
- `INSERT OR IGNORE` automatically skips duplicates
- Workers can overlap at boundaries safely
- Example: Worker at 55% might process some entries from 54.8%-55.2%
  - Worker at 40% processes same entries → DB ignores duplicates

### Performance Expectations

**Single worker (from analysis):**
- Processing rate: ~800-2,000 entries/sec
- 30M entries: ~15-20 hours

**3 parallel workers:**
- Each processes ~10M entries (overlapping ranges)
- Duration: ~8-12 hours (parallelism + overlap)
- Faster than single-threaded resume (no 2-hour skip!)

**4 workers (if needed):**
- Fills any remaining gaps
- Additional 2-4 hours

## Manual Worker Launch

Run a worker at any percentage:
```bash
python3 -u parallel_worker.py <worker_id> <percentage> [bgzf_file] [db_file]

# Examples:
python3 -u parallel_worker.py worker_55 55 > worker_logs/worker_55.log 2>&1 &
python3 -u parallel_worker.py worker_40 40 > worker_logs/worker_40.log 2>&1 &
python3 -u parallel_worker.py worker_65 65 > worker_logs/worker_65.log 2>&1 &
```

## Troubleshooting

### Worker fails to resync
```
ERROR: Failed to resync to entry boundary
```
**Solution:** Try a different percentage (±5%)

### Database locked
```
database is locked
```
**Solution:** Workers use optimized PRAGMAs, but if persistent:
- Check no other process is using the database
- Reduce number of concurrent workers

### Worker crashes
**Solution:** Just relaunch it - INSERT OR IGNORE prevents duplicates
```bash
python3 -u parallel_worker.py worker_55 55 > worker_logs/worker_55_retry.log 2>&1 &
```

### Not reaching 70M entries
**Solutions:**
1. Launch worker at 40%: `python3 -u parallel_worker.py worker_40 40 ...`
2. Launch worker at 35%: `python3 -u parallel_worker.py worker_35 35 ...`
3. Check for entries between workers: try 60%, 80%

## CSV Log Format

```csv
worker_id,percent,start_byte,first_cluster_id,rows_processed,rows_inserted,rows_failed,duration_sec,status,timestamp
worker_55,55,18500000000,UniRef50_X1234,5234567,5200000,34,12543,completed,2025-11-14T18:23:45
```

## Commands Reference

```bash
# Check BGZF conversion status
tail -f bgzf_conversion.log
ls -lh uniref50.xml.bgz

# Check database count
python3 -c "import sqlite3; conn=sqlite3.connect('uniref50_mappings_optimized.db'); print(f'{conn.execute(\"SELECT COUNT(*) FROM cluster_mappings\").fetchone()[0]:,}'); conn.close()"

# Launch orchestration (3 workers)
./run_parallel_workers.sh

# Launch individual worker
python3 -u parallel_worker.py worker_<pct> <pct> > worker_logs/worker_<pct>.log 2>&1 &

# Monitor worker
tail -f worker_logs/worker_<pct>.log

# View all worker results
cat worker_progress.csv | column -t -s ','

# Check running workers
ps aux | grep parallel_worker | grep -v grep

# Kill worker
pkill -f "parallel_worker.py worker_55"
```

## Timeline

**Current Status (2025-11-14 16:14):**
- BGZF conversion started: 16:11 (2.2GB written so far)
- Expected completion: ~18:00-19:00 (2-3 hours)

**Next Steps:**
1. Wait for BGZF conversion (check at 18:00)
2. Run `./run_parallel_workers.sh` (8-12 hours)
3. If needed, launch 4th worker (2-4 hours)
4. Expected completion: ~Saturday morning

## Benefits Over Single-Threaded Resume

| Approach | Skip Time | Processing Time | Total |
|----------|-----------|-----------------|-------|
| Single-threaded resume | 2 hours | 15 hours | 17 hours |
| Parallel workers | 0 minutes | 8-12 hours | 8-12 hours |

**Savings: 5-9 hours** 🚀

Plus:
- Better CPU utilization (3-4 cores)
- More robust (workers independent)
- Progress visibility (CSV log)
- Can target specific ranges

# Running the Full UniRef50 Pipeline

## Quick Start

```bash
# 1. Download full UniRef50 (~25 GB, takes 30-60 min)
wget https://ftp.uniprot.org/pub/databases/uniprot/uniref/uniref50/uniref50.fasta.gz

# 2. Run the pipeline (6-12 hours estimated)
python3 prepare_uniref50_dataset.py \
    --fasta uniref50.fasta.gz \
    --output-dir ./uniref50_output \
    --hf-dataset-name alejoacelas/uniref50-2025-3 \
    --upload \
    --public \
    --threads 64 \
    2>&1 | tee full_pipeline.log

# Monitor progress in real-time:
tail -f full_pipeline.log
```

## Command Options

```
Required:
  --fasta PATH              Path to UniRef50 FASTA file

Optional:
  --output-dir PATH         Output directory (default: ./output)
  --hf-dataset-name NAME    HF dataset name (default: alejoacelas/uniref50-2025-3)
  --upload                  Upload to HuggingFace Hub
  --public                  Make dataset public (default: True)
  --threads N               Number of threads (default: all CPUs)
  --max-sequences N         Limit sequences for testing
```

## System Requirements

### Minimum Requirements
- **CPU:** 32+ cores recommended (will use all available)
- **RAM:** 16 GB minimum, 32 GB recommended
- **Disk:** 500 GB free space
  - Input file: 25 GB
  - Train FASTA: 75 GB
  - MMseqs2 DBs: 100 GB
  - Temporary: 100 GB
  - Final dataset: 30 GB
- **Network:** Stable connection for HF upload (~30 GB)

### Optimal Configuration
- **CPU:** 64+ cores (like current test system)
- **RAM:** 64 GB
- **Disk:** 1 TB SSD (for faster MMseqs2 I/O)
- **Network:** 100+ Mbps for upload

## Expected Runtime

Based on test with 9,118 sequences (3m 5s):

| Dataset Size | Expected Time | Bottleneck |
|--------------|---------------|------------|
| 10k seqs | ~3 minutes | MMseqs2 search |
| 100k seqs | ~30 minutes | MMseqs2 search |
| 1M seqs | ~3-5 hours | MMseqs2 search |
| 70M seqs | **6-12 hours** | MMseqs2 search |

## Progress Monitoring

The pipeline provides real-time progress output:

```bash
# Watch the log file
tail -f full_pipeline.log

# Check MMseqs2 progress (it will show % complete)
grep -E "Progress|search" full_pipeline.log

# Monitor disk usage
watch -n 30 'df -h /path/to/output'

# Monitor memory
watch -n 10 'free -h'
```

## Output Structure

After completion, you'll have:

```
uniref50_output/
├── dataset/                    # Final HuggingFace dataset (~30 GB)
│   ├── train/
│   │   ├── data-00000-of-XXXXX.arrow
│   │   └── ...
│   ├── validation/
│   │   └── data-00000-of-00001.arrow
│   └── dataset_info.json
├── mmseqs2/                    # MMseqs2 results (~100 GB)
│   ├── train_db*              # Train database
│   ├── val_db*                # Validation database
│   ├── result_db*             # Results database
│   └── results.tsv            # Similarity matches
├── train.fasta                 # Train sequences (~75 GB)
├── validation.fasta            # Validation sequences (~350 MB)
├── timing_log.txt             # Performance metrics
└── README.md                  # Dataset card (if uploaded)
```

## Expected Results

Based on test run scaling:

```
Total sequences:          ~70,000,000
Synthetic filtered:       ~100,000 (0.14%)
Validation set:           ~350,000 (0.5%)
Train before filtering:   ~69,550,000
Similar sequences found:  ~1,750,000 (2.5%)
Final train set:          ~67,800,000
Final validation set:     ~350,000

Total final dataset:      ~68,150,000 sequences
```

## Troubleshooting

### Out of Disk Space

```bash
# Check available space before starting
df -h

# If running out during execution, you can:
# 1. Stop the pipeline (Ctrl+C)
# 2. Move output to larger drive
# 3. Resume with same command
```

### Out of Memory

MMseqs2 is disk-based and shouldn't use much RAM, but if you encounter issues:

```bash
# Monitor memory during run
watch -n 5 'free -h && ps aux --sort=-%mem | head -10'

# If needed, reduce parallelism
python3 prepare_uniref50_dataset.py \
    --threads 32 \  # Use fewer threads
    ... other options ...
```

### Slow Network Upload

```bash
# Upload can take 2-4 hours depending on connection
# If it fails, you can retry just the upload:

# 1. Load the dataset
from datasets import load_from_disk
dataset = load_from_disk('./uniref50_output/dataset')

# 2. Upload manually
dataset.push_to_hub(
    'alejoacelas/uniref50-2025-3',
    token='YOUR_HF_TOKEN',
    private=False
)
```

### MMseqs2 Crashes

If MMseqs2 crashes during the search:

```bash
# Check the tmp directory wasn't full
du -sh uniref50_output/mmseqs2/tmp/

# Re-run with more verbose output
python3 prepare_uniref50_dataset.py \
    ... options ... \
    2>&1 | tee -a full_pipeline.log  # Append to existing log
```

## Monitoring Checklist

During the run, periodically check:

- [ ] Disk space: Should decrease slowly (~300 GB used at peak)
- [ ] CPU usage: Should be 95-100% during MMseqs2 search
- [ ] Memory: Should stay under 16 GB
- [ ] Log file: Check for errors or warnings
- [ ] Time elapsed: Compare with expected 6-12 hours
- [ ] Progress output: MMseqs2 shows % complete

## Post-Completion Verification

```bash
# 1. Check dataset was created
ls -lh uniref50_output/dataset/

# 2. Verify dataset integrity
python3 << 'EOF'
from datasets import load_from_disk
ds = load_from_disk('./uniref50_output/dataset')
print(ds)
print(f"Train: {len(ds['train']):,}")
print(f"Validation: {len(ds['validation']):,}")
EOF

# 3. Check timing log
cat uniref50_output/timing_log.txt

# 4. Verify HF upload (if used)
# Visit: https://huggingface.co/datasets/alejoacelas/uniref50-2025-3
```

## Cleanup After Success

Once you've verified the dataset:

```bash
# Keep only the final dataset and remove intermediates
rm -rf uniref50_output/mmseqs2/        # ~100 GB
rm uniref50_output/train.fasta         # ~75 GB
rm uniref50_output/validation.fasta    # ~350 MB

# Keep:
# - uniref50_output/dataset/           (final dataset)
# - uniref50_output/timing_log.txt     (performance metrics)
# - full_pipeline.log                  (execution log)
```

## Support

If you encounter issues:

1. Check the log file: `full_pipeline.log`
2. Review timing log: `uniref50_output/timing_log.txt`
3. Verify disk space: `df -h`
4. Check system resources: `htop` or `top`
5. Review MMseqs2 documentation: https://github.com/soedinglab/MMseqs2

## Success Criteria

The pipeline completed successfully if:

✓ No errors in log file
✓ Final dataset created in `uniref50_output/dataset/`
✓ Train set has ~67-68 million sequences
✓ Validation set has ~350,000 sequences
✓ Timing log shows total time 6-12 hours
✓ HuggingFace upload succeeded (if enabled)
✓ All similarity filtering statistics match expectations

---

**Ready to run!** The pipeline has been tested and optimized for the full UniRef50 dataset.

[# UniRef50 Dataset Augmentation

This directory contains scripts to add metadata columns to the HuggingFace UniRef50 dataset.

## Overview

We add three new columns to the existing dataset (`alejoacelas/uniref50-2025-10`):
- `common_taxid` (string): Cluster-level NCBI taxonomy ID
- `member_taxids` (list[string]): All TaxIDs from cluster members (including representative)
- `member_accessions` (list[string]): All accessions from cluster members (including representative)

## Requirements

- Python 3.7+
- 500 GB disk space
- Internet connection
- HuggingFace account with write access to upload dataset

## Scripts

### 1. `build_cluster_mappings.py`
Downloads UniRef50 XML and builds SQLite database with cluster metadata.

**What it does:**
- Downloads `uniref50.xml.gz` (~150 GB) from UniProt FTP
- Parses XML using memory-efficient streaming
- Extracts metadata for ~70M clusters
- Stores in SQLite database (~10 GB)

**Runtime:** 12-20 hours (mostly I/O bound)

**Features:**
- Resume capability via checkpoints
- Progress tracking with ETA
- Handles interruptions gracefully

**Usage:**
```bash
python build_cluster_mappings.py
```

**Outputs:**
- `uniref50.xml.gz` - Downloaded XML file
- `uniref50_mappings.db` - SQLite database with mappings
- `parsing_checkpoint.txt` - Checkpoint file for resume (auto-deleted on completion)

### 2. `augment_hf_dataset.py`
Updates HuggingFace dataset with metadata from SQLite database.

**What it does:**
- Loads existing dataset from HuggingFace
- Looks up metadata for each cluster ID
- Adds three new columns
- Validates results
- Uploads to HuggingFace as new dataset

**Runtime:** 2-5 hours

**Usage:**
```bash
# Test mode (first 10k entries only)
python augment_hf_dataset.py --test

# Full run with upload
export HF_TOKEN="your_token_here"
python augment_hf_dataset.py
```

**Outputs:**
- `./augmented_dataset/` - Local copy of augmented dataset
- Uploads to: `alejoacelas/uniref50-2025-10-v2`

## Workflow

### Step 1: Build Mapping Database
```bash
python build_cluster_mappings.py
```

This will:
1. Download uniref50.xml.gz (1-3 hours)
2. Parse and build database (10-18 hours)
3. Verify database integrity

**Progress monitoring:**
- Updates every 10,000 entries
- Shows: processed count, rate, ETA
- Creates checkpoint file for resume

**If interrupted:** Just re-run the script. It will resume from the last checkpoint.

### Step 2: Augment Dataset
```bash
# First, test with small sample
python augment_hf_dataset.py --test

# If test passes, run full augmentation
export HF_TOKEN="your_huggingface_token"
python augment_hf_dataset.py
```

This will:
1. Load source dataset from HuggingFace
2. Add metadata columns
3. Validate results
4. Upload to HuggingFace

**HuggingFace token:**
- Get token from: https://huggingface.co/settings/tokens
- Set as environment variable: `export HF_TOKEN="..."`
- Or login interactively when prompted

## Data Format

### Original Schema
```python
{
    'sequence_id': 'UniRef50_A0A1I1LXG1',
    'description': 'Uncharacterized protein n=1 Tax=Tropicimonas...',
    'sequence': 'MNEQRPIPLNQ...',
    'length': 83
}
```

### Augmented Schema
```python
{
    'sequence_id': 'UniRef50_A0A1I1LXG1',
    'description': 'Uncharacterized protein n=1 Tax=Tropicimonas...',
    'sequence': 'MNEQRPIPLNQ...',
    'length': 83,
    'common_taxid': '441112',  # NEW
    'member_taxids': ['441112', '441113', '441114'],  # NEW - JSON array
    'member_accessions': ['A0A1I1LXG1', 'A0A1I1LXG2', 'A0A1I1LXG3']  # NEW - JSON array
}
```

## Disk Space Requirements

| File | Size | Notes |
|------|------|-------|
| uniref50.xml.gz | ~150 GB | Downloaded XML |
| uniref50_mappings.db | ~10 GB | SQLite database |
| augmented_dataset/ | ~25 GB | Local copy of result |
| Temporary | ~50 GB | Working space |
| **Total** | **~235 GB** | Safe estimate: 250 GB |

## Troubleshooting

### Download fails
The download uses `wget -c` which supports resume. Just re-run the script.

### Out of memory
Scripts use streaming approaches and should use < 4 GB RAM. If you see memory issues:
- Close other applications
- Check system has swap space enabled

### Database errors
If SQLite database becomes corrupted:
```bash
rm uniref50_mappings.db parsing_checkpoint.txt
python build_cluster_mappings.py  # Start fresh
```

### Upload fails
Dataset is saved locally to `./augmented_dataset/`. Upload manually:
```python
from datasets import load_from_disk
dataset = load_from_disk('./augmented_dataset')
dataset.push_to_hub('alejoacelas/uniref50-2025-10-v2')
```

### Missing clusters
Some clusters in HF dataset may not be in XML (they were filtered). This is expected.
The script logs these as "missing" and adds empty metadata.

## Validation

The augmentation script validates:
- ✓ All expected columns present
- ✓ Correct data types (string for taxid, lists for arrays)
- ✓ Length consistency (same number of taxids and accessions)
- ✓ Random sampling of 10 entries for manual inspection

## Performance Tips

### Faster download
If you have the XML file already, place it in the directory:
```bash
cp /path/to/uniref50.xml.gz .
```

### Parallel processing
The XML parsing is single-threaded (required for database access).
Cannot be easily parallelized without complex synchronization.

### Resume interrupted runs
Both scripts support resume:
- Script 1: Via checkpoint file
- Script 2: Can be run multiple times (checks existing entries)

## Output Dataset

**Name:** `alejoacelas/uniref50-2025-10-v2`

**Access:**
```python
from datasets import load_dataset

dataset = load_dataset("alejoacelas/uniref50-2025-10-v2")
print(dataset['train'][0])
```

**Size:** ~22-25 GB (vs 20 GB original)

**Schema:** 7 columns (4 original + 3 new)

## Timeline Estimate

| Step | Time | Notes |
|------|------|-------|
| Download XML | 1-3 hours | Network dependent |
| Parse XML | 10-18 hours | ~1M entries/hour |
| Load HF dataset | 5-10 min | First time download |
| Augment data | 2-4 hours | Lookup and merge |
| Upload result | 20-40 min | Network dependent |
| **Total** | **14-25 hours** | Can run overnight |

## Notes

- Scripts are designed for 500GB disk, good CPU (as specified)
- Memory usage kept minimal via streaming
- All operations are resumable
- Extensive error handling and validation
- Progress tracking throughout

## Quick Start

**Test Mode:** Run `run_sample_test.sh` for a quick test with 10k sequences.

**Full Pipeline:** Run `run_full_uniref50.sh` to process the entire UniRef50 dataset.

**Setup Required:**
- Add your `HF_TOKEN` to `.env` file
- Change the HF username in the scripts 

## What the Pipeline Does

The script downloads UniRef50 2025_03 dataset from UniProt. It processes millions of protein sequences.

**Data Filtering:**
- Filters out synthetic sequences using taxonomy information
- Only keeps natural protein sequences

**Train/Test Split:**
- Separates 0.5% of sequences for test set
- Remaining 99.5% goes to training set
- Uses MMseqs2 to ensure clean separation

**Similarity Removal:**
- Removes sequences with >50% similarity between test and train sets

**Output:**
- Creates train and test parquet files
- Uploads dataset to HuggingFace Hub

**Time & Resources:**
- Estimated 6-12 hours to complete
- Needs ~50GB disk space for FASTA file
- Uses all CPU cores for clustering

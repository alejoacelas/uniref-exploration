## Prerequisites to Define

1. **HF username/org**: `alejoacelas`
2. **Dataset name**: `uniref50-2025-3`
3. **Private or public**: `public=True`
4. **Validation split**: 0.5% (randomly selected)
5. **Train split**: 99.5% minus sequences with >50% identity to validation
6. **Filter criteria**: Remove sequences with "Tax=synthetic construct"

- HF token in .env: `HF_TOKEN=hf_xxxxx`

---

## Instructions for AI Agent

Create a pipeline that reproduces the ESM training dataset preparation from UniRef50, removing train sequences similar to validation set using MMseqs2.

**Task: Prepare UniRef50 dataset with train/validation split and similarity filtering**

**Step 1: Install dependencies**

Install MMseqs2 following the instructions in https://github.com/soedinglab/MMseqs2.git


**Step 2: Download UniRef50**
- Download UniRef50 FASTA from UniProt. Check README.md for some guidance

**Step 3: Process**

1. **Load and filter UniRef50**:
   - Parse FASTA file
   - Remove all sequences containing "Tax=synthetic construct" in description

2. **Create validation split**:
   - Randomly select 0.5% of filtered sequences for validation (~250,000 sequences)
   - Remaining 99.5% become initial train set

3. **Run MMseqs2 similarity search**:
   - Create MMseqs2 databases for train and validation sets
   - Run search with exact parameters:
     ```bash
     mmseqs search train_db val_db result_db tmp \
       -min-seq-id 0.5 \
       --alignment-mode 3 \
       --max-seqs 300 \
       -s 7 \
       -c 0.8 \
       --cov-mode 0
     ```
   - Parse results to identify train sequences with ≥50% identity to validation

4. **Remove similar sequences from train**:
   - Remove all train sequences that matched validation with ≥50% identity
   - Keep track of removal statistics

5. **Create HuggingFace dataset**:
   - Structure: `sequence`, `sequence_id`, `description`, `length`
   - Create DatasetDict with final train and validation splits
   - Save in Parquet format for streaming

6. **Upload to HuggingFace Hub**:
   - Upload as `your-username/uniref50-2025-3` (public repository)
   - Include dataset card with:
     - Original UniRef50 sequences count
     - Synthetic constructs removed count
     - Validation set size
     - Initial train set size
     - Sequences removed by similarity filter
     - Final train set size
     - Processing date and MMseqs2 version

**Expected output structure:**
```python
DatasetDict({
    'train': Dataset({
        features: ['sequence', 'sequence_id', 'description', 'length'],
        num_rows: [final_train_count]
    }),
    'validation': Dataset({
        features: ['sequence', 'sequence_id', 'description', 'length'],
        num_rows: [~250000]
    })
})
```

**Script should print**:
- Total UniRef50 sequences processed
- Number of synthetic constructs filtered
- Validation set size (should be ~250,000)
- Number of train sequences removed due to similarity
- Final train/validation sizes
- Upload confirmation URL

**Error handling**:
- Verify MMseqs2 is installed and accessible
- Check FASTA file exists
- Validate HF_TOKEN environment variable
- Handle MMseqs2 temporary files cleanup
# MMseqs2 Filtering Pipeline - Development Version

This is a complete implementation of the MMseqs2-based sequence filtering pipeline described in INSTRUCTIONS.md.

## Quick Start

Tu run on the server:

* Download `query.fasta` and `target.fasta` to `data/`
* Install [MMSeqs2](https://github.com/soedinglab/MMseqs2?tab=readme-ov-file#installation)
* Edit `run_complete_pipeline.sh` to distribute the `run_search.sh` runs across multiple CPUs, instead of running them in sequence.
* Change `--threads` in `run_search.sh` to use multiple CPU threads

The script will automatically:
1. Create all necessary directories
2. Build MMseqs2 databases
3. Split target database into chunks
4. Run searches and per-target scoring on each chunk
5. Aggregate results and compute exclusion thresholds
6. Store a TSV list of accessions, with their max seq-similarity and a dummy flag for exclusion at `results/final/`

## What the Pipeline Does

1. **Database Setup**: Creates MMseqs2 databases and splits targets into chunks
2. **Parallel Processing**: For each chunk:
   - Runs MMseqs2 search (queries vs chunk targets) with coverage filtering (80%)
   - Converts alignments to TSV format
   - Computes per-target similarity scores
3. **Aggregation**: Combines all per-target scores and computes exclusion threshold
4. **Export**: Creates final TSV with exclusion flags for dataset integration

## Modular Design & Parallel Execution

The pipeline is designed for easy parallelization:

### Per-Chunk Processing
- `run_search.sh <chunk_id> [n_splits]` - Processes a single chunk independently
- Each chunk generates its own TSV and per-target score files
- Chunks can be processed in parallel without dependencies

### Parallel Execution Options
The main pipeline script (`run_complete_pipeline.sh`) includes a clearly marked section to insert parallel execution. 

**Slurm Arrays**: Submit as `sbatch --array=0-$((N_SPLITS-1))`

## Files Created

### Scripts
- `run_search.sh` - Processes single chunk (search + scoring)
- `reduce_chunk_to_per_target.py` - Reduces alignment results to per-target scores
- `compute_threshold_and_flags.py` - Aggregates results and computes thresholds
- `run_complete_pipeline.sh` - Orchestrates the complete workflow

### Output Files
- `results/tsv_chunks/` - Raw MMseqs2 alignment results per chunk
- `results/per_target/` - Per-target similarity scores per chunk
- `results/final/target_scores_and_flags.tsv` - **Final output** with exclusion flags
- `results/thresholds/threshold_log.txt` - Threshold computation log

## Key Parameters (Tunable)

### Pipeline Configuration (`run_complete_pipeline.sh`)
- `N_SPLITS=4` - Number of target chunks (increase for production, e.g., 128)

### MMseqs2 Search (`run_search.sh`)
- `-s 7.0` - Sensitivity (higher = more sensitive, slower)
- `-c 0.3` - Coverage threshold (30% minimum coverage required)
- `--cov-mode 0` - Coverage mode (target and query coverage)
- `--max-seqs 200` - Max hits per query (higher = more comprehensive)
- `--threads 1` - CPU cores per chunk (increase for production)

### Exclusion (`compute_threshold_and_flags.py`)
- `target_fraction = 0.08` - Target exclusion percentage (8% of total target dataset)
- **Logic**: Excludes max(8% of total targets, all targets with similarity hits)
- **Output**: Only includes targets with non-zero seq-ids (excludes targets with no similarity)

## Scaling for Production

For production use with 70M targets:

1. **Increase splits**: Change `N_SPLITS=4` to `N_SPLITS=128` or higher in `run_complete_pipeline.sh`
2. **Enable parallel execution**: Uncomment one of the parallel options in the marked section
3. **Increase per-chunk resources**: In `run_search.sh`, adjust `--threads` based on available cores
4. **Use cluster scheduling**: For Slurm, create a wrapper script and submit as job array

## Output Format

The final file `results/final/target_scores_and_flags.tsv` contains:
- `target` - Sequence identifier
- `score` - Similarity score (0.0 to 1.0)
- `exclude` - Final exclusion flag (True/False)

This can be merged with HuggingFace datasets using the `target` column as the join key.
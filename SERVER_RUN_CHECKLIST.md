# Running the homology dataset pipeline on the departmental server

Reference from the 2026-03-17 meeting (Alejo, Aaron, Jaeyoung).

## Pre-run checklist

### 1. Human review of the scripts (before any run)

Both Alejo and Aaron agreed to review the logic of these scripts:

- [ ] `run_complete_pipeline.sh` — orchestration, chunk count, directory setup
- [ ] `run_search.sh` — MMseqs2 search params, convertalis format
- [ ] `reduce_chunk_to_per_target.py` — score definition (currently `max(fident)` per target)
- [ ] `compute_threshold_and_flags.py` — threshold logic, exclusion fraction (8%)

Rationale: Aaron said this is "one of those parts that if we get wrong, it could invalidate the paper later on." The team explicitly decided against relying on AI review for this.

### 2. Things that need changing for the departmental server

The scripts were originally written for Isambard (Slurm-based HPC). The departmental server has 4 GPUs with CPUs and ~1 TB RAM. Slurm should work (Aaron confirmed).

#### File paths

Every hardcoded path needs updating. Current paths use `/workspace/filtering`:

| File | Line(s) | Current value | Change to |
|------|---------|---------------|-----------|
| `run_complete_pipeline.sh` | 6 | `WORKDIR="/workspace/filtering"` | Server path |
| `run_search.sh` | 18 | `WORKDIR="/workspace/filtering"` | Server path |
| `compute_threshold_and_flags.py` | 14 | `WORKDIR = Path("/workspace/filtering")` | Server path |

#### Python path

Any sbatch scripts that reference a specific Python binary (e.g., from Isambard's module system) need to point to the server's Python install instead.

#### Resource allocations

- Jaeyoung originally requested 128 GB RAM on Isambard
- Departmental server has ~1 TB, so this should be fine
- Adjust `--mem`, `--cpus-per-task`, and `--time` in any sbatch headers to match the server's Slurm config

#### Chunk count

`run_complete_pipeline.sh` currently uses `N_SPLITS=4` (dev default). For the full dataset (~70M targets), the original design used 128 chunks. Decide the right value for the departmental server based on available RAM and cores.

### 3. Input data

Ensure these files are on the server:

- `data/query.fasta` — viral sequences (~700k)
- `data/target.fasta` — non-viral sequences (~70M)

Source: `alejoacelas/uniref50-2025-10-viral-split-fasta` on Hugging Face.

### 4. Dependencies

- MMseqs2 in `$PATH` (via `module load` or direct install)
- Python 3 with `pandas`
- Slurm (confirmed available on departmental server)

## Known issues to watch for

1. **Bug fix already applied:** Jaeyoung fixed a one-line bug and pushed it. Make sure you're running the corrected version.

2. **Score definition mismatch:** The CLAUDE.md design doc proposes `score = fident * max(qcov, tcov)`, but `reduce_chunk_to_per_target.py` currently uses `score = max(fident)`. Resolve this before running.

3. **`run_complete_pipeline.sh` summary reads wrong column:** Line 101 uses `cut -f4` but the output TSV has 3 columns (`target`, `seq-id`, `exclude`). Should be `cut -f3`.

4. **Iterative debugging expected:** Some path and config errors will only surface at runtime. Jaeyoung noted this is expected — run with a small chunk first to catch these.

## Run order

1. Upload input FASTA files to server
2. Update all file paths (see table above)
3. Adjust Slurm resource params
4. Do a test run with `N_SPLITS=2` on a small subset
5. Once paths and config are confirmed, run the full pipeline
6. Copy `results/final/target_scores_and_flags.tsv` off server for HF dataset merge

## Timeline

- Reviews: complete by Tuesday 2026-03-24
- Launch scripts after review is approved
- Aaron gets Felix update on Friday 2026-03-21
- Next meeting: Tuesday 2026-03-24

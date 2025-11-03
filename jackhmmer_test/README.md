# Jackhmmer Test Run - Summary

## What Was Done

1. **Installed HMMER** (version 3.4) via conda from bioconda channel
2. **Extracted test data**: 5 query sequences + 200 database sequences from mmseqs_test/test_input.fasta
3. **Ran iterative search** with jackhmmer using 3 iterations
4. **Generated results** and verified everything works

## Test Results

See `TEST_RESULTS.md` for detailed analysis.

**Quick summary:**
- 5 query sequences searched against 200 database sequences
- Converged in 2-3 iterations per query
- Found 1 potential remote homolog (E-value 0.17)
- All queries found themselves with perfect scores
- Total runtime: ~1 second

## Files in This Directory

- `query.fasta` - 5 test query sequences
- `database.fasta` - 200 database sequences (same as mmseqs_test)
- `results.txt` - Detailed jackhmmer output with alignments
- `results.tbl` - Parseable table of hits (TSV format)
- `TEST_RESULTS.md` - Detailed test results and analysis

## About Jackhmmer

Jackhmmer is an iterative protein sequence search tool from the HMMER suite, similar to PSI-BLAST:

1. **Iteration 1**: Searches query sequence against database
2. **Builds profile HMM**: From significant hits
3. **Iterations 2-N**: Searches with profile HMM, refining model
4. **Convergence**: Stops when no new sequences are included

### Key Differences from MMseqs2

| Feature | Jackhmmer | MMseqs2 |
|---------|-----------|---------|
| Purpose | Iterative homology search | Sequence clustering |
| Method | Profile HMM | Smith-Waterman alignment |
| Output | Query-centric hits | Cluster representatives |
| Speed | Moderate | Very fast |
| Sensitivity | High (iterative) | High (tunable) |

## Running Jackhmmer

Basic usage:
```bash
jackhmmer [options] <query.fasta> <database.fasta>
```

Common options:
```bash
-N <n>         # Maximum number of iterations (default: 5)
-E <x>         # E-value threshold for reporting (default: 10.0)
--tblout <f>   # Save table output
-o <f>         # Save full output
--cpu <n>      # Number of CPU threads
```

## Example from This Test

```bash
jackhmmer -N 3 --tblout results.tbl -o results.txt query.fasta database.fasta
```

This ran 3 iterations maximum, saving both detailed output and a parseable table.

## Parameters Used

- **Iterations**: 3 maximum (`-N 3`)
- **E-value threshold**: 10.0 (default)
- **Gap penalties**: Default HMMER settings
- **Database size**: 200 sequences (43,845 residues)

## Key Observations

1. **Fast convergence**: Most queries converged in 2 rounds
2. **Self-hits perfect**: All queries found themselves with E-values < 1e-100
3. **Remote homology**: Found 1 potential remote homolog between queries
4. **Efficient**: Total runtime < 1 second for small dataset

## Next Steps

### For Larger Datasets

1. **Increase iterations**: Use `-N 5` or more for deeper searches
2. **Adjust E-value**: Use stricter `-E 0.001` for high-confidence hits
3. **Save checkpoints**: Use `--chkhmm` and `--chkali` to save intermediate results
4. **Parallelize**: Use `--cpu` to utilize multiple cores

### Alternative HMMER Tools

- **phmmer**: Single-iteration search (like BLAST)
- **hmmsearch**: Search profile HMM against sequence database
- **hmmscan**: Search sequence against profile HMM database

## Use Cases

Jackhmmer is ideal for:

1. **Finding remote homologs**: Iterative search finds distant relatives
2. **Protein family discovery**: Builds comprehensive family profiles
3. **Functional annotation**: Transfer annotations from homologs
4. **Domain detection**: Identifies conserved protein domains

## Comparison with MMseqs2 Test

Both tools tested on the same 200 sequences:

**MMseqs2** (clustering):
- Found 160 clusters (20% reduction)
- 13 multi-member clusters
- Largest cluster: 10 members
- Focus: Grouping similar sequences

**Jackhmmer** (homology search):
- 5 queries against 200 targets
- Found self-hits + 1 remote homolog
- Converged in 2-3 iterations
- Focus: Finding related sequences for each query

## Questions?

- Check `TEST_RESULTS.md` for detailed analysis
- HMMER documentation: http://hmmer.org/
- HMMER user guide: http://eddylab.org/software/hmmer/Userguide.pdf

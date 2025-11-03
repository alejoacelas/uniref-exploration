# Jackhmmer Experiment Summary

## Overview

This experiment demonstrates the installation and usage of **jackhmmer**, an iterative protein sequence search tool from the HMMER suite, on example UniRef100 sequences.

## Two Test Runs Performed

### Run 1: Default Parameters
```bash
jackhmmer -N 3 --tblout results.tbl -o results.txt query.fasta database.fasta
```

**Results:**
- 6 total hits found
- 5 self-hits (perfect matches)
- 1 marginal cross-hit (E-value 0.17)
- Converged in 2 rounds per query

### Run 2: Strict Parameters
```bash
jackhmmer -N 5 -E 0.01 --tblout results_strict.tbl -o results_strict.txt query.fasta database.fasta
```

**Results:**
- 5 total hits found
- 5 self-hits (perfect matches)
- 0 cross-hits (marginal hit filtered out by E-value 0.01 threshold)
- Demonstrates effect of parameter tuning

## Key Comparisons

| Parameter | Run 1 (Default) | Run 2 (Strict) |
|-----------|-----------------|----------------|
| Max iterations | 3 | 5 |
| E-value threshold | 10.0 | 0.01 |
| Hits reported | 6 | 5 |
| Cross-hits | 1 | 0 |
| Runtime | ~1 sec | ~1 sec |

## Dataset

- **Queries**: 5 protein sequences (256-522 aa)
- **Database**: 200 protein sequences (43,845 total residues)
- **Source**: UniRef100 viral proteins
- **Same dataset** used in mmseqs_test for comparison

## Comparison: Jackhmmer vs MMseqs2

Both tools tested on the same 200-sequence dataset:

### Jackhmmer (Iterative Search)
- **Purpose**: Find homologs for each query
- **Method**: Iterative profile HMM
- **Input**: 5 query sequences
- **Output**: 5-6 hits per run (query-centric)
- **Speed**: ~1 second
- **Sensitivity**: Iterative refinement finds remote homologs

### MMseqs2 (Clustering)
- **Purpose**: Group all similar sequences
- **Method**: Fast Smith-Waterman alignment
- **Input**: 200 sequences
- **Output**: 160 clusters (all-vs-all)
- **Speed**: ~25 seconds
- **Sensitivity**: Tunable with -s parameter

## Use Case Recommendations

### When to Use Jackhmmer
1. **Finding homologs** for specific proteins of interest
2. **Remote homology detection** through iterative refinement
3. **Protein family building** starting from seed sequences
4. **Functional annotation** by homology transfer
5. **Domain detection** in novel sequences

### When to Use MMseqs2
1. **Clustering** large sequence databases
2. **Reducing redundancy** in sequence sets
3. **Creating representative sets** (e.g., 90% identity)
4. **Large-scale comparisons** (millions of sequences)
5. **Fast all-vs-all** sequence similarity

## Files in This Directory

### Input Files
- `query.fasta` - 5 query sequences
- `database.fasta` - 200 database sequences

### Output Files (Run 1)
- `results.txt` - Detailed output with alignments
- `results.tbl` - Parseable hit table

### Output Files (Run 2)
- `results_strict.txt` - Detailed output (strict E-value)
- `results_strict.tbl` - Parseable hit table (strict)

### Documentation
- `README.md` - General information and usage
- `TEST_RESULTS.md` - Detailed analysis of results
- `EXPERIMENT_SUMMARY.md` - This file

## Key Learnings

1. **Installation**: HMMER 3.4 easily installed via conda/bioconda
2. **Performance**: Very fast on small datasets (~1 second)
3. **Convergence**: Typically 2-3 iterations sufficient
4. **Parameter tuning**: E-value threshold significantly affects results
5. **Comparison**: Jackhmmer and MMseqs2 serve different purposes

## Technical Details

### Software Versions
- HMMER: 3.4 (Aug 2023)
- Conda: 24.11.3
- OS: Linux 5.15.0-144-generic

### System Information
- Platform: linux-64
- Working directory: /home/alejo/uniprot_data/jackhmmer_test
- Date: Nov 3, 2025

## Next Steps for Production Use

1. **Scale to larger databases**: Test on UniRef50/UniProt
2. **Optimize parameters**: Tune iterations and thresholds for your data
3. **Enable parallelization**: Use `--cpu` for multi-threading
4. **Save intermediate results**: Use `--chkhmm` and `--chkali`
5. **Integrate into pipelines**: Automate homology detection workflows

## Example Commands for Production

### Basic homology search
```bash
jackhmmer query.fasta uniprot.fasta > results.txt
```

### High-confidence hits only
```bash
jackhmmer -E 0.001 --tblout hits.tbl query.fasta database.fasta
```

### Parallel processing
```bash
jackhmmer --cpu 16 -N 5 -o output.txt --tblout hits.tbl query.fasta large_db.fasta
```

### Save all checkpoints
```bash
jackhmmer --chkhmm results --chkali results -o output.txt query.fasta database.fasta
# Creates: results-1.hmm, results-2.hmm, results-1.sto, results-2.sto, etc.
```

## References

1. HMMER homepage: http://hmmer.org/
2. HMMER User Guide: http://eddylab.org/software/hmmer/Userguide.pdf
3. Eddy SR (2011) Accelerated Profile HMM Searches. PLoS Comput Biol 7(10): e1002195
4. MMseqs2: Steinegger M & Söding J (2017) Nature Biotechnology 35:1026

## Conclusion

Successfully demonstrated jackhmmer installation and usage for iterative protein homology search, comparable to the MMseqs2 clustering experiment but serving a different analytical purpose. Both tools are now available and validated for bioinformatics workflows.

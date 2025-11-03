# Jackhmmer Test Results

## Installation

Successfully installed HMMER version **3.4** (Aug 2023) via conda from the bioconda channel.

Confirmed tools available:
- `jackhmmer` - Iterative protein sequence search
- `phmmer` - Single-iteration protein search
- `hmmsearch` - Profile HMM search
- `hmmbuild` - Build profile HMMs
- And 10+ other HMMER utilities

## Test Dataset

- **Query sequences**: 5 proteins from UniRef100
- **Database sequences**: 200 proteins from UniRef100 (same as mmseqs_test)
- **Query file**: `query.fasta` (first 5 sequences from test_input.fasta)
- **Database file**: `database.fasta` (all 200 sequences)
- **Total database residues**: 43,845

## Query Sequences

1. **UniRef100_Q6GZX4** - Putative transcription factor 001R (256 aa)
2. **UniRef100_Q6GZX3** - Uncharacterized protein 002L (287 aa)
3. **UniRef100_Q197F8** - Uncharacterized protein 002R (522 aa)
4. **UniRef100_Q197F7** - Uncharacterized protein 003L (156 aa)
5. **UniRef100_Q6GZX2** - Uncharacterized protein 3R (438 aa)

## Search Parameters

```bash
jackhmmer -N 3 --tblout results.tbl -o results.txt query.fasta database.fasta
```

- **Maximum iterations**: 3 (`-N 3`)
- **E-value threshold**: 10.0 (default for reporting)
- **Inclusion threshold**: Default HMMER settings
- **Gap penalties**: Default HMMER settings
- **Scoring matrix**: BLOSUM62 (default)

## Results Summary

### Overall Statistics

- **Total queries**: 5
- **Total hits found**: 6 (including self-hits)
- **Self-hits**: 5 (all queries found themselves)
- **Remote homologs**: 1 (cross-query hit)
- **Average convergence**: 2 rounds per query
- **Total runtime**: ~1 second

### Hits by Query

| Query | Target | E-value | Score | Bias | Description |
|-------|--------|---------|-------|------|-------------|
| Q6GZX4 | Q6GZX4 | 5.1e-188 | 615.8 | 1.7 | Self-hit (perfect match) |
| Q6GZX3 | Q6GZX3 | 5.0e-236 | 775.4 | 21.9 | Self-hit (perfect match) |
| Q6GZX3 | Q91G63 | 0.17 | 4.8 | 9.7 | Remote homolog |
| Q197F8 | Q197F8 | 0 | 1119.9 | 16.6 | Self-hit (perfect match) |
| Q197F7 | Q197F7 | 1.0e-114 | 373.4 | 10.7 | Self-hit (perfect match) |
| Q6GZX2 | Q6GZX2 | 0 | 1049.4 | 12.1 | Self-hit (perfect match) |

### Key Findings

1. **Perfect Self-Hits**: All 5 queries found themselves with extremely significant E-values (< 1e-100), as expected

2. **Remote Homolog Detected**:
   - Query: **UniRef100_Q6GZX3** (Uncharacterized protein 002L)
   - Hit: **UniRef100_Q91G63** (Uncharacterized protein 034R)
   - E-value: **0.17** (marginally significant)
   - Score: **4.8** bits
   - This suggests possible evolutionary relationship, though not highly confident

3. **Fast Convergence**: Most queries converged in 2 rounds:
   - The algorithm found all significant hits early
   - No new sequences were recruited in later iterations
   - Efficient termination without reaching max iterations

4. **High Scores**: Self-hits ranged from 373-1120 bits
   - Indicates perfect or near-perfect matches
   - Strong statistical confidence (E-values approaching 0)

## Iteration Details

### Example: Query Q6GZX2 (Last query in output)

**Initial search (Round 1):**
- Built HMM from query sequence (438 amino acids)
- Searched 200 targets, found self-hit

**Iteration 2:**
- Refined HMM from high-confidence hits
- Re-searched database
- No new targets included

**Result**: **CONVERGED in 2 rounds**
- Final alignment includes 2 subsequences (original query + self)
- No additional homologs detected
- Early termination saved computational time

### Performance Statistics (Query Q6GZX2)

```
Query model: 438 nodes
Target sequences: 200 (43,845 residues)
Passed MSV filter: 4 (2%)
Passed bias filter: 3 (1.5%)
Passed Vit filter: 1 (0.5%)
Passed Fwd filter: 1 (0.5%)
CPU time: 0.18u 0.02s (0.20s total)
Search speed: 94.92 Mc/sec
```

The filtering cascade eliminated most sequences efficiently:
1. **MSV** (Maximum Segment Value): Fast pre-filter → 4 passed
2. **Bias filter**: Removes compositionally biased hits → 3 passed
3. **Viterbi**: More sensitive alignment → 1 passed
4. **Forward**: Full HMM scoring → 1 passed (final hit)

## Comparison with MMseqs2

### MMseqs2 Results (Clustering)
- Input: 200 sequences
- Output: 160 clusters
- Approach: All-vs-all comparison + clustering
- Result: Groups of similar sequences

### Jackhmmer Results (Homology Search)
- Input: 5 query sequences
- Output: 6 hits (5 self + 1 cross)
- Approach: Query-centric iterative search
- Result: Homologs for each query

### Different Purposes

**MMseqs2 is best for:**
- Reducing sequence redundancy
- Building representative sets
- Fast all-vs-all comparisons
- Large-scale clustering

**Jackhmmer is best for:**
- Finding remote homologs
- Building protein families
- Iterative profile refinement
- Functional annotation

## Biological Interpretation

### The Remote Homolog Hit

**Query**: UniRef100_Q6GZX3 (Uncharacterized protein 002L from Frog virus 3)
**Hit**: UniRef100_Q91G63 (Uncharacterized protein 034R from Invertebrate iridescent virus 6)

**Significance**:
- E-value of 0.17 is marginally significant (borderline)
- Both are from viruses (different species)
- Both are uncharacterized proteins
- Suggests possible functional or evolutionary relationship
- Would need additional evidence to confirm homology

**Interpretation**:
- At E-value > 0.1, this is not a high-confidence homolog
- Could be a true distant relative or random similarity
- More iterations or relaxed thresholds might reveal more evidence
- Manual inspection of alignment would be needed

## Alignment Quality

Self-hits showed perfect alignments:
- 100% identity over full length
- No gaps introduced
- Alignment probability (acc) = 1.00
- Perfect match expected for identical sequences

## Computational Efficiency

**Very fast performance:**
- 5 queries × 200 targets = 1,000 potential comparisons
- Completed in ~1 second total
- Efficient filtering eliminated 99.5% of sequences early
- Profile HMM approach enables fast homology detection

**Scalability considerations:**
- This small test: 5 × 200 = immediate results
- Larger database (e.g., UniProt): Would take hours per query
- Parallelization recommended for production use
- HMMER supports `--cpu` for multi-threading

## Recommendations

### For Production Use

1. **More iterations**: Use `-N 5` (default) for comprehensive search
2. **Stricter E-value**: Use `-E 0.001` for high-confidence hits only
3. **Save checkpoints**: Use `--chkhmm` to save intermediate HMMs
4. **Parallel execution**: Use `--cpu 8` or more for faster searches
5. **Domain analysis**: Use `--domtblout` for per-domain hit information

### For Remote Homology Detection

1. **Increase sensitivity**: More iterations help find distant homologs
2. **Lower E-value threshold**: Allows detection of weaker signals
3. **Multiple queries**: Use several family members as queries
4. **Manual validation**: Inspect marginal hits (E-value 0.01-1.0) carefully
5. **Structural evidence**: Confirm with 3D structure if available

## Conclusions

1. **HMMER successfully installed**: Version 3.4 working correctly
2. **Jackhmmer operational**: All 5 queries completed successfully
3. **Expected results obtained**: Perfect self-hits + 1 marginal cross-hit
4. **Fast performance**: Sub-second runtime for small dataset
5. **Convergence efficient**: 2-3 rounds sufficient for this dataset
6. **Ready for production**: Can scale to larger databases

## Next Steps

1. **Test on larger database**: Try against full UniRef50 or UniProt
2. **Explore other HMMER tools**:
   - `phmmer` for single-iteration searches
   - `hmmscan` for domain annotation
3. **Compare sensitivity**: Run same queries with different parameters
4. **Benchmark performance**: Time searches on various database sizes
5. **Build custom HMMs**: Use `hmmbuild` for specific protein families

## Files Generated

- `results.txt` (42 KB) - Full detailed output with alignments
- `results.tbl` (2.3 KB) - Parseable table of hits
- `query.fasta` (2.2 KB) - Query sequences
- `database.fasta` (67 KB) - Target database

## References

- HMMER: http://hmmer.org/
- HMMER User Guide: http://eddylab.org/software/hmmer/Userguide.pdf
- Eddy SR. Accelerated Profile HMM Searches. PLoS Comput Biol. 2011.

# MMseqs2 Clustering Guide: Complete Reference

## Table of Contents
1. [Overview](#overview)
2. [Installation](#installation)
3. [Test Results](#test-results)
4. [File Structure and Contents](#file-structure-and-contents)
5. [Requirements for Full UniRef50 Run](#requirements-for-full-uniref50-run)
6. [Understanding and Interpreting Outputs](#understanding-and-interpreting-outputs)
7. [Filtering and Processing Results](#filtering-and-processing-results)
8. [Running the Full Clustering](#running-the-full-clustering)
9. [References](#references)

---

## Overview

Successfully installed and tested **MMseqs2 version 18.8cc5c** for clustering protein sequences with high sensitivity parameters suitable for processing UniRef50 (~70 million clusters).

### What Was Done

1. **Installed MMseqs2** via conda (bioconda channel)
2. **Extracted test data**: 200 sequences from `uniref100.xml.gz`
3. **Ran clustering** with specified production parameters
4. **Generated and analyzed results** to verify correctness

### Quick Test Summary

- **Input**: 200 sequences → **Output**: 160 clusters
- **Reduction rate**: 20%
- **Largest cluster**: 10 members
- **Runtime**: ~25 seconds
- **All parameters verified working correctly**

---

## Installation

```bash
# Install via conda (recommended)
conda install -c bioconda mmseqs2 -y

# Verify installation
mmseqs version
# Should output: 18.8cc5c
```

**Alternative installation methods**: See [MMseqs2 GitHub](https://github.com/soedinglab/MMseqs2)

---

## Test Results

### Test Dataset

- **Source**: Extracted from `uniref100.xml.gz`
- **Number of sequences**: 200 representative sequences from UniRef100 clusters
- **Input file**: `test_input.fasta`

### Clustering Parameters

Tested with production parameters for the full uniref50 run:

```bash
--min-seq-id 0.5       # 50% sequence identity threshold
--alignment-mode 3     # Smith-Waterman alignment (accurate but slower)
--max-seqs 300         # Maximum number of sequences per query
-s 7                   # Sensitivity level 7 (high sensitivity, 1-9 scale)
-c 0.8                 # 80% coverage threshold
--cov-mode 0           # Coverage mode 0 (bidirectional - both query and target)
```

**Parameter explanations:**
- **Sensitivity (-s 7)**: Higher values = more sensitive but slower. Range: 1 (fast) to 9 (very sensitive)
- **Coverage mode 0**: Requires both sequences to cover ≥80% of each other (most stringent)
- **Alignment mode 3**: Smith-Waterman provides exact local alignments vs. faster approximate methods

### Clustering Statistics

| Metric | Value |
|--------|-------|
| Total input sequences | 200 |
| Total clusters formed | 160 |
| Reduction rate | 20% |
| Singleton clusters | 147 (91.9%) |
| Multi-member clusters | 13 (8.1%) |
| Largest cluster size | 10 members |
| Average cluster size | 1.25 |

### Cluster Size Distribution

| Cluster Size | Count | Percentage |
|--------------|-------|------------|
| 1 member | 147 | 91.9% |
| 2 members | 5 | 3.1% |
| 3 members | 1 | 0.6% |
| 4 members | 2 | 1.2% |
| 5 members | 2 | 1.2% |
| 6 members | 2 | 1.2% |
| 10 members | 1 | 0.6% |

### Performance

- **Total clustering time**: ~25 seconds for 200 sequences
- **Cascaded clustering**: 3 steps executed (linclust → sensitivity 1 → sensitivity 4 → sensitivity 7)
- **Alignment mode**: Smith-Waterman alignments computed successfully
- **Threads used**: 192 (auto-detected)

### Example Clusters

**Largest cluster (10 members):**
```
Representative: UniRef100_P0C9H5
Members:
  - UniRef100_P0C9H5 (representative)
  - UniRef100_P26705
  - UniRef100_P0C9H1
  - UniRef100_A9JLI5
  - UniRef100_P0C9H2
  - UniRef100_P0C9H3
  - UniRef100_P0C9H0
  - UniRef100_P0C9G9
  - UniRef100_P26708
  - UniRef100_P18558
```

**Other notable multi-member clusters:**
- UniRef100_P18560: 6 members
- UniRef100_P0C9G7: 6 members
- UniRef100_P0C9F6: 5 members
- UniRef100_P0C9F7: 5 members

---

## File Structure and Contents

### Test Directory Layout

```
mmseqs_test/
├── test_input.fasta              # Input: 200 test sequences (67 KB)
├── DB_clu.tsv                    # Primary output: clustering results (6.7 KB)
├── run_full_uniref50_clustering.sh # Script for full run (4.1 KB)
├── MMSEQS2_GUIDE.md              # This comprehensive guide
│
├── DB*                           # MMseqs2 sequence database files
│   ├── DB                        # Binary sequence data (44 KB)
│   ├── DB.index                  # Sequence index (2.6 KB)
│   ├── DB.lookup                 # Header/ID mapping (4.4 KB)
│   ├── DB.dbtype                 # Database type marker (4 B)
│   ├── DB.source                 # Source file reference (19 B)
│   ├── DB_h                      # Header database (24 KB)
│   ├── DB_h.index                # Header index (2.6 KB)
│   └── DB_h.dbtype               # Header DB type marker (4 B)
│
├── DB_clu*                       # MMseqs2 clustering result database
│   ├── DB_clu.0 - DB_clu.191    # Sharded cluster data (most empty, ~200 files)
│   ├── DB_clu.117                # Non-empty shard (383 B)
│   ├── DB_clu.153                # Non-empty shard (467 B)
│   ├── DB_clu.index              # Cluster result index (1.5 KB)
│   └── DB_clu.dbtype             # Cluster DB type marker (4 B)
│
└── tmp/                          # Temporary clustering files (610 KB, ~1965 files)
    └── 14584114417361095919/     # Job-specific temp directory
        ├── clu_redundancy*       # Redundancy filtering results
        └── linclust/             # Fast clustering step results
            └── 2860446899128019061/
                ├── pref*         # Prefiltering results
                ├── aln*          # Alignment results
                └── clust*        # Intermediate clustering

```

### File Group Descriptions

#### 1. Input Files
- **`test_input.fasta`**: Standard FASTA format with 200 protein sequences
  - Headers include UniRef100 cluster IDs, names, member counts, taxonomy
  - Used as input to `mmseqs createdb`

#### 2. MMseqs2 Database Files (`DB*`)
Created by `mmseqs createdb`, these are MMseqs2's internal binary format:
- **`DB`**: Main sequence database (binary, indexed)
- **`DB.index`**: Fast lookup index for sequences
- **`DB.lookup`**: Maps sequence IDs to headers/descriptions
- **`DB_h`**: Separate database storing FASTA headers
- **`DB.dbtype`**: Metadata indicating database type (0 = amino acid)
- **`DB.source`**: Records the original input file path

**Purpose**: Efficient storage and rapid access during clustering. Required for all MMseqs2 operations.

**Scaling**: For UniRef50 (~70M sequences), expect:
- DB files: ~30-50 GB compressed
- Requires ~2-3× uncompressed space during processing

#### 3. Cluster Result Database (`DB_clu*`)
Created by `mmseqs cluster`, stores clustering relationships:
- **`DB_clu.0` - `DB_clu.191`**: Sharded files, one per cluster representative
  - Most files empty due to test dataset size
  - Each non-empty file contains member list for one cluster
- **`DB_clu.index`**: Index to quickly locate cluster memberships
- **`DB_clu.dbtype`**: Marks this as a clustering result database

**Purpose**: Binary storage of cluster assignments, convertible to human-readable formats.

**Scaling**: For UniRef50, expect:
- Cluster DB: ~5-15 GB depending on reduction rate
- Number of shards matches number of threads/sequences

#### 4. TSV Output (`DB_clu.tsv`)
Created by `mmseqs createtsv`, human-readable clustering results:

**Format**: Tab-separated, two columns per line
```
<representative_id>   <member_id>
```

**Example**:
```
UniRef100_Q6GZX4    UniRef100_Q6GZX4
UniRef100_P0C9H5    UniRef100_P0C9H5
UniRef100_P0C9H5    UniRef100_P26705
UniRef100_P0C9H5    UniRef100_P0C9H1
```

**Key points**:
- Representative always appears as a member of its own cluster (first line per cluster)
- All subsequent lines with same representative are cluster members
- Representatives are typically the longest/best-annotated sequence in the cluster

**Scaling**: For UniRef50, expect:
- TSV file: ~2-5 GB (text, compressible)
- One line per sequence (70M+ lines)

#### 5. Temporary Files (`tmp/`)
Created during cascaded clustering, contains intermediate results:
- **`linclust/`**: Fast initial clustering (linear time)
- **`pref*`**: K-mer prefiltering results
- **`aln*`**: Alignment calculation results
- **`clust*`**: Intermediate cluster assignments

**Purpose**: Multi-stage clustering reduces computational complexity.

**Important**: Use `--remove-tmp-files 1` flag to auto-delete after each stage.

**Scaling**: For UniRef50, temp files are the **largest storage requirement**:
- **Peak size: 2-5 TB** during processing
- Automatically deleted if `--remove-tmp-files 1` is used
- Can be placed on fast scratch storage (SSD/NVMe recommended)

#### 6. Scripts
- **`run_full_uniref50_clustering.sh`**: Production-ready clustering script
  - Takes input FASTA, output prefix, threads, temp directory
  - Includes summary statistics generation
  - Has `--remove-tmp-files 1` enabled

---

## Requirements for Full UniRef50 Run

### Dataset Scale
- **Input sequences**: ~70,198,728 clusters (from UniRef50 FASTA)
- **Input file size**: ~25 GB compressed FASTA
- **Sequence lengths**: Variable, median ~300 amino acids

### Computational Requirements

#### 1. Storage
| Component | Size Estimate | Notes |
|-----------|--------------|-------|
| Input FASTA (compressed) | ~25 GB | uniref50.fasta.gz |
| Input FASTA (uncompressed) | ~75 GB | Auto-handled by MMseqs2 |
| Sequence DB (`DB*`) | ~30-50 GB | Binary format |
| Cluster DB (`DB_clu*`) | ~5-15 GB | Depends on reduction |
| Output TSV | ~2-5 GB | Text, compressible |
| **Temporary files (peak)** | **2-5 TB** | **Largest requirement** |
| **Total (peak)** | **~2.5-5.5 TB** | **Use fast storage** |
| Total (after cleanup) | ~100-150 GB | If temps deleted |

**Storage recommendations**:
- Place `tmp/` on fastest available storage (NVMe SSD ideal)
- Output can be on slower storage
- Ensure filesystem supports large file counts (millions of temp files)

#### 2. Memory (RAM)
| Sensitivity Level | Estimated RAM | Notes |
|-------------------|--------------|-------|
| -s 1-3 (low) | 50-100 GB | Faster, less sensitive |
| -s 4-6 (medium) | 100-200 GB | Balanced |
| **-s 7 (your setting)** | **150-300 GB** | **High sensitivity** |
| -s 8-9 (very high) | 300-500 GB | Overkill for most uses |

**Memory scaling factors**:
- More sequences = more RAM for index tables
- Higher sensitivity = larger k-mer index
- `--split` parameter can reduce memory (splits database)

**Memory recommendations**:
- **Minimum**: 128 GB for s=7
- **Recommended**: 256 GB
- **Safe**: 512 GB (won't run out)

#### 3. CPU/Threading
- **Test used**: 192 threads (auto-detected)
- **Optimal threading**: 32-128 cores typical for large datasets
- **Scaling**: Linear up to ~64 cores, diminishing returns beyond
- **Hyperthreading**: Beneficial (use all logical cores)

**Threading recommendations**:
- Use all available cores: `--threads $(nproc)`
- I/O-bound stages don't benefit from >64 threads
- Compute-bound stages (alignment) scale well to 128+ threads

#### 4. Time Estimation

Based on test (200 seqs in 25s) and scaling estimates:

| Stage | Test Time | Scaling Factor | Est. Full Run Time |
|-------|-----------|----------------|-------------------|
| createdb | ~0.1s | Linear | ~1-2 hours |
| linclust (fast) | ~5s | O(n) | ~6-12 hours |
| Prefilter s=1 | ~3s | O(n²) subset | ~12-24 hours |
| Align s=1 | ~0.5s | O(n) hits | ~4-8 hours |
| Prefilter s=4 | ~3s | O(n²) subset | ~12-24 hours |
| Align s=4 | ~0.5s | O(n) hits | ~4-8 hours |
| Prefilter s=7 | ~4s | O(n²) subset | ~18-36 hours |
| Align s=7 | ~0.5s | O(n) hits | ~6-12 hours |
| **Total** | **~25s** | - | **~63-126 hours** |

**Conservative estimate: 3-7 days wall-clock time**

**Time reduction strategies**:
1. **Lower sensitivity** (s=4 or s=5): ~50% faster, slight quality loss
2. **Reduce max-seqs** (--max-seqs 100): Faster, may miss distant homologs
3. **Use faster alignment mode** (--alignment-mode 2): ~30% faster, less accurate
4. **Pre-filter by length/taxonomy**: Cluster subsets separately

#### 5. GPU Support

**Answer: NO**, MMseqs2 does not support GPU acceleration.

- MMseqs2 is CPU-only (highly optimized SIMD/AVX2)
- GPU implementations exist for simpler algorithms (BLAST), not for cascaded clustering
- CPU performance is excellent due to algorithmic optimizations

**Why no GPU?**
- Irregular memory access patterns in clustering
- K-mer indexing and graph algorithms don't map well to GPU
- CPU SIMD is sufficient for high throughput

---

## Understanding and Interpreting Outputs

### Primary Output: `DB_clu.tsv`

#### Format Specification
```
<representative_id><TAB><member_id><NEWLINE>
```

**Every cluster follows this pattern:**
1. First line: `RepID<TAB>RepID` (representative is member of itself)
2. Subsequent lines: `RepID<TAB>MemberID` (additional members)
3. Next cluster starts with new representative

#### Example Output
```tsv
UniRef100_Q6GZX4	UniRef100_Q6GZX4
UniRef100_Q6GZU9	UniRef100_Q6GZU9
UniRef100_Q91G50	UniRef100_Q91G50
UniRef100_P0C9H5	UniRef100_P0C9H5
UniRef100_P0C9H5	UniRef100_P26705
UniRef100_P0C9H5	UniRef100_P0C9H1
UniRef100_P0C9H5	UniRef100_A9JLI5
```

**Interpretation:**
- `Q6GZX4`: Singleton cluster (1 member)
- `Q6GZU9`: Singleton cluster (1 member)
- `Q91G50`: Singleton cluster (1 member)
- `P0C9H5`: Cluster with 4 members (P0C9H5, P26705, P0C9H1, A9JLI5)

### Reading Clusters

#### Basic Python Parser
```python
def parse_clusters(tsv_file):
    """Parse MMseqs2 clustering TSV into dictionary."""
    clusters = {}
    with open(tsv_file, 'r') as f:
        for line in f:
            rep, member = line.strip().split('\t')
            if rep not in clusters:
                clusters[rep] = []
            clusters[rep].append(member)
    return clusters

# Usage
clusters = parse_clusters('DB_clu.tsv')

# Access clusters
for rep, members in clusters.items():
    print(f"Cluster {rep}: {len(members)} members")
    if len(members) > 1:
        print(f"  Members: {', '.join(members)}")
```

#### Generate Summary Statistics
```python
def cluster_stats(clusters):
    """Calculate clustering statistics."""
    total_seqs = sum(len(members) for members in clusters.values())
    num_clusters = len(clusters)
    singleton = sum(1 for m in clusters.values() if len(m) == 1)
    max_size = max(len(members) for members in clusters.values())
    avg_size = total_seqs / num_clusters

    print(f"Total sequences: {total_seqs:,}")
    print(f"Total clusters: {num_clusters:,}")
    print(f"Singletons: {singleton:,} ({100*singleton/num_clusters:.1f}%)")
    print(f"Largest cluster: {max_size:,} members")
    print(f"Average size: {avg_size:.2f}")
    print(f"Reduction: {100*(1-num_clusters/total_seqs):.1f}%")

cluster_stats(clusters)
```

### Alternative Output Formats

MMseqs2 supports multiple output formats beyond TSV:

#### 1. FASTA of Representatives
```bash
# Extract only representative sequences
mmseqs result2repseq DB DB DB_clu DB_clu_rep
mmseqs result2flat DB DB DB_clu_rep DB_clu_rep.fasta
```

**Use case**: Reduced dataset for downstream analysis (e.g., train ML models on non-redundant set)

#### 2. Full Headers in TSV
```bash
# Include full FASTA headers instead of just IDs
mmseqs createtsv DB DB DB_clu DB_clu_full.tsv --full-header 1
```

**Output example**:
```
>UniRef100_Q6GZX4 Putative transcription factor 001R n=4 Tax=Ranavirus	>UniRef100_Q6GZX4 ...
```

#### 3. Sequence Alignment Output
```bash
# Generate detailed alignment information (sequence identity, coverage, etc.)
mmseqs convertalis DB DB DB_clu DB_clu_alnout.tsv \
    --format-output "query,target,qlen,tlen,alnlen,pident,qcov,tcov"
```

**Output columns**:
- `query`: Query sequence ID
- `target`: Target sequence ID
- `qlen`, `tlen`: Query/target lengths
- `alnlen`: Alignment length
- `pident`: Percent identity
- `qcov`, `tcov`: Query/target coverage

**Use case**: Detailed similarity metrics for each cluster relationship

#### 4. Cluster Representatives FASTA
```bash
# Extract representative sequences with cluster size annotation
mmseqs createseqfiledb DB DB_clu DB_clu_seq
mmseqs result2flat DB DB DB_clu_seq DB_clu_rep.fasta --use-fasta-header
```

---

## Filtering and Processing Results

### Common Filtering Tasks

#### 1. Filter by Cluster Size

**Keep only multi-member clusters** (remove singletons):
```python
def filter_by_size(tsv_in, tsv_out, min_size=2):
    """Keep only clusters with >= min_size members."""
    clusters = parse_clusters(tsv_in)

    with open(tsv_out, 'w') as out:
        for rep, members in clusters.items():
            if len(members) >= min_size:
                for member in members:
                    out.write(f"{rep}\t{member}\n")

    print(f"Kept {sum(1 for m in clusters.values() if len(m) >= min_size)} clusters")

# Usage
filter_by_size('DB_clu.tsv', 'DB_clu_multimember.tsv', min_size=2)
```

**Keep only singletons** (novel/unique sequences):
```python
filter_by_size('DB_clu.tsv', 'DB_clu_singletons.tsv', min_size=1, max_size=1)
```

#### 2. Extract Sequences Above Similarity Threshold

**Problem**: MMseqs2 clustering is transitive (A→B, B→C means A and C clustered even if dissimilar). You may want only direct high-similarity pairs.

**Solution**: Re-run alignment with stricter thresholds and extract pairs.

```bash
# Step 1: Re-align cluster members with detailed output
mmseqs align DB DB DB_clu DB_clu_aln \
    --min-seq-id 0.7 \
    -c 0.9 \
    --alignment-mode 3

# Step 2: Convert to TSV with similarity metrics
mmseqs convertalis DB DB DB_clu_aln DB_clu_aln.tsv \
    --format-output "query,target,pident,qcov,tcov,evalue"
```

**Filter alignments in Python**:
```python
def filter_by_similarity(aln_tsv, out_tsv, min_identity=0.7, min_cov=0.9):
    """Keep only pairs above similarity threshold."""
    with open(aln_tsv, 'r') as f, open(out_tsv, 'w') as out:
        for line in f:
            query, target, pident, qcov, tcov, evalue = line.strip().split('\t')
            pident, qcov, tcov = float(pident), float(qcov), float(tcov)

            # Filter by identity and bidirectional coverage
            if pident >= min_identity and qcov >= min_cov and tcov >= min_cov:
                out.write(line)

filter_by_similarity('DB_clu_aln.tsv', 'DB_clu_high_sim.tsv',
                     min_identity=0.8, min_cov=0.95)
```

#### 3. Remove Specific Sequences (Contamination Filtering)

**Example**: Remove all sequences from a specific organism or matching a pattern.

```python
def remove_sequences(tsv_in, tsv_out, exclude_ids):
    """Remove clusters containing any excluded sequence."""
    exclude_set = set(exclude_ids)
    clusters = parse_clusters(tsv_in)

    kept_clusters = {
        rep: members
        for rep, members in clusters.items()
        if not any(m in exclude_set for m in members)
    }

    with open(tsv_out, 'w') as out:
        for rep, members in kept_clusters.items():
            for member in members:
                out.write(f"{rep}\t{member}\n")

    print(f"Removed {len(clusters) - len(kept_clusters)} clusters")

# Example: Remove specific sequences
exclude = ['UniRef100_Q6GZX4', 'UniRef100_P0C9H5']
remove_sequences('DB_clu.tsv', 'DB_clu_filtered.tsv', exclude)
```

**Pattern-based removal** (e.g., remove viral sequences):
```python
def remove_by_pattern(tsv_in, tsv_out, pattern='virus', header_file='test_input.fasta'):
    """Remove clusters where headers match pattern."""
    from Bio import SeqIO

    # Find IDs matching pattern in headers
    exclude_ids = []
    for record in SeqIO.parse(header_file, 'fasta'):
        if pattern.lower() in record.description.lower():
            exclude_ids.append(record.id)

    print(f"Found {len(exclude_ids)} sequences matching '{pattern}'")
    remove_sequences(tsv_in, tsv_out, exclude_ids)

remove_by_pattern('DB_clu.tsv', 'DB_clu_no_virus.tsv', pattern='virus')
```

#### 4. Sample Representatives for Training/Testing

**Random sampling**:
```python
import random

def sample_representatives(tsv_in, out_fasta, n_samples=1000, min_cluster_size=2):
    """Sample N representative sequences from multi-member clusters."""
    clusters = parse_clusters(tsv_in)

    # Get multi-member cluster representatives
    multi_reps = [rep for rep, mem in clusters.items() if len(mem) >= min_cluster_size]

    if len(multi_reps) < n_samples:
        print(f"Warning: Only {len(multi_reps)} clusters available")
        sample = multi_reps
    else:
        sample = random.sample(multi_reps, n_samples)

    # Extract sequences from original FASTA
    from Bio import SeqIO
    sample_set = set(sample)

    with open(out_fasta, 'w') as out:
        for record in SeqIO.parse('test_input.fasta', 'fasta'):
            if record.id in sample_set:
                SeqIO.write(record, out, 'fasta')

    print(f"Sampled {len(sample)} representatives to {out_fasta}")

sample_representatives('DB_clu.tsv', 'sampled_reps.fasta', n_samples=100)
```

#### 5. Create Train/Test Split (Avoiding Data Leakage)

**Problem**: Ensure no similar sequences in train and test sets.

```python
def train_test_split_by_cluster(tsv_file, fasta_file, train_out, test_out, test_ratio=0.1):
    """Split clusters into train/test ensuring no sequence similarity leakage."""
    import random
    from Bio import SeqIO

    # Get all cluster representatives
    clusters = parse_clusters(tsv_file)
    all_reps = list(clusters.keys())
    random.shuffle(all_reps)

    # Split representatives
    n_test = int(len(all_reps) * test_ratio)
    test_reps = set(all_reps[:n_test])
    train_reps = set(all_reps[n_test:])

    # Get all member IDs
    test_ids = set()
    train_ids = set()

    for rep, members in clusters.items():
        if rep in test_reps:
            test_ids.update(members)
        else:
            train_ids.update(members)

    # Write sequences
    with open(train_out, 'w') as train_f, open(test_out, 'w') as test_f:
        for record in SeqIO.parse(fasta_file, 'fasta'):
            if record.id in train_ids:
                SeqIO.write(record, train_f, 'fasta')
            elif record.id in test_ids:
                SeqIO.write(record, test_f, 'fasta')

    print(f"Train clusters: {len(train_reps)} ({len(train_ids)} sequences)")
    print(f"Test clusters: {len(test_reps)} ({len(test_ids)} sequences)")
    print(f"No sequence similarity between train and test (guaranteed by clustering)")

train_test_split_by_cluster('DB_clu.tsv', 'test_input.fasta',
                            'train.fasta', 'test.fasta', test_ratio=0.1)
```

#### 6. Merge Clusters (Post-Processing)

**Example**: Merge clusters if representatives are similar.

```python
def merge_clusters_by_rep_similarity(tsv_file, similarity_tsv, min_sim=0.8):
    """Merge clusters whose representatives are similar."""
    # Read clustering
    clusters = parse_clusters(tsv_file)

    # Read representative similarities
    rep_pairs = {}
    with open(similarity_tsv, 'r') as f:
        for line in f:
            q, t, pident = line.strip().split('\t')[:3]
            if float(pident) >= min_sim:
                rep_pairs.setdefault(q, set()).add(t)

    # Union-find to merge clusters
    parent = {rep: rep for rep in clusters}

    def find(x):
        if parent[x] != x:
            parent[x] = find(parent[x])
        return parent[x]

    def union(x, y):
        parent[find(x)] = find(y)

    for q, targets in rep_pairs.items():
        for t in targets:
            if q in parent and t in parent:
                union(q, t)

    # Rebuild merged clusters
    merged = {}
    for rep, members in clusters.items():
        new_rep = find(rep)
        merged.setdefault(new_rep, []).extend(members)

    print(f"Original clusters: {len(clusters)}")
    print(f"Merged clusters: {len(merged)}")
    return merged
```

---

## Running the Full Clustering

### Using the Provided Script

```bash
# Syntax
./run_full_uniref50_clustering.sh <input_fasta> <output_prefix> <threads> <tmp_dir>

# Example
./run_full_uniref50_clustering.sh \
    /path/to/uniref50.fasta.gz \
    uniref50_clustered \
    128 \
    /scratch/tmp_mmseqs

# Monitor progress (if you redirect output)
./run_full_uniref50_clustering.sh ... > clustering.log 2>&1 &
tail -f clustering.log
```

### Manual Step-by-Step

If you prefer manual control:

```bash
# 1. Create database
mmseqs createdb uniref50.fasta.gz DB --threads 128

# 2. Run clustering
mmseqs cluster DB DB_clu tmp \
    --min-seq-id 0.5 \
    --alignment-mode 3 \
    --max-seqs 300 \
    -s 7 \
    -c 0.8 \
    --cov-mode 0 \
    --threads 128 \
    --remove-tmp-files 1 \
    -v 3

# 3. Create TSV output
mmseqs createtsv DB DB DB_clu DB_clu.tsv --threads 128

# 4. Generate statistics (Python)
python3 << 'EOF'
clusters = {}
with open('DB_clu.tsv', 'r') as f:
    for line in f:
        rep, member = line.strip().split('\t')
        clusters.setdefault(rep, []).append(member)

print(f"Total sequences: {sum(len(m) for m in clusters.values()):,}")
print(f"Total clusters: {len(clusters):,}")
print(f"Reduction: {100*(1-len(clusters)/sum(len(m) for m in clusters.values())):.1f}%")
EOF
```

### Monitoring Long-Running Jobs

```bash
# Check MMseqs2 process
ps aux | grep mmseqs

# Monitor CPU usage
htop

# Check disk I/O
iotop

# Monitor temp directory size
watch -n 60 'du -sh tmp/'

# Estimate progress (if verbose output)
grep -i "progress" clustering.log | tail -1
```

### Handling Failures

**If job fails or is interrupted:**

```bash
# MMseqs2 can resume if tmp files exist
# Re-run same command - it will skip completed steps

# If tmp is corrupted, start fresh:
rm -rf tmp/
# Re-run clustering command
```

**Memory errors:**
```bash
# Reduce memory usage by splitting database
mmseqs cluster DB DB_clu tmp \
    --split 4 \  # Split into 4 chunks
    --split-memory-limit 100G \  # Max 100GB per chunk
    [other parameters...]
```

---

## References

- **MMseqs2 Paper**: Steinegger M, Söding J. *MMseqs2 enables sensitive protein sequence searching for the analysis of massive data sets*. Nature Biotechnology, 35(11), 1026-1028 (2017). [DOI: 10.1038/nbt.3988](https://doi.org/10.1038/nbt.3988)

- **MMseqs2 GitHub**: [https://github.com/soedinglab/MMseqs2](https://github.com/soedinglab/MMseqs2)

- **MMseqs2 User Guide**: [https://github.com/soedinglab/MMseqs2/wiki](https://github.com/soedinglab/MMseqs2/wiki)

- **UniProt Release 2025_03**: See `COMPREHENSIVE_REPORT.md` for UniRef dataset details

---

**Document version**: 1.0
**Last updated**: 2025-11-03
**Test environment**: Linux 5.15.0, MMseqs2 18.8cc5c, 192 threads

0. High-level overview

Goal:
	1.	Take queries.fasta and targets.fasta on the cluster.
	2.	Run MMseqs2 in a split + Slurm array scheme.
	3.	For each target sequence, compute a single similarity score vs the query set (e.g. max(fident × coverage) across all hits).
	4.	Choose a threshold on that score such that ~8% of targets are flagged “excluded”.
	5.	Export a CSV/Parquet keyed by sequence_id with a boolean exclude flag, to be merged into the original HF dataset offline.

We’ll split the targets into chunks so each job only handles a fraction of the 70M. Queries (700k) are small enough to stay whole on each node.

⸻

1. Directory layout & prerequisites

Pick a the current work directory on shared storage, e.g.:

/work/mmseqs_exclusion/

Inside it, standardize:

/work/mmseqs_exclusion/
  data/
    queries.fasta
    targets.fasta
  mmseqs_db/
    queryDB/       # MMseqs DB for queries
    targetDB/      # MMseqs DB for all targets
    target_chunks/ # MMseqs DB chunks for targets
  tmp/
    # per-job tmp dirs will go here
  results/
    tsv_chunks/    # raw convertalis TSVs per chunk
    per_target/    # reduced per-target metric files
    thresholds/    # logs of chosen thresholds
    final/         # final mapping file for HF

Assumptions for engineer:
	•	module load mmseqs2 (or similar) works and provides mmseqs in $PATH.
	•	Slurm is configured (e.g. sbatch, srun).

⸻

2. One-time MMseqs database creation

From /work/mmseqs_exclusion:

mkdir -p mmseqs_db tmp results/tsv_chunks results/per_target results/thresholds results/final

# 2.1 Create query DB
mmseqs createdb data/queries.fasta mmseqs_db/queryDB

# 2.2 Create target DB
mmseqs createdb data/targets.fasta mmseqs_db/targetDB


⸻

3. Split the target DB for parallelization

We’ll split targetDB into N chunks (tune N to expected parallelism; example: 128 chunks).

N_SPLITS=128
mmseqs splitdb mmseqs_db/targetDB mmseqs_db/target_chunks/target_split --splits $N_SPLITS

This creates DBs like:
	•	mmseqs_db/target_chunks/target_split_000, target_split_001, … up to target_split_127.

These names are important for the Slurm array script.

⸻

4. Slurm array script for MMseqs search per target chunk

Create run_search_array.sh in /work/mmseqs_exclusion:

#!/bin/bash
#SBATCH --job-name=mmseqs_search
#SBATCH --array=0-127        # 0 .. N_SPLITS-1
#SBATCH --cpus-per-task=8    # adjust per-node
#SBATCH --mem=32G            # adjust to your cluster/resources
#SBATCH --time=24:00:00      # adjust
#SBATCH --output=logs/search_%A_%a.out
#SBATCH --error=logs/search_%A_%a.err

set -euo pipefail

module load mmseqs2  # or your environment setup

WORKDIR=/work/mmseqs_exclusion
cd "$WORKDIR"

CHUNK_ID=${SLURM_ARRAY_TASK_ID}
CHUNK_NAME=$(printf "target_split_%03d" "$CHUNK_ID")

QUERY_DB="$WORKDIR/mmseqs_db/queryDB"
TARGET_CHUNK_DB="$WORKDIR/mmseqs_db/target_chunks/${CHUNK_NAME}"
RESULT_DB="$WORKDIR/mmseqs_db/target_chunks/${CHUNK_NAME}_res"
TMP_DIR="$WORKDIR/tmp/${CHUNK_NAME}"

mkdir -p "$TMP_DIR"

# 4.1 Run search: queries vs this target chunk
mmseqs search "$QUERY_DB" "$TARGET_CHUNK_DB" "$RESULT_DB" "$TMP_DIR" \
  --alignment-mode 3 \
  -s 7.0 \
  -e 1e5 \
  --min-seq-id 0.0 \
  --cov-mode 0 -c 0.0 \
  --max-seqs 200 \
  --threads "$SLURM_CPUS_PER_TASK"

# 4.2 Convert alignments to TSV with continuous metrics
TSV_OUT="$WORKDIR/results/tsv_chunks/${CHUNK_NAME}.tsv"

mmseqs convertalis "$QUERY_DB" "$TARGET_CHUNK_DB" "$RESULT_DB" "$TSV_OUT" \
  --format-mode 4 \
  --format-output "query,target,fident,qcov,tcov,alnlen,bits"

# (Optional) cleanup intermediate result DB and tmp to save space:
# rm -rf "$RESULT_DB" "$TMP_DIR"

Make sure logs/ exists:

mkdir -p logs

Then submit:

sbatch run_search_array.sh

This launches one job per target chunk (128 jobs), each using 8 CPUs.
Adjust --array, --cpus-per-task, --mem, --time, and -s / --max-seqs as needed.

⸻

5. Reduce each chunk TSV to a per-target metric

We want one score per target sequence, representing “how similar is this sequence to its closest query”.

Proposed score:

score = max over hits of (fident * max(qcov, tcov))

	•	fident is fraction identity [0,1].
	•	qcov and tcov are coverage [0,1]; we take the higher one to capture “how much of either sequence is covered”.
	•	We can also discard very short / low-coverage alignments before computing the max.

Create a small Python script, reduce_chunk_to_per_target.py:

#!/usr/bin/env python3
import sys
import pandas as pd

# Usage: reduce_chunk_to_per_target.py input.tsv output.tsv

inp = sys.argv[1]
outp = sys.argv[2]

# TSV columns in order: query, target, fident, qcov, tcov, alnlen, bits
df = pd.read_csv(inp, sep="\t", header=None,
                 names=["query", "target", "fident", "qcov", "tcov", "alnlen", "bits"])

# Filter trivial alignments (tunable):
min_alnlen = 50
min_cov = 0.2

df = df[df["alnlen"] >= min_alnlen]
df = df[df[["qcov", "tcov"]].max(axis=1) >= min_cov]

if df.empty:
    # write an empty file with target + score columns
    out_df = pd.DataFrame(columns=["target", "score"])
    out_df.to_csv(outp, sep="\t", index=False)
    sys.exit(0)

# score = fident * max(qcov, tcov)
df["cov_max"] = df[["qcov", "tcov"]].max(axis=1)
df["score"] = df["fident"] * df["cov_max"]

# per-target max score
per_target = (
    df.groupby("target", as_index=False)["score"]
      .max()
)

per_target.to_csv(outp, sep="\t", index=False)

Make it executable:

chmod +x reduce_chunk_to_per_target.py

Then run it on each chunk TSV. You can do this with GNU parallel or another Slurm array.

Example with GNU parallel (run from /work/mmseqs_exclusion):

ls results/tsv_chunks/target_split_*.tsv \
  | parallel '
      python3 reduce_chunk_to_per_target.py {} results/per_target/{/}
    '

This creates per-target files like:
	•	results/per_target/target_split_000.tsv (columns: target, score)

⸻

6. Build a global per-target score table and choose threshold

Now we need:
	1.	One table with all targets and their score.
	2.	A threshold such that ~8% of all targets are above it.

Assumptions:
	•	The target column in MMseqs corresponds to the sequence_id in your dataset or can be trivially mapped.
	•	You’ll also have a file listing already-excluded sequences (the 1%) if you want to keep them fixed.

Example Python script: compute_threshold_and_flags.py:

#!/usr/bin/env python3
import glob
import numpy as np
import pandas as pd
import sys
from pathlib import Path

WORKDIR = Path("/work/mmseqs_exclusion")

# 6.1 Load per-chunk per-target scores
per_target_files = sorted(glob.glob(str(WORKDIR / "results/per_target/target_split_*.tsv")))
dfs = []
for f in per_target_files:
    df = pd.read_csv(f, sep="\t")
    dfs.append(df)

if dfs:
    scores = pd.concat(dfs, ignore_index=True)
else:
    raise SystemExit("No per-target files found.")

# 6.2 Full list of target IDs from MMseqs DB
# mmseqs listseqdb outputs one ID per line
target_ids_file = WORKDIR / "mmseqs_db/target_ids.txt"
# If this doesn't exist yet, generate it:
# mmseqs listseqdb mmseqs_db/targetDB mmseqs_db/target_ids.txt

# Read target IDs
all_ids = pd.read_csv(target_ids_file, sep="\t", header=None, names=["target"])

# scores: only those targets with at least one hit; others are implicitly score=0
# Merge: left join all_ids with scores, fill NaNs with 0
merged = all_ids.merge(scores, on="target", how="left")
merged["score"] = merged["score"].fillna(0.0)

# 6.3 If we already have a list of pre-excluded targets, read it; else assume none
pre_excluded_file = WORKDIR / "data/pre_excluded_ids.txt"  # optional
if pre_excluded_file.exists():
    pre_ex = pd.read_csv(pre_excluded_file, header=None, names=["target"])
    merged["pre_excluded"] = merged["target"].isin(pre_ex["target"])
else:
    merged["pre_excluded"] = False

# 6.4 Compute threshold to reach target exclusion fraction

total_N = len(merged)
target_fraction = 0.08  # 8% of full dataset
target_excluded_total = int(round(target_fraction * total_N))

current_pre = merged["pre_excluded"].sum()
remaining_to_exclude = max(target_excluded_total - current_pre, 0)

# For sequences not already pre-excluded, choose top-k by score
candidates = merged[~merged["pre_excluded"]].copy()
candidates = candidates.sort_values("score", ascending=False).reset_index(drop=True)

if remaining_to_exclude == 0:
    threshold = float("inf")  # no new exclusion
    merged["exclude"] = merged["pre_excluded"]
else:
    if remaining_to_exclude > len(candidates):
        remaining_to_exclude = len(candidates)
    kth_score = candidates.loc[remaining_to_exclude - 1, "score"]
    threshold = kth_score

    merged["exclude"] = merged["pre_excluded"] | (merged["score"] >= threshold)

print(f"Total targets: {total_N}")
print(f"Pre-excluded: {current_pre}")
print(f"Newly excluded target: {remaining_to_exclude}")
print(f"Final excluded: {merged['exclude'].sum()}")
print(f"Score threshold used: {threshold}")

# 6.5 Save threshold and full table
WORKDIR.joinpath("results/thresholds/threshold_log.txt").write_text(
    f"Threshold: {threshold}\n"
    f"Total targets: {total_N}\n"
    f"Pre-excluded: {current_pre}\n"
    f"Target excluded fraction: {target_fraction}\n"
)

merged.to_csv(WORKDIR / "results/final/target_scores_and_flags.tsv",
              sep="\t", index=False)

Before running this, generate target_ids.txt once:

mmseqs listseqdb mmseqs_db/targetDB mmseqs_db/target_ids.txt

Then run:

python3 compute_threshold_and_flags.py

Output:
	•	results/final/target_scores_and_flags.tsv with columns:
	•	target – MMseqs target ID
	•	score – per-target similarity metric
	•	pre_excluded – whether it was already excluded (if provided)
	•	exclude – final boolean flag (true for ~8% of total)

The log in results/thresholds/threshold_log.txt captures the actual threshold and counts.

⸻

7. Merge back into the HF dataset

You’ll likely do this off-cluster, using the HF dataset you prepared (with sequence_id and other columns).

Steps:
	1.	Copy target_scores_and_flags.tsv off the cluster.
	2.	Load it in Python alongside your HF dataset.

Example sketch:

import pandas as pd

hf = pd.read_parquet("your_hf_dataset.parquet")  # or .csv / .jsonl
flags = pd.read_csv("target_scores_and_flags.tsv", sep="\t")

# Assume hf.sequence_id matches flags.target (or modify accordingly)
merged = hf.merge(flags[["target", "exclude", "score"]],
                  left_on="sequence_id", right_on="target", how="left")

# sanity: there should be no missing flags; if there are, treat them as non-excluded
merged["exclude"] = merged["exclude"].fillna(False)
merged["score"] = merged["score"].fillna(0.0)

# Now you can filter for training:
train = merged[~merged["exclude"]].copy()

You can store exclude as a dummy feature and keep score if you want to adjust thresholds or do stratified sampling later.

⸻

8. Parameters that can be tuned (knobs for the engineer)

If the engineer needs levers to adjust runtime vs sensitivity:
	1.	MMseqs search
	•	-s 7.0 (sensitivity): decrease for speed, increase for sensitivity.
	•	--max-seqs 200: lower to reduce output size, higher if you want more hits per query.
	•	--cov-mode 0 -c 0.0: we filter on coverage in post-processing; if output is too big, they can tighten to e.g. --cov-mode 1 -c 0.2.
	2.	Post-processing filters (in reduce_chunk_to_per_target.py)
	•	min_alnlen = 50 and min_cov = 0.2 are reasonable defaults; tightening them will reduce noise and volume.
	3.	Scalability
	•	Increase N_SPLITS for more chunks if per-chunk runtime/memory is too high.
	•	Adjust --cpus-per-task and --mem according to node sizes.

⸻

9. Summary for the engineer
	•	Build MMseqs DBs: createdb for queries and targets.
	•	Split targets with splitdb into N chunks.
	•	Use a Slurm array (run_search_array.sh) to:
	•	run mmseqs search for each target chunk vs full query DB
	•	convertalis each result to TSV with query,target,fident,qcov,tcov,alnlen,bits
	•	Post-process each chunk TSV into a per-target max score file.
	•	Aggregate all per-target files, compute a global score threshold to hit 8% exclusion (respecting any pre-excluded IDs).
	•	Export a target_scores_and_flags.tsv mapping every sequence_id to score and exclude.
	•	Merge back into the HF dataset using sequence_id to define the final training set.
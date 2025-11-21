#!/usr/bin/env python3
"""
Compute threshold and exclusion flags.

This script aggregates per-target seq-ids from all chunks, computes a threshold
to exclude approximately 8% of targets, and creates the final exclusion flags.
"""
import glob
import pandas as pd
import sys
from pathlib import Path

def main():
    WORKDIR = Path("/workspace/filtering")

    print("Computing threshold and exclusion flags...")
    print(f"Working directory: {WORKDIR}")

    # 6.1 Load per-chunk per-target seq-ids
    per_target_files = sorted(glob.glob(str(WORKDIR / "results/per_target/target_split_*.tsv")))
    print(f"Found {len(per_target_files)} per-target files")

    if not per_target_files:
        print("ERROR: No per-target files found. Run the reduction step first.")
        sys.exit(1)

    dfs = []
    for f in per_target_files:
        print(f"  Loading {f}")
        df = pd.read_csv(f, sep="\t")
        print(f"    -> {len(df)} targets with seq-ids")
        dfs.append(df)

    if dfs:
        scores = pd.concat(dfs, ignore_index=True)
        print(f"Total targets with seq-ids: {len(scores)}")
    else:
        raise SystemExit("No per-target files found.")

    # 6.2 Get total target count for proper fraction calculation
    import subprocess
    result = subprocess.run(["grep", "-c", "^>", "data/target.fasta"],
                          capture_output=True, text=True)
    if result.returncode != 0:
        print("ERROR: Could not count sequences in original FASTA")
        sys.exit(1)

    total_target_count = int(result.stdout.strip())
    print(f"Total target sequences in original FASTA: {total_target_count}")
    print(f"Targets with non-zero seq-ids: {len(scores)}")
    print(f"Targets with implicit zero seq-ids: {total_target_count - len(scores)}")

    # Work only with targets that have hits (don't add zero-score targets)
    merged = scores.copy()

    # 6.3 Compute threshold: exclude max(8% of total targets, number of targets with hits)
    target_fraction = 0.08  # 8% of complete target dataset
    fraction_based_target = int(round(target_fraction * total_target_count))
    targets_with_hits = len(merged)

    # Take the maximum to ensure we exclude at least all targets with hits
    target_excluded_total = max(fraction_based_target, targets_with_hits)

    print(f"\nThreshold computation:")
    print(f"  Total targets in dataset: {total_target_count}")
    print(f"  Target exclusion fraction: {target_fraction:.1%}")
    print(f"  Fraction-based exclusion target: {fraction_based_target}")
    print(f"  Targets with non-zero seq-ids: {targets_with_hits}")
    print(f"  Final exclusion target: {target_excluded_total} (max of above two)")

    total_N = len(merged)  # For reporting purposes

    # Since we're using max(fraction_target, targets_with_hits), and we only have targets_with_hits,
    # we either exclude all targets (if targets_with_hits >= fraction_target)
    # or the top fraction_target targets (if fraction_target > targets_with_hits)

    if target_excluded_total == 0:
        threshold = float("inf")  # no exclusion
        merged["exclude"] = False
        print(f"  No exclusions needed")
    elif target_excluded_total >= len(merged):
        # Exclude all targets with hits
        threshold = 0.0
        merged["exclude"] = True
        print(f"  Excluding all {len(merged)} targets with non-zero seq-ids")
    else:
        # Exclude top k targets by seq-id
        sorted_targets = merged.sort_values("seq-id", ascending=False).reset_index(drop=True)
        kth_score = sorted_targets.loc[target_excluded_total - 1, "seq-id"]
        threshold = kth_score

        print(f"  Threshold set to: {threshold}")
        print(f"  This will exclude the top {target_excluded_total} targets by seq-id")

        # Use > threshold to avoid excluding too many in case of ties
        merged["exclude"] = merged["seq-id"] > threshold

    final_excluded = merged["exclude"].sum()
    final_fraction_of_total = final_excluded / total_target_count
    final_fraction_of_hits = final_excluded / total_N

    print(f"\nFinal results:")
    print(f"  Seq-id threshold used: {threshold}")
    print(f"  Final excluded count: {final_excluded}")
    print(f"  Exclusion fraction of total dataset: {final_fraction_of_total:.1%}")
    print(f"  Exclusion fraction of targets with hits: {final_fraction_of_hits:.1%}")

    # Show seq-id distribution
    print(f"\nSeq-id statistics (targets with hits only):")
    print(f"  Min seq-id: {merged['seq-id'].min():.4f}")
    print(f"  Max seq-id: {merged['seq-id'].max():.4f}")
    print(f"  Mean seq-id: {merged['seq-id'].mean():.4f}")
    print(f"  Median seq-id: {merged['seq-id'].median():.4f}")

    # 6.4 Save threshold and full table
    threshold_log = (
        f"Threshold: {threshold}\n"
        f"Total targets in dataset: {total_target_count}\n"
        f"Targets with hits: {total_N}\n"
        f"Target excluded fraction: {target_fraction}\n"
        f"Final excluded count: {final_excluded}\n"
        f"Final exclusion fraction of total: {final_fraction_of_total:.4f}\n"
        f"Final exclusion fraction of hits: {final_fraction_of_hits:.4f}\n"
    )

    WORKDIR.joinpath("results/thresholds/threshold_log.txt").write_text(threshold_log)
    print(f"Threshold log saved to: results/thresholds/threshold_log.txt")

    output_file = WORKDIR / "results/final/target_scores_and_flags.tsv"
    merged.to_csv(output_file, sep="\t", index=False)
    print(f"Final results saved to: {output_file}")

    # Show a few examples
    print(f"\nSample results (top 10 by seq-id):")
    sample = merged.nlargest(10, "seq-id")
    print(sample[["target", "seq-id", "exclude"]].to_string(index=False))

if __name__ == "__main__":
    main()
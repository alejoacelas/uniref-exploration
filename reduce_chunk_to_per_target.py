#!/usr/bin/env python3
"""
Reduce chunk TSV to per-target metric.

This script takes a TSV file with MMseqs2 alignment results and computes
a single similarity seq-id per target sequence.

Usage: reduce_chunk_to_per_target.py input.tsv output.tsv
"""
import sys
import pandas as pd

def main():
    if len(sys.argv) != 3:
        print("Usage: reduce_chunk_to_per_target.py input.tsv output.tsv", file=sys.stderr)
        sys.exit(1)

    inp = sys.argv[1]
    outp = sys.argv[2]

    print(f"Processing {inp} -> {outp}")

    # TSV columns in order: query, target, fident, qcov, tcov, alnlen, bits
    # MMseqs2 includes headers, so read with header=0
    df = pd.read_csv(inp, sep="\t", header=0)

    print(f"Loaded {len(df)} alignments")

    if df.empty:
        # write an empty file with target + seq-id columns
        print("No alignments passed filters - writing empty output")
        out_df = pd.DataFrame(columns=["target", "seq-id"])
        out_df.to_csv(outp, sep="\t", index=False)
        return

    # seq-id = fident (which equals seq-identity for alignment-mode 3)
    df["seq-id"] = df["fident"]

    # per-target max seq-id
    per_target = (
        df.groupby("target", as_index=False)["seq-id"]
          .max()
    )

    print(f"Computed seq-ids for {len(per_target)} unique targets")
    print(f"Seq-id range: {per_target['seq-id'].min():.3f} - {per_target['seq-id'].max():.3f}")

    per_target.to_csv(outp, sep="\t", index=False)
    print(f"Saved per-target seq-ids to {outp}")

if __name__ == "__main__":
    main()
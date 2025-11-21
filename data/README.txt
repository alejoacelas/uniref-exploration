MMseqs2 Filtering Pipeline - Data Directory
==========================================

Place your input FASTA files here:

REQUIRED FILES:
- query.fasta    : Query sequences (smaller set, e.g., 700k sequences)
- target.fasta   : Target sequences (larger set, e.g., 70M sequences)

OPTIONAL FILES:
- pre_excluded_ids.txt : List of sequence IDs already excluded (one per line)

NOTES:
- FASTA files can be compressed (.gz) - MMseqs2 will handle them
- For large files, ensure sufficient disk space for databases and results
- The pipeline will create MMseqs2 databases from these FASTA files automatically

EXAMPLE USAGE:
1. Copy your FASTA files to this directory
2. Run: ./run_complete_pipeline.sh
3. Results will be saved to results/final/target_scores_and_flags.tsv
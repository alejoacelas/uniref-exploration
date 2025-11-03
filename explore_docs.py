#!/usr/bin/env python3
"""
Simple script to explore UniProt knowledgebase documentation files.
Shows structure and samples from various controlled vocabulary files.
"""

import gzip
import os
from pathlib import Path


def parse_structured_file(filepath, max_entries=5):
    """Parse structured UniProt text files with ID/AC/DE format."""
    entries = []
    current_entry = {}

    opener = gzip.open if filepath.endswith('.gz') else open
    mode = 'rt' if filepath.endswith('.gz') else 'r'

    with opener(filepath, mode) as f:
        for line in f:
            line = line.rstrip()
            if not line or line.startswith('-') or line.startswith('_'):
                continue

            if line.startswith('ID   '):
                if current_entry:
                    entries.append(current_entry)
                    if len(entries) >= max_entries:
                        break
                current_entry = {'ID': line[5:].strip()}
            elif line.startswith('AC   '):
                current_entry['AC'] = line[5:].strip()
            elif line.startswith('DE   '):
                current_entry.setdefault('DE', []).append(line[5:].strip())
            elif line.startswith('//'):
                if current_entry:
                    entries.append(current_entry)
                    if len(entries) >= max_entries:
                        break
                current_entry = {}

    return entries


def explore_humdisease():
    """Explore human disease vocabulary file."""
    print("\n" + "="*70)
    print("HUMAN DISEASES (humdisease.txt)")
    print("="*70)

    filepath = "docs/humdisease.txt"
    entries = parse_structured_file(filepath, max_entries=3)

    print(f"\nFound {len(entries)} sample disease entries:\n")
    for entry in entries:
        print(f"ID: {entry.get('ID', 'N/A')}")
        print(f"AC: {entry.get('AC', 'N/A')}")
        if 'DE' in entry:
            print(f"Definition: {' '.join(entry['DE'][:2])}")
        print()


def explore_keywords():
    """Explore keywords vocabulary file."""
    print("\n" + "="*70)
    print("KEYWORDS (keywlist.txt)")
    print("="*70)

    filepath = "docs/keywlist.txt"
    entries = parse_structured_file(filepath, max_entries=5)

    print(f"\nFound {len(entries)} sample keyword entries:\n")
    for entry in entries:
        print(f"ID: {entry.get('ID', 'N/A')}")
        print(f"AC: {entry.get('AC', 'N/A')}")
        print()


def explore_deleted_accessions():
    """Explore deleted accession numbers."""
    print("\n" + "="*70)
    print("DELETED ACCESSIONS (delac_tr.txt.gz)")
    print("="*70)

    filepath = "docs/delac_tr.txt.gz"
    count = 0
    sample_accessions = []

    with gzip.open(filepath, 'rt') as f:
        in_data = False
        for line in f:
            line = line.strip()
            if line.startswith('_'):
                in_data = True
                continue
            if in_data and line and not line.startswith('A0A'):
                continue
            if in_data and line.startswith('A0A'):
                count += 1
                if count <= 10:
                    sample_accessions.append(line)
            if count > 100000:  # Stop after counting many
                break

    print(f"\nTotal deleted accessions (sample count): {count:,}")
    print(f"\nFirst 10 deleted accessions:")
    for acc in sample_accessions:
        print(f"  {acc}")


def explore_journal_list():
    """Explore journal abbreviations."""
    print("\n" + "="*70)
    print("JOURNAL LIST (jourlist.txt)")
    print("="*70)

    filepath = "docs/jourlist.txt"
    journals = []

    with open(filepath) as f:
        in_data = False
        for line in f:
            line = line.strip()
            if line.startswith('_'):
                in_data = True
                continue
            if in_data and line and len(journals) < 10:
                journals.append(line)

    print(f"\nSample journal abbreviations:")
    for journal in journals:
        print(f"  {journal}")


def show_file_summary():
    """Show summary of all documentation files."""
    print("\n" + "="*70)
    print("FILE SUMMARY")
    print("="*70)

    docs_dir = Path("docs")
    files_by_ext = {}

    for filepath in docs_dir.iterdir():
        if filepath.is_file():
            ext = filepath.suffix
            size = filepath.stat().st_size
            files_by_ext.setdefault(ext, []).append((filepath.name, size))

    print("\nFiles by extension:")
    for ext, files in sorted(files_by_ext.items()):
        print(f"\n{ext or 'no extension'} files ({len(files)}):")
        # Show largest 5 files of each type
        for name, size in sorted(files, key=lambda x: x[1], reverse=True)[:5]:
            size_mb = size / (1024 * 1024)
            print(f"  {name:40s} {size_mb:10.2f} MB")


if __name__ == "__main__":
    print("UniProt Knowledgebase Documentation Explorer")
    print("=" * 70)

    os.chdir(Path(__file__).parent)

    show_file_summary()
    explore_humdisease()
    explore_keywords()
    explore_deleted_accessions()
    explore_journal_list()

    print("\n" + "="*70)
    print("Exploration complete!")
    print("="*70)

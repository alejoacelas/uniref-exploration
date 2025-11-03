#!/usr/bin/env python3
"""
Simple script to explore UniProt Knowledgebase data.
This includes Swiss-Prot (curated) and TrEMBL (automated) protein sequences.
"""

import gzip
import tarfile
import os
from pathlib import Path


def explore_kb_archive_structure():
    """Examine the structure of the knowledgebase archive."""
    print("\n" + "="*70)
    print("KNOWLEDGEBASE ARCHIVE STRUCTURE")
    print("="*70)

    archive_path = "knowledgebase_sample.tar.gz"

    if not os.path.exists(archive_path):
        print(f"\nError: {archive_path} not found!")
        return

    print(f"\nExploring: {archive_path}")
    print(f"File size: {os.path.getsize(archive_path) / (1024*1024):.2f} MB (sample)")

    try:
        with tarfile.open(archive_path, 'r:gz', ignore_zeros=True) as tar:
            print("\nArchive contents (partial):")
            members = []
            dirs = set()
            files = []

            try:
                for member in tar.getmembers():
                    members.append(member)
                    if member.isdir():
                        dirs.add(member.name)
                    else:
                        files.append(member)

                    if len(members) >= 50:
                        break
            except Exception as e:
                print(f"  (Reached end of partial archive: {type(e).__name__})")

            print(f"\nDirectories found: {len(dirs)}")
            for d in sorted(dirs)[:10]:
                print(f"  {d}")

            print(f"\nFiles found (first 20): {len(files)}")
            for f in files[:20]:
                size_mb = f.size / (1024*1024)
                print(f"  {f.name:50s} {size_mb:10.2f} MB")

    except Exception as e:
        print(f"\nError reading archive: {e}")


def describe_uniprot_format():
    """Describe UniProt data formats."""
    print("\n" + "="*70)
    print("UNIPROT DATA FORMATS")
    print("="*70)

    description = """
UniProt Knowledgebase contains:

  1. Swiss-Prot: Manually curated, reviewed protein sequences
  2. TrEMBL: Automatically annotated, unreviewed sequences

Available formats:
  - DAT (text): Original UniProt flat file format
  - FASTA: Sequence data only
  - XML: Structured protein data
  - RDF/TTL: Linked data formats
  - GFF: Genome feature format

DAT format structure (example):
  ID   ENTRY_NAME     STATUS; LENGTH.
  AC   P12345; Q98765;
  DT   DATE
  DE   DESCRIPTION
  GN   GENE_NAME
  OS   ORGANISM
  OC   ORGANISM_CLASSIFICATION
  OX   NCBI_TAXONOMY_ID
  RN   [REFERENCE_NUMBER]
  ...
  SQ   SEQUENCE ... AA;
       SEQUENCE DATA
  //

Key features:
  - Protein function and interactions
  - Post-translational modifications
  - Disease associations
  - Subcellular location
  - Domain and motif information
  - Cross-references to other databases
"""

    print(description)


def example_dat_parser():
    """Show example code for parsing UniProt DAT files."""
    print("\n" + "="*70)
    print("EXAMPLE: Parsing UniProt DAT Format")
    print("="*70)

    code = '''
# Example code to parse UniProt DAT files:

def parse_uniprot_dat(filepath):
    """Parse UniProt DAT/text format."""
    opener = gzip.open if filepath.endswith('.gz') else open
    mode = 'rt' if filepath.endswith('.gz') else 'r'

    with opener(filepath, mode) as f:
        entry = {}
        in_sequence = False
        sequence_lines = []

        for line in f:
            line = line.rstrip()

            if line.startswith('ID   '):
                if entry:
                    yield entry
                entry = {'ID': line[5:].strip()}
                in_sequence = False
                sequence_lines = []

            elif line.startswith('AC   '):
                accessions = line[5:].strip().replace(';', '').split()
                entry['accessions'] = accessions

            elif line.startswith('DE   '):
                entry.setdefault('description', []).append(line[5:].strip())

            elif line.startswith('OS   '):
                entry['organism'] = line[5:].strip()

            elif line.startswith('OX   '):
                # Parse taxonomy ID
                tax_id = line[5:].strip()
                entry['taxonomy_id'] = tax_id

            elif line.startswith('SQ   '):
                in_sequence = True

            elif in_sequence:
                if line.startswith('//'):
                    entry['sequence'] = ''.join(sequence_lines)
                    yield entry
                    entry = {}
                    in_sequence = False
                    sequence_lines = []
                else:
                    # Remove spaces and make uppercase
                    seq = line.strip().replace(' ', '').upper()
                    sequence_lines.append(seq)

# Usage:
for protein in parse_uniprot_dat("uniprot_sprot.dat.gz"):
    acc = protein.get('accessions', [''])[0]
    organism = protein.get('organism', 'Unknown')
    seq_len = len(protein.get('sequence', ''))
    print(f"{acc}: {organism}, {seq_len} aa")
'''

    print(code)


def example_fasta_parser():
    """Show example code for parsing UniProt FASTA files."""
    print("\n" + "="*70)
    print("EXAMPLE: Parsing UniProt FASTA Format")
    print("="*70)

    code = '''
# Example code to parse UniProt FASTA files:

def parse_uniprot_fasta(filepath):
    """Parse UniProt FASTA format."""
    opener = gzip.open if filepath.endswith('.gz') else open
    mode = 'rt' if filepath.endswith('.gz') else 'r'

    with opener(filepath, mode) as f:
        header = None
        sequence = []

        for line in f:
            line = line.strip()
            if line.startswith('>'):
                if header:
                    yield {
                        'header': header,
                        'accession': header.split('|')[1] if '|' in header else None,
                        'name': header.split('|')[2].split()[0] if '|' in header else None,
                        'sequence': ''.join(sequence)
                    }
                header = line
                sequence = []
            else:
                sequence.append(line)

        if header:
            yield {
                'header': header,
                'accession': header.split('|')[1] if '|' in header else None,
                'name': header.split('|')[2].split()[0] if '|' in header else None,
                'sequence': ''.join(sequence)
            }

# FASTA header format:
# >db|accession|name description OS=organism GN=gene PE=level SV=version

# Example:
# >sp|P12345|PROT_HUMAN Protein name OS=Homo sapiens GN=GENE PE=1 SV=2

# Usage:
for protein in parse_uniprot_fasta("uniprot_sprot.fasta.gz"):
    print(f"{protein['accession']}: {protein['name']}, {len(protein['sequence'])} aa")
'''

    print(code)


def show_expected_files():
    """Show expected files in full knowledgebase archive."""
    print("\n" + "="*70)
    print("EXPECTED FILES IN FULL ARCHIVE")
    print("="*70)

    expected = """
Full knowledgebase2025_03.tar.gz (~186GB) contains:

Swiss-Prot (reviewed):
  - uniprot_sprot.dat.gz          # DAT format
  - uniprot_sprot.fasta.gz        # FASTA format
  - uniprot_sprot.xml.gz          # XML format

TrEMBL (unreviewed):
  - uniprot_trembl.dat.gz         # DAT format (very large!)
  - uniprot_trembl.fasta.gz       # FASTA format (very large!)
  - uniprot_trembl.xml.gz         # XML format (very large!)

Additional formats:
  - Various taxonomic subsets
  - RDF/TTL formats
  - GFF files

Documentation:
  - Same docs/ directory as in knowledgebase-docs-only archive

Statistics (approximate):
  - Swiss-Prot: ~570,000 entries (manually curated)
  - TrEMBL: ~250,000,000 entries (automatically annotated)
"""

    print(expected)


if __name__ == "__main__":
    print("UniProt Knowledgebase Explorer")
    print("=" * 70)

    os.chdir(Path(__file__).parent)

    describe_uniprot_format()
    explore_kb_archive_structure()
    example_dat_parser()
    example_fasta_parser()
    show_expected_files()

    print("\n" + "="*70)
    print("Exploration complete!")
    print("="*70)

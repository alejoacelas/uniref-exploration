#!/usr/bin/env python3
"""
Simple script to explore UniRef cluster data.
Shows actual data from downloaded UniRef files.
"""

import gzip
import os
import xml.etree.ElementTree as ET
from pathlib import Path


def describe_uniref_format():
    """Describe the expected UniRef data format."""
    print("\n" + "="*70)
    print("UNIREF DATA FORMAT")
    print("="*70)

    description = """
UniRef (UniProt Reference Clusters) provides clustered sets of sequences
from the UniProt Knowledgebase at three levels of identity:

  - UniRef100: 100% identical sequences and sub-fragments
  - UniRef90:  90% identity clusters
  - UniRef50:  50% identity clusters

Expected file formats:
  - FASTA format (.fasta): Sequence data with cluster representatives
  - XML format (.xml): Detailed cluster information
  - RDF format (.rdf): Linked data representation

Typical FASTA header format:
  >UniRef100_P99999 Protein name n=X Tax=Taxon TaxID=Y RepID=Z

Where:
  - P99999 is the representative sequence ID
  - n=X is the number of members in the cluster
  - Tax=Taxon is the common taxon name
  - TaxID=Y is the taxonomy ID
  - RepID=Z is the representative protein entry name

XML contains:
  - Cluster ID and members
  - Representative sequence
  - Taxonomy information
  - Cross-references to other UniRef levels
  - Sequence data
"""

    print(description)


def show_uniref_stats():
    """Show statistics about UniRef release."""
    print("\n" + "="*70)
    print("UNIREF RELEASE STATISTICS")
    print("="*70)

    # Try to read release notes
    release_files = [
        ("uniref50.release_note", "UniRef50"),
        ("uniref90.release_note", "UniRef90"),
        ("uniref100.release_note", "UniRef100")
    ]

    found_any = False
    for rf, name in release_files:
        if os.path.exists(rf):
            found_any = True
            with open(rf) as f:
                content = f.read()
                print(f"\n{name}:")
                # Extract just the key info
                for line in content.split('\n'):
                    if 'Release:' in line or 'Number of clusters:' in line:
                        print(f"  {line.strip()}")

    if found_any:
        print("\nThese cluster counts represent:")
        print("  - UniRef100: Nearly unique sequences (~465M clusters)")
        print("  - UniRef90: Clustered at 90% identity (~208M clusters)")
        print("  - UniRef50: Clustered at 50% identity (~70M clusters)")
    else:
        print("\nRelease note files not found.")
        print("Expected to find: uniref50/90/100.release_note")


def show_sample_fasta_data():
    """Show actual FASTA data from sample file."""
    print("\n" + "="*70)
    print("SAMPLE FASTA DATA")
    print("="*70)

    fasta_file = "uniref100_sample.fasta"

    if not os.path.exists(fasta_file):
        print(f"\nSample file {fasta_file} not found.")
        return

    print(f"\nReading from: {fasta_file}\n")

    with open(fasta_file) as f:
        entry_count = 0
        for line in f:
            if line.startswith('>'):
                entry_count += 1
                header = line[1:].strip()
                parts = header.split()
                cluster_id = parts[0]

                # Extract key information
                n_members = "?"
                taxon = "?"
                rep_id = "?"

                for part in parts:
                    if part.startswith('n='):
                        n_members = part[2:]
                    elif part.startswith('Tax='):
                        taxon_parts = []
                        idx = parts.index(part)
                        for p in parts[idx:]:
                            if p.startswith('TaxID='):
                                break
                            taxon_parts.append(p[4:] if p.startswith('Tax=') else p)
                        taxon = ' '.join(taxon_parts)
                    elif part.startswith('RepID='):
                        rep_id = part[6:]

                protein_name = ' '.join(parts[1:parts.index('n=' + n_members) if 'n=' + n_members in ' '.join(parts) else 1])

                print(f"Entry {entry_count}: {cluster_id}")
                print(f"  Protein: {protein_name}")
                print(f"  Members: {n_members}")
                print(f"  Taxonomy: {taxon}")
                print(f"  RepID: {rep_id}")
            else:
                seq = line.strip()
                if seq and entry_count <= 3:
                    print(f"  Sequence: {seq[:60]}... ({len(seq)} aa total)")
                    print()

    print(f"Total entries in sample: {entry_count}")


def show_sample_xml_data():
    """Show actual XML data from sample file."""
    print("\n" + "="*70)
    print("SAMPLE XML DATA")
    print("="*70)

    xml_file = "uniref100.xml.gz"

    if not os.path.exists(xml_file):
        print(f"\nSample file {xml_file} not found.")
        return

    print(f"\nReading first few entries from: {xml_file}\n")

    try:
        with gzip.open(xml_file, 'rt') as f:
            # Read only the first few KB to avoid loading the whole file
            sample_data = ""
            for i, line in enumerate(f):
                sample_data += line
                if i > 200:  # Read ~200 lines
                    break

            # Parse what we have
            # Add a closing tag to make it valid
            if '</entry>' in sample_data:
                last_entry = sample_data.rfind('</entry>')
                sample_data = sample_data[:last_entry + 8] + '\n</UniRef100>'

            try:
                root = ET.fromstring(sample_data)
                entries = root.findall('.//{http://uniprot.org/uniref}entry')

                print(f"Found {len(entries)} complete entries in sample:")

                for idx, entry in enumerate(entries[:3], 1):
                    entry_id = entry.get('id')
                    name = entry.find('.//{http://uniprot.org/uniref}name')

                    # Get properties
                    props = {}
                    for prop in entry.findall('.//{http://uniprot.org/uniref}property'):
                        props[prop.get('type')] = prop.get('value')

                    print(f"\nEntry {idx}: {entry_id}")
                    print(f"  Name: {name.text if name is not None else 'N/A'}")
                    print(f"  Members: {props.get('member count', 'N/A')}")
                    print(f"  Common taxon: {props.get('common taxon', 'N/A')}")
                    print(f"  Taxon ID: {props.get('common taxon ID', 'N/A')}")

                    # Get representative member info
                    rep_member = entry.find('.//{http://uniprot.org/uniref}representativeMember')
                    if rep_member is not None:
                        db_ref = rep_member.find('.//{http://uniprot.org/uniref}dbReference')
                        if db_ref is not None:
                            rep_props = {}
                            for prop in db_ref.findall('.//{http://uniprot.org/uniref}property'):
                                rep_props[prop.get('type')] = prop.get('value')

                            print(f"  Representative: {rep_props.get('protein name', 'N/A')}")
                            print(f"  UniProtKB: {rep_props.get('UniProtKB accession', 'N/A')}")
                            print(f"  Organism: {rep_props.get('source organism', 'N/A')}")
                            print(f"  Length: {rep_props.get('length', 'N/A')} aa")

                        seq = rep_member.find('.//{http://uniprot.org/uniref}sequence')
                        if seq is not None and seq.text:
                            seq_text = seq.text.strip()
                            print(f"  Sequence: {seq_text[:60]}...")

            except ET.ParseError as e:
                print(f"XML parsing note: {e}")
                print("Showing raw XML structure instead:\n")
                # Show first entry manually
                lines = sample_data.split('\n')
                in_entry = False
                line_count = 0
                for line in lines:
                    if '<entry ' in line:
                        in_entry = True
                    if in_entry:
                        print(line)
                        line_count += 1
                        if line_count > 30 or '</entry>' in line:
                            break

    except Exception as e:
        print(f"Error reading XML: {e}")


def show_readme_info():
    """Show README information."""
    print("\n" + "="*70)
    print("UNIREF README INFORMATION")
    print("="*70)

    readme_file = "README"

    if not os.path.exists(readme_file):
        print(f"\nREADME file not found.")
        return

    print(f"\nKey information from README:\n")

    with open(readme_file) as f:
        content = f.read()

        # Extract key sections
        in_key_section = False
        for line in content.split('\n'):
            # Show header
            if 'UniProt Reference Clusters (UniRef)' in line:
                in_key_section = True
                print(line)
            elif in_key_section and ('=' * 10 in line or line.strip() == ''):
                if '=' * 10 in line:
                    in_key_section = False
                print(line)
            elif in_key_section:
                print(line)
                if 'hiding redundant sequences' in line:
                    print()
                    break


def example_parsing_code():
    """Show example code for parsing UniRef FASTA."""
    print("\n" + "="*70)
    print("EXAMPLE: Parsing UniRef FASTA with Python")
    print("="*70)

    code = '''
# Example code to parse UniRef FASTA files:

def parse_uniref_fasta(filepath):
    """Parse UniRef FASTA file."""
    import gzip

    opener = gzip.open if filepath.endswith('.gz') else open
    mode = 'rt' if filepath.endswith('.gz') else 'r'

    with opener(filepath, mode) as f:
        header = None
        sequence = []

        for line in f:
            line = line.strip()
            if line.startswith('>'):
                if header:
                    # Parse header
                    parts = header[1:].split()
                    cluster_id = parts[0]

                    # Extract n= value
                    n_members = None
                    for part in parts:
                        if part.startswith('n='):
                            n_members = int(part[2:])

                    yield {
                        'cluster_id': cluster_id,
                        'header': header,
                        'members': n_members,
                        'sequence': ''.join(sequence)
                    }
                header = line
                sequence = []
            else:
                sequence.append(line)

        if header:
            parts = header[1:].split()
            cluster_id = parts[0]
            n_members = None
            for part in parts:
                if part.startswith('n='):
                    n_members = int(part[2:])

            yield {
                'cluster_id': cluster_id,
                'header': header,
                'members': n_members,
                'sequence': ''.join(sequence)
            }

# Usage:
for cluster in parse_uniref_fasta("uniref90.fasta.gz"):
    print(f"{cluster['cluster_id']}: {len(cluster['sequence'])} aa, "
          f"{cluster['members']} members")
'''

    print(code)


if __name__ == "__main__":
    print("UniRef Cluster Data Explorer")
    print("=" * 70)

    os.chdir(Path(__file__).parent)

    describe_uniref_format()
    show_uniref_stats()
    show_readme_info()
    show_sample_fasta_data()
    show_sample_xml_data()
    example_parsing_code()

    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    print("\nFull UniRef archive (~254GB) contains:")
    print("  - uniref50.fasta.gz, uniref50.xml.gz, uniref50.rdf.gz")
    print("  - uniref90.fasta.gz, uniref90.xml.gz, uniref90.rdf.gz")
    print("  - uniref100.fasta.gz, uniref100.xml.gz, uniref100.rdf.gz")
    print("\nUse these clusters to:")
    print("  - Speed up sequence similarity searches")
    print("  - Reduce redundancy in large-scale analyses")
    print("  - Get representative sequences for each cluster")
    print("="*70)

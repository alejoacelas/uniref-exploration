#!/usr/bin/env python3
"""
Generate a larger test XML file by replicating the sample entries.
This creates a realistic test file with proper structure for benchmarking.
"""

import gzip
import re
import sys

def generate_test_xml(input_file, output_file, target_entries=1000):
    """Generate test XML by replicating and modifying entries."""

    print(f"Generating test XML with {target_entries:,} entries...")
    print(f"Input: {input_file}")
    print(f"Output: {output_file}")

    # Read the sample XML
    with open(input_file, 'r', encoding='ISO-8859-1') as f:
        content = f.read()

    # Extract header (everything before first <entry>)
    header_match = re.search(r'^(.*?)<entry', content, re.DOTALL)
    if not header_match:
        print("ERROR: Could not find header")
        sys.exit(1)
    header = header_match.group(1)

    # Extract all entries
    entry_pattern = r'<entry.*?</entry>'
    entries = re.findall(entry_pattern, content, re.DOTALL)

    print(f"Found {len(entries)} entries in sample")

    if not entries:
        print("ERROR: No entries found")
        sys.exit(1)

    # Open output file (compressed)
    with gzip.open(output_file, 'wt', encoding='ISO-8859-1') as out:
        # Write header
        out.write(header)

        # Generate entries by cycling through the sample
        for i in range(target_entries):
            base_entry = entries[i % len(entries)]

            # Modify IDs to be unique
            # Replace UniRef100_XXXXXX with UniRef100_TEST000000001, etc.
            modified = base_entry

            # Find and replace the entry ID
            id_match = re.search(r'id="(UniRef\d+_\w+)"', base_entry)
            if id_match:
                old_id = id_match.group(1)
                # Create new ID with test prefix and number
                new_id = f"UniRef50_TEST{i:09d}"
                modified = modified.replace(old_id, new_id)

            # Also update any references to accessions
            # Replace accessions like Q6GZX4 with TEST0000001, etc.
            acc_matches = re.findall(r'value="([A-Z0-9]{6,10})"', base_entry)
            for j, acc in enumerate(set(acc_matches)):
                if acc.startswith('UniRef') or acc.startswith('UPI'):
                    continue  # Skip UniRef/UniParc IDs
                new_acc = f"TEST{i:07d}_{j}"
                modified = modified.replace(f'value="{acc}"', f'value="{new_acc}"')

            out.write(modified)
            out.write('\n')

            if (i + 1) % 100 == 0:
                print(f"  Generated {i+1:,} entries...", end='\r')

        # Write footer
        out.write('</UniRef100>\n')

    print(f"\n✓ Generated {target_entries:,} entries")

    # Check file size
    import os
    size_mb = os.path.getsize(output_file) / (1024 * 1024)
    print(f"  Output file size: {size_mb:.2f} MB")


if __name__ == "__main__":
    input_file = "uniref_detailed_sample.xml"
    output_file = "test_sample_1000.xml.gz"
    target = 1000

    if len(sys.argv) > 1:
        target = int(sys.argv[1])

    generate_test_xml(input_file, output_file, target)

#!/usr/bin/env python3
"""
Benchmark original vs optimized implementations.
"""

import os
import sys
import time
import subprocess
import shutil
from pathlib import Path

def run_script(script_name, xml_file, db_file, description):
    """Run a script and measure performance."""
    print(f"\n{'='*80}")
    print(f"TESTING: {description}")
    print(f"{'='*80}")
    print(f"Script: {script_name}")
    print(f"Input: {xml_file}")
    print(f"Output: {db_file}")

    # Clean up previous database
    if os.path.exists(db_file):
        os.remove(db_file)
        print(f"Removed previous database: {db_file}")

    # Remove checkpoint files
    for checkpoint in ['parsing_checkpoint.txt', 'parsing_checkpoint_optimized.json']:
        if os.path.exists(checkpoint):
            os.remove(checkpoint)

    # Run the script
    start_time = time.time()

    try:
        # Modify the script temporarily to use our XML file
        result = subprocess.run(
            [sys.executable, script_name, xml_file],
            capture_output=True,
            text=True,
            timeout=300
        )

        elapsed_time = time.time() - start_time

        if result.returncode == 0:
            print(f"\n✓ SUCCESS in {elapsed_time:.2f} seconds")

            # Get database size
            if os.path.exists(db_file):
                db_size = os.path.getsize(db_file) / (1024 * 1024)  # MB
                print(f"  Database size: {db_size:.2f} MB")

                # Get entry count
                import sqlite3
                conn = sqlite3.connect(db_file)
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM cluster_mappings")
                count = cursor.fetchone()[0]
                conn.close()
                print(f"  Entries: {count:,}")
                print(f"  Rate: {count/elapsed_time:.1f} entries/second")

                return {
                    'success': True,
                    'time': elapsed_time,
                    'entries': count,
                    'rate': count / elapsed_time,
                    'db_size_mb': db_size
                }
            else:
                print(f"✗ Database file not created")
                return {'success': False}

        else:
            print(f"\n✗ FAILED with exit code {result.returncode}")
            print("STDOUT:", result.stdout[-500:])
            print("STDERR:", result.stderr[-500:])
            return {'success': False}

    except subprocess.TimeoutExpired:
        print(f"\n✗ TIMEOUT after 5 minutes")
        return {'success': False}

    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        return {'success': False}


def create_modified_original_script(xml_file):
    """Create a modified version of the original script that accepts CLI args."""
    # Read original
    with open('build_cluster_mappings.py', 'r') as f:
        content = f.read()

    # Add CLI arg support at the end, before main()
    modified = content.replace(
        'if __name__ == "__main__":\n    main()',
        '''if __name__ == "__main__":
    # Support test mode with custom XML file
    if len(sys.argv) > 1:
        XML_FILE = sys.argv[1]
        DB_FILE = XML_FILE.replace('.xml.gz', '_mappings_original.db').replace('.xml', '_mappings_original.db')
        print(f"TEST MODE: Using {XML_FILE}")
    main()'''
    )

    # Write modified version
    with open('build_cluster_mappings_test.py', 'w') as f:
        f.write(modified)

    return 'build_cluster_mappings_test.py'


def main():
    """Run benchmarks."""
    print(f"\n{'='*80}")
    print(f"BENCHMARKING: ORIGINAL VS OPTIMIZED")
    print(f"{'='*80}")

    # Use the test XML file
    xml_file = "test_sample_1000.xml.gz"

    if not os.path.exists(xml_file):
        print(f"ERROR: Test file not found: {xml_file}")
        print("Run: python generate_test_xml.py 10000")
        sys.exit(1)

    # Get file info
    xml_size_mb = os.path.getsize(xml_file) / (1024 * 1024)
    print(f"\nTest file: {xml_file}")
    print(f"Size: {xml_size_mb:.2f} MB")

    # Create modified original script
    print("\nPreparing original script for testing...")
    original_script = create_modified_original_script(xml_file)

    results = {}

    # Test 1: Original implementation
    original_db = xml_file.replace('.xml.gz', '_mappings_original.db')
    results['original'] = run_script(
        original_script,
        xml_file,
        original_db,
        "ORIGINAL IMPLEMENTATION"
    )

    # Test 2: Optimized implementation
    optimized_db = xml_file.replace('.xml.gz', '_mappings.db')
    results['optimized'] = run_script(
        'build_cluster_mappings_optimized.py',
        xml_file,
        optimized_db,
        "OPTIMIZED IMPLEMENTATION"
    )

    # Compare results
    print(f"\n{'='*80}")
    print(f"BENCHMARK RESULTS")
    print(f"{'='*80}")

    if results['original']['success'] and results['optimized']['success']:
        orig = results['original']
        opt = results['optimized']

        print(f"\nTest file: {xml_file} ({xml_size_mb:.2f} MB)")
        print(f"\n{'Metric':<30} {'Original':<20} {'Optimized':<20} {'Speedup':<15}")
        print("-" * 85)

        print(f"{'Time (seconds)':<30} {orig['time']:>18.2f}  {opt['time']:>18.2f}  {orig['time']/opt['time']:>13.2f}x")
        print(f"{'Entries processed':<30} {orig['entries']:>18,}  {opt['entries']:>18,}  {'':>13}")
        print(f"{'Processing rate (entries/s)':<30} {orig['rate']:>18.1f}  {opt['rate']:>18.1f}  {opt['rate']/orig['rate']:>13.2f}x")
        print(f"{'Database size (MB)':<30} {orig['db_size_mb']:>18.2f}  {opt['db_size_mb']:>18.2f}  {orig['db_size_mb']/opt['db_size_mb']:>13.2f}x")

        print(f"\n{'='*80}")
        print(f"OPTIMIZATIONS SUMMARY")
        print(f"{'='*80}")

        speedup = orig['time'] / opt['time']
        rate_improvement = opt['rate'] / orig['rate']
        size_improvement = orig['db_size_mb'] / opt['db_size_mb']

        print(f"\n✓ Overall speedup: {speedup:.2f}x faster")
        print(f"✓ Throughput improvement: {rate_improvement:.2f}x higher")
        print(f"✓ Database size: {size_improvement:.2f}x {'smaller' if size_improvement > 1 else 'larger'}")

        print(f"\nOptimizations applied:")
        print(f"  • WITHOUT ROWID table design")
        print(f"  • 64KB page size (vs 4KB default)")
        print(f"  • Bulk inserts: 5M rows/transaction (vs 100K)")
        print(f"  • INSERT OR IGNORE (no per-entry SELECT)")
        print(f"  • Optimized SQLite PRAGMAs")
        print(f"  • Single-pass XPath parsing")
        print(f"  • Producer-consumer pipeline")
        print(f"  • Parallel decompression (pigz)")

        # Extrapolate to full dataset
        print(f"\n{'='*80}")
        print(f"EXTRAPOLATION TO FULL DATASET")
        print(f"{'='*80}")

        # Assume 70M entries, 150GB compressed XML
        full_entries = 70_000_000
        full_xml_gb = 150

        # Estimate based on test performance
        orig_full_hours = (full_entries / orig['rate']) / 3600
        opt_full_hours = (full_entries / opt['rate']) / 3600

        print(f"\nAssuming full UniRef50 dataset:")
        print(f"  • ~70 million entries")
        print(f"  • ~150 GB compressed XML")
        print(f"\nEstimated processing time:")
        print(f"  • Original: {orig_full_hours:.1f} hours")
        print(f"  • Optimized: {opt_full_hours:.1f} hours")
        print(f"  • Time saved: {orig_full_hours - opt_full_hours:.1f} hours")

    else:
        print("\n⚠ Could not compare - one or both runs failed")
        if not results['original']['success']:
            print("  ✗ Original implementation failed")
        if not results['optimized']['success']:
            print("  ✗ Optimized implementation failed")

    # Clean up
    if os.path.exists(original_script):
        os.remove(original_script)


if __name__ == "__main__":
    main()

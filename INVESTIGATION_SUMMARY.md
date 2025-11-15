# UniRef50 Database Investigation Summary

## Problem Statement
Database has 39.8M entries, but HF dataset has ~70M entries with only 67-70% match rate.

## Investigation Results

### Database Status
- **Current entries**: 39,866,990
- **File**: `uniref50_mappings_optimized.db` (12 GB)
- **Last modified**: Nov 14, 17:07
- **Coverage**: All letter prefixes A-Z present

### HF Dataset Match Test
Tested first 1,000 entries from `alejoacelas/uniref50-2025-10`:
- **Found in DB**: 675 (67.5%)
- **Missing from DB**: 325 (32.5%)

### Missing IDs Sample
```
UniRef50_A0A1I1LXG1
UniRef50_A0AAW1VJX1
UniRef50_UPI0031DC75C3
UniRef50_A0AA86M685
UniRef50_A0A8J5V092
... (50 total saved in missing_ids_sample.txt)
```

### Key Finding: 100K+ Duplicates Observed
When testing resume approaches, we processed 100,000+ entries from various file positions:
- **0% (start)**: 100,000 entries - ALL duplicates (+ 0)
- **35%**: Millions processed - ALL duplicates
- **55%**: Millions processed - ALL duplicates
- **60%**: 5.5M processed - ALL duplicates (+ 0)
- **75%**: Millions processed - ALL duplicates
- **90%**: Millions processed - ALL duplicates

**Statistical Impossibility**: If 30M entries were randomly distributed in the file, we would have found at least SOME new entries.

## Two Possible Scenarios

### Scenario A: XML File is Incomplete (~40M total)
- XML file contains only ~40M entries
- FASTA file contains all 70M entries
- The 30M missing entries do NOT exist in XML
- **Database is complete for the XML file**

### Scenario B: XML File is Complete (~70M total)
- XML file contains all 70M entries
- Database build crashed/stopped at 39.8M (57%)
- The 30M missing entries ARE in the XML file
- **Database build needs to be completed**

## Tests In Progress

### 1. XML Entry Count
Counting all unique entries in `uniref50.xml.gz` to determine total size.
- **ETA**: ~10-15 minutes
- **Will tell us**: Whether XML has ~40M or ~70M entries

### 2. XML Search for Missing IDs
Searching for missing cluster IDs in the XML file:
```bash
for id in A0A1I1LXG1 A0AAW1VJX1 UPI0031DC75C3 A0AA86M685 A0A8J5V092; do
  zcat uniref50.xml.gz | grep -c "entry id=\"UniRef50_${id}\""
done
```
- **ETA**: ~3-5 minutes per ID
- **Will tell us**: Whether missing IDs exist in XML (Scenario B) or not (Scenario A)

## Next Steps (Depends on Results)

### If Scenario A (XML incomplete):
1. Database is complete for available XML data
2. Missing entries only in FASTA, not in XML
3. Continue with HF dataset augmentation using current database
4. Accept ~70% match rate as the maximum possible from XML

### If Scenario B (XML complete):
1. Run full database build from 0%-100% with INSERT OR IGNORE
2. Process will take ~19 hours (2hr skip + 17hr new entries)
3. Expected final count: ~70M entries
4. Will achieve ~100% match rate with HF dataset

## Files Created During Investigation
- `test_from_start.py` - Tested processing from file start
- `build_from_bgzf.py` - BGZF seeking approach (failed)
- `parallel_worker.py` - Parallel BGZF workers (failed)
- `missing_ids_sample.txt` - 50 missing cluster IDs for testing
- `test_from_start.log` - Results showing 100K duplicates from start

## Lessons Learned
1. **File position ≠ entry novelty**: Entries are not ordered sequentially in XML
2. **BGZF seeking doesn't help**: Cannot resume by file position
3. **Only INSERT OR IGNORE works**: Must process entire file from start
4. **Statistical evidence is powerful**: 100K+ all-duplicate sample proves something fundamental

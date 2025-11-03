# Example Files Overview

This folder contains representative files demonstrating UniProt data structure and linkages.

## Files Included

### UniRef Cluster Data
1. **README** (7.1 KB)
   - Official UniRef documentation
   - Explains CD-HIT clustering algorithm
   - Documents representative selection criteria
   - Describes FASTA and XML formats

2. **uniref100.release_note** (312 bytes)
   - Release: 2025_03, 18-Jun-2025
   - Number of clusters: 465,330,530
   - License information

3. **uniref100_sample.fasta** (1.4 KB)
   - 3 sample clusters in FASTA format
   - Shows header format: `>UniRef100_Q6GZX4 Protein n=4 Tax=Ranavirus TaxID=10492 RepID=001R_FRG3G`
   - Contains complete sequences

4. **uniref_detailed_sample.xml** (8.3 KB)
   - 4 complete clusters in XML format
   - Shows all metadata fields: member lists, taxonomy, cross-references
   - Demonstrates UniParc IDs and UniRef90/50 linkage

### Taxonomic Information
5. **speindex.txt** (16 MB)
   - Complete species index for all organisms
   - Maps: organism names → Swiss-Prot entry names → accessions
   - Covers thousands of species from viruses to mammals
   - Example: `Abies grandis` → `TPSD1_ABIGR` → `O81086`

6. **humchr01.txt** (368 KB)
   - Human chromosome 1 proteins (2,066 entries)
   - Maps: gene names → chromosomal positions → Swiss-Prot accessions → MIM codes
   - Example: `ABCA4` at `1p21-p22.1` → P78363 → MIM 601691

7. **arath.txt** (2.3 MB)
   - *Arabidopsis thaliana* proteins
   - Maps: chromosome locus → gene names → Swiss-Prot accessions
   - Example: `At1g01040` → DCL1 → Q9SP32

### Controlled Vocabularies
8. **keywlist.txt** (644 KB)
   - Protein function keywords
   - 10 categories: Biological process, Cellular component, Disease, Domain, etc.
   - Example: `KW-0002` = "3D-structure"

9. **humdisease.txt** (4.4 MB)
   - Human disease associations
   - Maps: disease names → accessions → MIM codes
   - Example: `DI-04240` = "2,4-dienoyl-CoA reductase deficiency" → MIM 616034

## Quick Examination Commands

```bash
# View UniRef cluster structure
head -5 uniref100_sample.fasta

# See XML metadata
head -50 uniref_detailed_sample.xml

# Browse human genes on chromosome 1
grep "ABCA4" humchr01.txt

# Look up a species
grep "Arabidopsis" speindex.txt | head -5

# Find a keyword
grep "^ID   3D-structure" keywlist.txt -A 10

# Search for a disease
grep "DECRD" humdisease.txt -A 10
```

## Key Linkages Demonstrated

```
UniRef Entry (uniref100_sample.fasta)
    ↓ UniProtKB accession: Q6GZX4
    ↓
Knowledgebase Entry (not included - 186GB full archive)
    ↓ Contains gene name, organism, keywords, diseases
    ↓
Organism-specific file (humchr01.txt or arath.txt)
    ↓ Maps to chromosomal location
    ↓
External databases (MIM, FlyBase, TAIR)
```

All vocabularies (keywords, diseases) use controlled IDs that can be looked up in keywlist.txt or humdisease.txt.

## File Sizes Summary
- Total: ~24 MB
- Largest: speindex.txt (16 MB) - can search with `grep`
- Smallest: uniref100.release_note (312 bytes) - quick statistics

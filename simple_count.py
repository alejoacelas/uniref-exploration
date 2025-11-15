#!/usr/bin/env python3
import gzip
import sys
from lxml import etree as ET

xml_file = "uniref50.xml.bgz"
log_file = "count_progress.log"

with open(log_file, 'w', buffering=1) as log:
    log.write("Starting XML entry count...\n")
    log.flush()

    stream = gzip.open(xml_file, 'rb')
    count = 0

    try:
        context = ET.iterparse(stream, events=('end',), tag='{http://uniprot.org/uniref}entry')

        for event, elem in context:
            count += 1

            if count % 1000000 == 0:
                log.write(f"Progress: {count:,} entries\n")
                log.flush()
                sys.stdout.write(f"Progress: {count:,} entries\n")
                sys.stdout.flush()

            elem.clear()
            while elem.getprevious() is not None:
                del elem.getparent()[0]

        log.write(f"\nFINAL COUNT: {count:,} entries\n")
        log.flush()
        print(f"\nFINAL COUNT: {count:,} entries")

    except Exception as e:
        log.write(f"\nERROR: {e}\n")
        raise
    finally:
        stream.close()

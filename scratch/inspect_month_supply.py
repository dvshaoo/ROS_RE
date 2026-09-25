import sys

sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, 'tools')
import load_table as tables

for signature in (0x5c64e12a, 0x462e4a27):
    records = tables.load(signature)
    print(hex(signature), 'records=', len(records))
    for record_id, record in sorted(records.items()):
        print(record_id, record.get('value', {}))

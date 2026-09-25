import sys

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, 'tools')
import load_table as tables

records = tables.load(0x9e1c8652)
for supplement_id, record in sorted(records.items()):
    value = record.get('value', {})
    kind = value.get('KIND', 1)
    if kind not in (3, 7):
        continue
    currency = (value.get('CURRENCY_OPTION') or {}).get('value', {})
    print('id=%s kind=%s name=%r currency=%r list=%d guarantee=%d' % (
        supplement_id, kind, value.get('NAME'), currency,
        len(value.get('SUPPLEMENT_LIST') or []), len(value.get('GUARANTEE_LIST') or [])))

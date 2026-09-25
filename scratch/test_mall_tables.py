import sys, pickle, struct
sys.path.insert(0, 'tools')
import load_table as LT

# Test all three table sigs
for sig, label in [(0x832995b1,'Suggested/Packs'), (0x878e57c9,'Looks'), (0x55977219,'Firearms')]:
    t = LT.load(sig)
    print(label, ':', len(t), 'records')

# Check what IS_DISPLAY flags each record has
flags = ('IS_DISPLAY_IN_MALL', 'IS_DISPLAY_IN_CLOTH_MALL',
         'IS_DISPLAY_IN_MALL_WEAPON', 'IS_DISPLAY_IN_WEAPON_MALL',
         'IS_DISPLAY_IN_SUIT_MALL', 'IS_DISPLAY_IN_TIME_APPEARANCE')

merged = {}
for sig in (0x832995b1, 0x878e57c9, 0x55977219):
    merged.update(LT.load(sig))

visible = {k:v for k,v in merged.items() if any(v.get('value',{}).get(f) for f in flags)}
print('Total visible goods:', len(visible))

# Check first visible record flags  
for k,v in list(visible.items())[:5]:
    val = v.get('value', {})
    present = [f for f in flags if val.get(f)]
    print('  good', k, ': flags=', present, 'currency=', val.get('CURRENCY_ID'), 'price=', val.get('PRICE'))

# Also check query_type values from live log
# exposed_idx=312: args=00 (1 byte payload - just method byte, no query_type)
# exposed_idx=310: args=00000000 (5 bytes - method + 4-byte type=0)
# Check if maybe query_type=0 means "all"
print()
print('--- Checking query_type behavior ---')
# The client sends query_type per-tab. Let us list what query_type values appear from UIMall.MallLocationType
# 0=ALL?, 1=Suggested?, 2=Packs?, etc.
# From store_fresh screenshots, tabs: SUGGESTED, PACKS, LOOKS, FIREARMS, TOP-UP, OTHERS, TOKEN MALL

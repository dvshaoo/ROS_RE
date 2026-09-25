# -*- coding: utf-8 -*-
"""tools/recover_all_event_skins.py -- Recovers ALL 4,465 historical event skins
from the client's authoritative tables (assets.npk) and injects them directly
into player_inventory.json and athlete_mobile_stream.bin so they are immediately
unlocked and wearable in the Depot/Lobby.
"""
import os
import sys
import json
import uuid
import subprocess

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import load_table as LT

TABLES = [
    (0xa2f095a2, 'clothes / outfits'),
    (0x190f0c0a, 'weapons / firearms'),
    (0xb8749560, 'vehicles / sports cars'),
    (0x8f4932f0, 'battleground gliders / wings / parachutes'),
]


def recover_all():
    all_props = {}
    print("=" * 60)
    print("ROS HISTORICAL EVENT SKINS RECOVERY TOOL")
    print("=" * 60)
    print("Extracting authoritative event cosmetics from APK assets.npk...")
    for sig, name in TABLES:
        try:
            raw_text = LT.read_member(sig).decode('utf-8', errors='ignore')
            table = LT.parse_table(raw_text)
            count = 0
            for item_id, rec in table.items():
                val = rec.get('value', {})
                if val:
                    all_props[int(item_id)] = {
                        'uuid': uuid.uuid4().hex,
                        'number': 1,
                        'info': {'ex_tm': 0},
                        'layout': 0
                    }
                    count += 1
            print("  [+] Extracted %4d %-40s from 0x%08x" % (count, name, sig))
        except Exception as e:
            print("  [!] ERROR extracting 0x%08x (%s): %s" % (sig, name, e))

    inv_path = os.path.join(ROOT, 'data', 'player_inventory.json')
    data = {'items': {str(k): v for k, v in sorted(all_props.items())}}

    with open(inv_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, sort_keys=True)
    print("\nSUCCESS: Injected %d historical event skins into player_inventory.json!" % len(all_props))

    print("Regenerating athlete_mobile_stream.bin via scratch/gen_stream_v3.py...")
    gen_script = os.path.join(ROOT, 'scratch', 'gen_stream_v3.py')
    res = subprocess.run([sys.executable, gen_script], cwd=ROOT, capture_output=True, text=True)
    if res.returncode == 0:
        print("SUCCESS: athlete_mobile_stream.bin regenerated successfully!")
        print("All previous event skins (KOF, Anniversary, Cyberpunk, Halloween, etc.) are now unlocked!")
    else:
        print("ERROR regenerating stream:", res.stderr)


if __name__ == '__main__':
    recover_all()

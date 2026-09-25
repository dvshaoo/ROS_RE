# -*- coding: utf-8 -*-
"""Find Fits of Fury / monthly appearance themes across assets.npk members."""
import hashlib
import sys

sys.path.insert(0, r'C:\Users\Raysoo\Downloads\ROS_RE\tools')
from load_table import members

NEEDLES = [
    'Fits of Fury', 'Fits Of Fury', 'FITS OF FURY', 'FitsOfFury', 'fits_of_fury',
    'Fury', 'fury',
    '狂怒', '怒焰', '烈焰狂怒', '劲爽狂怒',
]
HASHES = [
    hashlib.md5(s.encode()).hexdigest() for s in (
        'Fits of Fury', 'fits of fury', 'Fits Of Fury', 'FITS OF FURY',
        'FitsOfFury', 'Fury', '狂怒', '狂怒套装', '怒焰',
    )
]


def main():
    for sig, raw in members():
        text = raw.decode('utf-8', 'ignore')
        hits = []
        for n in NEEDLES:
            if n in text:
                hits.append(n)
        for h in HASHES:
            if h in text:
                hits.append('md5:' + h)
        if hits:
            print('HIT', hex(sig), hits[:8], 'len', len(raw))
            # context for Fury
            if 'Fury' in text or '狂怒' in text:
                i = text.find('Fury')
                if i < 0:
                    i = text.find('狂怒')
                print('  ctx', repr(text[max(0, i - 80):i + 100])[:220])


if __name__ == '__main__':
    main()

"""usage: python tools/script_query.py <file-substring> [name-regex]   -- names/consts of matching scripts from scratch/script_index.txt"""
import sys, re, collections
sub = sys.argv[1].lower(); rx = re.compile(sys.argv[2], re.I) if len(sys.argv) > 2 else None
d = collections.defaultdict(list)
for line in open(r'C:\Users\Raysoo\Downloads\ROS_RE\scratch\script_index.txt', encoding='utf-8'):
    f, _, n = line.rstrip('\n').partition(' :: ')
    if sub in f.lower() and (rx is None or rx.search(n)):
        d[f].append(n)
for f, ns in d.items():
    print('==', f, len(ns)); print('  ' + ' | '.join(ns)[:3000])

"""Index every module in the mobile script.npk: file name -> all string constants / names, for grepping the client's
Python UI code without source. Output: scratch/script_index.txt  (one 'FILE :: name-or-const' per line).
Uses ros_script_decrypt from the legacy tools directory."""
import sys, struct, os
sys.path.insert(0, r'c:\Users\Raysoo\Downloads\RulesOfSurvivalOld (2)\RulesOfSurvivalOld\tools\re')
import ros_script_decrypt as RS

DATA = open(r'C:\Users\Raysoo\Downloads\ROS_RE\04_obb\extracted\script.npk', 'rb').read()
CNT = struct.unpack_from('<I', DATA, 4)[0]
IO = struct.unpack_from('<I', DATA, 0x14)[0]


def iter_modules():
    for i in range(CNT):
        sig, off, ln, _ = struct.unpack_from('<IIII', DATA, IO + i * 28)
        raw = DATA[off:off + ln]
        if raw[:2] != b'\x7a\x1c':
            continue
        try:
            co = RS.P(RS.member_marshal(raw)).load()
        except Exception:
            continue
        yield sig, co


def walk(co, out):
    if not isinstance(co, dict):
        return
    for k in ('names', 'consts', 'varnames'):
        seq = co.get(k, [])
        if not isinstance(seq, (list, tuple)):
            continue
        for v in seq:
            if isinstance(v, bytes):
                out.add(v.decode('latin1', 'replace'))
            elif isinstance(v, str):
                out.add(v)
            elif isinstance(v, dict) and 'code' in v:
                walk(v, out)


if __name__ == '__main__':
    with open(r'C:\Users\Raysoo\Downloads\ROS_RE\scratch\script_index.txt', 'w', encoding='utf-8') as f:
        n = 0
        for sig, co in iter_modules():
            fn = co.get('file')
            fn = fn.decode('latin1', 'ignore') if isinstance(fn, bytes) else str(fn)
            s = set(); walk(co, s)
            for x in sorted(s):
                f.write('%s :: %s\n' % (fn, x.replace('\n', '\n')))
            n += 1
    print('modules indexed:', n)

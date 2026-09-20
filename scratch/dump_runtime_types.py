"""Read the COMPLETE runtime DataType tree of Athlete's 832 properties from live memory.

Structure facts (from decompiled SequenceDataType::createFromStream, FUN_00aa4b14):
  ARRAY DataType   +0x28 -> element DataType*      +0x30 -> int32 FIXED size (0 = read a
                    4-byte count from the wire; >0 = NO count on the wire, exactly N elements)
  FIXED_DICT       +0x20 -> begin, +0x28 -> end of a vector of 40-byte field records:
                    [std::string name (24 B)][DataType* (8 B)][8 B misc]

Class names come from RTTI (vtable[-1] -> typeinfo -> mangled name), so no vtable addresses
are hard-coded and the result survives a different load base.
"""
import json, os, struct, subprocess, sys

ADB = [r'C:\Users\Raysoo\AppData\Local\Android\Sdk\platform-tools\adb.exe', '-s', 'emulator-5554']
ROOT = r'C:\Users\Raysoo\Downloads\ROS_RE'
CHUNK = 64 * 1024
_cache = {}


def sh(cmd, binary=False, t=40):
    r = subprocess.run(ADB + ['exec-out', cmd], capture_output=True, timeout=t)
    return r.stdout if binary else r.stdout.decode(errors='replace')


def pid_of():
    return sh('pidof com.netease.chiji').strip().split()[0]


PID = None


def dd_b64(skip, bs, count):
    """Binary-safe memory read. `adb exec-out` cannot be used: this adbd/su combination turns every
    0x0A byte into 0x0D 0x0A (a 4096-byte page came back as 4169 bytes), shifting all later data.
    Round-tripping through base64 keeps the payload text-only, so line-ending translation is harmless."""
    import base64
    cmd = f"su 0 sh -c 'dd if=/proc/{PID}/mem bs={bs} skip={skip} count={count} 2>/dev/null | base64'"
    r = subprocess.run(ADB + ['shell', cmd], capture_output=True, timeout=60)
    txt = b''.join(r.stdout.split())
    try:
        return base64.b64decode(txt + b'=' * (-len(txt) % 4))
    except Exception:
        return b''


def chunk(ci):
    if ci not in _cache:
        data = dd_b64(ci, CHUNK, 1)
        if len(data) < CHUNK:
            # short read = part of the window is unmapped; /proc/pid/mem stops at the first fault,
            # so re-read page by page and zero-fill only the unreadable pages
            data = b''
            for pnum in range(CHUNK // 4096):
                pg = dd_b64(ci * (CHUNK // 4096) + pnum, 4096, 1)
                data += pg.ljust(4096, bytes(1))[:4096]
        _cache[ci] = data[:CHUNK]
    return _cache[ci]


def rd(addr, n):
    out = b''
    while n > 0:
        ci, off = divmod(addr, CHUNK)
        piece = chunk(ci)[off:off + n]
        if not piece:
            break
        out += piece
        addr += len(piece)
        n -= len(piece)
    return out


def u64(b, o):
    return struct.unpack_from('<Q', b, o)[0]


def i32(b, o):
    return struct.unpack_from('<i', b, o)[0]


def heap_ptr(v):
    return 0x700000000000 <= v < 0x800000000000


def cstr(addr, limit=160):
    b = rd(addr, limit)
    return b.split(b'\0', 1)[0].decode('latin1')


_cls = {}


def class_name(vt):
    if vt not in _cls:
        try:
            ti = u64(rd(vt - 8, 8), 0)
            nm = u64(rd(ti + 8, 8), 0)
            _cls[vt] = cstr(nm)
        except Exception:
            _cls[vt] = '?'
    return _cls[vt]


def sso(b, o):
    b0 = b[o]
    if b0 & 1 == 0:
        return b[o + 1:o + 1 + (b0 >> 1)].decode('latin1', 'ignore')
    ln, ptr = struct.unpack_from('<QQ', b, o + 8)
    return rd(ptr, min(ln, 200)).decode('latin1', 'ignore') if heap_ptr(ptr) else '?'


def short(cls):
    """Mangled RTTI name -> a compact readable label."""
    import re
    parts = re.findall(r'\d+([A-Za-z_]+)', cls)
    tail = [p for p in parts if p not in ('neox', 'bwclient')]
    lab = tail[0] if tail else cls
    if 'IntegerDataType' in cls or 'FloatDataType' in cls:
        m = re.search(r'E([A-Za-z]+)E$', cls)
        m2 = re.search(r'IN?[0-9]*[a-z_]*([a-z]{1,2})E', cls)
        lab += '<%s>' % (cls[-4:-2] if cls.endswith('EE') else cls[-3:])
    return lab


_memo = {}


def read_dt(ptr, depth=0):
    if ptr in _memo:
        return {'ref': hex(ptr)}
    obj = rd(ptr, 0x120)
    cls = class_name(u64(obj, 0))
    node = {'ptr': hex(ptr), 'cls': cls}
    _memo[ptr] = node
    if depth > 6:
        return node
    if 'Sequence' in cls or 'Array' in cls:
        node['kind'] = 'ARRAY'
        node['fixed'] = i32(obj, 0x30)
        ep = u64(obj, 0x28)
        node['elem'] = read_dt(ep, depth + 1) if heap_ptr(ep) else None
    elif 'FixedDict' in cls:
        node['kind'] = 'FIXED_DICT'
        b, e = u64(obj, 0x20), u64(obj, 0x28)
        fields = []
        if heap_ptr(b) and b < e <= b + 40 * 400 and (e - b) % 40 == 0:
            rec = rd(b, e - b)
            for i in range((e - b) // 40):
                name = sso(rec, i * 40)
                dtp = u64(rec, i * 40 + 24)
                fields.append({'name': name, 'type': read_dt(dtp, depth + 1) if heap_ptr(dtp) else None})
        node['fields'] = fields
    return node


def main():
    global PID
    PID = pid_of()
    maps = sh(f"su 0 grep libclient.so /proc/{PID}/maps | head -1")
    base = int(maps.split('-')[0], 16)
    print(f'pid={PID} base=0x{base:x}')
    v = rd(base + 0x45785f0, 24)
    begin, end = u64(v, 0), u64(v, 8)
    n_types = (end - begin) // 8
    print('EntityType count:', n_types)
    if n_types < 60:
        print('EntityType table not populated yet -- log in first'); sys.exit(2)
    athlete = u64(rd(begin + 51 * 8, 8), 0)
    pb, pe = struct.unpack('<QQ', rd(athlete + 0x58, 16))
    total = (pe - pb) // 0x68
    raw = rd(pb, total * 0x68)
    print('athlete EntityType @ 0x%x  prop table 0x%x..0x%x' % (athlete, pb, pe))
    print('properties:', total)
    names = {}
    for line in open(os.path.join(ROOT, 'scratch', 'athlete_props_full.txt'), encoding='utf-8'):
        import re
        m = re.match(r'\[\s*(\d+)\] (.{52}) f@0x20=(\w+)', line)
        if m:
            names[int(m.group(1))] = (m.group(2).strip(), int(m.group(3)[:2], 16))
    out = []
    for i in range(total):
        dtp = u64(raw, i * 0x68 + 0x18)
        out.append({'idx': i, 'name': names.get(i, ('?', 0))[0], 'flag': names.get(i, ('?', 0))[1],
                    'type': read_dt(dtp)})
        if i % 100 == 0:
            print('  read', i, 'properties; page cache chunks:', len(_cache), flush=True)
    path = os.path.join(ROOT, 'scratch', 'athlete_runtime_types.json')
    json.dump(out, open(path, 'w'), indent=1)
    print('wrote', path)


if __name__ == '__main__':
    main()

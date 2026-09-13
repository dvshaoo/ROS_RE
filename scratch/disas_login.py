import sys, dis
sys.path.insert(0, 'C:/tools/re')
import ros_dump_module as R

with open('scratch/uilogin.raw', 'rb') as f:
    raw = f.read()

m = R.member_marshal(raw)
co = R.P(m).load()

uilogin = None
for c in co.consts:
    if hasattr(c, 'name') and c.name == b'UILogin':
        uilogin = c
        break

def dump_fn(name):
    for c in uilogin.consts:
        if hasattr(c, 'name') and c.name == name:
            print('=== ' + name.decode('latin1') + ' ===')
            print('names:', c.names)
            print('varnames:', c.varnames)
            print('consts:', [x for x in c.consts if not hasattr(x, 'code')])
            code_bytes = c.code
            i = 0
            while i < len(code_bytes):
                offset = i
                op = code_bytes[i]
                i += 1
                arg = None
                if op >= 90:
                    arg = code_bytes[i] | (code_bytes[i+1] << 8)
                    i += 2
                opname = dis.opname[op] if op < len(dis.opname) else str(op)
                extra = ''
                if op == 100 and arg < len(c.consts):
                    extra = repr(c.consts[arg])
                elif op in (101, 106, 108, 116) and arg < len(c.names):
                    extra = repr(c.names[arg])
                elif op in (124, 125, 126) and arg < len(c.varnames):
                    extra = repr(c.varnames[arg])
                elif op in (90, 95) and arg < len(c.names):
                    extra = repr(c.names[arg])
                print(f'{offset:4d} {opname:20s} {str(arg):5s} {extra}')

for fn in [b'onLoginBtnTouch', b'doLoginGame', b'startLogin', b'tryChannelLogin', b'getURS']:
    dump_fn(fn)

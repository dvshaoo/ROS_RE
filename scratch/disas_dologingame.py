import sys
sys.path.insert(0, 'C:/tools/re')
import ros_dump_module as R
import disas_one as D

with open('scratch/uilogin.raw', 'rb') as f:
    raw = f.read()

m = R.member_marshal(raw)
co = R.P(m).load()
objs = []
R.walk(co, R._name(co.name), objs)
for path, c in objs:
    name = R._name(c.name)
    if name in ['doLoginGame', 'startLogin', 'onLoginBtnTouch']:
        print('='*80)
        print(f'FUNCTION: {path} (firstline: {c.firstlineno}, argcount: {c.argcount})')
        print('Varnames:', R._names_list(c.varnames))
        print('Names:', R._names_list(c.names))
        print('Consts:', [R.s_disp(x) for x in c.consts or [] if not hasattr(x, 'code')])
        print('\nDisassembly:')
        try:
            D.disas(c)
        except Exception as e:
            print('Disas err:', e)

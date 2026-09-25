import sys, os, struct
sys.path.insert(0, r'c:\Users\Raysoo\Downloads\RulesOfSurvivalOld (2)\RulesOfSurvivalOld\tools\re')
import ros_script_decrypt as RS

# This client does NOT use the legacy neox-tools permutation previously copied
# here.  These anchors are verified against this build's code objects (for
# example, supplement_utils.getSupplementKind).  Keep unknowns explicit rather
# than silently assigning an opcode from a different NeoX build.
DEC = {
    10:21, 12:12, 23:25, 37:20, 43:68, 57:1, 63:24, 66:22, 67:23, 74:83, 77:54,
    90:90, 93:124, 96:106, 101:100, 104:125,
    110:115, 114:105, 125:93, 131:131, 135:102, 136:132, 137:113,
    143:100, 148:114, 149:92, 151:107, 155:116, 156:110,
    158:120, 132:110, 176:95,
    103:113, # JUMP_ABSOLUTE
    33:87,  # POP_BLOCK
    58:60,  # STORE_SUBSCR (SupplementID2BoxIndex[id] = n)
    32:2,   # ROT_TWO (tuple assign box1Used, box2Used = False, False in UISupplyPackage.onQueryAvailableSupplement)
}

# NeoX fused instruction: LOAD_CONST oparg; RETURN_VALUE.  Verified by the
# explicit and compiler-added implicit returns in getSupplementKind.
CUSTOM = {
    94: ('RETURN_CONST', True),
    # Fused LOAD_FAST varnames[oparg>>8] + LOAD_ATTR names[oparg&255].
    160: ('LOAD_FAST_ATTR', True),
}

STD = {0:'STOP_CODE',1:'POP_TOP',2:'ROT_TWO',3:'ROT_THREE',4:'DUP_TOP',5:'ROT_FOUR',9:'NOP',
10:'UNARY_POSITIVE',11:'UNARY_NEGATIVE',12:'UNARY_NOT',13:'UNARY_CONVERT',15:'UNARY_INVERT',
19:'BINARY_POWER',20:'BINARY_MULTIPLY',21:'BINARY_DIVIDE',22:'BINARY_MODULO',23:'BINARY_ADD',
24:'BINARY_SUBTRACT',25:'BINARY_SUBSCR',26:'BINARY_FLOOR_DIVIDE',27:'BINARY_TRUE_DIVIDE',
28:'INPLACE_FLOOR_DIVIDE',29:'INPLACE_TRUE_DIVIDE',30:'SLICE+0',31:'SLICE+1',32:'SLICE+2',
33:'SLICE+3',40:'STORE_SLICE+0',54:'STORE_MAP',55:'INPLACE_ADD',56:'INPLACE_SUBTRACT',
57:'INPLACE_MULTIPLY',59:'INPLACE_MODULO',60:'STORE_SUBSCR',61:'DELETE_SUBSCR',
62:'BINARY_LSHIFT',63:'BINARY_RSHIFT',64:'BINARY_AND',65:'BINARY_XOR',66:'BINARY_OR',
68:'GET_ITER',71:'PRINT_ITEM',72:'PRINT_NEWLINE',80:'BREAK_LOOP',81:'WITH_CLEANUP',
83:'RETURN_VALUE',84:'IMPORT_STAR',85:'EXEC_STMT',86:'YIELD_VALUE',87:'POP_BLOCK',
88:'END_FINALLY',89:'BUILD_CLASS',90:'STORE_NAME',91:'DELETE_NAME',92:'UNPACK_SEQUENCE',
93:'FOR_ITER',94:'LIST_APPEND',95:'STORE_ATTR',96:'DELETE_ATTR',97:'STORE_GLOBAL',
98:'DELETE_GLOBAL',99:'DUP_TOPX',100:'LOAD_CONST',101:'LOAD_NAME',102:'BUILD_TUPLE',
103:'BUILD_LIST',104:'BUILD_SET',105:'BUILD_MAP',106:'LOAD_ATTR',107:'COMPARE_OP',
108:'IMPORT_NAME',109:'IMPORT_FROM',110:'JUMP_FORWARD',111:'JUMP_IF_FALSE_OR_POP',
112:'JUMP_IF_TRUE_OR_POP',113:'JUMP_ABSOLUTE',114:'POP_JUMP_IF_FALSE',115:'POP_JUMP_IF_TRUE',
116:'LOAD_GLOBAL',119:'CONTINUE_LOOP',120:'SETUP_LOOP',121:'SETUP_EXCEPT',122:'SETUP_FINALLY',
124:'LOAD_FAST',125:'STORE_FAST',126:'DELETE_FAST',130:'RAISE_VARARGS',131:'CALL_FUNCTION',
132:'MAKE_FUNCTION',133:'BUILD_SLICE',134:'MAKE_CLOSURE',135:'LOAD_CLOSURE',136:'LOAD_DEREF',
137:'STORE_DEREF',140:'CALL_FUNCTION_VAR',141:'CALL_FUNCTION_KW',142:'CALL_FUNCTION_VAR_KW',
143:'SETUP_WITH',146:'SET_ADD',147:'MAP_ADD'}
HAVE_ARG = 90
cmp_op = ('<','<=','==','!=','>','>=','in','not in','is','is not','exc match','BAD')

def nm(b):
    try: return b.decode('latin1') if isinstance(b,bytes) else str(b)
    except: return repr(b)

def const_disp(c):
    if isinstance(c, dict) and 'name' in c: return '<code %s>' % nm(c['name'])
    if isinstance(c, bytes):
        try: return repr(c.decode('utf-8'))
        except: return repr(c)
    return repr(c)

def disas(co):
    code = co.get('code', b'')
    names = [nm(x) for x in (co.get('names') or [])]
    varnames = [nm(x) for x in (co.get('varnames') or [])]
    consts = list(co.get('consts') or [])
    free = [nm(x) for x in (co.get('freevars') or [])] + [nm(x) for x in (co.get('cellvars') or [])]
    print('--- %s (file=%s, argc=%d) ---' % (nm(co.get('name')), nm(co.get('file')), len(varnames)))
    print('VARNAMES:', varnames)
    print('NAMES:   ', names)
    i = 0; n = len(code)
    while i < n:
        neox = code[i]; off = i; i += 1
        if neox in CUSTOM:
            opn, has_arg = CUSTOM[neox]
            arg = code[i] | (code[i + 1] << 8); i += 2
            if opn == 'RETURN_CONST':
                extra = const_disp(consts[arg]) if arg < len(consts) else '?'
            elif opn == 'LOAD_FAST_ATTR':
                vi, ni = arg >> 8, arg & 0xff
                extra = '%s.%s' % (
                    varnames[vi] if vi < len(varnames) else '?',
                    names[ni] if ni < len(names) else '?')
            else:
                extra = str(arg)
            print('%4d  %-22s %d  (%s)' % (off, opn, arg, extra))
            continue
        std = DEC.get(neox)
        if std is None:
            # NeoX's unknown opcodes in this build are argument-bearing.  Show
            # the raw oparg and consume it so one unknown cannot desynchronise
            # the rest of the listing.
            if i + 1 < n:
                arg = code[i] | (code[i + 1] << 8); i += 2
                print('%4d  ??neox=%d arg=%d' % (off, neox, arg))
            else:
                print('%4d  ??neox=%d' % (off, neox))
            continue
        opn = STD.get(std, 'op%d' % std)
        if std < HAVE_ARG:
            print('%4d  %s' % (off, opn))
        else:
            arg = code[i] | (code[i+1] << 8); i += 2
            extra = ''
            if opn in ('LOAD_GLOBAL','LOAD_NAME','STORE_NAME','LOAD_ATTR','STORE_ATTR','IMPORT_NAME','IMPORT_FROM','STORE_GLOBAL'):
                extra = names[arg] if arg < len(names) else '?'
            elif opn in ('LOAD_FAST','STORE_FAST'):
                extra = varnames[arg] if arg < len(varnames) else '?'
            elif opn in ('LOAD_DEREF','STORE_DEREF','LOAD_CLOSURE'):
                extra = free[arg] if arg < len(free) else '?'
            elif opn == 'LOAD_CONST':
                extra = const_disp(consts[arg]) if arg < len(consts) else '?'
            elif opn == 'COMPARE_OP':
                extra = cmp_op[arg] if arg < len(cmp_op) else '?'
            elif opn == 'CALL_FUNCTION' or opn.startswith('CALL_FUNCTION_'):
                extra = 'pos=%d kw=%d' % (arg & 0xff, (arg >> 8) & 0xff)
            else:
                extra = str(arg)
            line_str = '%4d  %-22s %d  (%s)' % (off, opn, arg, extra)
            print(line_str.encode(sys.stdout.encoding or 'utf-8', errors='backslashreplace').decode(sys.stdout.encoding or 'utf-8'))

npk_path = r'c:\Users\Raysoo\Downloads\ROS_RE\04_obb\extracted\script.npk'

def find_mod(sig):
    data = open(npk_path, 'rb').read()
    cnt = struct.unpack_from('<I', data, 4)[0]
    io = struct.unpack_from('<I', data, 0x14)[0]
    for i in range(cnt):
        b = io + i*28
        s, off, ln, oln = struct.unpack_from('<IIII', data, b)
        if s == sig:
            raw = data[off:off+ln]
            dec = RS.member_marshal(raw)
            return RS.P(dec).load()
    return None

if __name__ == '__main__':
    # Retain the old ad-hoc entry point without running it when script_disas.py
    # imports this module as a library.
    ath = find_mod(0xc7ef2b17)
    print("\n================== DISASSEMBLY: Athlete.py ==================")
    for c in ath.get('consts', []):
        if isinstance(c, dict) and c.get('name') == b'PlayerAthlete':
            for cc in c.get('consts', []):
                if isinstance(cc, dict):
                    cname = nm(cc.get('name'))
                    if cname in ('showSelectCharacter', 'onCreateCharacter', 'onRoleCreateSuc', 'enterHall', '_realEnterHall'):
                        disas(cc)

import struct

WINDOW_PATH = r"C:\Users\Raysoo\Downloads\ROS_RE\scratch\heap_dump_2\window_athlete.bin"
WINDOW_BASE_VA = 0x7638501d4a80  # abs_start from the dd invocation

with open(WINDOW_PATH, 'rb') as f:
    data = f.read()

print("window size:", len(data))

# PyStringObject (CPython 2.7, 64-bit) header layout:
#   Py_ssize_t ob_refcnt;   (8)
#   PyTypeObject *ob_type;  (8)
#   Py_ssize_t ob_size;     (8)
#   long ob_shash;          (8)
#   int ob_sstate;          (4)
#   int _pad;               (4)   <- natural alignment padding before ob_sval
#   char ob_sval[1];        starts here
HEADER_LEN = 40

targets = [b'Athlete.py', b'iWeekendPush.py']
string_obj_vas = {}  # text -> list of object VAs (header start)

for t in targets:
    idx = 0
    hits = []
    while True:
        idx = data.find(t, idx)
        if idx == -1:
            break
        text_va = WINDOW_BASE_VA + idx
        obj_va = text_va - HEADER_LEN
        hits.append((idx, text_va, obj_va))
        idx += 1
    string_obj_vas[t] = hits
    print("%s: %d occurrences" % (t, len(hits)))
    for idx, text_va, obj_va in hits[:5]:
        print("  text_off=0x%x text_va=0x%x candidate_obj_va=0x%x" % (idx, text_va, obj_va))

# Now search for 8-byte LE pointers in the window matching any candidate obj_va
# (these would be co_filename fields inside PyCodeObject structs referencing our strings)
print()
print("=== Searching for pointers to candidate string objects ===")
for t, hits in string_obj_vas.items():
    for idx, text_va, obj_va in hits:
        pattern = struct.pack('<Q', obj_va)
        pidx = 0
        found = []
        while True:
            pidx = data.find(pattern, pidx)
            if pidx == -1:
                break
            found.append(pidx)
            pidx += 1
        if found:
            print("%s obj_va=0x%x referenced by %d pointer site(s):" % (t.decode(), obj_va, len(found)))
            for f in found[:10]:
                ref_va = WINDOW_BASE_VA + f
                print("    pointer at file_off=0x%x VA=0x%x" % (f, ref_va))

from fetch_lldb_server import HttpFile
import zipfile, os, sys

URL = sys.argv[1]
f = HttpFile(URL)
zf = zipfile.ZipFile(f)
candidates = [n for n in zf.namelist() if 'lldb-server' in n and 'aarch64' in n]
print('candidates:', candidates)
name = candidates[0]

out_path = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(__file__), "lldb-server-android-arm64")
print("extracting (streams only the ~10MB compressed entry, not the full archive)...")
with zf.open(name) as src, open(out_path, "wb") as dst:
    dst.write(src.read())
print("wrote", out_path, os.path.getsize(out_path), "bytes")

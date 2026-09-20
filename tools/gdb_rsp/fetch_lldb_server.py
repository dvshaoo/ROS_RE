"""Extract a single file from a remote ZIP (the Android NDK) via HTTP range requests,
without downloading the whole ~660MB archive.

Uses Python's zipfile against a seekable file-like object backed by HTTP Range.
"""
import zipfile
import urllib.request

import sys
URL = sys.argv[1] if len(sys.argv) > 1 else "https://dl.google.com/android/repository/android-ndk-r27c-linux.zip"


class HttpFile:
    def __init__(self, url):
        self.url = url
        req = urllib.request.Request(url, method='HEAD')
        with urllib.request.urlopen(req) as r:
            self.size = int(r.headers['Content-Length'])
        self.pos = 0

    def seek(self, offset, whence=0):
        if whence == 0:
            self.pos = offset
        elif whence == 1:
            self.pos += offset
        elif whence == 2:
            self.pos = self.size + offset
        return self.pos

    def tell(self):
        return self.pos

    def read(self, n=-1):
        if n is None or n < 0:
            end = self.size - 1
        else:
            end = min(self.pos + n, self.size) - 1
        if end < self.pos:
            return b''
        req = urllib.request.Request(self.url, headers={'Range': f'bytes={self.pos}-{end}'})
        with urllib.request.urlopen(req) as r:
            data = r.read()
        self.pos += len(data)
        return data

    def readable(self):
        return True

    def seekable(self):
        return True


print("Fetching central directory listing (metadata only)...")
f = HttpFile(URL)
zf = zipfile.ZipFile(f)

targets = [n for n in zf.namelist() if 'lldb-server' in n and 'aarch64' in n]
print(f"found {len(targets)} matching entries:")
for t in targets:
    info = zf.getinfo(t)
    print(f"  {t}  compressed={info.compress_size}  uncompressed={info.file_size}")

if not targets:
    print("No aarch64 lldb-server found; listing all lldb-server entries instead:")
    for n in zf.namelist():
        if 'lldb-server' in n:
            print(" ", n)

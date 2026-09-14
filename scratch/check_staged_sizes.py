import subprocess

out = subprocess.check_output(['git', 'diff', '--cached', '--name-only'], text=True, errors='ignore')
staged = out.splitlines()
print(f"Total staged files: {len(staged)}")
too_large = []
import os
for p in staged:
    if os.path.exists(p):
        sz = os.path.getsize(p)
        if sz > 50 * 1024 * 1024:
            too_large.append((sz, p))
            print(f"  WARNING TOO LARGE: {sz / (1024*1024):.2f} MB: {p}")

if not too_large:
    print("ALL STAGED FILES ARE UNDER 50 MB! SAFE TO COMMIT AND PUSH.")

import subprocess, sys

out = subprocess.check_output(['git', 'ls-tree', '-r', '-l', 'HEAD'], text=True, errors='ignore')
large_files = []
for line in out.splitlines():
    parts = line.split()
    if len(parts) >= 5:
        size = parts[3]
        path = ' '.join(parts[4:])
        if size.isdigit() and int(size) > 20 * 1024 * 1024: # > 20 MB
            large_files.append((int(size), path))

large_files.sort(reverse=True)
print(f"Files > 20MB in HEAD: {len(large_files)}")
for s, p in large_files:
    print(f"  {s / (1024*1024):.2f} MB: {p}")

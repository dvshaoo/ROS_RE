import os, re

base_dir = r'C:\Users\Raysoo\Downloads\ROS_RE\01_apk\base_decompiled'
smali_dirs = [
    os.path.join(base_dir, 'smali'),
    os.path.join(base_dir, 'smali_classes2'),
    os.path.join(base_dir, 'smali_classes3'),
]

# 1. Scan for System.loadLibrary
print("=== 1. System.loadLibrary ===")
load_lib_results = []
for sdir in smali_dirs:
    for root, dirs, files in os.walk(sdir):
        for f in files:
            if f.endswith('.smali'):
                path = os.path.join(root, f)
                with open(path, 'r', encoding='utf-8', errors='ignore') as fl:
                    content = fl.read()
                if 'loadLibrary' in content:
                    matches = re.findall(r'const-string[^\"]*\"([^\"]+)\"\s+invoke-static[^\n]*System;->loadLibrary', content)
                    for m in matches:
                        load_lib_results.append((f, m, path))
                    # Also look for other patterns of loadLibrary
                    if not matches:
                        for line in content.splitlines():
                            if 'loadLibrary' in line:
                                load_lib_results.append((f, line.strip(), path))

print(f"Found {len(load_lib_results)} loadLibrary occurrences:")
for f, m, p in load_lib_results:
    print(f"  [{f}] -> {m}")

# 2. Scan for native methods
print("\n=== 2. Native Methods ===")
native_methods = []
for sdir in smali_dirs:
    for root, dirs, files in os.walk(sdir):
        for f in files:
            if f.endswith('.smali'):
                path = os.path.join(root, f)
                with open(path, 'r', encoding='utf-8', errors='ignore') as fl:
                    content = fl.read()
                if 'native ' in content:
                    matches = re.findall(r'\.method\s+([^;\n]*native[^\n]+)', content)
                    for m in matches:
                        # get class name from first line
                        first_line = content.splitlines()[0]
                        native_methods.append((first_line, m))

print(f"Found {len(native_methods)} native method declarations.")
for cls, m in native_methods:
    if 'netease' in cls.lower():
        print(f"  {cls} :: {m}")

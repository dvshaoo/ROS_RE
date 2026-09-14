import re

smali_path = r'C:\Users\Raysoo\Downloads\ROS_RE\01_apk\base_decompiled\smali\com\netease\neox\Client.smali'
with open(smali_path, 'r', encoding='utf-8', errors='ignore') as f:
    content = f.read()

methods = re.findall(r'\.method\s+([^\n]+)', content)
print(f'Total methods in Client.smali: {len(methods)}')
for m in methods:
    if any(k in m.lower() for k in ['native', 'init', 'start', 'login', 'game', 'neox', 'run', 'create', 'resume']):
        print('  ', m)

print('\n--- Native methods declared in Client.smali ---')
native_methods = re.findall(r'\.method\s+[^p]*native\s+([^\n]+)', content)
for nm in native_methods:
    print('  native ', nm)

print('\n--- System.loadLibrary in Client.smali ---')
loads = re.findall(r'const-string[^\"]*\"([^\"]+)\"\s+invoke-static[^\n]*System;->loadLibrary', content)
print('Loaded libraries:', loads)

print('\n--- Target Strings in Client.smali ---')
strings = re.findall(r'const-string[^\"]*\"([^\"]+)\"', content)
for s in sorted(set(strings)):
    if any(k in s.lower() for k in ['h45na', 'lib', 'neox', 'client', 'login', 'auth', 'patch', 'bigworld', 'server', 'init', 'start', 'unisdk', 'channel']):
        print('  ', s)

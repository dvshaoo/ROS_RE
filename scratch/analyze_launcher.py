import os, re

smali_path = r'C:\Users\Raysoo\Downloads\ROS_RE\01_apk\base_decompiled\smali\com\netease\neox\Launcher.smali'
with open(smali_path, 'r', encoding='utf-8', errors='ignore') as f:
    content = f.read()

# Find all method definitions
methods = re.findall(r'\.method\s+([^\n]+)', content)
print(f'Total methods in Launcher.smali: {len(methods)}')
for m in methods:
    print('  ', m)

print('\n--- Strings in Launcher.smali ---')
strings = re.findall(r'const-string[^\"]*\"([^\"]+)\"', content)
for s in sorted(set(strings)):
    if any(k in s.lower() for k in ['patch', 'obb', 'client', 'update', 'url', 'http', 'version', 'start', 'init', 'load', 'so', 'h45na', 'neox', 'res', 'launch']):
        print('  ', s)

import re

with open(r'01_apk\base_decompiled\AndroidManifest.xml', 'rb') as f:
    raw = f.read()

print('Length:', len(raw))
# Check if it has null bytes
print('Null bytes count:', raw.count(b'\x00'))

text = raw.decode('utf-8', errors='ignore')
# Find application name
app = re.findall(r'<application[^>]+android:name="([^"]+)"', text)
print('Application:', app)

# Find activities
activities = re.findall(r'<activity[^>]+android:name="([^"]+)"[^>]*>', text)
print('Found activities:', len(activities))
for a in activities[:20]:
    print('  Activity:', a)

# Find launcher activity
launcher = re.findall(r'<activity[^>]+android:name="([^"]+)"[\s\S]*?android\.intent\.action\.MAIN[\s\S]*?</activity>', text)
print('Launcher activity:', launcher)

import sys, glob, re
sys.stdout.reconfigure(encoding='utf-8')

log_files = glob.glob('logcat*.txt') + glob.glob('06_notes/*.txt')
patterns = ['neox', 'login', 'patch', 'serverconnection', 'server_list', 'mercury', 'unisdk', 'mpay', 'onlogin']

found = {}
for lf in log_files:
    try:
        with open(lf, 'rb') as f:
            raw = f.read()
        enc = 'utf-16le' if raw.startswith(b'\xff\xfe') or raw.count(b'\x00') > 100 else 'utf-8'
        text = raw.decode(enc, errors='ignore')
        
        lines = text.splitlines()
        for line in lines:
            ll = line.lower()
            if any(p in ll for p in ['channel_login', 'serverconnection', 'mercury', 'server_list_ad', 'ntonlogin', 'logonbegin', 'patchversion', 'uilogin', 'uipatch', 'neox::bwclient']):
                tag = line[:100]
                if tag not in found:
                    found[tag] = line
    except Exception as e:
        pass

print(f"Found {len(found)} unique interesting logcat lines:")
for k in list(found.keys())[:50]:
    print("  ", found[k])

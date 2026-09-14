import glob

log_files = glob.glob('logcat*.txt') + glob.glob('06_notes/*.txt')
for lf in log_files:
    try:
        with open(lf, 'rb') as f:
            raw = f.read(500)
        encoding = 'utf-16le' if raw.startswith(b'\xff\xfe') or raw.count(b'\x00') > 50 else 'utf-8'
        with open(lf, 'r', encoding=encoding, errors='ignore') as f:
            lines = [f.readline() for _ in range(5)]
        print(f"File: {lf} (enc={encoding}), lines:")
        for l in lines[:2]:
            print("  ", l.strip()[:100])
    except Exception as e:
        print(f"Error {lf}: {e}")

import os

target = b"Account login failed"

print("Searching decrypted scripts and dex...")
for root, dirs, files in os.walk(r"c:\Users\Raysoo\Downloads\ROS_RE"):
    for f in files:
        p = os.path.join(root, f)
        try:
            data = open(p, "rb").read()
            if target in data:
                print(f"MATCH: {p}")
        except Exception:
            pass
print("Done search.")

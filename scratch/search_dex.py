import os

dex_dir = r"c:\Users\Raysoo\Downloads\ROS_RE\02_dex"
targets = [b"LoginCallback-onFailure", b"minor_status", b"1002", b"onFailure"]

for f in os.listdir(dex_dir):
    if f.endswith(".dex"):
        path = os.path.join(dex_dir, f)
        data = open(path, "rb").read()
        print(f"File: {f}, size: {len(data)}")
        for t in targets:
            idx = 0
            count = 0
            while True:
                idx = data.find(t, idx)
                if idx == -1:
                    break
                count += 1
                snippet = data[max(0, idx-40):min(len(data), idx+60)]
                print(f"  Match for {t} at {hex(idx)}: {snippet!r}")
                idx += len(t)
                if count > 5:
                    print("  ... capped")
                    break

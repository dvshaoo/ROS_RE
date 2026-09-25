import json

with open(r'c:\Users\Raysoo\Downloads\ROS_RE\data\athlete_exposed_methods.json', encoding='utf-8') as f:
    d = json.load(f)

print('Total entries:', len(d))
for k, v in sorted(d.items(), key=lambda x: int(x[0])):
    idx = int(k)
    if 305 <= idx <= 325:
        print(idx, v)

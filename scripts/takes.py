import json
from collections import Counter

takes = json.load(open("/Users/shaibby/egoexo/takes.json"))

# see every scenario name and how many takes each has
print(Counter(t["parent_task_name"] for t in takes))

bike = [
    t for t in takes
    if "bike" in t["parent_task_name"].lower()
    and t.get("is_narrated")          # person talks while working
    and not t.get("is_dropped")       # skip broken takes
    and 60 <= t["duration_sec"] <= 180  # 1–3 min: cheap to test
]

print(len(bike), "narrated bike takes")
for t in sorted(bike, key=lambda t: t["duration_sec"]):
    print(t["take_uid"], t["task_name"], round(t["duration_sec"]), "s", t["best_exo"])
"""Rebuild the tables in README.md from the slim result files.

Usage: python scripts/analyze.py data

Copyright (c) 2026 Hert4 (https://github.com/Hert4). MIT licensed.
Results come from AutomationBench by Zapier (https://github.com/zapier/AutomationBench);
all tasks, tools and assertions are theirs.
"""
import json, sys, collections, os

D = sys.argv[1] if len(sys.argv) > 1 else "data"
MODELS = [("base", "Qwen3.6-27B base"), ("opera", "beyoru/Opera"),
          ("gemma", "gemma-4-31B-it"), ("opsi", "beyoru/Ops-I")]

for key, label in MODELS:
    p = f"{D}/{key}_ab600.slim.json"
    if not os.path.exists(p):
        continue
    d = json.load(open(p))
    ts = d["tasks"]
    neg_t = neg_p = 0
    pos_t = pos_p = 0
    miss = collections.Counter()
    for t in ts:
        for a in t["assertions"]:
            if a["excluded"]:
                continue
            isneg = "_not_" in a["type"] or a["type"].endswith("_not_exists")
            if isneg:
                neg_t += 1; neg_p += a["passed"]
            else:
                pos_t += 1; pos_p += a["passed"]
        if not t["passed"]:
            miss[t["assertions_total"] - t["assertions_passed"]] += 1
    npass = sum(1 for t in ts if t["passed"])
    print(f"== {label}")
    print(f"   pass {npass}/{len(ts)} = {100*npass/len(ts):.2f}%  partial {100*d['summary']['avg_score']:.2f}%")
    print(f"   positive assertions {pos_p}/{pos_t} = {100*pos_p/pos_t:.1f}%")
    print(f"   negative assertions {neg_p}/{neg_t} = {100*neg_p/neg_t:.1f}%")
    print(f"   fail-by-1 assertion: {miss[1]}  fail-by-2: {miss[2]}  fail-by-3+: {sum(v for k,v in miss.items() if k>=3)}")
    steps = [t["steps"] for t in ts]
    hit50 = sum(1 for t in ts if t["steps"] >= 50)
    print(f"   avg steps {sum(steps)/len(steps):.1f}  tasks hitting max_steps(50): {hit50}")

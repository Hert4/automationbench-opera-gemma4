"""Derive the published slim dataset from raw AutomationBench export JSONs.

Drops `messages` and `end_state` (>99% of the bytes) and keeps every metric plus the per-assertion
pass/fail record, so the results stay analysable inside a git repo. Also emits tasks_all.csv and
manifest.json. Raw exports with full trajectories are published separately on Hugging Face.

Copyright (c) 2026 Hert4 (https://github.com/Hert4). MIT licensed.
Results come from AutomationBench by Zapier (https://github.com/zapier/AutomationBench);
all tasks, tools and assertions are theirs.
"""
import json, os, gzip, csv, collections

AB = "/root/work/AutomationBench"
OUT = "/tmp/ab600_pub"
os.makedirs(OUT, exist_ok=True)
os.makedirs(OUT + "/data", exist_ok=True)

MODELS = [
    ("base", "base_ab600.json", "Qwen3.6-27B (base)"),
    ("opera", "opera_ab600.json", "beyoru/Opera"),
    ("gemma", "gemma_ab600.json", "gemma-4-31B-it"),
    ("opsi", "opsi_ab600.json", "beyoru/Ops-I"),
]

KEEP = ["id", "name", "score", "passed", "assertions_total", "assertions_passed",
        "input_tokens", "output_tokens", "cached_input_tokens", "uncached_input_tokens",
        "reasoning_tokens", "num_tool_calls", "num_model_calls", "model_time_s",
        "tool_time_s", "steps"]

manifest = {}
rows = []
atype = collections.defaultdict(lambda: collections.defaultdict(lambda: [0, 0]))

for key, fn, label in MODELS:
    p = os.path.join(AB, fn)
    if not os.path.exists(p):
        continue
    d = json.load(open(p))
    slim_tasks = []
    for t in d["tasks"]:
        r = {k: t[k] for k in KEEP}
        r["finish_reasons"] = t.get("finish_reasons")
        r["assertions"] = [{"type": a["type"], "passed": a["passed"],
                            "excluded": a.get("excluded", False)}
                           for a in t.get("assertion_results", [])]
        slim_tasks.append(r)
        rows.append([key, t["id"], t["name"], t["name"].split(".")[0], t["score"],
                     int(t["passed"]), t["assertions_total"], t["assertions_passed"],
                     t["input_tokens"], t["output_tokens"], t["num_tool_calls"],
                     t["num_model_calls"], t["steps"], round(t["model_time_s"], 2)])
        for a in t.get("assertion_results", []):
            if a.get("excluded"):
                continue
            e = atype[key][a["type"]]
            e[0] += 1
            e[1] += 1 if a["passed"] else 0
    slim = {"meta": d["meta"], "summary": d["summary"], "tasks": slim_tasks}
    out = os.path.join(OUT, "data", f"{key}_ab600.slim.json")
    json.dump(slim, open(out, "w"), ensure_ascii=False)
    manifest[key] = {"label": label, "meta": d["meta"], "summary": d["summary"],
                     "slim_bytes": os.path.getsize(out),
                     "raw_bytes": os.path.getsize(p)}

with open(os.path.join(OUT, "data", "tasks_all.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["model", "task_id", "task_name", "domain", "score", "passed",
                "assertions_total", "assertions_passed", "input_tokens", "output_tokens",
                "num_tool_calls", "num_model_calls", "steps", "model_time_s"])
    w.writerows(rows)

json.dump({"models": manifest,
           "assertion_types": {k: {t: v for t, v in sorted(d.items())}
                               for k, d in atype.items()}},
          open(os.path.join(OUT, "data", "manifest.json"), "w"), indent=2)

for root, _, files in os.walk(OUT):
    for fl in files:
        fp = os.path.join(root, fl)
        print(os.path.getsize(fp), fp)

#!/usr/bin/env python3
"""對一批人類寫的繁中文章跑 twtone，算每個訊號的分布，再把目標文章放進去比。

用法：python3 baseline.py corpus/ [目標.md ...] [--save baseline.json]
"""
import glob, json, os, statistics as st, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from twtone import analyze  # noqa: E402

def run(path):
    rep = analyze(open(path, encoding="utf-8").read())
    row = {s["key"]: s["per_k"] for s in rep["signals"]}
    S = rep["structure"]
    row["sentence_cv"] = S["sentence_cv"]
    row["headings_per_k"] = S["headings_per_k"]
    row["han"] = S["han"]
    return row

def pct(xs, p):
    xs = sorted(x for x in xs if x is not None)
    if not xs: return None
    k = (len(xs) - 1) * p
    f, c = int(k), min(int(k) + 1, len(xs) - 1)
    return round(xs[f] + (xs[c] - xs[f]) * (k - f), 2)

args = [a for i, a in enumerate(sys.argv[1:], 1) if not a.startswith("--") and not sys.argv[i-1].startswith("--")]
corpus_dir, targets = args[0], args[1:]
files = sorted(glob.glob(os.path.join(corpus_dir, "*.md")))
rows = {os.path.basename(f): run(f) for f in files}
keys = ["contrast", "colon_conclusion", "dunhao_run", "bridge_opener", "emdash", "semicolon",
        "x_numbers", "x_connectives", "x_yiweizhe", "sentence_cv", "headings_per_k"]
base = {k: {"median": pct([r[k] for r in rows.values()], .5),
            "p75": pct([r[k] for r in rows.values()], .75),
            "max": max(r[k] for r in rows.values() if r[k] is not None)} for k in keys}
base["_n"] = len(rows)
base["_han_total"] = sum(r["han"] for r in rows.values())
base["_files"] = list(rows)

print(f"# 基準：{len(rows)} 篇，共 {base['_han_total']} 漢字\n")
print(f"{'訊號':18s} {'中位':>7s} {'p75':>7s} {'最大':>7s}  " + "  ".join(f"{t[:10]:>10s}" for t in targets))
tgt = {t: run(t) for t in targets}
for k in keys:
    b = base[k]
    line = f"{k:18s} {str(b['median']):>7s} {str(b['p75']):>7s} {str(b['max']):>7s}  "
    for t in targets:
        v = tgt[t][k]
        flag = "" if v is None or b["p75"] is None else (" ▲" if v > b["max"] else (" △" if v > b["p75"] else ""))
        line += f"{str(v)+flag:>12s}"
    print(line)

print("\n# 逐篇（/千字）")
print(f"{'file':28s} {'漢字':>5s} " + " ".join(f"{k[:9]:>9s}" for k in keys[:6]) + "  sent_cv")
for f, r in rows.items():
    print(f"{f:28s} {r['han']:5d} " + " ".join(f"{r[k]:9.2f}" for k in keys[:6]) + f"  {r['sentence_cv']}")

if "--save" in sys.argv:
    out = sys.argv[sys.argv.index("--save") + 1]
    json.dump({"baseline": base, "rows": rows, "targets": tgt}, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\nsaved {out}")

#!/usr/bin/env python3
"""把 zhtw-mcp 的 JSON 與 twtone 的 JSON 合成一份人讀報告。

zhtw-mcp 那側只保留 warning 以上，以及 ai_style 全部；info 級翻譯腔只給計數。
"""
import json
import sys
from collections import Counter, defaultdict

zh = json.load(open(sys.argv[1], encoding="utf-8"))
tw = json.load(open(sys.argv[2], encoding="utf-8"))

out = [f"# 檢查報告 · {tw['file']}", ""]

# ---------------- zhtw-mcp
issues = zh.get("issues", [])
sc = zh.get("style_scorecard", {}).get("style_scores", {})
out.append("## 一、zhtw-mcp（用詞／標點／翻譯腔）")
out.append(f"- 總計 {zh.get('total', len(issues))} 筆：warning {zh.get('warnings', 0)}、error {zh.get('errors', 0)}")
if sc:
    out.append(f"- 分數：AI {sc.get('ai')}、翻譯腔 {round(sc.get('translationese', 0), 2)}、兩岸用詞密度 {round(sc.get('regional_density', 0), 2)}（0–1，越低越乾淨）")

by_type = defaultdict(list)
for it in issues:
    by_type[it.get("rule_type") or it.get("type")].append(it)

def show(it):
    sug = f" → {'／'.join(it['suggestions'])}" if it.get("suggestions") else ""
    ctx = f"　　{it['context']}" if it.get("context") else ""
    return f"  - L{it['line']}：{it['found']}{sug}{ctx}"

for t in ("cross_strait", "political_coloring", "confusable", "typo", "variant", "proper_noun"):
    if by_type.get(t):
        out.append(f"- **{t}**（{len(by_type[t])}）")
        out += [show(i) for i in by_type[t]]
if by_type.get("ai_style"):
    out.append(f"- **ai_style**（{len(by_type['ai_style'])}；此層訊號弱，對照下方 twtone）")
    out += [show(i) for i in by_type["ai_style"]]
tr = by_type.get("translationese", [])
if tr:
    warn = [i for i in tr if i.get("severity") == "warning"]
    kinds = Counter((i.get("context") or "").split(" — ")[0].split("：")[-1] for i in tr)
    out.append(f"- **translationese**（{len(tr)}，其中 warning {len(warn)}）：" + "、".join(f"{k} {v}" for k, v in kinds.most_common()))
    out += [show(i) for i in warn]
others = {k: v for k, v in by_type.items() if k not in ("cross_strait", "political_coloring", "confusable", "typo", "variant", "proper_noun", "ai_style", "translationese")}
for k, v in others.items():
    out.append(f"- {k}（{len(v)}）")
out.append("")

# ---------------- twtone
S = tw["structure"]
out.append("## 二、twtone（表層 AI tell，lieflat 配對研究有效項）")
out.append(f"- 漢字 {S['han']}，句 {S['sentences']}")
grade_name = {"A": "A 機械改", "B": "B 建議改", "F": "F 指紋", "C": "C 只報告", "X": "X 已否決，永不改"}
for g in "ABFCX":
    group = [s for s in tw["signals"] if s["grade"] == g]
    if not group:
        continue
    out.append(f"### {grade_name[g]}")
    for s in group:
        out.append(f"- **{s['name']}**：{s['count']} 次，{s['per_k']}/千字　　參照：{s['ref']}")
        for h in s["hits"][:6]:
            q = "（引文內）" if h["quote"] else ""
            out.append(f"  - L{h['line']}{q}：{h['text']}")
        if len(s["hits"]) > 6:
            out.append(f"  - …另 {len(s['hits']) - 6} 處")
out.append("### 整篇分布（只報告）")
out.append(f"- 句長 CV {S['sentence_cv']}（均 {S['sentence_mean']} 字）。{S['sentence_cv_ref']}")
out.append(f"- 小標題 {S['headings_per_k']}/千字，節長中位數 {S['section_len_median']}，節長 CV {S['section_len_cv']}。{S['section_ref']}")
out.append(f"- 相鄰三句同構 {len(S['isomorphic_triples'])} 組。{S['isomorphic_ref']}")
for h in S["isomorphic_triples"][:4]:
    out.append(f"  - L{h['line']}：{h['text']}")
out.append("")
out.append("—— 兩層都是零 token 的規則偵測。下一步若要用 LLM，只餵上面的命中句，不重寫全文。")
print("\n".join(out))

#!/usr/bin/env python3
"""twtone quick：只講嚴重的，其他略過。

門檻來自 out/baseline-pre2022.json（AI 之前的台灣同類文體）：
  嚴重   = 超過基準語料裡任何一篇的最大值   → 列出句子，要改
  注意   = 超過 p75 但沒超過最大值           → 一行帶過，預設略過（--verbose 才展開）
  略過   = 其他

用詞／標點交給 zhtw-mcp：唯一候選的兩岸用詞自動改到 <檔名>.tw.md（不動原檔），
其他 zhtw-mcp 命中只給計數。

用法：
    python3 quick.py 報告.md              # 報告 + 自動修一份副本
    python3 quick.py 報告.md --no-fix     # 只報告
    python3 quick.py 報告.md --verbose    # 連「注意」級也展開
    python3 quick.py 報告.md --gate       # 有「嚴重」就 exit 1（接 CI / 發佈前）
"""
import json, os, shutil, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from twtone import analyze  # noqa: E402

ZHTW = os.environ.get("ZHTW", os.path.join(HERE, "zhtw-mcp"))
BASE = json.load(open(os.path.join(HERE, "out", "baseline-pre2022.json"), encoding="utf-8"))["baseline"]

NAME = {"contrast": "對舉「不是…而是／，是」", "colon_conclusion": "結論提示冒號", "dunhao_run": "頓號連排",
        "bridge_opener": "段首承接語", "yiweizhe": "這意味著／這表明", "residue": "AI 工具／對話殘留",
        "formula_opener": "公式化開場", "stance_vacuum": "立場真空", "sermon_tag": "勸誡反問收尾",
        "emdash": "破折號", "semicolon": "分號",
        "headings_per_k": "小標題密度", "sentence_cv": "句長 CV"}
HINT = {"contrast": "把判斷直接說出來，保留兩邊的限定詞；澄清誤讀的那幾句可以留，但同一節別連用",
        "colon_conclusion": "刪掉「核心是：」這類提示語，冒號後面的話直接講",
        "dunhao_run": "一句排三個以上就拆句，或只留最重要的兩個",
        "bridge_opener": "段首的「這也解釋了／換句話說」直接刪，段落照樣接得上",
        "yiweizhe": "台灣慣用「這表示／這代表」，或直接講結論",
        "residue": "直接刪；連結本體保留",
        "formula_opener": "刪掉時代帽子，第一句就給只有這篇才有的資訊",
        "stance_vacuum": "寫出作者實際的選擇與理由；沒有就標（需作者補充），不代編",
        "sermon_tag": "刪反問，句子停在事實上",
        "emdash": "破折號改句號或逗號",
        "semicolon": "分號串起來的多檔場景拆成兩三句"}


def level(key, v):
    b = BASE.get(key)
    if b is None or v is None:
        return "skip"
    if v > b["max"]:
        return "severe"
    if v > b["p75"]:
        return "note"
    return "skip"


def zhtw(path, fix):
    if not os.path.exists(ZHTW):
        return None, None
    cmd = [ZHTW, "--overrides", os.path.join(HERE, "overrides.json"), "lint", path,
           "--content-type", "markdown", "--off", "rhythm", "--format", "json"]
    out = subprocess.run(cmd, capture_output=True, text=True).stdout
    try:
        rep = json.loads(out)
    except json.JSONDecodeError:
        return None, None
    fixed = None
    if fix:
        fixed = os.path.splitext(path)[0] + ".tw.md"
        shutil.copyfile(path, fixed)
        subprocess.run([ZHTW, "--overrides", os.path.join(HERE, "overrides.json"), "lint", fixed,
                        "--content-type", "markdown", "--off", "rhythm", "--fix=lexical_safe"],
                       capture_output=True, text=True)
        if open(fixed, encoding="utf-8").read() == open(path, encoding="utf-8").read():
            os.remove(fixed)
            fixed = None
    return rep, fixed


def main(argv):
    if len(argv) < 2 or argv[1].startswith("-"):
        print(__doc__); return 0
    path = argv[1]
    verbose = "--verbose" in argv
    fix = "--no-fix" not in argv
    gate = "--gate" in argv

    rep = analyze(open(path, encoding="utf-8").read())
    S = rep["structure"]
    sigs = {s["key"]: s for s in rep["signals"]}
    severe, notes, skipped = [], [], 0
    for key in ["residue", "contrast", "colon_conclusion", "yiweizhe", "dunhao_run", "bridge_opener",
                "formula_opener", "stance_vacuum", "sermon_tag", "emdash", "semicolon"]:
        s = sigs[key]
        lv = level(key, s["per_k"])
        if key == "residue":                                   # 確定性殘留：出現就是嚴重，不看基準
            lv = "severe" if s["count"] else "skip"
        if sigs[key]["grade"] == "C" and lv == "severe":       # speak-human-tw 的內容類 pattern 未驗證：最多注意級
            lv = "note"
        if key in ("emdash", "semicolon") and s["per_k"] <= 2.0:   # 指紋：lieflat 的 >2/千字 才算
            lv = "note" if lv == "severe" else lv
        if S["han"] < 1000 and s["count"] < 2 and lv == "severe":  # 短文密度會爆，單次命中不算嚴重
            lv = "note"
        if lv == "severe":
            severe.append((key, s))
        elif lv == "note":
            notes.append((key, s))
        else:
            skipped += 1
    struct_notes = []
    for key, v in (("headings_per_k", S["headings_per_k"]), ("sentence_cv", S["sentence_cv"])):
        lv = level(key, v)
        if lv != "skip":
            struct_notes.append((key, v, lv))

    zrep, fixed = zhtw(path, fix)

    print(f"# twtone quick · {os.path.basename(path)} · {S['han']} 漢字")
    if severe:
        print(f"\n## 要改（超過台灣基準語料任何一篇）")
        for key, s in severe:
            b = BASE[key]
            print(f"\n**{NAME[key]}** {s['count']} 次，{s['per_k']}/千字（基準最大 {b['max']}，中位 {b['median']}）")
            print(f"  改法：{HINT[key]}")
            for h in s["hits"]:
                print(f"  - L{h['line']}{'（引文內，不改）' if h['quote'] else ''}：{h['text']}")
    else:
        print("\n表層 AI tell：沒有超過台灣基準的項目。")

    rest = []
    if notes:
        rest.append("、".join(f"{NAME[k]} {s['per_k']}/千字" for k, s in notes))
    if struct_notes:
        rest.append("、".join(f"{NAME[k]} {v}" for k, v, _ in struct_notes) + "（體裁差異，不改）")
    if rest or skipped:
        print(f"\n略過：{'；'.join(rest)}{'；' if rest else ''}另 {skipped} 項低於門檻。" + ("" if verbose or not notes else " 加 --verbose 展開。"))
    if verbose and notes:
        for key, s in notes:
            print(f"\n  {NAME[key]}（注意級，基準 p75 {BASE[key]['p75']}）")
            for h in s["hits"][:6]:
                print(f"    - L{h['line']}：{h['text']}")

    if zrep is not None:
        issues = zrep.get("issues", [])
        lex = [i for i in issues if i.get("rule_type") in ("cross_strait", "typo", "proper_noun", "political_coloring") and len(i.get("suggestions", [])) == 1]
        multi = [i for i in issues if i.get("rule_type") == "cross_strait" and len(i.get("suggestions", [])) != 1]
        trans = [i for i in issues if i.get("rule_type") == "translationese" and i.get("severity") == "warning"]
        print(f"\n## 用詞（zhtw-mcp）")
        if lex:
            for i in lex:
                print(f"  - L{i['line']}：{i['found']} → {i['suggestions'][0]}" + ("　✓ 已改進副本" if fixed else ""))
        else:
            print("  沒有可自動改的兩岸用詞。")
        if multi:
            print(f"  另 {len(multi)} 處用詞有多個候選，要人選：" + "、".join(f"L{i['line']} {i['found']}" for i in multi[:5]))
        if trans:
            print(f"  翻譯腔 warning {len(trans)} 處（定語堆疊／的的不休），不自動改" + ("，--verbose 展開" if not verbose else "") + "。")
            if verbose:
                for i in trans:
                    print(f"    - L{i['line']}：{i['found']}")
        if fixed:
            print(f"\n修好用詞的副本：{fixed}（原檔未動）")
    else:
        print("\n（找不到 zhtw-mcp binary，用詞層略過；設 ZHTW=/path/to/zhtw-mcp）")

    return 1 if (gate and severe) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

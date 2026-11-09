#!/usr/bin/env python3
"""twtone — 繁中報告的表層 AI tell 檢查器（零 token、純正則）。

只收 lieflat-less-ai-tone 兩輪配對研究裡「跨模型成立」或「單模型指紋」且正則抓得到的訊號，
加上一組「X 級：已被否決、永不改」的計數，防止往錯的方向改。
它不改文章，只報告；用詞／標點／字形交給 zhtw-mcp。

用法：
    python3 twtone.py 報告.md            # 人讀格式
    python3 twtone.py 報告.md --json     # 機器格式
    python3 twtone.py 報告.md --max-hits 3

參考值出處：larashero3-dotcom/lieflat-less-ai-tone README §3（簡中語料，僅供方向參考，
不是繁中台灣寫作的基準；見各項 note）。
"""
from __future__ import annotations

import json
import re
import statistics as st
import sys
from dataclasses import dataclass, field, asdict

HAN = re.compile(r"[一-鿿]")
SENT_END = "。！？"
CLAUSE_END = "，。！？；："

# ---------------------------------------------------------------- markdown 前處理


@dataclass
class Line:
    no: int          # 1-based 行號（原檔）
    text: str        # 去掉 markdown 標記後的散文
    kind: str        # prose | heading | list | quote | skip


def preprocess(src: str) -> list[Line]:
    out: list[Line] = []
    in_fence = False
    for i, raw in enumerate(src.splitlines(), 1):
        s = raw.rstrip()
        if s.startswith("```"):
            in_fence = not in_fence
            out.append(Line(i, "", "skip"))
            continue
        if in_fence or not s.strip():
            out.append(Line(i, "", "skip"))
            continue
        if s.lstrip().startswith("|"):          # 表格
            out.append(Line(i, "", "skip"))
            continue
        kind = "prose"
        if re.match(r"^#{1,6}\s", s):
            kind = "heading"
            s = re.sub(r"^#{1,6}\s+", "", s)
        elif re.match(r"^\s{0,3}(?:[-*+]|\d+[.、)])\s", s):
            kind = "list"
            s = re.sub(r"^\s{0,3}(?:[-*+]|\d+[.、)])\s+", "", s)
        elif s.lstrip().startswith(">"):
            kind = "quote"
            s = s.lstrip()[1:].strip()
        s = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", s)
        s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)
        s = re.sub(r"[*_`]", "", s)
        out.append(Line(i, s, kind))
    return out


def han_count(s: str) -> int:
    return len(HAN.findall(s))


def in_quote(text: str, pos: int) -> bool:
    """命中位置是否落在「」或『』內（引文不建議改）。"""
    depth = 0
    for ch in text[:pos]:
        if ch in "「『":
            depth += 1
        elif ch in "」』" and depth:
            depth -= 1
    return depth > 0


# ---------------------------------------------------------------- 訊號定義


@dataclass
class Hit:
    line: int
    text: str
    quote: bool = False


@dataclass
class Signal:
    key: str
    name: str
    grade: str                 # A 機械改 / B 建議改 / C 只報告 / F 指紋 / X 已否決永不改
    count: int = 0
    per_k: float = 0.0
    ref: str = ""              # 研究參照
    note: str = ""
    hits: list[Hit] = field(default_factory=list)


def regex_signal(lines, key, name, grade, pattern, ref, note, kinds=("prose", "list", "quote")):
    sig = Signal(key, name, grade, ref=ref, note=note)
    rx = re.compile(pattern)
    for ln in lines:
        if ln.kind not in kinds:
            continue
        for m in rx.finditer(ln.text):
            sig.count += 1
            sig.hits.append(Hit(ln.no, m.group(0), in_quote(ln.text, m.start())))
    return sig


def sentences(lines):
    """回傳 (行號, 句子) 清單，只取散文與清單。"""
    out = []
    for ln in lines:
        if ln.kind not in ("prose", "list", "quote"):
            continue
        for s in re.split(f"[{SENT_END}]", ln.text):
            if han_count(s) >= 4:
                out.append((ln.no, s.strip()))
    return out


def analyze(src: str) -> dict:
    lines = preprocess(src)
    total_han = sum(han_count(l.text) for l in lines if l.kind != "skip")
    k = max(total_han, 1) / 1000
    sents = sentences(lines)
    sigs: list[Signal] = []

    # ---- 第一層：跨模型成立（GPT 與 Opus 同向顯著）
    sigs.append(regex_signal(
        lines, "contrast", "對舉：不是 A 而是／，是 B", "B",
        r"(?:不是|並非|不在於|與其說)[^。！？\n]{1,30}?(?:[，、；]\s*)?(?:而是|而在於|不如說|，是|、是)",
        "研究中最強的純寫作訊號：GPT δ+0.88 / Opus +0.72；第一輪人類參考約 0.22 次/千字",
        "導讀體裁澄清誤讀時本來會用；看密度與是否集中在段落結論位。引文內（quote=true）不改。"))

    sigs.append(regex_signal(
        lines, "colon_conclusion", "結論提示冒號", "A",
        r"(?:一句話(?:總結|說|概括)?|簡單說|簡單來說|說白了|說穿了|先說結論|總結|小結|結論|核心(?:是|在於|觀點)?"
        r"|關鍵(?:是|在於)?|重點(?:是)?|原因(?:如下|有|在於)?|問題(?:是|在於)?|答案(?:是)?|本質(?:是|上)?"
        r"|換句話說|也就是說|我的(?:觀點|判斷|結論)|建議(?:是)?|殘酷的現實是|真相是|意思是)：",
        "「結論提示」冒號 AI 2.1 倍（冒號總量人類反而多，所以只抓這類）",
        "刪提示語、把判斷直接說出來，零語義風險。清單與表格標籤已排除。"))

    sigs.append(regex_signal(
        lines, "dunhao_run", "頓號連排（一句內 ≥3 項）", "B",
        r"(?![一二三四五六七八九十甲乙丙丁]、[一二三四五六七八九十甲乙丙丁]、)[^，。！？；：、\n]{2,14}、[^，。！？；：、\n]{2,14}、[^，。！？；：、\n]{2,14}",
        "密集並列 AI 7.8 vs 人類 5.4 次/千字（1.45 倍）",
        "清單式列舉在報告裡常是必要的；看是否整句都在排場景維度。"))

    sigs.append(regex_signal(
        lines, "bridge_opener", "段首承接語", "C",
        r"^(?:這也解釋了|從這個角度看|換句話說|也就是說|更重要的是|值得注意的是|這意味著|問題在於|有意思的是|關鍵在於)",
        "AI 段間明確承接 98.9% vs 人類 95.2%；人類每 14 段跳一次新話題，AI 每 50 段一次",
        "只報告。不是每處都要刪，但連續多段用同一招就會「太順」。", kinds=("prose",)))

    # ---- 繁中修正：lieflat 在簡中語料列 X（人類反而多），但台灣 2015–2022 語料 11 篇 0 次
    sigs.append(regex_signal(
        lines, "yiweizhe", "這意味著／這表明", "B",
        r"這(?:也)?意味著|這表明|這說明了?",
        "lieflat 簡中：人類反而多（X 級）；台灣基準 25,384 字 0 次；zhtw-mcp 與 speak-human-tw 皆列為訊號",
        "台灣慣用「這表示／這代表」或直接講結論。簡中結論不適用於繁中，這條是本 repo 自己的基準推翻的。"))

    # ---- 工具殘留（src:speak-human-tw 第 30、37 種）：確定性，零誤殺，命中即改
    sigs.append(regex_signal(
        lines, "residue", "AI 工具／對話殘留", "A",
        r"utm_source=(?:chatgpt|openai|copilot|perplexity)[\w.]*|cite\s*turn\d+\w*|oai_citation|希望這對你有幫助|如果你需要我[^。！？\n]{0,12}|以下是(?:修改|清理|改寫)後的版本|好問題！|這真是一個(?:非常)?棒的問題",
        "speak-human-tw SF-09／SF-20；不需要基準，出現就是殘留",
        "直接刪；連結本體保留。"))

    # ---- speak-human-tw 的內容類 pattern（未經配對驗證，只報告）
    sigs.append(regex_signal(
        lines, "formula_opener", "公式化開場（時代大帽子）", "C",
        r"^(?:在當今|在這個[^，。]{0,12}的時代|隨著[^，。]{2,16}(?:快速|迅速|蓬勃)?(?:發展|演進|崛起)|近年來，?隨著)",
        "speak-human-tw 第 21 種；台灣基準見 baseline",
        "只報告。真的在論述時代變化、底下接具體數字時放行。", kinds=("prose",)))

    sigs.append(regex_signal(
        lines, "stance_vacuum", "立場真空", "C",
        r"各有(?:其)?優缺點|因人而異|見仁見智|取決於(?:多方面|諸多|許多)因素|沒有(?:標準|絕對的)答案|值得(?:我們)?深思",
        "speak-human-tw 第 9 種：整段沒有判斷",
        "只報告。作者有給具體選擇條件時放行（SNF-13）。"))

    sigs.append(regex_signal(
        lines, "sermon_tag", "勸誡反問收尾", "C",
        r"(?:不是嗎|對吧|你說是不是|何樂而不為)[？?]",
        "speak-human-tw 第 16 種",
        "只報告。"))

    # ---- 第二層：單模型指紋
    sigs.append(regex_signal(
        lines, "emdash", "破折號", "F",
        r"——|—",
        "GPT δ−0.54（比人少）/ Opus +0.95（100% 文章使用）；方向相反，合併統計會抵消",
        ">2/千字優先處理；低於此值也看局部用法。"))

    sigs.append(regex_signal(
        lines, "semicolon", "分號", "F",
        r"；",
        "GPT δ+0.80（專屬）/ Opus −0.11",
        "三檔場景用兩個分號串成一句，人類多半拆三句。"))

    # ---- X 級：配對複測已否決，只計數、永不改
    x_items = [
        ("x_numbers", "精確數字", r"\d+(?:\.\d+)?%?", "δ −0.06：話題混雜假象，配對後消失"),
        ("x_connectives", "首先／其次／總之", r"首先|其次|再者|總之|總而言之", "δ +0.02：對當代模型徹底失效"),
        ("x_numbered", "序數詞小標題（一、／1.）", r"^(?:[一二三四五六七八九十]、|（[一二三四五六七八九十]）|\d+[.、])", "人類 8.6% vs AI 4.9%，方向反了；AI 愛的是多分節，不是編號"),
        ("x_blacklist", "賦能／閉環／抓手", r"賦能|閉環|抓手|落地|痛點", "δ +0.10：配對同事實後無差（這幾個詞是用語問題，交 zhtw-mcp）"),
    ]
    for key, name, pat, ref in x_items:
        kinds = ("heading",) if key == "x_numbered" else ("prose", "list", "quote")
        s = regex_signal(lines, key, name, "X", pat, ref, "永不據此刪改；列出只為防誤改。", kinds=kinds)
        s.hits = s.hits[:0]   # X 級不列例句，只給計數
        sigs.append(s)

    for s in sigs:
        s.per_k = round(s.count / k, 2)

    # ---- 整篇分布（C 級，只報告，不假裝成某句的錯）
    lens = [han_count(s) for _, s in sents]
    sent_cv = round(st.pstdev(lens) / st.mean(lens), 2) if len(lens) >= 5 else None

    headings = [l for l in lines if l.kind == "heading"]
    sec_lens, cur = [], 0
    for l in lines:
        if l.kind == "heading":
            if cur:
                sec_lens.append(cur)
            cur = 0
        elif l.kind != "skip":
            cur += han_count(l.text)
    if cur:
        sec_lens.append(cur)
    sec_cv = round(st.pstdev(sec_lens) / st.mean(sec_lens), 2) if len(sec_lens) >= 3 else None

    # 相鄰三句同構：連續三句開頭兩字相同，或長度相同（±1）
    iso = []
    for i in range(len(sents) - 2):
        a, b, c = sents[i][1], sents[i + 1][1], sents[i + 2][1]
        same_open = a[:2] == b[:2] == c[:2] and han_count(a[:2]) == 2
        same_len = abs(len(a) - len(b)) <= 1 and abs(len(b) - len(c)) <= 1 and len(a) <= 20
        if same_open or same_len:
            iso.append(Hit(sents[i][0], f"{a[:18]}… / {b[:18]}… / {c[:18]}…"))

    structure = {
        "han": total_han,
        "sentences": len(sents),
        "sentence_mean": round(st.mean(lens), 1) if lens else None,
        "sentence_cv": sent_cv,
        "sentence_cv_ref": "人類參考：配對複測 0.54、第一輪抽樣 0.67（兩口徑不可混用）；AI 0.41–0.55。不為節奏改句長。",
        "headings": len(headings),
        "headings_per_k": round(len(headings) / k, 2),
        "section_len_median": int(st.median(sec_lens)) if sec_lens else None,
        "section_len_cv": sec_cv,
        "section_ref": "AI 1.3–1.7 個小標題/千字、節數中位數 7 vs 人類 1。注意：研究語料是文章不是報告，報告體裁本來分節，此項只做參考。",
        "isomorphic_triples": [asdict(h) for h in iso],
        "isomorphic_ref": "相鄰句高度同構 AI 8.71% vs 人類 5.52%（弱訊號）",
    }

    return {"signals": [asdict(s) for s in sigs], "structure": structure}


# ---------------------------------------------------------------- 輸出


def render(report: dict, path: str, max_hits: int) -> str:
    S = report["structure"]
    out = [f"# twtone · {path}", f"漢字 {S['han']}，句 {S['sentences']}，小標題 {S['headings']}", ""]
    grade_name = {"A": "A 機械改", "B": "B 建議改", "C": "C 只報告", "F": "F 指紋", "X": "X 已否決（永不改）"}
    for g in "ABFCX":
        group = [s for s in report["signals"] if s["grade"] == g]
        if not group:
            continue
        out.append(f"## {grade_name[g]}")
        for s in group:
            out.append(f"- **{s['name']}**：{s['count']} 次，{s['per_k']}/千字")
            out.append(f"  - 參照：{s['ref']}")
            if s["note"]:
                out.append(f"  - 說明：{s['note']}")
            shown = s["hits"][:max_hits]
            for h in shown:
                q = "（引文內）" if h["quote"] else ""
                out.append(f"  - L{h['line']}{q}：{h['text']}")
            if len(s["hits"]) > max_hits:
                out.append(f"  - …另 {len(s['hits']) - max_hits} 處")
        out.append("")
    out.append("## 整篇分布（只報告）")
    out.append(f"- 句長：均 {S['sentence_mean']} 字，CV {S['sentence_cv']}。{S['sentence_cv_ref']}")
    out.append(f"- 分節：{S['headings_per_k']} 個小標題/千字，節長中位數 {S['section_len_median']} 字，節長 CV {S['section_len_cv']}。{S['section_ref']}")
    out.append(f"- 相鄰三句同構：{len(S['isomorphic_triples'])} 組。{S['isomorphic_ref']}")
    for h in S["isomorphic_triples"][:max_hits]:
        out.append(f"  - L{h['line']}：{h['text']}")
    return "\n".join(out)


def main(argv):
    if len(argv) < 2 or argv[1] in ("-h", "--help"):
        print(__doc__)
        return 0
    path = argv[1]
    as_json = "--json" in argv
    max_hits = 5
    if "--max-hits" in argv:
        max_hits = int(argv[argv.index("--max-hits") + 1])
    src = open(path, encoding="utf-8").read()
    rep = analyze(src)
    rep["file"] = path
    if as_json:
        print(json.dumps(rep, ensure_ascii=False, indent=1))
    else:
        print(render(rep, path, max_hits))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

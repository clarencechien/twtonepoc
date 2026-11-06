# twtonepoc

繁中報告的「表層 AI tell ＋ 在地用語」零 token 檢查 PoC。
兩層確定性工具，不改文章，只報告；LLM 留到最後、只看命中句。

```
寫完 .md
  ├─ zhtw-mcp lint        用詞／標點／字形／翻譯腔      （Rust，0 token）
  ├─ twtone.py            lieflat 配對研究有效的表層訊號（Python，0 token）
  └─ merge.py             合成一份人讀報告
```

一篇 4,500 字的報告跑完 0.3 秒。

## 快速模式（日常用這個）

```bash
python3 quick.py 報告.md          # 只講嚴重的；唯一候選的用詞自動改到 報告.tw.md，原檔不動
python3 quick.py 報告.md --gate   # 有「要改」就 exit 1，接發佈前關卡
python3 quick.py 報告.md --verbose
```

門檻來自 `out/baseline-pre2022.json`：**超過台灣基準語料任何一篇的最大值才叫嚴重**，超過 p75 一行帶過，其餘不提。
fifth-move 跑出來只剩一項要改（對舉 6 句），用詞自動修 2 處，其他 30 筆全部略過。

## 完整用法

```bash
# 1. 建 zhtw-mcp（會從 GitHub 抓 OpenCC 字典，約 2 分鐘）
git clone https://github.com/sysprog21/zhtw-mcp && cd zhtw-mcp && make && cd ..
cp zhtw-mcp/target/release/zhtw-mcp .

# 2. 跑
./run.sh fixtures/fifth-move.md            # 報告寫到 out/
python3 twtone.py 報告.md                   # 只跑 twtone
python3 twtone.py 報告.md --json
```

`overrides.json` 關掉 zhtw-mcp 已知誤報的規則，之後持續累積。

## 這個 PoC 在回答什麼

起點是兩個 repo：

- **[lieflat-less-ai-tone](https://github.com/larashero3-dotcom/lieflat-less-ai-tone)**（簡中，CC BY-NC）：用 629 篇對照＋270 對同題同事實配對，逐條檢驗流傳的「AI 味」判準。結論是大半判準不成立，少數幾條成立。
- **[zhtw-mcp](https://github.com/sysprog21/zhtw-mcp)**（繁中，MIT，Jserv）：教育部標準為依據的 zh-TW linter，約 2,000 條規則，可當 MCP server。

問題是：這兩套哪些能用在台灣繁中的報告上，要花多少 token，值不值得。

## Findings（2026-11-06）

### 1. 去 AI 味：規則最小改動有效，LLM 整篇重寫是白功

- 「Computational Turing Test」（arXiv 2511.04195）：persona 描述對降低可偵測性效果近零；風格範例降 2–6 點、檢索脈絡再降 2–10 點；最好組合平均降約 10 點，從未接近 50%。越像人、語義保真越低。
- 「Base Models Look Human To AI Detectors」（arXiv 2605.19516）：base model 續寫 96.7% 被判為人，instruct 版 30.3%。AI 味是 post-training 加的；zero-shot 改寫 prompt「沒有有意義的取捨空間」，有效的是微調過的改寫器。
- 「Narrative Flattening」（arXiv 2605.27878）：post-training 把風格變異壓到人類的 0.5 倍，prompt 救不回。

所以 humanizer 類「整篇重寫」skill 花最多 token、效果最差、還改壞語義。lieflat 自己的結論也是：最小改動、資訊守恆、不製造參差、結構不動。

### 2. lieflat 的方法論可借，規則和門檻值不能直接搬

可借：配對殺混雜、分模型統計、負結果同報、X 級「永不改」清單、先報告等回覆再改。
不能搬：基準值用簡中 8 個內容源校準；正則寫死簡體字（遇繁中靜默漏抓，數字偏低看起來像沒 AI 味）；模型指紋是 Opus 4.6 / GPT-5.6 時點；授權 NC。

它的語義層每篇 40–80 次模型判讀，對日常報告太貴，而且綁 Jev 介面。本 PoC 只取它那張「哪幾條訊號有效、哪幾條被否決」的表。

被配對複測否決、本 PoC 列為 X 級只計數不改的：精確數字（δ−0.06）、賦能／閉環類黑名單詞（+0.10）、首先／其次／總之（+0.02）、「這意味著」（人類反而多）、一二三編號（方向反）、破折號當通用規則（GPT −0.54 / Opus +0.95，是指紋不是通則）。

### 3. 在地化不是白功，而且訓練端做不好，lint 是目前唯一可靠的補法

- Taiwan-LLM（arXiv 2311.17487）用 351 億 token 繁中語料繼續預訓練，論文自己承認沒有系統測 zh-TW vs zh-CN 用詞。
- TMLU（arXiv 2403.20180）：針對台灣華語微調的開放模型落後簡中版本。
- 中研院 CKIP-Llama-2 用簡轉繁的中國資料集微調，答出「國慶 10 月 1 日」。

在地化是查表問題，有標準答案（教育部辭典、樂詞網），規則引擎做得比 LLM 好。OpenCC 只做字形與詞彙對照，不碰句法，跟去 AI 味無關；zhtw-mcp 刻意不編入 OpenCC 的 TWPhrases，用詞由自己的規則庫決定。

### 4. zhtw-mcp 是繁中這一脈的匯流點

它已吸收 tzengyuxio/skills 的 humanize（101 條）、dewesternise（45 條）、shyuan/writing-humanizer、cuimao-translator 的規則，每條標 `src:` tag 可整族關閉。Chrome 擴充「字正腔圓」就是上游 `extension/` 目錄的改名打包。

弱點：AI 味那層的人類基準值寫死在 `ai_score.rs`，沒有配對驗證；把「這意味著」當 AI 訊號加權（lieflat 列 X 級）；破折號當通用規則。

### 5. fifth-move 實測：zhtw-mcp 漏掉了最強的那個訊號

對 [fixtures/fifth-move.md](fixtures/fifth-move.md)（4,577 漢字）：

| 層 | 結果 |
|---|---|
| zhtw-mcp 用詞 | 2 筆：模板→範本（可改）、渲染→算繪（嚴格立場） |
| zhtw-mcp 翻譯腔 | warning 11，全是定語堆疊／的的不休，一半在轉述原文 |
| zhtw-mcp ai_style | 3 筆，全誤報（「扮演」是主題詞、金句疊句是版型 pull quote） |
| twtone 對舉「不是 A，（而）是 B」 | **6 次、1.31/千字**，人類參考約 0.22，6 處全在「校讀」段 |
| twtone 其他 | 結論冒號 0、破折號 0、段首承接語 0、頓號連排 2.84/千字（低於人類 5.4） |
| 句長 CV | 0.69，高於人類參考 0.54–0.67，節奏沒問題 |

zhtw-mcp 的 `negative_parallel` 只抓「不只是／不僅是…而是」，純「不是…而是」不在範圍。這是 twtone 存在的理由。

參數教訓：`--rhythm` 對報告體裁噪音太大（長句 29 筆），關掉；`--spacing` 用預設 `require`，誤開 `strip` 會多 187 筆標點。

完整報告：[out/fifth-move.report.md](out/fifth-move.report.md)。

### 6. 基準不能用自己的近作，要用 AI 之前的台灣同類文體

自己的近作都是 AI 初稿改過的，拿來當基準等於把 AI 分布當常態（lieflat 第一輪犯的錯）。
而且口味會漂：Yakura 等人（arXiv 2409.01754）發現 ChatGPT 上線後，人類演講裡 GPT 偏好詞的使用頻率上升；每天改 AI 初稿的人漂得只會更多。

所以基準改抓 2015–2022 的台灣科技評論／科普／解釋型長文（iThome 專欄、INSIDE、泛科學、報導者），11 篇、25,384 漢字，來源見 [corpus/SOURCES.md](corpus/SOURCES.md)。
排除了書摘（翻譯文）和 2023 以後的文章。

```bash
python3 baseline.py corpus/ fifth-move.md --save out/baseline-pre2022.json
```

合併口徑（總命中 ÷ 總漢字，每千字）：

| 訊號 | 台灣 2015–2022 | lieflat 簡中人類 | fifth-move | 倍率（對台灣） |
|---|---|---|---|---|
| 對舉「不是…而是／，是」 | **0.08** | ~0.22 | **1.31** | **16.6×** |
| 結論提示冒號 | 0.08 | — | 0 | — |
| 頓號連排 | 1.50 | 5.4 | 2.84 | 1.9× |
| 段首承接語 | 0.04 | — | 0 | — |
| 破折號 | 0.04 | — | 0 | — |
| 分號 | 1.14 | — | 2.62 | 2.3× |
| 精確數字（X 級） | 8.98 | — | 8.08 | 0.9× |
| 句長 CV（中位） | 0.60 | 0.54–0.67 | 0.69 | — |
| 小標題/千字（中位） | 1.62 | — | 4.37 | 2.7× |

三個觀察：

- 台灣人類文章的對舉密度比 lieflat 的簡中人類語料還低（0.08 vs 0.22），11 篇裡只有 2 處。fifth-move 的 6 處是基準的 16 倍，超過語料裡任何一篇的最大值（0.53）。這條訊號在繁中成立，而且更強。
- 頓號、分號、小標題都在 2–3 倍，但都還在「報告體裁本來比專欄多」可以解釋的範圍；小標題尤其是體裁差異，不是 AI 味。
- 精確數字、句長 CV 跟人類沒差，印證 lieflat 把它們列 X 級是對的。

限制：11 篇是很小的樣本，中位數對稀有事件（對舉、冒號）不穩，所以主表用合併口徑。體裁也只是近似：專欄和報導不是「導讀」。要更準就擴到 30 篇以上，並補 2015–2022 的導讀／書評類原創文章。

## 下一步

1. `zhtw-mcp hook install` 掛成 Claude Code PostToolUse hook。
2. `run.sh` 接進 imitator 發佈流程，`PUT` 前跑，warning 超門檻就擋。
3. 要用 LLM 時只餵命中句（這篇 6 句），每句回「改／留＋理由＋改法」，不碰全文。
4. 基準語料擴到 30 篇以上（補 2015–2022 的導讀、書評類原創文）；AI 初稿 vs 定稿的 diff 另外量「還抓得到什麼」。

## 已知限制

- 對舉規則排除標題行。
- 「相鄰三句同構」用句長近似，是弱訊號，只列不改。
- 整篇分布（分節密度、句長 CV）的研究語料是文章不是報告，報告體裁本來分節，只做參考。
- 參考值全部來自簡中語料，方向可信、數值不是繁中基準。

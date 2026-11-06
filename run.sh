#!/usr/bin/env bash
# 零 token 的兩層檢查：zhtw-mcp（用詞／標點／翻譯腔）＋ twtone（表層 AI tell）。
# 用法：run.sh 報告.md [輸出目錄]
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ZHTW="${ZHTW:-$HERE/zhtw-mcp}"           # zhtw-mcp binary 路徑，可用環境變數覆蓋
IN="$1"; OUT="${2:-$HERE/out}"
mkdir -p "$OUT"
base="$(basename "${IN%.*}")"

# 1. zhtw-mcp：只 lint，不 --fix；關 rhythm（長句建議對報告體裁噪音太大）
"$ZHTW" --overrides "$HERE/overrides.json" lint "$IN" \
  --content-type markdown --off rhythm \
  --detect-ai high --detect-translationese \
  --format json > "$OUT/$base.zhtw.json" || true

# 2. twtone
python3 "$HERE/twtone.py" "$IN" --json > "$OUT/$base.twtone.json"

# 3. 合併成一份人讀報告
python3 "$HERE/merge.py" "$OUT/$base.zhtw.json" "$OUT/$base.twtone.json" > "$OUT/$base.report.md"
cat "$OUT/$base.report.md"

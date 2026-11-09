#!/usr/bin/env bash
# 回歸測試：SNF 不可誤殺（gate 要過），SF 要抓到（gate 要擋），fifth-move 維持只剩對舉一項。
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"; cd "$HERE"
fail=0
check() { # name expected_exit cmd...
  local name=$1 want=$2; shift 2
  "$@" >/tmp/twtone-test.out 2>&1; local got=$?
  if [ "$got" = "$want" ]; then echo "PASS  $name"; else echo "FAIL  $name (exit $got, want $want)"; sed 's/^/      /' /tmp/twtone-test.out | head -20; fail=1; fi
}
check "SNF 全部放行"            0 python3 quick.py fixtures/snf.md --no-fix --gate
check "SF 至少擋下一項"         1 python3 quick.py fixtures/sf.md  --no-fix --gate
check "fifth-move 仍有嚴重項"   1 python3 quick.py fixtures/fifth-move.md --no-fix --gate
# SF 裡應該被抓到的具體項目
python3 quick.py fixtures/sf.md --no-fix --verbose >/tmp/twtone-test.out 2>&1
for k in "對舉" "AI 工具／對話殘留" "破折號"; do
  grep -q "^\*\*$k" /tmp/twtone-test.out && echo "PASS  SF 要改：$k" || { echo "FAIL  SF 沒列為要改：$k"; fail=1; }
done
for k in "這意味著" "公式化開場" "立場真空" "勸誡反問"; do   # 短文單次命中／未驗證 pattern：至少要列出
  grep -q "$k" /tmp/twtone-test.out && echo "PASS  SF 有列出：$k" || { echo "FAIL  SF 沒列出：$k"; fail=1; }
done
# SNF 不該出現「要改」
python3 quick.py fixtures/snf.md --no-fix >/tmp/twtone-test.out 2>&1
grep -q "## 要改" /tmp/twtone-test.out && { echo "FAIL  SNF 出現要改區"; fail=1; } || echo "PASS  SNF 無要改區"
exit $fail

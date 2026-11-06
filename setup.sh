#!/usr/bin/env bash
# 把 zhtw-mcp 的預編 binary 放到 repo 根目錄（驗 SHA256）。沒有對應平台就改用原始碼建。
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE"
[ -x ./zhtw-mcp ] && { echo "zhtw-mcp 已存在，略過（要重抓先 rm zhtw-mcp）"; exit 0; }

case "$(uname -s)-$(uname -m)" in
  Linux-x86_64)   T=x86_64-unknown-linux-gnu ;;
  Linux-aarch64)  T=aarch64-unknown-linux-gnu ;;
  Darwin-arm64)   T=aarch64-apple-darwin ;;
  MINGW*|MSYS*|CYGWIN*) T=x86_64-pc-windows-msvc ;;
  *) T="" ;;
esac

BASE=https://github.com/sysprog21/zhtw-mcp/releases/download/latest
if [ -n "$T" ]; then
  F="zhtw-mcp-$T.tar.gz"
  echo "下載 $F ..."
  curl -sSL -o "/tmp/$F" "$BASE/$F"
  curl -sSL -o /tmp/zhtw-SHA256SUMS "$BASE/SHA256SUMS"
  want=$(grep " $F\$" /tmp/zhtw-SHA256SUMS | cut -d' ' -f1)
  got=$(sha256sum "/tmp/$F" 2>/dev/null | cut -d' ' -f1 || shasum -a 256 "/tmp/$F" | cut -d' ' -f1)
  [ "$want" = "$got" ] || { echo "SHA256 不符，中止"; exit 1; }
  tar xzf "/tmp/$F" -C /tmp zhtw-mcp && mv /tmp/zhtw-mcp ./zhtw-mcp && chmod +x ./zhtw-mcp
  rm -f "/tmp/$F" /tmp/zhtw-SHA256SUMS
else
  echo "沒有預編 binary（$(uname -s)-$(uname -m)），改從原始碼建（需要 Rust + make，約 2 分鐘）"
  command -v cargo >/dev/null || { echo "沒有 cargo，請先裝 Rust：https://rustup.rs"; exit 1; }
  rm -rf /tmp/zhtw-src && git clone -q --depth 1 https://github.com/sysprog21/zhtw-mcp /tmp/zhtw-src
  (cd /tmp/zhtw-src && make >/dev/null) && cp /tmp/zhtw-src/target/release/zhtw-mcp ./zhtw-mcp
fi
./zhtw-mcp --help | head -1
echo "完成。用法：./twtone 報告.md"

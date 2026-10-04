#!/usr/bin/env bash
# ================================================================
# abs-path-check.sh — 机器特定绝对路径检查
# ================================================================
# 目的：防止开发者本机的绝对路径被提交进仓库。
#       这类信息对其他人无意义、会泄露本机目录结构，且随开发机变化而失效。
#
# 检查范围：git 已跟踪的文本文件（-I 跳过二进制）
# 命中规则：
#   1. Windows 盘符绝对路径（盘符 + 冒号 + 反斜杠）
#   2. Unix 家目录        /Users/<名>  /home/<名>
# 不会误报：URL（http://… 不含反斜杠）、标准环境变量形式（%ProgramFiles%）
#
# 豁免：确需保留的行，在行尾加注释 `abs-path-check: allow`
#
# 用法:   bash scripts/abs-path-check.sh
# 退出码: 0 通过 / 1 发现命中
# ================================================================

set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

echo "🔍 检查机器特定绝对路径..."

# 盘符路径的正则里，反斜杠在 ERE 中需转义为 \\
# 盘符前必须不是字母 / 数字 / 下划线：否则 Python 里 `True:\n`、`"key":\n`
# 这类"冒号 + 转义序列"会被误判成盘符路径（2026-10-04 实测踩到）。
PATTERN='(^|[^A-Za-z0-9_])[A-Za-z]:\\|/Users/[A-Za-z]|/home/[a-z]'

HITS="$(git grep -n -I -E "$PATTERN" -- . 2>/dev/null | grep -v 'abs-path-check: allow' || true)"

if [ -z "$HITS" ]; then
    echo -e "${GREEN}✅ 未发现机器特定绝对路径${NC}"
    exit 0
fi

echo -e "${RED}❌ 发现机器特定绝对路径（仓库文件不应包含本机路径）：${NC}"
echo ""
echo "$HITS"
echo ""
echo "  处理建议："
echo "    - 仓库内路径 → 改用相对路径或占位符，如 <仓库根>/docs"
echo "    - 标准系统路径 → 改用环境变量形式，如 %ProgramFiles%、%SystemRoot%、\$HOME"
echo "    - 确需保留（如示例文本）→ 在该行加注释 abs-path-check: allow"
exit 1

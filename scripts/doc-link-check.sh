#!/usr/bin/env bash
# ================================================================
# doc-link-check.sh — 检查仓库内 Markdown 文档的相对链接是否全部可达
# ================================================================
# 用法:   bash scripts/doc-link-check.sh
# 退出码: 0 全部可达 / 1 发现死链
#
# 检查范围: docs/**/*.md + CLAUDE.md + README.md + README_cn.md + CONTRIBUTING.md
# 跳过:     http/https 外链、锚点（#...）、mailto / tel
# 支持:     URL 编码路径（%20 空格等）自动解码
#
# 被以下入口调用:
#   - .githooks/pre-commit
#   - .github/workflows/ci.yml（docs job）
#   - scripts/ci-check.sh（第 1 步）
# ================================================================

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEAD=0

echo "🔍 Checking document links..."

check_file() {
    local file="$1"
    local dir rel found_dead
    dir="$(dirname "$file")"
    rel="${file#"$ROOT"/}"
    found_dead=0

    # 用进程替换（而非管道）让 while 在当前 shell 执行，变量修改可传播。
    # 注意：DEAD 明细必须输出到 stderr——stdout 只用于回传计数，
    # 否则多行输出会破坏调用方的 `test "$count" -gt 0` 判断
    # （2026-09-29 由反向测试发现并修复）。
    while IFS= read -r link; do
        test -z "$link" && continue

        # 跳过外部链接 / 锚点 / 协议
        case "$link" in
            http://*|https://*|mailto:*|tel:*|'#'*) continue ;;
        esac

        # 解码 URL 编码（%20 → 空格等）
        link="$(printf '%b' "${link//%/\\x}")"
        # 去掉锚点后缀（path#section）
        link="${link%%#*}"
        test -z "$link" && continue

        # 解析为绝对路径
        case "$link" in
            /*) target="$ROOT$link" ;;
            *)  target="$dir/$link" ;;
        esac

        # 规范化路径（去掉 /./ 与 /../）
        target="$(cd "$(dirname "$target")" 2>/dev/null && pwd)/$(basename "$target")" || true

        if test -z "$target" || test ! -e "$target"; then
            echo "  DEAD: $rel -> $link" >&2
            found_dead=$((found_dead + 1))
        fi
    done < <(grep -o ']([^)]*)' "$file" 2>/dev/null | sed 's/^](//;s/)$//' || true)

    # stdout 只回传死链数量
    echo "$found_dead"
}

# 收集待检查文件
FILES=()
while IFS= read -r f; do
    FILES+=("$f")
done < <(find "$ROOT/docs" -name "*.md" -type f 2>/dev/null)
for f in "$ROOT/CLAUDE.md" "$ROOT/README.md" "$ROOT/README_cn.md" "$ROOT/CONTRIBUTING.md"; do
    test -f "$f" && FILES+=("$f")
done

for file in "${FILES[@]}"; do
    count="$(check_file "$file")"
    count="${count:-0}"
    if [ "$count" -gt 0 ] 2>/dev/null; then
        DEAD=1
    fi
done

if test "$DEAD" -eq 1; then
    echo ""
    echo "❌ 发现死链！请修复后再提交。"
    echo "   手动检查: bash scripts/doc-link-check.sh"
    exit 1
else
    echo "✅ 所有文档链接正常（共检查 ${#FILES[@]} 个文件）"
    exit 0
fi

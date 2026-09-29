#!/usr/bin/env bash
# ================================================================
# ci-check.sh — InsightGraph push 前本地全量检查
# （与 .github/workflows/ci.yml 的检查口径对应）
# ================================================================
# 用法:   bash scripts/ci-check.sh
# 退出码: 0 全部通过 / 1 存在失败
#
# 设计原则（借鉴 CoSense / love-lobster 的实证）:
#   1. 硬门禁 0 容忍：ruff / eslint 出现任何告警即 FAIL
#   2. backend/ frontend/ 尚未建立时自动跳过对应检查（SKIP，不算失败）
#   3. 文档死链检查始终执行
#   4. 不在本脚本跑真实 LLM 评测（成本与波动），
#      真实评测走手动触发的独立 workflow
# ================================================================

set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m'

pass() { echo -e "  ${GREEN}[PASS]${NC} $*"; }
fail() { echo -e "  ${RED}[FAIL]${NC} $*"; }
skip() { echo -e "  ${YELLOW}[SKIP]${NC} $*"; }

echo "================================================================"
echo "  InsightGraph — Pre-Push CI Check"
echo "================================================================"
echo ""

HAS_ERROR=0

# ================================================================
# 1. 文档死链检查
# ================================================================
echo -e "${CYAN}[1/4] Docs — 死链检查${NC}"
if bash "$ROOT/scripts/doc-link-check.sh"; then
    pass "文档链接全部可达"
else
    fail "发现死链，修复后重新运行"
    HAS_ERROR=1
fi

# ================================================================
# 2. 后端 — Ruff（0 错误 hard gate）+ Pytest（mock 单测）
# ================================================================
echo ""
echo -e "${CYAN}[2/4] Backend — Ruff + Pytest（mock 单测）${NC}"
if [ -f "$ROOT/backend/pyproject.toml" ]; then
    if ! command -v uv >/dev/null 2>&1; then
        fail "未找到 uv（安装: https://docs.astral.sh/uv/），无法运行后端检查"
        HAS_ERROR=1
    else
        echo "  ▶ Ruff"
        if (cd "$ROOT/backend" && uv run ruff check app/); then
            pass "Ruff"
        else
            fail "Ruff — 存在 lint 错误，修复后重新运行"
            HAS_ERROR=1
        fi
        echo "  ▶ Pytest（-m \"not integration\"）"
        if (cd "$ROOT/backend" && uv run pytest -m "not integration" -q); then
            pass "Pytest（mock 单测）"
        else
            fail "Pytest — 存在失败测试"
            HAS_ERROR=1
        fi
    fi
else
    skip "backend/ 尚未建立（Phase 2 建立后自动启用）"
fi

# ================================================================
# 3. 前端 — ESLint（0 警告 hard gate）+ tsc 类型检查
# ================================================================
echo ""
echo -e "${CYAN}[3/4] Frontend — ESLint + tsc${NC}"
if [ -f "$ROOT/frontend/package.json" ]; then
    echo "  ▶ ESLint"
    if (cd "$ROOT/frontend" && pnpm lint); then
        pass "ESLint"
    else
        fail "ESLint — 存在 warning/error"
        HAS_ERROR=1
    fi
    echo "  ▶ TypeScript（tsc -b；不要用 pnpm build --noEmit，见文档 §3.2）"
    if (cd "$ROOT/frontend" && pnpm exec tsc -b); then
        pass "TypeScript"
    else
        fail "TypeScript"
        HAS_ERROR=1
    fi
else
    skip "frontend/ 尚未建立（Phase 3 建立后自动启用）"
fi

# ================================================================
# 4. 安全门禁 — 疑似硬编码密钥扫描
# ================================================================
echo ""
echo -e "${CYAN}[4/4] Security — 疑似硬编码密钥扫描${NC}"
SUSPECTS=""
for scan_dir in backend/app frontend/src; do
    [ -d "$scan_dir" ] || continue
    hits=$(grep -rn -E '(sk-[A-Za-z0-9]{16,}|ghp_[A-Za-z0-9]{20,}|gho_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|xox[baprs]-[A-Za-z0-9-]{10,})' \
        "$scan_dir" \
        --include='*.py' --include='*.ts' --include='*.tsx' --include='*.js' \
        2>/dev/null | grep -v -E '(test_|\.spec\.|\.example)' || true)
    [ -n "$hits" ] && SUSPECTS="${SUSPECTS}${hits}
"
done

if [ -z "$SUSPECTS" ]; then
    pass "未发现疑似硬编码密钥"
else
    fail "发现疑似硬编码密钥（应改为环境变量读取）："
    echo "$SUSPECTS" | head -10
    HAS_ERROR=1
fi

# ================================================================
# Summary
# ================================================================
echo ""
echo "================================================================"
if [ "$HAS_ERROR" -eq 0 ]; then
    echo -e "  ${GREEN}All checks passed!${NC} Safe to push."
    echo "================================================================"
    exit 0
else
    echo -e "  ${RED}Some checks failed.${NC} Fix errors before pushing."
    echo "================================================================"
    exit 1
fi

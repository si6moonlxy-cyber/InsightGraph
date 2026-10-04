#!/usr/bin/env bash
# ================================================================
# poc-guard.sh — POC 代码隔离铁律 · 强制层（唯一真源）
# ================================================================
# 铁律（CLAUDE.md §二）：
#   1. POC 代码必须隔离在 poc/ 目录下（或独立分支），严禁合并入 dev / main 主分支。
#   2. POC 完成后，必须以正式架构纪律重写，方可进入生产代码。
#   3. POC 的唯一目标是验证技术可行性，不求代码质量。
#
# 执行点（三处，本脚本是唯一真源）：
#   - .githooks/pre-commit        （本地最早拦截）
#   - scripts/ci-check.sh         （push 前全量检查，含 pre-push 钩子调用）
#   - .github/workflows/ci.yml    （服务端 guard job，不可绕过）
#
# 检查项：
#   R1 主分支禁入：当前分支为 main / dev 时，不得存在被跟踪（含暂存）的 poc/ 文件。
#   R2 生产引用隔离：backend/app、frontend/src 中的代码不得 import / 引用 poc/。
#   R3 POC 自解释：poc/ 存在时必须包含非空 poc/README.md（spike 目标 / 验证结论 / 重写去向）。
#
# 用法:   bash scripts/poc-guard.sh
# 退出码: 0 通过 / 1 违规
# ================================================================

set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

pass() { echo -e "  ${GREEN}[PASS]${NC} $*"; }
fail() { echo -e "  ${RED}[FAIL]${NC} $*"; }

HAS_ERROR=0

# ---- 分支识别（本地 / CI 通用；CI checkout 用 GITHUB_REF_NAME）----
BRANCH="${GITHUB_REF_NAME:-}"
if [ -z "$BRANCH" ] || [ "$BRANCH" = "HEAD" ]; then
    BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo '')"
    [ "$BRANCH" = "HEAD" ] && BRANCH=""
fi

echo "▶ [poc-guard] POC 隔离铁律检查（分支: ${BRANCH:-未知}）"

# ================================================================
# R1 主分支禁入：main / dev 不得出现被跟踪的 poc/
# ================================================================
case "$BRANCH" in
    main|dev)
        POC_TRACKED="$(git ls-files -- poc/ 2>/dev/null || true)"
        if [ -n "$POC_TRACKED" ]; then
            fail "R1 主分支禁入：${BRANCH} 上存在被跟踪的 poc/ 文件（铁律：POC 严禁合并入 dev / main）"
            echo "$POC_TRACKED" | head -5 | sed 's/^/       /'
            echo "       → 处理：把 poc/ 移到独立分支（如 poc/spike-xxx）并从主分支删除该目录"
            HAS_ERROR=1
        else
            pass "R1 主分支禁入：${BRANCH} 上无 poc/ 内容"
        fi
        ;;
    *)
        if [ -n "$BRANCH" ]; then
            pass "R1 主分支禁入：当前非 main / dev（${BRANCH}），poc/ 允许存在"
        else
            echo -e "  ${YELLOW}[SKIP]${NC} R1 无法识别分支（detached HEAD），跳过主分支禁入检查"
        fi
        ;;
esac

# ================================================================
# R2 生产引用隔离：生产代码不得 import / 引用 poc
# ================================================================
POC_REF_PATTERN='(import[[:space:]]+poc([^A-Za-z0-9_]|$))|(from[[:space:]]+poc([.][A-Za-z0-9_]+)?[[:space:]]+import)|([^A-Za-z0-9_]poc/)'
POC_REF_HITS=""
for scan_dir in backend/app frontend/src; do
    [ -d "$scan_dir" ] || continue
    hits="$(grep -rn -E "$POC_REF_PATTERN" "$scan_dir" \
        --include='*.py' --include='*.ts' --include='*.tsx' --include='*.js' 2>/dev/null || true)"
    [ -n "$hits" ] && POC_REF_HITS="${POC_REF_HITS}${hits}
"
done

if [ -z "$POC_REF_HITS" ]; then
    pass "R2 生产引用隔离：生产代码未引用 poc"
else
    fail "R2 生产引用隔离：生产代码引用了 poc（POC 必须以正式架构纪律重写后才能进生产）："
    echo "$POC_REF_HITS" | head -5 | sed 's/^/       /'
    HAS_ERROR=1
fi

# ================================================================
# R3 POC 自解释：poc/ 存在时必须带非空 README.md
# ================================================================
if [ -d poc ]; then
    if [ -s poc/README.md ]; then
        pass "R3 POC 自解释：poc/README.md 存在且非空"
    else
        fail "R3 POC 自解释：poc/ 缺少非空 README.md（需写明 spike 目标 / 验证结论 / 重写去向）"
        HAS_ERROR=1
    fi
else
    pass "R3 POC 自解释：当前无 poc/（无需检查）"
fi

exit "$HAS_ERROR"

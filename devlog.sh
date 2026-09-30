#!/usr/bin/env bash
# ================================================================
# devlog.sh — InsightGraph 开发日志一键同步
# ================================================================
# 在 dev-log 分支的工作树（.devlog/）内运行。
#
# 用法:
#   bash devlog.sh sync [提交说明]     # 提交说明可选，默认 "dlog: 更新开发日志"
#   bash devlog.sh pull                # 仅拉取（不提交不推送；供 start.bat 等自动化调用）
#
# 流程:
#   [1] 格式校验（scripts/check-devlog.sh，错误则中止）
#   [2] 有改动 → 提交 DEV_LOG.md
#   [3] pull --rebase（冲突则中止并提示手动处理）
#   [4] push；被拒自动重试（最多 3 轮）
#
# 首次使用（无上游跟踪）: 自动执行 git push -u origin dev-log
# ================================================================

set -uo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

CMD="${1:-sync}"
MSG="${2:-dlog: 更新开发日志}"

case "$CMD" in
    sync) ;;
    pull) ;;
    *)
        echo "用法: bash devlog.sh sync [提交说明]   # 校验 + 提交 + 拉取 + 推送"
        echo "      bash devlog.sh pull              # 仅拉取（供 start.bat 等自动化调用）"
        exit 1
        ;;
esac

# ── pull：仅拉取，不提交、不推送、失败静默 ──
if [ "$CMD" = "pull" ]; then
    echo "▶ [pull] 拉取最新开发日志..."
    if [ -n "$(git status --porcelain)" ]; then
        echo "ℹ️  工作区有未提交改动，跳过拉取（处理后请跑: bash devlog.sh sync）"
        exit 0
    fi
    if ! git rev-parse --abbrev-ref '@{upstream}' >/dev/null 2>&1; then
        echo "ℹ️  尚未建立上游跟踪，请先跑一次: bash devlog.sh sync"
        exit 0
    fi
    if ! git pull --rebase --quiet; then
        echo "ℹ️  拉取失败（离线或冲突），已跳过，不影响本地使用"
        exit 0
    fi
    NEW="$(git log --oneline ORIG_HEAD..HEAD 2>/dev/null || true)"
    if [ -n "$NEW" ]; then
        echo "✅ 拉到新更新："
        echo "$NEW" | sed 's/^/   /'
    else
        echo "✅ 已是最新"
    fi
    exit 0
fi

# ── [1] 格式校验 ──
echo "▶ [1/4] 校验 DEV_LOG.md 格式..."
if ! bash "$ROOT/scripts/check-devlog.sh"; then
    echo ""
    echo "❌ 格式校验未通过，已中止（修正 DEV_LOG.md 后重新运行）"
    exit 1
fi

# ── [2] 提交本地改动 ──
echo ""
echo "▶ [2/4] 提交本地改动..."
if [ -n "$(git status --porcelain DEV_LOG.md)" ]; then
    git add DEV_LOG.md
    git commit -m "$MSG"
else
    echo "  （DEV_LOG.md 无改动，跳过提交）"
fi

# ── 首次使用：无上游跟踪 → 建立 ──
if ! git rev-parse --abbrev-ref '@{upstream}' >/dev/null 2>&1; then
    echo ""
    echo "▶ [3/4] 首次同步：git push -u origin dev-log ..."
    if git push -u origin dev-log; then
        echo ""
        echo "✅ 首次同步完成（已建立上游跟踪，之后直接 bash devlog.sh sync）"
        exit 0
    fi
    echo "❌ 首次推送失败，请检查网络与仓库权限后重试"
    exit 1
fi

# ── [3]+[4] 拉取 + 推送（被拒自动重试） ──
for attempt in 1 2 3; do
    echo ""
    echo "▶ [3/4] 拉取最新（第 ${attempt} 轮）: git pull --rebase ..."
    if ! git pull --rebase; then
        echo ""
        echo "❌ pull --rebase 出现冲突（大概率两人改了同一行）。手动处理："
        echo "   1) 打开 DEV_LOG.md 解决冲突"
        echo "   2) git add DEV_LOG.md"
        echo "   3) git rebase --continue"
        echo "   4) 重新运行: bash devlog.sh sync"
        exit 1
    fi

    echo "▶ [4/4] 推送（第 ${attempt} 轮）: git push ..."
    if git push; then
        echo ""
        echo "✅ 同步完成"
        exit 0
    fi

    echo "⚠️  push 被拒（对方抢先提交），自动重新拉取后重试..."
done

echo ""
echo "❌ 重试 3 轮仍失败，请手动检查 git status 与网络后重试"
exit 1

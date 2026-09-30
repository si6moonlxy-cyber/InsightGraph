#!/usr/bin/env bash
# ================================================================
# check-devlog.sh — DEV_LOG.md 格式与陈旧条目检查（本地 / CI 共用）
# ================================================================
# 用法:   bash scripts/check-devlog.sh
# 退出码: 0 通过（可能有 WARN） / 1 存在格式错误
#
# 校验项:
#   - 区块标题:  ## 名字（分支）
#   - 条目格式:  - [yyyy-mm-dd] 一句话任务 @区域/模块
#   - 日期合法（不合法 → ERROR）
#   - 陈旧提醒:  超过 7 天未更新 → WARN（不阻断）；日期在未来 → WARN
# ================================================================

set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FILE="$ROOT/DEV_LOG.md"
STALE_DAYS=7

ERRORS=0
WARNINGS=0

err() { echo "  [ERROR] $*"; if [ "${CI:-}" = "true" ]; then echo "::error file=DEV_LOG.md::$*"; fi; ERRORS=$((ERRORS + 1)); }
warn() { echo "  [WARN]  $*"; if [ "${CI:-}" = "true" ]; then echo "::warning file=DEV_LOG.md::$*"; fi; WARNINGS=$((WARNINGS + 1)); }

if [ ! -f "$FILE" ]; then
    echo "  [ERROR] 缺少 DEV_LOG.md（唯一真源应位于 dev-log 分支根目录）"
    exit 1
fi

# GNU date 优先，BSD/macOS date 兜底
to_epoch() {
    date -d "$1" +%s 2>/dev/null || date -j -f "%Y-%m-%d" "$1" +%s 2>/dev/null
}

TODAY="$(date +%s)"
NLINE=0
SECTION_COUNT=0
ENTRY_COUNT=0

while IFS= read -r line; do
    NLINE=$((NLINE + 1))

    case "$line" in
        '## '*)
            SECTION_COUNT=$((SECTION_COUNT + 1))
            if [[ ! "$line" =~ ^##\ .+（.+）$ ]]; then
                err "第 ${NLINE} 行: 区块标题格式应为「## 名字（分支）」（发现: $line）"
            fi
            ;;
        '- '*)
            ENTRY_COUNT=$((ENTRY_COUNT + 1))
            if [[ ! "$line" =~ ^-\ \[[0-9]{4}-[0-9]{2}-[0-9]{2}\]\ .+\ @.+$ ]]; then
                err "第 ${NLINE} 行: 条目格式应为「- [yyyy-mm-dd] 一句话任务 @区域/模块」（发现: $line）"
                continue
            fi
            d="${line:3:10}"
            ts="$(to_epoch "$d")"
            if [ -z "$ts" ]; then
                err "第 ${NLINE} 行: 日期不合法: $d"
                continue
            fi
            if [ "$ts" -gt "$TODAY" ]; then
                warn "第 ${NLINE} 行: 日期在未来（$d），确认是否笔误"
            elif [ $(( (TODAY - ts) / 86400 )) -gt "$STALE_DAYS" ]; then
                warn "第 ${NLINE} 行: 已 $(( (TODAY - ts) / 86400 )) 天未更新（阈值 ${STALE_DAYS} 天），确认是否已完成并删除本行"
            fi
            ;;
    esac
done < "$FILE"

if [ "$SECTION_COUNT" -eq 0 ]; then
    err "没有任何区块（至少应有每人一个「## 名字（分支）」区块）"
fi

echo "  DEV_LOG.md: ${SECTION_COUNT} 个区块 / ${ENTRY_COUNT} 条任务；ERROR=${ERRORS} WARN=${WARNINGS}"

if [ "$ERRORS" -gt 0 ]; then
    echo ""
    echo "❌ 存在格式错误，请修正后重试"
    exit 1
fi

if [ "$WARNINGS" -gt 0 ]; then
    echo ""
    echo "⚠️  有 ${WARNINGS} 条提醒（不阻断，但请尽快清理陈旧条目）"
fi

echo "✅ 格式校验通过"
exit 0

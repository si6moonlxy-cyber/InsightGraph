"""引擎符号类型到 Canonical NodeKind 的白名单映射。"""

from app.domain.codegraph.kinds import NodeKind


def map_symbol_kind(raw_kind: str | None) -> NodeKind | None:
    if raw_kind is None:
        return None
    normalized = raw_kind.casefold()
    if normalized in {"function", "method"}:
        return NodeKind.FUNCTION
    if normalized == "class":
        return NodeKind.CLASS
    return None

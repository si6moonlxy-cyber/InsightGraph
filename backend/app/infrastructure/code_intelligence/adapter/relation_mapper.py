"""外部关系类型白名单。"""

from app.domain.codegraph.kinds import EdgeKind


def map_relation_kind(raw_type: str) -> EdgeKind | None:
    return EdgeKind.CALLS if raw_type.casefold() == "calls" else None

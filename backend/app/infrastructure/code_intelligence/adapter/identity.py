"""引擎符号到 Canonical 节点身份的保守匹配。"""

from pathlib import Path

from app.domain.codegraph.kinds import NodeKind
from app.domain.codegraph.models import CodeNode
from app.infrastructure.code_intelligence.adapter.span_mapper import line_matches
from app.infrastructure.code_intelligence.adapter.symbol_mapper import map_symbol_kind
from app.infrastructure.code_intelligence.raw_models.symbol import RawSymbol


def match_canonical_node(raw: RawSymbol, nodes: tuple[CodeNode, ...], root: Path) -> CodeNode | None:
    path_text = _relative_posix(raw.path, root)
    if path_text is None:
        return None
    mapped_kind = map_symbol_kind(raw.kind)
    candidates = [
        node
        for node in nodes
        if node.kind in {NodeKind.FUNCTION, NodeKind.CLASS}
        and (mapped_kind is None or node.kind is mapped_kind)
        and node.source.file_path.casefold() == path_text.casefold()
        and line_matches(raw.line_start, node)
    ]
    named = [node for node in candidates if node.qualified_name.rsplit(".", 1)[-1] == raw.name]
    if named:
        candidates = named
    return candidates[0] if len(candidates) == 1 else None


def _relative_posix(raw_path: str, root: Path) -> str | None:
    normalized_raw = raw_path.replace("\\", "/")
    normalized_root = str(root.resolve()).replace("\\", "/").rstrip("/")
    prefix = normalized_root + "/"
    if normalized_raw.casefold().startswith(prefix.casefold()):
        return normalized_raw[len(prefix) :]
    path = Path(raw_path)
    if not path.is_absolute():
        return path.as_posix()
    return None

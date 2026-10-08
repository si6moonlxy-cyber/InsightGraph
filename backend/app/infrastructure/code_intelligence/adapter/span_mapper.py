"""引擎节点行号定位规则。"""

from app.domain.codegraph.models import CodeNode


def line_matches(raw_line_1based: int, node: CodeNode) -> bool:
    """实测 CodeGraphAI v0.20.1 使用 1-based 行号；边界保留 ±1 容错。"""
    return node.source.line_start - 1 <= raw_line_1based <= node.source.line_end + 1

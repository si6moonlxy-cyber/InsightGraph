"""CodeGraph 稳定 ID 的纯函数构造规则。

ID 不含 revision：GraphRAG 与 datamodel 通过稳定 ID 跨层引用 CodeGraph 节点
（ADR-001 / ADR-008），引用必须在新提交后继续有效；扫描作用域由
CodeGraph 的 repository_id + revision 界定。完整决策见 ADR-010。

边 ID 解析规则：两侧 ID 自身含 `:`，解析时先按第一个 `->` 切分 source 与 target，
再从左侧按第一个 `:` 切出 kind（kind 为闭枚举，无歧义）。
"""

from app.domain.codegraph.kinds import EdgeKind, NodeKind

_SEPARATOR = ":"
_DUPLICATE_MARK = "#"


def validate_repository_id(repository_id: str) -> str:
    """repository_id 是 ID 前缀，必须非空且不含分隔符 ":"。"""
    if not repository_id:
        raise ValueError("repository_id 不能为空")
    if _SEPARATOR in repository_id:
        raise ValueError("repository_id 不得包含 ':'")
    return repository_id


def build_node_id(
    repository_id: str,
    kind: NodeKind,
    qualified_name: str,
    *,
    duplicate_index: int | None = None,
) -> str:
    """构造节点 ID：{repository_id}:{kind}:{qualified_name}[#{n}]。

    duplicate_index 仅用于同一 (kind, qualified_name) 在仓库内出现多个定义
    （如 @overload 桩、条件分支定义）时，按 line_start 升序的第 2..N 个定义；
    首个定义保持裸名，传 None。
    """
    if not qualified_name:
        raise ValueError("qualified_name 不能为空")
    node_id = _SEPARATOR.join((validate_repository_id(repository_id), str(kind), qualified_name))
    if duplicate_index is None:
        return node_id
    if duplicate_index < 2:
        raise ValueError("duplicate_index 从 2 开始；首个定义不带后缀")
    return f"{node_id}{_DUPLICATE_MARK}{duplicate_index}"


def node_id_matches(
    node_id: str,
    repository_id: str,
    kind: NodeKind,
    qualified_name: str,
) -> bool:
    """校验候选 ID 是否符合构造规则（含重名后缀）。"""
    base = build_node_id(repository_id, kind, qualified_name)
    prefix = f"{base}{_DUPLICATE_MARK}"
    if node_id == base:
        return True
    if not node_id.startswith(prefix):
        return False
    suffix = node_id[len(prefix) :]
    return suffix.isdigit() and int(suffix) >= 2


def build_edge_id(kind: EdgeKind, source_id: str, target_id: str) -> str:
    """构造边 ID：{kind}:{source_id}->{target_id}；同一关系只保留一条边。"""
    if not source_id or not target_id:
        raise ValueError("edge 的 source_id 与 target_id 不能为空")
    return f"{kind}{_SEPARATOR}{source_id}->{target_id}"

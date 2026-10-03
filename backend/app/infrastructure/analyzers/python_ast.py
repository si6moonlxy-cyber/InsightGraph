"""Python AST 分析器：把 SourceManifest 转换为基础 CodeGraph IR。

口径（ADR-010 / ADR-011 + 步骤 4 决策记录）：
- 模块节点：清单中每个 `.py` 文件一个 Module 节点；qualified_name 为仓库相对路径
  点号化（`__init__.py` 映射为包名，如 `app/utils/__init__.py` → `app.utils`）；
  span 覆盖全文件（空文件为 1..1）。模块名按路径字面推导：路径片段含非标识符
  字符（如连字符，常见于夹具目录或直接执行的脚本）时按字面保留，不做改写。
- Class / Function 节点：qualified name 遵循 Python `__qualname__` 语义
  （嵌套定义使用 `<locals>`）；span 起始行包含装饰器行；`content_hash` 为
  span 源文本（CRLF 已归一）的 SHA-256；重名定义按行号序追加 `#2`..（ADR-010）。
- 边：DEFINES（module → class/function、class → method、function → 嵌套定义）与
  IMPORTS（module → module）。IMPORTS 解析规则：`import a.b` → 解析 `a.b`；
  `from M import n` → 解析 `M`，且当 `M.n` 为仓库内子模块时追加解析 `M.n`；
  `from . import n` → 当前包，子模块同理；相对导入按层级上溯补全。解析方式为
  精确匹配 → 唯一包边界后缀匹配 → 失败不建边（第三方 / stdlib / 歧义不建边，
  留待步骤 5 引入 resolved / ambiguous / unresolved 状态）。
- 失败：单文件错误（syntax_error / file_encoding / file_disappeared /
  file_unreadable）为局部失败，不中断整体；根目录不存在为 fatal；
  清单中的非 `.py` 项静默跳过。
"""

import ast
import asyncio
import hashlib
from dataclasses import dataclass
from pathlib import Path

from app.application.scans.models import (
    AnalyzeOutcome,
    ScanError,
    ScanErrorCode,
    ScanErrorSeverity,
    ScanRequest,
    ScanStage,
    SourceManifest,
)
from app.domain.codegraph.ids import build_edge_id, build_node_id
from app.domain.codegraph.kinds import EdgeKind, NodeKind
from app.domain.codegraph.models import CodeEdge, CodeGraph, CodeNode, SourceSpan

PARSER_VERSION = "python-ast/0.1"


@dataclass
class _ParsedFile:
    """单文件解析产物：路径、模块名与按行切分的源码。"""

    path_text: str
    module_name: str
    is_package: bool
    lines: list[bytes]
    tree: ast.Module


@dataclass
class _Definition:
    """类 / 函数定义（含嵌套），parent_index 指向外层定义；None 表示父为模块。"""

    kind: NodeKind
    qualified_name: str
    line_start: int
    line_end: int
    parent_index: int | None


class PythonAstAnalyzer:
    """CodeAnalyzer 的 Python 标准库 AST 实现。

    request.path 必须为仓库根（由 Collector 的管道不变量保证）；
    本分析器直接以该路径为 base 拼接 manifest 内相对路径，不做子目录推导。
    """

    async def analyze(self, request: ScanRequest, manifest: SourceManifest) -> AnalyzeOutcome:
        """异步外壳；解析与文件 IO 在线程中执行，不阻塞事件循环。"""
        return await asyncio.to_thread(self._analyze_sync, request, manifest)

    def _analyze_sync(self, request: ScanRequest, manifest: SourceManifest) -> AnalyzeOutcome:
        root = request.path
        if not root.is_dir():
            return _fatal(f"仓库根目录不存在或不是目录: {root}")

        errors: list[ScanError] = []
        parsed_files: list[_ParsedFile] = []
        for source_file in manifest.files:
            if not source_file.path.endswith(".py"):
                continue
            parsed = _parse_file(root, source_file.path, errors)
            if parsed is not None:
                parsed_files.append(parsed)

        module_names = {parsed.module_name for parsed in parsed_files}
        nodes: list[CodeNode] = []
        edges: list[CodeEdge] = []
        for parsed in parsed_files:
            file_nodes, file_edges = _build_file_graph(manifest.repository_id, parsed, module_names)
            nodes.extend(file_nodes)
            edges.extend(file_edges)

        # 统一排序，保证字节级确定性输出
        nodes.sort(key=lambda node: node.id)
        edges.sort(key=lambda edge: edge.id)

        graph = CodeGraph(
            repository_id=manifest.repository_id,
            revision=manifest.revision,
            parser_version=PARSER_VERSION,
            nodes=tuple(nodes),
            edges=tuple(edges),
        )
        return AnalyzeOutcome(graph=graph, errors=tuple(errors))


def _parse_file(root: Path, path_text: str, errors: list[ScanError]) -> _ParsedFile | None:
    """读取并解析单文件；任何局部失败登记错误并返回 None，不中断整体。"""
    try:
        data = (root / path_text).read_bytes()
    except FileNotFoundError:
        errors.append(_local_error(ScanErrorCode.FILE_DISAPPEARED, "文件在分析期间消失", path_text))
        return None
    except OSError as error:
        errors.append(_local_error(ScanErrorCode.FILE_UNREADABLE, f"文件无法读取: {error}", path_text))
        return None

    normalized = data.replace(b"\r\n", b"\n")
    try:
        text = normalized.decode("utf-8")
    except UnicodeDecodeError:
        errors.append(_local_error(ScanErrorCode.FILE_ENCODING, "内容不是有效 UTF-8", path_text))
        return None

    try:
        tree = ast.parse(text, filename=path_text)
    except (SyntaxError, ValueError) as error:
        errors.append(_local_error(ScanErrorCode.SYNTAX_ERROR, f"语法错误: {error}", path_text))
        return None

    return _ParsedFile(
        path_text=path_text,
        module_name=_module_name(path_text),
        is_package=path_text.endswith("__init__.py"),
        lines=normalized.splitlines(keepends=True),
        tree=tree,
    )


def _module_name(path_text: str) -> str:
    """仓库相对路径 → 模块点号名；`__init__.py` 映射为包名。"""
    parts = path_text.split("/")
    if parts[-1] == "__init__.py":
        parts = parts[:-1]
        if not parts:
            return "__init__"  # 仓库根级 __init__.py 的退化处理
    else:
        parts[-1] = parts[-1][: -len(".py")]
    return ".".join(parts)


def _build_file_graph(
    repository_id: str,
    parsed: _ParsedFile,
    module_names: set[str],
) -> tuple[list[CodeNode], list[CodeEdge]]:
    """单文件 → 节点与边；重名序号按收集顺序（文档序 / 行号序）分配。"""
    lines = parsed.lines
    total_lines = max(1, len(lines))
    module_id = build_node_id(repository_id, NodeKind.MODULE, parsed.module_name)
    nodes: list[CodeNode] = [
        CodeNode(
            id=module_id,
            kind=NodeKind.MODULE,
            qualified_name=parsed.module_name,
            language="python",
            source=SourceSpan(file_path=parsed.path_text, line_start=1, line_end=total_lines),
            content_hash=_span_hash(lines, 1, total_lines),
        )
    ]

    defs: list[_Definition] = []
    for statement in parsed.tree.body:
        _walk_statements(statement, parent_qual=parsed.module_name, parent_kind=None, parent_index=None, defs=defs)

    def_ids: list[str] = []
    ordinals: dict[tuple[NodeKind, str], int] = {}
    for definition in defs:
        key = (definition.kind, definition.qualified_name)
        ordinals[key] = ordinals.get(key, 0) + 1
        occurrence = ordinals[key]
        node_id = build_node_id(
            repository_id,
            definition.kind,
            definition.qualified_name,
            duplicate_index=None if occurrence == 1 else occurrence,
        )
        def_ids.append(node_id)
        nodes.append(
            CodeNode(
                id=node_id,
                kind=definition.kind,
                qualified_name=definition.qualified_name,
                language="python",
                source=SourceSpan(
                    file_path=parsed.path_text,
                    line_start=definition.line_start,
                    line_end=definition.line_end,
                ),
                content_hash=_span_hash(lines, definition.line_start, definition.line_end),
            )
        )

    edges: list[CodeEdge] = []
    edge_keys: set[tuple[str, str, str]] = set()
    for index, definition in enumerate(defs):
        source_id = module_id if definition.parent_index is None else def_ids[definition.parent_index]
        _add_edge(edges, edge_keys, EdgeKind.DEFINES, source_id, def_ids[index])
    for target_module in _imported_modules(parsed, module_names):
        _add_edge(
            edges, edge_keys, EdgeKind.IMPORTS, module_id, build_node_id(repository_id, NodeKind.MODULE, target_module)
        )
    return nodes, edges


def _walk_statements(
    statement: ast.stmt,
    *,
    parent_qual: str,
    parent_kind: NodeKind | None,
    parent_index: int | None,
    defs: list[_Definition],
) -> None:
    """遍历语句：定义语句建节点，容器语句（if/for/try/…）保持作用域继续下潜。"""
    if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        kind = NodeKind.CLASS if isinstance(statement, ast.ClassDef) else NodeKind.FUNCTION
        qualified_name = _child_qualname(
            parent_qual, statement.name, parent_is_function=parent_kind is NodeKind.FUNCTION
        )
        index = len(defs)
        defs.append(
            _Definition(
                kind=kind,
                qualified_name=qualified_name,
                line_start=_definition_start_line(statement),
                line_end=statement.end_lineno if statement.end_lineno is not None else statement.lineno,
                parent_index=parent_index,
            )
        )
        for block in _nested_blocks(statement):
            for child in block:
                _walk_statements(child, parent_qual=qualified_name, parent_kind=kind, parent_index=index, defs=defs)
        return
    for block in _nested_blocks(statement):
        for child in block:
            _walk_statements(
                child, parent_qual=parent_qual, parent_kind=parent_kind, parent_index=parent_index, defs=defs
            )


def _nested_blocks(node: ast.stmt) -> list[list[ast.stmt]]:
    """返回语句包含的嵌套语句块（不改变限定名父级；异常处理器与 match 分支同层处理）。"""
    blocks: list[list[ast.stmt]] = []
    body = getattr(node, "body", None)
    if isinstance(body, list):
        blocks.append(body)
    if isinstance(node, (ast.If, ast.For, ast.AsyncFor, ast.While)):
        blocks.append(node.orelse)
    elif isinstance(node, ast.Try):
        blocks.extend(handler.body for handler in node.handlers)
        blocks.append(node.orelse)
        blocks.append(node.finalbody)
    elif isinstance(node, ast.Match):
        blocks.extend(case.body for case in node.cases)
    return blocks


def _child_qualname(parent_qual: str, name: str, *, parent_is_function: bool) -> str:
    """生成子定义限定名，遵循 CPython `__qualname__` 的 `<locals>` 约定。"""
    separator = ".<locals>." if parent_is_function else "."
    return f"{parent_qual}{separator}{name}"


def _definition_start_line(node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) -> int:
    """定义起始行：包含装饰器时取最早装饰器行。"""
    if node.decorator_list:
        return min(decorator.lineno for decorator in node.decorator_list)
    return node.lineno


def _span_hash(lines: list[bytes], line_start: int, line_end: int) -> str:
    """span 源文本（CRLF 已归一）的 SHA-256。"""
    span_bytes = b"".join(lines[line_start - 1 : line_end])
    return f"sha256:{hashlib.sha256(span_bytes).hexdigest()}"


def _package_of(parsed: _ParsedFile) -> str:
    """当前模块所属包名；顶层模块返回空串。"""
    if parsed.is_package:
        return parsed.module_name
    if "." in parsed.module_name:
        return parsed.module_name.rsplit(".", 1)[0]
    return ""


def _imported_modules(parsed: _ParsedFile, module_names: set[str]) -> list[str]:
    """提取文件内全部 import 语句解析出的仓库内目标模块（去重、保持遍历序）。"""
    package = _package_of(parsed)
    targets: list[str] = []

    def add(candidate: str | None) -> None:
        if not candidate:
            return
        resolved = _resolve_module(candidate, module_names)
        if resolved is not None and resolved not in targets:
            targets.append(resolved)

    for node in ast.walk(parsed.tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            base = _import_from_base(node, package)
            if base:
                add(base)
                for alias in node.names:
                    add(f"{base}.{alias.name}")
    return targets


def _import_from_base(node: ast.ImportFrom, package: str) -> str | None:
    """`from` 导入的基准模块候选：绝对导入用 module，相对导入按层级上溯补全。"""
    if node.level == 0:
        return node.module
    if not package:
        return None  # 顶层模块无法进行相对导入
    ascended = _ascend_package(package, node.level - 1)
    if ascended is None:
        return None
    if node.module:
        return f"{ascended}.{node.module}" if ascended else node.module
    return ascended


def _ascend_package(package: str, levels: int) -> str | None:
    """把包名向上回溯 levels 层；越出顶层返回 None。"""
    parts = package.split(".")
    if levels >= len(parts):
        return None
    if levels == 0:
        return package
    return ".".join(parts[: len(parts) - levels])


def _resolve_module(candidate: str, module_names: set[str]) -> str | None:
    """导入目标解析：精确匹配 → 唯一包边界后缀匹配 → 失败返回 None。"""
    if candidate in module_names:
        return candidate
    suffix = "." + candidate
    matches = [name for name in module_names if name.endswith(suffix)]
    if len(matches) == 1:
        return matches[0]
    return None


def _add_edge(
    edges: list[CodeEdge],
    edge_keys: set[tuple[str, str, str]],
    kind: EdgeKind,
    source_id: str,
    target_id: str,
) -> None:
    """追加去重后的边；自引用不建边。"""
    if source_id == target_id:
        return
    key = (kind.value, source_id, target_id)
    if key in edge_keys:
        return
    edge_keys.add(key)
    edges.append(
        CodeEdge(
            id=build_edge_id(kind, source_id, target_id),
            kind=kind,
            source_id=source_id,
            target_id=target_id,
        )
    )


def _local_error(code: ScanErrorCode, message: str, file_path: str) -> ScanError:
    return ScanError(
        stage=ScanStage.ANALYZE,
        code=code,
        severity=ScanErrorSeverity.LOCAL,
        message=message,
        file_path=file_path,
    )


def _fatal(message: str) -> AnalyzeOutcome:
    return AnalyzeOutcome(
        errors=(
            ScanError(
                stage=ScanStage.ANALYZE,
                code=ScanErrorCode.PATH_INVALID,
                severity=ScanErrorSeverity.FATAL,
                message=message,
            ),
        )
    )

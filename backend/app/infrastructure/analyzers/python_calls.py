"""Python 调用关系补扫器：以保守、确定性的浅绑定产生 CALLS 事实。"""

import ast
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from app.application.scans.models import CallFunnel
from app.domain.codegraph.kinds import CallResolution, NodeKind
from app.domain.codegraph.models import SourceSpan

MAX_AMBIGUOUS_CANDIDATES = 5


class ParsedPythonFile(Protocol):
    """补扫器所需的最小解析文件视图。"""

    path_text: str
    module_name: str
    is_package: bool
    tree: ast.Module


@dataclass(frozen=True)
class DefinitionSymbol:
    """AST 定义与 Canonical 节点之间的进程内映射。"""

    node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef
    node_id: str
    kind: NodeKind
    qualified_name: str
    module_name: str


@dataclass(frozen=True)
class CallFact:
    """可物化为 CALLS 边的单个候选事实。"""

    source_id: str
    target_id: str
    resolution: CallResolution
    call_span: SourceSpan
    is_truncated: bool = False


@dataclass
class _MutableFunnel:
    dynamic: int = 0
    unresolved: int = 0
    oversized: int = 0


@dataclass(frozen=True)
class _Bindings:
    module_targets: dict[str, str]
    symbol_targets: dict[str, tuple[str, ...]]
    class_targets: dict[str, tuple[DefinitionSymbol, ...]]


def scan_python_calls(
    parsed_files: Sequence[ParsedPythonFile],
    symbols: list[DefinitionSymbol],
    module_ids: dict[str, str],
) -> tuple[list[CallFact], CallFunnel]:
    """扫描全部调用点；dynamic/unresolved 只进入漏斗，不产生边。"""
    by_module: dict[str, list[DefinitionSymbol]] = {}
    by_node = {id(symbol.node): symbol for symbol in symbols}
    for symbol in symbols:
        by_module.setdefault(symbol.module_name, []).append(symbol)
    facts: list[CallFact] = []
    funnel = _MutableFunnel()
    module_names = set(module_ids)
    for parsed in parsed_files:
        bindings = _build_bindings(parsed, by_module, module_names)
        _scan_scope(
            parsed.tree.body,
            parsed=parsed,
            source_id=module_ids[parsed.module_name],
            current_class=None,
            parameters=set(),
            bindings=bindings,
            by_module=by_module,
            by_node=by_node,
            facts=facts,
            funnel=funnel,
        )
    facts.sort(key=lambda fact: (fact.source_id, fact.call_span.line_start, fact.call_span.line_end, fact.target_id))
    return facts, CallFunnel(
        calls_dynamic=funnel.dynamic,
        calls_unresolved=funnel.unresolved,
        oversized_ambiguous_calls=funnel.oversized,
    )


def _build_bindings(
    parsed: ParsedPythonFile,
    by_module: dict[str, list[DefinitionSymbol]],
    module_names: set[str],
) -> _Bindings:
    module_targets: dict[str, str] = {}
    symbol_targets: dict[str, list[str]] = {}
    class_targets: dict[str, list[DefinitionSymbol]] = {}
    for symbol in by_module.get(parsed.module_name, []):
        if _is_top_level(symbol.qualified_name, parsed.module_name):
            name = symbol.node.name
            symbol_targets.setdefault(name, []).append(symbol.node_id)
            if symbol.kind is NodeKind.CLASS:
                class_targets.setdefault(name, []).append(symbol)
    package = parsed.module_name if parsed.is_package else parsed.module_name.rpartition(".")[0]
    for statement in parsed.tree.body:
        if isinstance(statement, ast.Import):
            for alias in statement.names:
                resolved = _resolve_module(alias.name, module_names)
                if resolved is not None:
                    bound = alias.asname or alias.name.split(".")[0]
                    module_targets[bound] = resolved
        elif isinstance(statement, ast.ImportFrom):
            base = _import_from_base(statement, package)
            resolved_base = _resolve_module(base, module_names) if base else None
            for alias in statement.names:
                bound = alias.asname or alias.name
                child_module = _resolve_module(f"{base}.{alias.name}", module_names) if base else None
                if child_module is not None:
                    module_targets[bound] = child_module
                    continue
                if resolved_base is None:
                    continue
                matches = [item for item in by_module.get(resolved_base, []) if item.node.name == alias.name]
                if matches:
                    symbol_targets.setdefault(bound, []).extend(item.node_id for item in matches)
                    class_matches = [item for item in matches if item.kind is NodeKind.CLASS]
                    if class_matches:
                        class_targets.setdefault(bound, []).extend(class_matches)
    return _Bindings(
        module_targets=module_targets,
        symbol_targets={name: tuple(sorted(values)) for name, values in symbol_targets.items()},
        class_targets={
            name: tuple(sorted(values, key=lambda item: item.node_id)) for name, values in class_targets.items()
        },
    )


def _scan_scope(
    statements: list[ast.stmt],
    *,
    parsed: ParsedPythonFile,
    source_id: str,
    current_class: DefinitionSymbol | None,
    parameters: set[str],
    bindings: _Bindings,
    by_module: dict[str, list[DefinitionSymbol]],
    by_node: dict[int, DefinitionSymbol],
    facts: list[CallFact],
    funnel: _MutableFunnel,
) -> None:
    local_instances = _local_instance_bindings(statements, bindings)
    for statement in statements:
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
            symbol = by_node[id(statement)]
            owner_class = current_class
            _scan_scope(
                statement.body,
                parsed=parsed,
                source_id=symbol.node_id,
                current_class=owner_class,
                parameters=_parameter_names(statement.args),
                bindings=bindings,
                by_module=by_module,
                by_node=by_node,
                facts=facts,
                funnel=funnel,
            )
            continue
        if isinstance(statement, ast.ClassDef):
            class_symbol = by_node[id(statement)]
            _scan_scope(
                statement.body,
                parsed=parsed,
                source_id=source_id,
                current_class=class_symbol,
                parameters=set(),
                bindings=bindings,
                by_module=by_module,
                by_node=by_node,
                facts=facts,
                funnel=funnel,
            )
            continue
        for call in _calls_without_nested_definitions(statement):
            candidates, dynamic = _resolve_call(
                call,
                current_class=current_class,
                parameters=parameters,
                local_instances=local_instances,
                bindings=bindings,
                by_module=by_module,
            )
            if dynamic:
                funnel.dynamic += 1
                continue
            if not candidates:
                funnel.unresolved += 1
                continue
            candidate_ids = sorted(set(candidates))
            truncated = len(candidate_ids) > MAX_AMBIGUOUS_CANDIDATES
            if truncated:
                funnel.oversized += 1
                candidate_ids = candidate_ids[:MAX_AMBIGUOUS_CANDIDATES]
            resolution = (
                CallResolution.RESOLVED if len(candidate_ids) == 1 and not truncated else CallResolution.AMBIGUOUS
            )
            span = SourceSpan(
                file_path=parsed.path_text,
                line_start=call.lineno,
                line_end=call.end_lineno or call.lineno,
            )
            facts.extend(
                CallFact(source_id, target_id, resolution, span, truncated)
                for target_id in candidate_ids
                if target_id != source_id
            )


def _resolve_call(
    call: ast.Call,
    *,
    current_class: DefinitionSymbol | None,
    parameters: set[str],
    local_instances: dict[str, tuple[DefinitionSymbol, ...]],
    bindings: _Bindings,
    by_module: dict[str, list[DefinitionSymbol]],
) -> tuple[list[str], bool]:
    func = call.func
    if isinstance(func, ast.Name):
        if func.id in parameters:
            return [], True
        classes = bindings.class_targets.get(func.id, ())
        if classes:
            return [_constructor_target(item, by_module) for item in classes], False
        return list(bindings.symbol_targets.get(func.id, ())), False
    if not isinstance(func, ast.Attribute):
        return [], True
    base = func.value
    if isinstance(base, ast.Call):
        return [], True
    if isinstance(base, ast.Attribute):
        root_name = _attribute_root_name(base)
        return [], root_name in parameters if root_name is not None else True
    if not isinstance(base, ast.Name):
        return [], True
    if base.id == "self" and current_class is not None:
        return _class_method_targets(current_class, func.attr, by_module), False
    if base.id in parameters:
        return [], True
    if base.id in local_instances:
        targets: list[str] = []
        for class_symbol in local_instances[base.id]:
            targets.extend(_class_method_targets(class_symbol, func.attr, by_module))
        return targets, False
    module_name = bindings.module_targets.get(base.id)
    if module_name is not None:
        return [item.node_id for item in by_module.get(module_name, []) if item.node.name == func.attr], False
    return [], False


def _attribute_root_name(attribute: ast.Attribute) -> str | None:
    """返回属性链根名字；仓库外模块链据此保守归为 unresolved。"""
    value: ast.expr = attribute
    while isinstance(value, ast.Attribute):
        value = value.value
    return value.id if isinstance(value, ast.Name) else None


def _constructor_target(symbol: DefinitionSymbol, by_module: dict[str, list[DefinitionSymbol]]) -> str:
    methods = _class_method_targets(symbol, "__init__", by_module)
    return methods[0] if methods else symbol.node_id


def _class_method_targets(
    class_symbol: DefinitionSymbol,
    method_name: str,
    by_module: dict[str, list[DefinitionSymbol]],
) -> list[str]:
    prefix = class_symbol.qualified_name + "."
    return sorted(
        item.node_id
        for item in by_module.get(class_symbol.module_name, [])
        if item.kind is NodeKind.FUNCTION
        and item.node.name == method_name
        and item.qualified_name.startswith(prefix)
        and ".<locals>." not in item.qualified_name[len(prefix) :]
    )


def _local_instance_bindings(
    statements: list[ast.stmt], bindings: _Bindings
) -> dict[str, tuple[DefinitionSymbol, ...]]:
    assignments: dict[str, list[tuple[DefinitionSymbol, ...] | None]] = {}
    for statement in statements:
        if not isinstance(statement, ast.Assign) or len(statement.targets) != 1:
            continue
        target = statement.targets[0]
        value = statement.value
        if not isinstance(target, ast.Name) or not isinstance(value, ast.Call) or not isinstance(value.func, ast.Name):
            continue
        assignments.setdefault(target.id, []).append(bindings.class_targets.get(value.func.id))
    return {name: values[0] for name, values in assignments.items() if len(values) == 1 and values[0]}


def _parameter_names(arguments: ast.arguments) -> set[str]:
    return (
        {argument.arg for argument in (*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs)}
        | ({arguments.vararg.arg} if arguments.vararg else set())
        | ({arguments.kwarg.arg} if arguments.kwarg else set())
    )


def _calls_without_nested_definitions(statement: ast.stmt) -> list[ast.Call]:
    calls: list[ast.Call] = []

    class Visitor(ast.NodeVisitor):
        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            return

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            return

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            return

        def visit_Call(self, node: ast.Call) -> None:
            calls.append(node)
            self.generic_visit(node)

    Visitor().visit(statement)
    return sorted(calls, key=lambda item: (item.lineno, item.end_lineno or item.lineno, item.col_offset))


def _is_top_level(qualified_name: str, module_name: str) -> bool:
    remainder = qualified_name[len(module_name) + 1 :]
    return "." not in remainder


def _resolve_module(candidate: str, module_names: set[str]) -> str | None:
    if candidate in module_names:
        return candidate
    matches = [name for name in module_names if name.endswith("." + candidate)]
    return matches[0] if len(matches) == 1 else None


def _import_from_base(node: ast.ImportFrom, package: str) -> str | None:
    if node.level == 0:
        return node.module
    if not package:
        return None
    parts = package.split(".")
    levels = node.level - 1
    if levels >= len(parts):
        return None
    ascended = ".".join(parts[: len(parts) - levels]) if levels else package
    return f"{ascended}.{node.module}" if node.module and ascended else node.module or ascended

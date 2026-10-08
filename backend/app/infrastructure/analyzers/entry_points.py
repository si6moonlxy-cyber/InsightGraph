"""入口识别的检测规则（步骤 5 先行件：规则与测试先行，产物表示待设计）。

本模块只做「识别」：在已解析的模块 AST 上应用确定性规则，产出 EntryPoint 记录。
如何写入 CodeGraph 产物（节点标记 / 新边类型 / 独立清单）属于步骤 5 的契约设计，
须待开源调研 ADR 落账后定夺——本模块刻意不触碰任何冻结契约。

规则（v1）：
- MAIN_GUARD：模块顶层 `if __name__ == "__main__":` 守卫（比较两侧顺序不敏感）；
  symbol 取守卫体中第一个「直接以名字调用模块级函数」的函数名（仅 Name 调用、
  仅本模块顶层 def，不做任何跨模块解析），无匹配时为 None。
- WEB_APP：模块顶层 `app = FastAPI(...)` 形式的赋值（含 `fastapi.FastAPI(...)`
  属性形式与带注解形式）；symbol 为被赋值的变量名。
"""

import ast
from dataclasses import dataclass

from app.domain.codegraph.kinds import EntryKind

EntryPointKind = EntryKind


@dataclass(frozen=True)
class EntryPoint:
    """一条入口识别结果（表示层待步骤 5 契约设计）。"""

    kind: EntryPointKind
    module_name: str
    line_start: int
    symbol: str | None = None
    line_end: int | None = None


def find_entry_points(module_name: str, tree: ast.Module) -> list[EntryPoint]:
    """按源码顺序返回模块内的入口识别结果（确定性）。"""
    top_level_defs = {node.name for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    findings: list[EntryPoint] = []
    for statement in tree.body:
        if isinstance(statement, ast.If) and _is_main_guard(statement.test):
            findings.append(
                EntryPoint(
                    kind=EntryPointKind.MAIN_GUARD,
                    module_name=module_name,
                    line_start=statement.lineno,
                    symbol=_first_local_call(statement.body, top_level_defs),
                    line_end=statement.end_lineno,
                )
            )
        elif isinstance(statement, (ast.Assign, ast.AnnAssign)) and _is_fastapi_call(statement.value):
            targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
            symbol = next(
                (target.id for target in targets if isinstance(target, ast.Name)),
                None,
            )
            findings.append(
                EntryPoint(
                    kind=EntryPointKind.WEB_APP,
                    module_name=module_name,
                    line_start=statement.lineno,
                    symbol=symbol,
                    line_end=statement.end_lineno,
                )
            )
    return findings


def _is_main_guard(test: ast.expr) -> bool:
    """`__name__ == "__main__"` 判断（两侧顺序不敏感）。"""
    if not isinstance(test, ast.Compare) or len(test.ops) != 1 or len(test.comparators) != 1:
        return False
    if not isinstance(test.ops[0], ast.Eq):
        return False
    left, right = test.left, test.comparators[0]
    return (_is_name(left, "__name__") and _is_string(right, "__main__")) or (
        _is_name(right, "__name__") and _is_string(left, "__main__")
    )


def _is_name(node: ast.expr, identifier: str) -> bool:
    return isinstance(node, ast.Name) and node.id == identifier


def _is_string(node: ast.expr, value: str) -> bool:
    return isinstance(node, ast.Constant) and node.value == value


def _first_local_call(body: list[ast.stmt], local_defs: set[str]) -> str | None:
    """守卫体中第一个直接调用模块级函数的调用名（仅 Name 调用，按源码序）。"""
    for statement in body:
        for node in ast.walk(statement):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in local_defs:
                return node.func.id
    return None


def _is_fastapi_call(value: ast.expr | None) -> bool:
    """`FastAPI(...)` 或 `fastapi.FastAPI(...)` 形式的调用。"""
    if not isinstance(value, ast.Call):
        return False
    func = value.func
    if isinstance(func, ast.Name):
        return func.id == "FastAPI"
    return isinstance(func, ast.Attribute) and func.attr == "FastAPI"

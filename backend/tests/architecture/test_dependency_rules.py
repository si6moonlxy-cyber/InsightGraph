"""通过 AST 守卫核心依赖方向，防止领域层被框架污染。"""

import ast
from pathlib import Path

DOMAIN_ROOT = Path(__file__).parents[2] / "app" / "domain"
FORBIDDEN_ROOTS = {
    "alembic",
    "asyncpg",
    "fastapi",
    "langgraph",
    "neo4j",
    "redis",
    "sqlalchemy",
}


def imported_root_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".", maxsplit=1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".", maxsplit=1)[0])
    return roots


def test_domain_does_not_import_framework_or_infrastructure() -> None:
    violations: dict[str, list[str]] = {}
    for path in DOMAIN_ROOT.rglob("*.py"):
        forbidden = sorted(imported_root_names(path) & FORBIDDEN_ROOTS)
        if forbidden:
            violations[str(path.relative_to(DOMAIN_ROOT))] = forbidden

    assert violations == {}

"""入口识别规则测试：正例、反例与夹具仓库集成。"""

import ast
from pathlib import Path

from app.infrastructure.analyzers.entry_points import EntryPoint, EntryPointKind, find_entry_points

_FIXTURE_MAIN = (
    Path(__file__).resolve().parents[4]
    / "eval"
    / "codegraph"
    / "cases"
    / "golden-python-calls"
    / "repo"
    / "app"
    / "main.py"
)
_FIXTURE_API = _FIXTURE_MAIN.parent / "api.py"


def _find(source: str, module_name: str = "app.m") -> list[EntryPoint]:
    return find_entry_points(module_name, ast.parse(source))


def test_main_guard_with_direct_local_call() -> None:
    source = 'def main():\n    return 1\n\n\nif __name__ == "__main__":\n    main()\n'

    findings = _find(source)

    assert findings == [EntryPoint(kind=EntryPointKind.MAIN_GUARD, module_name="app.m", line_start=5, symbol="main")]


def test_main_guard_with_reversed_comparison_order() -> None:
    source = 'def main():\n    return 1\n\n\nif "__main__" == __name__:\n    main()\n'

    findings = _find(source)

    assert findings[0].kind is EntryPointKind.MAIN_GUARD
    assert findings[0].symbol == "main"


def test_non_main_condition_is_not_a_guard() -> None:
    source = 'if __name__ != "__main__":\n    pass\n'

    assert _find(source) == []


def test_guard_without_local_call_has_no_symbol() -> None:
    source = 'from app.helpers import greet\n\n\nif __name__ == "__main__":\n    greet("x")\n'

    findings = _find(source)

    assert findings == [EntryPoint(kind=EntryPointKind.MAIN_GUARD, module_name="app.m", line_start=4, symbol=None)]


def test_guard_inside_function_is_not_top_level() -> None:
    source = 'def outer():\n    if __name__ == "__main__":\n        pass\n'

    assert _find(source) == []


def test_fastapi_direct_assignment() -> None:
    source = "from fastapi import FastAPI\n\napp = FastAPI()\n"

    findings = _find(source)

    assert findings == [EntryPoint(kind=EntryPointKind.WEB_APP, module_name="app.m", line_start=3, symbol="app")]


def test_fastapi_attribute_form_and_annotated_form() -> None:
    source = "import fastapi\n\napi = fastapi.FastAPI()\nservice: object = fastapi.FastAPI()\n"

    findings = _find(source)

    assert [finding.symbol for finding in findings] == ["api", "service"]
    assert all(finding.kind is EntryPointKind.WEB_APP for finding in findings)


def test_other_constructor_is_not_web_app() -> None:
    source = "from http.client import HTTPClient\n\nclient = HTTPClient()\n"

    assert _find(source) == []


def test_findings_follow_source_order() -> None:
    source = (
        "from fastapi import FastAPI\n\n"
        "def main():\n    return 1\n\n"
        "app = FastAPI()\n\n"
        'if __name__ == "__main__":\n    main()\n'
    )

    findings = _find(source)

    assert [finding.kind for finding in findings] == [EntryPointKind.WEB_APP, EntryPointKind.MAIN_GUARD]


def test_fixture_repo_entry_points() -> None:
    main_findings = _find(_FIXTURE_MAIN.read_text(encoding="utf-8"), "app.main")
    api_findings = _find(_FIXTURE_API.read_text(encoding="utf-8"), "app.api")

    assert [finding.kind for finding in main_findings] == [EntryPointKind.MAIN_GUARD]
    assert main_findings[0].symbol == "main"
    assert [finding.kind for finding in api_findings] == [EntryPointKind.WEB_APP]
    assert api_findings[0].symbol == "app"

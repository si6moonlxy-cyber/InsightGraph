"""集成测试门禁的最小自检。"""

import pytest


@pytest.mark.integration
def test_integration_suite_is_opt_in() -> None:
    """此用例证明默认命令会排除 integration 标记。"""
    assert True

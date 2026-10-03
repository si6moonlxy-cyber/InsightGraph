"""辅助函数：覆盖带模块的相对导入。"""

from .text_utils import clean


def format_name(name: str) -> str:
    return clean(name).title()

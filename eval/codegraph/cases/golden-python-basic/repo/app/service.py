"""服务模块：覆盖绝对包导入与类方法。"""

from app.utils.helpers import format_name


class Service:
    def __init__(self, name: str):
        self._name = format_name(name)

    def describe(self) -> str:
        return f"service: {self._name}"

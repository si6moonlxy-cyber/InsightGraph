"""入口模块：覆盖类、方法、装饰器、异步函数与嵌套函数。"""

import os

from app.service import Service


def logged(func):
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    return wrapper


@logged
def build_service(name: str) -> Service:
    def normalize(value: str) -> str:
        return value.strip()

    return Service(normalize(name))


class App:
    def __init__(self, service: Service):
        self._service = service

    async def run(self) -> str:
        return self._service.describe()


def main() -> None:
    app = App(build_service("demo"))
    print(os.name, app)

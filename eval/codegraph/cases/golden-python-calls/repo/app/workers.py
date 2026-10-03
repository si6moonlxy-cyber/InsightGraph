"""调用形态：跨模块直呼、模块属性、类实例化、方法调用与 self 方法。"""

from app import helpers
from app.helpers import greet


class Worker:
    def __init__(self, name: str):
        self._name = name

    def run(self) -> str:
        return self._format(greet(self._name))

    def _format(self, text: str) -> str:
        return f"[{text}]"


def pipeline() -> str:
    worker = Worker("pipeline")
    greeting = greet("world")
    loud = helpers.shout(greeting)
    return worker.run() + loud

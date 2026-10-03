"""被调用方：跨模块直呼 / 导入别名 / 模块属性三种取用路径的目标。"""


def greet(name: str) -> str:
    return f"hello {name}"


def shout(text: str) -> str:
    return text.upper()

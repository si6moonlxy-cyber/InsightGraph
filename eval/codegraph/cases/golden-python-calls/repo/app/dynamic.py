"""调用形态：高阶层（ambiguous）与动态调用（dynamic）语料。"""

from app.helpers import greet


def call_via_variable(callback) -> str:
    return callback("variable")


def call_dynamic(module, name: str):
    return getattr(module, name)("dynamic")


def assign_callback() -> str:
    callback = greet
    return call_via_variable(callback)

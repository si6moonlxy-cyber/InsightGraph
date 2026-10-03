"""调用形态：导入别名与模块别名。"""

import app.helpers as helpers
from app.helpers import greet as g


def use_alias() -> str:
    return g("alias") + helpers.shout("path")

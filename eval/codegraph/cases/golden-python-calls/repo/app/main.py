"""入口与未解析外部调用语料：main guard + stdlib 调用。"""

import os

from app.workers import pipeline


def main() -> str:
    base = os.path.join("root", "child")
    return pipeline() + base


if __name__ == "__main__":
    main()

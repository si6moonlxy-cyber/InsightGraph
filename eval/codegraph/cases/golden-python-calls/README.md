# golden-python-calls（步骤 5 Golden Dataset）

> 状态：**期望结果已由 Human 人工复核并冻结**（2026-10-08）。
> CALLS 边表示（`source_span` / `resolution` / `is_truncated`）、图级 `entries` 清单与四态判定口径已决；
> 固定期望见 `expected_codegraph.json`；任何修改必须重新人工审核，不得按当前实现自动覆盖。
> POC 参考：codegraph-ai/CodeGraph 对本夹具的记分见 `eval/codegraph/.outputs/codegraph-ai-poc/scorecard.md`（本地证据，未入库）。

## 语料矩阵

| 文件 | 调用形态 | 冻结预期 |
| --- | --- | --- |
| `app/helpers.py` | 被调用方（无调用） | — |
| `app/workers.py` | 跨模块直呼 `greet(...)` | resolved |
| | 模块属性 `helpers.shout(...)` | resolved |
| | 类实例化 `Worker(...)` | resolved（目标 `__init__`） |
| | self 方法 `self._format(...)` | resolved |
| | 局部实例方法 `worker.run()` | resolved（单一直接赋值浅推断） |
| `app/aliases.py` | 导入别名 `g(...)` | resolved（别名还原） |
| | 模块别名 `helpers.shout(...)` | resolved |
| `app/dynamic.py` | 高阶回调 `callback(...)` | dynamic（不建边） |
| | `getattr(...)(...)` | dynamic |
| `app/main.py` | stdlib `os.path.join(...)` | unresolved（仓库外，不建边） |
| | main guard + `main()` | 入口识别语料（规则已先行实现） |
| `app/api.py` | `app = FastAPI()` | 入口识别语料（web_app） |
| `app/ambiguous.py` | 同模块重名 `choose`（含 `#2`） | ambiguous（两条候选边） |

## 使用方式

- 执行：`uv run python ../eval/codegraph/evaluator.py --case golden-python-calls`（在 `backend/` 下）。
- evaluator 会生成本地 candidate，并与 `expected_codegraph.json` 做节点、边、CALLS 字段与 entries 的双向集合比对。
- 指标：resolved 精度 / 召回、未解析比例、误报与漏报清单
  （对齐 Development Plan 步骤 5 完成门槛）。
- 入口采用**图级清单**（与 nodes / edges 平级、不入 EdgeKind）；当前识别规则见 `backend/app/infrastructure/analyzers/entry_points.py`。

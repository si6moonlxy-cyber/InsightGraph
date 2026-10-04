# golden-python-calls（步骤 5 语料骨架）

> 状态：**语料已就位；契约已冻结（决策文档 §16），期望结果未冻结**。
> CALLS 边表示（`source_span` / `resolution` / `is_truncated`）、图级 `entries` 清单与四态判定口径已决；
> 期望冻结随步骤 5 实施（AST 补扫器产出后由 evaluator 生成期望并人工复核；规矩同 `golden-python-basic`）。
> POC 参考：codegraph-ai/CodeGraph 对本夹具的记分见 `eval/codegraph/.outputs/codegraph-ai-poc/scorecard.md`（本地证据，未入库）。

## 语料矩阵

| 文件 | 调用形态 | 预期归属（初步意图，非冻结） |
| --- | --- | --- |
| `app/helpers.py` | 被调用方（无调用） | — |
| `app/workers.py` | 跨模块直呼 `greet(...)` | resolved |
| | 模块属性 `helpers.shout(...)` | resolved |
| | 类实例化 `Worker(...)` | resolved（目标 `__init__`） |
| | self 方法 `self._format(...)` | resolved |
| | 局部实例方法 `worker.run()` | 待定（局部赋值来源的类型推断深度） |
| `app/aliases.py` | 导入别名 `g(...)` | resolved（别名还原） |
| | 模块别名 `helpers.shout(...)` | resolved |
| `app/dynamic.py` | 高阶回调 `callback(...)` | ambiguous |
| | `getattr(...)(...)` | dynamic |
| `app/main.py` | stdlib `os.path.join(...)` | unresolved（仓库外，不建边） |
| | main guard + `main()` | 入口识别语料（规则已先行实现） |
| `app/api.py` | `app = FastAPI()` | 入口识别语料（web_app） |

## 使用方式（待步骤 5 接入）

- 接入 `eval/codegraph/evaluator.py` 后：`run_case("golden-python-calls")`；
  期望文件命名沿用 `expected_codegraph.json`。
- 指标：resolved 精度 / 召回、未解析比例、误报与漏报清单
  （对齐 Development Plan 步骤 5 完成门槛）。
- 入口表示的表示层已决（2026-10-04）：**图级清单**（与 nodes / edges 平级、不入 EdgeKind；决策文档 §16）；当前识别规则见 `backend/app/infrastructure/analyzers/entry_points.py`。

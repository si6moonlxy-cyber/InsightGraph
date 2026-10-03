# golden-python-calls（步骤 5 语料骨架）

> 状态：**语料已就位，期望结果未冻结**。
> CALLS 边的表示与 resolved / ambiguous / dynamic / unresolved 的判定口径，
> 待步骤 5 前置调研（参考开源调用图项目）ADR 落账后，由 evaluator 生成期望并
> 人工审核冻结（规矩同 `golden-python-basic`）。

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
- 入口识别的表示层（节点标记 / 新边类型 / 独立清单）同样在步骤 5 设计时定夺，
  当前实现见 `backend/app/infrastructure/analyzers/entry_points.py`（仅识别规则）。

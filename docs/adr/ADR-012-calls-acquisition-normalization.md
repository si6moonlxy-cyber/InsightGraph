# ADR-012：CALLS 获取与归一化纪律

- 状态：Accepted
- 日期：2026-10-08
- 实现证据：`b389760`（M1）、`1964f81`（M2）、`0dd7187`（M2 测试）
- Human 评审：2026-10-08；确认 M1/M2 路线，并要求大型仓库必须具备有界降级

## Context

步骤 5 需要为 GraphRAG 提供可信、可追溯且确定性的调用关系。Python 的动态特性意味着任何单一
静态分析器都无法同时保证完整召回与零误报；CodeGraphAI POC 也证明：它能提供跨文件结构关系，
但在方法体、导入别名、模块属性和 call-site 行号方面存在缺口，Golden 契约口径命中约 33%。

本项目同时受到以下约束：

1. CALLS 必须回溯到调用点源码，不能把引擎符号 span 伪装成调用点证据。
2. `resolved / ambiguous / dynamic / unresolved` 必须进入统一契约；动态或未解析事实不能伪装成边。
3. 外部 native 引擎是可替换 infrastructure 细节，不能成为 domain/application 的依赖。
4. 相同输入必须产生确定性 Artifact；引擎失败不能使基础 AST 扫描失败。
5. CodeGraphAI v0.20.1 的 one-shot 模式按函数启动进程，耗时随可调用节点数近似线性增长。
   InsightGraph 自扫描 470 节点 / 951 边耗时 220.817 秒；大型仓库很可能超过 15 分钟，必须有
   强制预算与可用结果兜底，而不能只依赖运维人员中断。

## Decision

### 1. 采用混合增强 A

CALLS 的正式数据流为：

```text
stdlib AST CallScanner（确定性事实 + call-site span）
        +
可选 CodeGraphAIProvider（跨文件 resolved 信号）
        ↓
Canonical Adapter（身份、关系、状态、provenance）
        ↓
确定性 merge → schema v2 CodeGraph Artifact
```

AST scanner 是正确性与可用性的基础；外部引擎只做可选增强。引擎关闭、不可用、失败或超预算时，
扫描仍以 scanner-only 正常完成。

### 2. 稳定契约由本仓库掌控

- `CodeEdge(kind=calls)` 强制携带调用点 `source_span` 与 `resolved/ambiguous` resolution。
- `dynamic / unresolved` 不物化边，只进入 `CallFunnel`；不可解析是分析事实，不新增错误码。
- ambiguous 最多物化 5 个候选；截断使用 `is_truncated` 与 `oversized_ambiguous_calls` 显式记录。
- 入口使用图级 `entries` 清单，不扩张 `EdgeKind`。
- `CodeGraph.schema_version` 为 2；稳定 ID、排序、去重与双跑确定性继续遵守 ADR-010。

### 3. 引擎通过 Provider + Raw DTO + Canonical Adapter 隔离

- `CallGraphProvider` 是 infrastructure 内部 Protocol；具体实现通过 registry 创建。
- CodeGraphAI 以 `--graph-only --run-tool codegraph_get_call_graph` one-shot 模式调用，不引入 MCP
  会话依赖。
- Raw DTO 使用 `extra="ignore"`，坏节点/坏边逐条跳过并计数；含边却缺 `root` 的响应视为失败。
- 引擎节点按仓库相对路径、1-based 行号窗口、名称与可用 kind 保守匹配 Canonical 节点；多命中丢弃。
- v0.20.1 查询行号使用 AST 定义节点 `lineno`，不能使用包含装饰器的 Canonical span 首行。
- 仅整批成功才写 `ProviderRecord{name, version, asset_hash, tools_used}`；降级结果 provenance 为空。

### 4. Evidence First 合并纪律

- 合并键为 `(source_id, target_id)`；代表 span 取 scanner 事实中的最早调用点。
- engine-only 关系因没有可信 call-site span，**不物化**，只进入诊断计数。
- 同一调用点已有多个 ambiguous 候选时，引擎不得单方面把其中一个升级成 resolved。
- endpoints 不存在、自环、非 `calls` 白名单关系全部丢弃。
- 引擎输出不得修改既有 DEFINES / IMPORTS / entries。

### 5. 大型仓库的有界降级

外部引擎采用四层安全边界：

1. `codegraph_engine_enabled=false`：默认关闭，CI 与普通扫描不依赖本地二进制。
2. `codegraph_engine_timeout_seconds=30`：限制单次工具调用。
3. `codegraph_engine_total_budget_seconds=900`：限制整批引擎查询；预算耗尽立即停止后续查询，丢弃
   未完成引擎结果并返回完整 scanner-only 图。
4. 任一 probe、JSON、子进程或查询失败同样整批降级，避免“部分成功”被误读为完整增强。

总预算是正确性兜底，不是性能优化。首次真实大型仓库触发预算、或连续观测到 one-shot 时间主要消耗
在进程启动时，重新评审以下优化，并用同一 Golden 与真实仓库配对测量：

- `--serve` 常驻引擎；
- 批量/工作区级图导出，减少逐函数进程数；
- 按模块分区并缓存已完成结果；
- 只对 scanner 未解析或高价值入口的符号查询引擎。

任何优化都不得移除 scanner-only 降级，也不得放宽 call-site 证据门槛。

### 6. 评测与 CI

- 常驻 CI 运行 scanner + mock Provider，命令继续排除 `integration` marker；不下载或执行外部资产。
- 真实引擎测试仅在本地显式设置 `CODEGRAPH_ENGINE_PATH` 后手动运行。
- M2 验证结果：真实 Golden 中 engine ∪ scanner 与 scanner-only 的 nodes / edges / entries 完全一致，
  provenance 正确写入；双 Golden eval-v2 保持 1.0000；InsightGraph 自扫描 220.817 秒、0 局部错误。
- 引擎升级必须重新校验 sha256、真实 Golden 幂等、行号口径与性能。

## Alternatives

- **纯自研 resolver**：控制力最高，但重复建设跨文件解析和多语言能力，交付慢；保留 AST scanner 作为
  确定性基础与定向补洞，不重造完整引擎。
- **直接使用引擎图**：最快，但缺四态、调用点证据、稳定 ID 与确定性保证；否决。
- **engine-only 边使用调用者函数 span**：可以提高表面召回，但伪造调用点证据；否决。
- **默认双引擎或 Pyright/scip-python**：精度上限更高，但依赖与运行成本显著增加；只有 Golden 证明
  需要类型推断时再评审。
- **立即引入 `--serve`**：可降低逐函数启动成本，但增加守护进程生命周期、socket、并发与清理复杂度；
  当前 220.817 秒未触发预算，先保留为有数据触发的优化。
- **无总预算，只设置单次超时**：大型仓库仍可能在数百次成功调用中运行数小时；否决。

## Consequences

- 正向：基础 CALLS 始终可用；外部引擎失败或大型仓库超预算不会拖垮扫描；领域契约与供应商解耦；
  每条物化边都有真实调用点证据；CI 不依赖 native 资产。
- 负向：大型仓库可能频繁降级，从而只获得 scanner 能力；one-shot 模式仍有明显线性成本；成功前已花费的
  引擎时间无法回收；为避免半成品，预算触发时会丢弃此前取得的全部引擎增强。
- 复审触发：真实仓库触发 900 秒预算；Golden precision/recall 回退；引擎许可证、输出 schema 或行号
  口径变化；需要多语言、MRO/继承或类型推断；需要在 API 任务层展示“增强已降级”的独立状态。

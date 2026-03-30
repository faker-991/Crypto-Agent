# ReAct Research Agent And Observability Baseline Design

Date: 2026-03-30

## Context

当前项目已经具备这些基础能力：

- `Planner -> Executor -> Agents` 的主执行链路
- `ResearchAgent`、`KlineAgent`、`SummaryAgent`
- Binance 实时行情与多周期 K 线分析
- 本地文件型 trace
- `/traces` 可读执行流程页
- MCP registry、独立 MCP server 脚本和 `/tools` 展示页

但就“真实数据驱动的 Tool-augmented Agent 链路”和“可观测性”而言，当前实现仍有明显缺口：

1. `ResearchAgent` 还是代码写死顺序的 loop，不是真正由模型自主选择工具的 ReAct agent。
2. 工具调用信息分散在 `task_results.tool_calls`、`events`、`payload` 等多个位置，trace 没有统一的工具级 span 语义。
3. token 消耗、工具输入输出体积、异常细节和调用链父子关系还没有统一数据模型。
4. 前端 `/traces` 已能看可读流程，但还不是面向排障的 tool-level observability 视图。
5. MCP 虽已有 registry 与 server 骨架，但还没有形成“面向工具 schema 的统一接入层 + trace 采集层”。

用户要的不是单纯“有日志”，而是：

- `ResearchAgent` 成为真正单 LLM 驱动的 ReAct agent
- 保留并扩展现有 Binance 实时行情与 K 线能力
- 让工具接入接口面向 MCP 可扩展
- 让 trace 能体现 token、工具调用、异常定位和执行过程审计
- 前端能直观看出哪里出问题

## User-Approved Direction

在 brainstorming 里，用户确认了以下约束：

- 第一阶段可观测性做到 `Agent + Tool 调用级`
- 为了支撑 token 消耗与 ReAct 调试，第一阶段同时记录 `LLM step` span，但前端主视图仍以 agent / tool 为主
- `ResearchAgent` 第一阶段允许自主调用 `research + market` 工具
- ReAct 决策内核使用 `单 LLM 驱动`
- token 统计口径第一阶段做到：
  - `LLM token`
  - `工具 payload 大小`
- “回放”第一阶段定义为：
  - 运行时完整记录
  - 事后可回看
  - 不要求重执行 replay
- 前端 trace 详情页优先采用 `B. 时间线优先` 的视觉结构

## Goals

- 把 `ResearchAgent` 升级成真正的单 LLM 驱动 ReAct agent。
- 统一 agent、LLM、tool 三层执行单元的 trace 语义。
- 在 trace 中记录：
  - token 消耗
  - tool call 次数、状态、参数摘要、输出摘要
  - 错误与异常定位字段
  - 执行链父子关系和时间信息
- 在现有 Binance 市场数据能力之上，为 ReAct agent 暴露 market tools。
- 设计一层面向 MCP 的扩展式工具接入接口，使本地工具和 MCP 工具共享统一 contract。
- 让 `/traces` 页面在 3 秒内帮助用户看出“是否失败、失败在哪里、耗时/成本是否异常”。

## Non-Goals

- 第一阶段不把所有 agent 都改成 ReAct。
- 第一阶段不做整条 trace 的重执行 replay。
- 第一阶段不做审批流、签名、不可篡改存证等更重的审计基础设施。
- 第一阶段不做任意开放 registry 的完全开放工具选择。
- 第一阶段不重写整个 `Planner -> Executor -> Agents` 架构。

## Recommended Approach

推荐采用“渐进增强现有架构”的方式，而不是一次性重构所有 agent runtime。

### Why This Approach

1. 当前项目已经有稳定主链路，直接重做统一 runtime 风险过高。
2. 用户最关心的是 `ResearchAgent` 真正 agent 化，以及 trace 能不能承担可观测性叙事。
3. `KlineAgent` 目前已经有真实数据链路，保留它作为稳定 market worker 更有利于分阶段交付。
4. 在现有结构之上增加 `ToolRuntime + TraceRuntime`，能把后续 MCP 接入和其他 agent 演进都纳入统一 contract。

## Target Runtime Architecture

### High-Level Flow

第一阶段目标链路：

```text
User Query
  -> Planner
  -> Executor
  -> ResearchAgent
     -> ReActLoopService
        -> LLM step
        -> ToolRuntime
           -> Local Tool or MCP Tool
        -> TraceRuntime(span + metrics + audit fields)
  -> SummaryAgent
  -> Final Answer
  -> Trace API
  -> /traces
```

### Core Runtime Units

新增两个基础运行时单元：

1. `ToolRuntime`
   统一执行工具。接收工具名、参数、调用上下文，返回标准化结果。

2. `TraceRuntime`
   统一记录执行单元。agent step、LLM call、tool call 都通过它落成结构化 span。

### TraceRuntime Minimal API

第一阶段必须把 `TraceRuntime` 定义成明确接口，而不是抽象概念。

```python
class TraceRuntime:
    def start_span(
        self,
        *,
        trace_id: str,
        parent_span_id: str | None,
        kind: str,
        name: str,
        input_summary: dict | None = None,
        attributes: dict | None = None,
    ) -> dict: ...

    def finish_span(
        self,
        *,
        span_id: str,
        status: str,
        output_summary: dict | None = None,
        metrics: dict | None = None,
        audit: dict | None = None,
        attributes: dict | None = None,
    ) -> dict: ...

    def record_error(
        self,
        *,
        span_id: str,
        error: str,
        exception_type: str | None = None,
    ) -> None: ...

    def finalize_trace(
        self,
        *,
        trace_id: str,
        summary: dict,
    ) -> dict: ...
```

生命周期约束：

- span 只能由创建它的运行单元关闭
- `parent_span_id` 在创建时固定，不允许事后改写
- redaction 在 `finish_span` 前完成
- summary 聚合只发生在 `finalize_trace`
- persistence 由 `TraceRuntime` 统一落盘，调用方不直接写 trace 文件

`attributes` 用于写入 kind-specific 字段：

- `tool` span:
  - `tool_name`
  - `tool_server`
  - `args`
  - `result_preview`
  - `retry_count`
- `llm` span:
  - `model`
  - `decision_summary`
  - `action`
  - `termination_reason`

第一阶段不要求把原始 chain-of-thought 持久化到 trace；trace 中只保留可审计的 `decision_summary`。

持久化 shape 统一规则：

- 所有 kind-specific 字段都放在 `span.attributes`
- 前端和后端都使用 `span.attributes.*` 访问这些字段
- 不把 `tool_name`、`model`、`action` 等字段提升为顶层平铺字段

### Why ToolRuntime And TraceRuntime Must Be Separate

- `ToolRuntime` 负责“怎么执行工具”
- `TraceRuntime` 负责“怎么记录执行”

两者分离可以避免把 trace 逻辑继续散在 agent 代码里，也能让未来 `KlineAgent`、`SummaryAgent`、MCP tools 复用同一层。

## ResearchAgent Design

### Design Goal

把当前 `ResearchAgent` 从“写死顺序的搜索与抓取 loop”升级为“单 LLM 驱动的 ReAct agent”。

### New Internal Structure

第一阶段建议拆成这四个单元：

1. `ResearchAgent`
   - 接收研究任务
   - 组装上下文
   - 选择允许的工具集合
   - 调用 `ReActLoopService`

2. `ReActLoopService`
   - 维护每轮 `decision -> action -> observation`
   - 调用 LLM 产生结构化动作
   - 处理停止条件与护栏

3. `ToolRuntime`
   - 执行工具
   - 返回标准化 tool result

4. `ResearchResultAssembler`
   - 把 loop 中的观察整理成最终 `summary / findings / risks / missing_information`

#### ReActLoopService Contract

```python
class ReActStepOutput(TypedDict):
    decision_summary: str
    action: str | None
    args: dict
    termination: bool
    termination_reason: str | None
```

```python
class Observation(TypedDict):
    tool_name: str
    status: Literal["success", "failed", "degraded"]
    summary: str
    structured_data: dict
```

```python
class ReActLoopService:
    def run(
        self,
        *,
        asset: str,
        tool_specs: list[ToolSpec],
        initial_context: dict,
    ) -> tuple[ReActTerminalState, list[Observation], list[ToolResult]]: ...
```

### ReAct Output Contract

每轮 LLM 不输出自由文本协议，而输出结构化动作：

```json
{
  "decision_summary": "需要先确认市场状态，再决定是否抓网页。",
  "action": "get_ticker",
  "args": {
    "symbol": "SUI",
    "market_type": "spot"
  },
  "termination": false,
  "termination_reason": null
}
```

这样可以避免解析脆弱的 `Thought/Action/Observation` 文本格式，同时保留 ReAct 本质：

- 模型先推理
- 选择下一步工具
- 观察结果
- 继续迭代

这里区分两类输出：

1. `step output`
   - 单轮动作对象
2. `terminal output`
   - 循环结束时交给 `ResearchResultAssembler` 的终态对象

#### Terminal ReAct State

```python
class ReActTerminalState(TypedDict):
    termination_reason: str
    rounds_used: int
    observations: list[Observation]
    successful_tools: list[str]
    failed_tools: list[str]
    missing_information: list[str]
    evidence_status: Literal["sufficient", "insufficient", "failed"]
```

约束：

- LLM 不直接生成最终 `findings / risks / catalysts`
- LLM 只负责逐轮决策与终止
- `ResearchResultAssembler` 根据 `observations + terminal state` 生成最终结构化 research result

#### Malformed LLM Output Rules

结构化 ReAct 的主要失败模式之一是 LLM 输出不合法，因此第一阶段必须固定处理规则：

- 非法 JSON / 无法解析
  - 当前 `llm` span `status=failed`
  - loop 立即停止
  - trace `status=failed`

- 缺少必填字段
  - 当前 `llm` span `status=failed`
  - loop 立即停止
  - trace `status=failed`

- `termination=true` 且同时给出非空 `action`
  - 以 `termination=true` 为准
  - 记录 `degraded_reason=conflicting_llm_step`
  - loop 终止

- 未知工具名
  - 当前 `llm` span `status=degraded`
  - 写入 tool-selection error
  - 允许 LLM 再试一轮，计入 no-progress 统计

- 参数 schema 校验失败
  - 当前 step 记为 `degraded`
  - 不执行工具
  - 允许 LLM 再试一轮

- `termination=false` 但 `action` 为空
  - 当前 `llm` span `status=failed`
  - loop 立即停止
  - trace `status=failed`

- `args` 不是 object
  - 当前 `llm` span `status=failed`
  - loop 立即停止
  - trace `status=failed`

- `action` 不在允许工具集合中
  - 等同于未知工具名处理
  - 当前 `llm` span `status=degraded`
  - 写入 tool-selection error
  - 允许 LLM 再试一轮，计入 no-progress 统计

### Allowed Tool Set

用户确认第一阶段 `ResearchAgent` 可调用 `research + market` 工具，但不对全 registry 完全开放。

建议第一阶段允许这些工具：

- `search_web`
- `fetch_page`
- `get_market_snapshot`
- `get_protocol_snapshot`
- `get_ticker`
- `get_klines`
- `read_asset_memory`

它们来自两个逻辑域：

- `research`
  - 网页搜索、页面抓取、内存读取
- `market`
  - Binance 行情与 K 线、外部市场快照、协议快照

这里明确约束：

- `read_asset_memory` 第一阶段归入 `research` domain
- 第一阶段 domain enum 只有：
  - `research`
  - `market`
- 不单独引入第三个 `memory` domain，避免 runtime、trace 和模型提示三处同时增加复杂度

### Stop Conditions

除了 LLM 自身可输出 `termination=true`，系统还必须有硬护栏：

- 超过最大轮数
- 重复调用相同工具与相同参数
- 连续两轮没有新增信息
- 工具失败次数超过阈值
- 证据已足够

这些停止原因必须写入 trace，并回传到最终结果。

第一阶段给出明确默认值，后续如需调参再单独优化：

- `max_rounds = 6`
- `max_same_call_repeats = 1`
  - 同一 `tool_name + normalized args` 最多允许连续重复一次
- `max_tool_failures = 2`
  - 超过后停止 loop，并返回 `status=failed`
- `max_no_progress_rounds = 2`
  - 如果连续两轮 observation 都没有新增：
    - 新证据
    - 新结构化字段
    - 新可执行候选动作
    则停止并返回 `status=insufficient`
- `evidence_sufficient = true` 的默认判定：
  - 至少拿到一个市场侧 observation
  - 至少拿到一个非空 research/source observation
  - 最终 `missing_information` 项不超过 `2`

这里的“新增信息”定义为：

- 新的成功 tool result
- 新的 source url
- 新的结构化 market/protocol field
- 新的可供 assembler 使用的 observation 摘要条目

如果 LLM 输出 `termination=true` 但系统判定证据不足，系统仍允许终止，但最终状态必须是 `insufficient`，不能伪装为 `success`。

### Why KlineAgent Is Not ReAct In Phase 1

第一阶段不建议把 `KlineAgent` 一起改为 ReAct，原因是：

- `KlineAgent` 当前已连接 Binance 真数据链路
- 当前最关键缺口是 `ResearchAgent` 自主性与 observability
- 如果同时 agent 化 `KlineAgent`，范围会显著膨胀

第一阶段更稳妥的方案是：

- `ResearchAgent` 真正 agent 化
- `KlineAgent` 继续作为稳定 worker
- 给 `ResearchAgent` 暴露 market tools，使它能在需要时自主拉行情

## Tool Runtime And MCP Integration Design

### Tool Contract

所有工具都必须通过统一 contract 暴露给 `ToolRuntime`：

- `name`
- `server`
- `domain`
- `description`
- `input_schema`
- `executor`
- `source_type`
  - `local`
  - `mcp`
- `audit_level`
- `replay_mode`

第一阶段要求把这个 contract 固化成明确接口，而不是概念字段列表。

#### ToolSpec

```python
class ToolSpec(TypedDict):
    name: str
    server: str
    domain: Literal["research", "market"]
    description: str
    usage_guidance: str
    input_schema: dict
    output_schema: dict
    executor_ref: str
    source_type: Literal["local", "mcp"]
    audit_level: Literal["basic", "sensitive"]
    replay_mode: Literal["view_only"]
```

#### ToolRuntime Interface

```python
class ToolRuntime:
    def execute(
        self,
        *,
        tool_name: str,
        args: dict,
        trace_context: dict,
    ) -> ToolResult: ...
```

#### ToolResult

```python
class ToolResult(TypedDict):
    status: Literal["success", "failed", "degraded"]
    tool_name: str
    server: str
    domain: str
    args: dict
    output: dict
    output_summary: dict
    error: str | None
    reason: str | None
    exception_type: str | None
    degraded: bool
    metrics: dict
```

#### Tool Error Shape

工具执行失败时必须标准化为：

```python
{
  "status": "failed",
  "tool_name": "...",
  "server": "...",
  "domain": "...",
  "args": {...},
  "output": {},
  "output_summary": {},
  "error": "...",
  "reason": "...",
  "exception_type": "HTTPStatusError" | "TimeoutException" | "ValueError" | "...",
  "degraded": false,
  "metrics": {
    "input_bytes": 0,
    "output_bytes": 0
  }
}
```

这保证本地工具、MCP 工具和 trace layer 之间的边界是可测且稳定的。

这里的 `executor_ref` 是运行时绑定键，不要求把可执行对象直接序列化到 trace 或暴露给模型。模型侧实际只需要看到：

- `name`
- `description`
- `usage_guidance`
- `input_schema`
- `output_schema`

第一阶段 `input_schema` 与 `output_schema` 统一采用：

- JSON Schema Draft 7 的受限子集
- 允许字段：
  - `type`
  - `properties`
  - `required`
  - `items`
  - `enum`
  - `description`
  - `default`

本地工具和 MCP 工具都使用这同一套 schema dialect。

### Why Tool Schema Matters

ReAct LLM 不是根据代码里的 if/else 选工具，而是根据工具 schema 决策。

因此 schema 至少要告诉模型：

- 这个工具是干什么的
- 需要什么参数
- 哪些参数必填
- 输出大概会返回什么
- 什么时候适合用它

### MCP Strategy

第一阶段不要求真正动态发现所有远端 MCP server，但 contract 必须为未来扩展预留：

- 本地工具和 MCP 工具共享统一 `ToolSpec`
- `ToolRuntime` 根据 `source_type` 决定走本地 executor 或 MCP registry
- trace 不区分“本地工具”与“MCP 工具”的记录方式，只在 metadata 中标注来源

### Market Tools In Scope

为保证“真实数据驱动”成立，第一阶段正式收进 tool 层的 market tools 只包含项目里已经存在或已有稳定 provider 的能力：

- `get_ticker`
- `get_klines`
- `get_market_snapshot`
- `get_protocol_snapshot`

其中：

- `get_ticker` / `get_klines` 使用现有 Binance market adapter
- `get_market_snapshot` 使用当前已存在的 CoinGecko market snapshot 能力
- `get_protocol_snapshot` 使用当前已存在的 DefiLlama protocol snapshot 能力

这里的两个 snapshot tool 不是未来占位项，而是对现有 `ExternalResearchService` / `ExternalResearchAdapter` 的 tool 化包装，因此仍在第一阶段范围内。

但第一阶段不再引入新的第三方 provider，也不扩展更多非现有工具。

## Trace Data Model

### Summary Layer And Execution Layer

trace 升级为双层结构：

1. `Summary Layer`
   给列表页、快速概览和最终回答使用

2. `Execution Layer`
   给排错、复盘和审计使用

### Summary Layer Fields

建议新增并长期保留：

- `trace_id`
- `user_query`
- `status`
- `conversation_id`
- `start_ts`
- `end_ts`
- `duration_ms`
- `token_usage_total`
- `tool_usage_summary`
- `error_summary`
- `agent_summaries`
- `llm_call_count`
- `tool_call_count`
- `failure_count`
- `metrics_summary`

其中 `metrics_summary` 固定为：

```python
{
  "prompt_tokens": int,
  "completion_tokens": int,
  "total_tokens": int,
  "input_bytes": int,
  "output_bytes": int,
}
```

`tool_usage_summary` 固定为：

```python
{
  "total_calls": int,
  "failed_calls": int,
  "degraded_calls": int,
}
```

### Execution Layer: Spans

统一使用 `spans` 描述执行单元。

第一阶段至少支持：

- `planner`
- `agent`
- `llm`
- `tool`
- `summary`

### Status Enums

为避免后端和前端状态语义漂移，第一阶段统一使用这套状态枚举：

- span `status`
  - `success`
- `failed`
- `degraded`
- `insufficient`
- `skipped`
- `unknown`

- trace `status`
- trace `status`
  - `execute`
  - `partial_failure`
  - `failed`
  - `clarify`
  - `cancelled`

- final answer `evidence_status`
  - `sufficient`
  - `insufficient`
  - `failed`

### Shared Span Fields

每个 span 至少包含：

- `span_id`
- `parent_span_id`
- `trace_id`
- `kind`
- `name`
- `status`
- `start_ts`
- `end_ts`
- `duration_ms`
- `input_summary`
- `output_summary`
- `error`
- `attributes`
- `metrics`
- `audit`

其中 `metrics` 至少包含：

- `prompt_tokens`
- `completion_tokens`
- `total_tokens`
- `input_bytes`
- `output_bytes`

第一阶段不要求每个 span 都填满全部 metrics 字段，按 kind 约束：

- `llm` span 必须提供：
  - `prompt_tokens`
  - `completion_tokens`
  - `total_tokens`
  - `input_bytes`
  - `output_bytes`
- `tool` span 必须提供：
  - `input_bytes`
  - `output_bytes`
- `planner / agent / summary` span 可为空对象，或只保留 bytes 统计

### Tool Span Fields

`tool` span 在 `attributes` 下必须包含：

- `tool_name`
- `tool_server`
- `tool_domain`
- `args`
- `result_preview`
- `exception_type`
- `retry_count`
- `degraded`

### LLM Span Fields

`llm` span 在 `attributes` 下必须包含：

- `model`
- `provider`
- `temperature`
- `decision_summary`
- `action`
- `termination_reason`

### Audit Fields

第一阶段执行过程审计不做重型安全机制，但必须保留足够排查上下文：

- `actor`
- `source`
- `tool_server`
- `tool_version` if available
- `request_id`
- `span_id`
- `parent_span_id`
- `start_ts`
- `end_ts`

### Compatibility Strategy

第一阶段不能把旧 trace 读取链路一次性打断。

因此建议：

- 保留现有 `plan / task_results / events / execution_summary`
- 新增 `spans` 与 `metrics_summary`
- `/api/traces/{trace_id}` 同时返回旧字段和新字段

这样：

- 旧前端能继续工作
- 新前端可以逐步切到 `spans`
- 历史 trace 仍可读取

legacy trace fallback 第一阶段采用“服务端转换 + 前端统一消费”的策略：

- 新 trace：原生返回 `spans`
- 旧 trace：由后端 read path 派生 `pseudo_spans`
- 前端统一消费 `spans`
- 只有当后端无法派生时，前端才退回现有 legacy raw-trace 组件

这样 migration 逻辑主要留在后端，前端不需要同时维护两套主渲染路径

最小 legacy -> `pseudo_spans` 映射表：

- `plan` -> `planner` span
- `task_results[*].task_type == research` -> `agent` span with `name=ResearchAgent`
- `task_results[*].task_type == kline` -> `agent` span with `name=KlineAgent`
- `task_results[*].task_type == summary` -> `summary` span
- `task_results[*].tool_calls[*]` -> `tool` pseudo-span
- `events` 中已有 timing 的项
  - 作为对应 span 的 timing 补充
- legacy trace 缺失的字段
  - `metrics={}`
  - `attributes={}`
  - `status` 优先来自 task result，否则回退 `unknown`

### Persistence And Redaction Rules

第一阶段“回放”的含义是可回看，不是重执行。因此 trace 必须明确哪些内容被持久化、截断或脱敏。

统一规则：

- 所有 tool span 持久化：
  - 完整 `args`
  - `output_summary`
  - `result_preview`
- 默认不把完整大 payload 直接写入主 trace
- 对大文本输出，例如 `fetch_page.text`：
  - `result_preview` 最多保留前 `1,000` 个字符
  - 记录 `output_truncated=true`
- `audit_level=sensitive` 的工具：
  - 主 trace 中必须 redaction 敏感字段
  - 包括 API key、cookie、header、长正文原文

这样 trace 既能用于回看和异常定位，也不会无限膨胀成 raw dump

### Aggregation Rules

span 到 trace summary 的聚合规则第一阶段固定如下：

1. 若任一 `planner` span 失败，trace `status=failed`
2. 若任一 `agent` 或 `llm` span 失败，且没有成功收敛到最终回答，trace `status=failed`
3. 若存在任一 `tool` span `failed` 或 `degraded`，但最终回答仍生成，则 trace `status=partial_failure`
4. 若没有 `failed/degraded`，但最终 evidence 不足，则 trace `status=partial_failure`
5. 全部关键 span 成功，则 trace `status=execute`
6. 若 planner 明确要求补充输入且没有进入执行阶段，则 trace `status=clarify`
7. 若用户主动中断且没有最终回答，则 trace `status=cancelled`

聚合计数规则：

- `Total Tokens` = 所有 `llm` span 的 `total_tokens` 之和
- `LLM Calls` = `kind=llm` 的 span 数量
- `Tool Calls` = `kind=tool` 的 span 数量
- `Failures` = `status in {"failed", "degraded", "insufficient"}` 的 span 数量
- `Total Duration` = root trace duration

这些字段必须同时回填到 summary layer：

- `token_usage_total = Total Tokens`
- `llm_call_count = LLM Calls`
- `tool_call_count = Tool Calls`
- `failure_count = Failures`
- `duration_ms = Total Duration`
- `tool_usage_summary.total_calls = Tool Calls`
- `tool_usage_summary.failed_calls = count(tool span status=failed)`
- `tool_usage_summary.degraded_calls = count(tool span status=degraded)`

前端渲染规则：

- `clarify`
  - `Trace Status` 显示“待澄清”
  - 时间线只渲染 planner span
  - 不渲染 tool/llm 异常概览态
- `cancelled`
  - `Trace Status` 显示“已取消”
  - 时间线渲染到最后一个已关闭 span
  - 不显示最终回答卡片

## Frontend Trace Page Design

### User-Approved Direction

用户确认 trace 详情页主方向采用 `B. 时间线优先`。

### Page Structure

桌面端建议采用：

1. 顶部概览条
2. 主时间线
3. 底部详情面板
4. 最底部折叠 raw trace

### Top Overview Bar

固定展示这 6 个高信号指标：

- `Trace Status`
- `Total Tokens`
- `LLM Calls`
- `Tool Calls`
- `Failures`
- `Total Duration`

视觉规则：

- 有失败则 `Failures` 卡片变红
- token 高于阈值则 `Total Tokens` 变黄
- 存在局部失败但最终恢复则显示 `Partial Failure`

第一阶段给出明确派生规则：

- `Total Tokens` 高阈值：
  - `> 8,000` 显示黄色
  - `> 20,000` 显示红色
- `Partial Failure`：
  - trace `status=partial_failure` 时显示
- `Failures` 数量：
  - 统计 `failed + degraded + insufficient` span

### Main Timeline

时间线按 span 顺序渲染，而不是按低层 event name 手工拼接。

每个节点统一展示：

- 状态色条
- 标题
- 一行关键摘要
- 右侧轻量指标

关键摘要示例：

- `HTTP 403 · 2.3s · 182 bytes`
- `prompt=1,260 · completion=142`
- `Binance get_klines · 4h · success`

这样用户不展开详情也能先扫出异常点。

### Detail Panel

点击时间线节点后，在页面下方展开详情面板，使用四个 tab：

- `Input`
- `Output`
- `Error`
- `Audit`

这样能直接映射用户关心的四类信息：

1. token 消耗量
   - 顶部汇总
   - 节点右侧指标
   - detail 中完整 metrics

2. 工具调用情况
   - 时间线节点显示工具名、耗时、状态
   - detail 中展示参数摘要与输出摘要

3. 异常定位
   - 失败节点直接染红
   - `Error` tab 展示 `error / exception_type / args / result_preview`

4. 执行过程审计
   - `Audit` tab 展示 `span_id / parent_span_id / actor / tool_server / timing`

### Default Interaction Rules

为保证“哪里出问题了”足够直观，建议：

- 默认自动滚动到第一个失败 span
- 提供过滤器：
  - `All`
  - `Failed Only`
  - `LLM`
  - `Tool`
- 允许展开失败 span 的上下游一层上下文
- raw trace 保留，但默认折叠在页面底部

### Mobile Behavior

移动端不复刻桌面端横向信息密度，而是退化为竖向堆叠：

1. 顶部概览卡片改为两列网格
2. 时间线保留单列
3. detail panel 仍在时间线下方展开
4. raw trace 默认继续折叠

移动端目标是“还能定位失败节点”，而不是展示全部桌面密度。

### Workstream Boundary

虽然第一阶段同时改 backend runtime/schema 和 `/traces` 前端页面，但它们不是两个独立子系统重做，而是同一条 shared trace contract 下的两个工作流：

- backend 负责产出稳定 trace contract
- frontend 负责消费该 contract 并做时间线优先展示

implementation planning 必须按“先 contract，后 UI”的顺序拆任务，而不是并行猜接口。

## Error Handling And Degraded Semantics

第一阶段必须区分三类失败：

1. `hard failure`
   - 例如 LLM 调用失败、工具 executor 崩溃

2. `soft failure`
   - 例如页面抓取失败，但 agent 可以继续

3. `insufficient`
   - 工具都正常，但证据仍不够

这三类状态必须同时反映在：

- span `status`
- trace `status`
- 前端视觉状态
- 最终回答的 `missing_information / degraded_reason`

第一阶段具体映射规则如下：

- `hard failure`
  - span `status=failed`
  - trace `status=failed`，除非失败发生在非关键 tool span 且系统完成恢复
  - 前端节点红色
  - 最终回答可为空，或返回明确失败说明

- `soft failure`
  - span `status=degraded`
  - trace `status=partial_failure`
  - 前端节点黄色或浅红
  - 最终回答必须带 `degraded_reason`

- `insufficient`
  - span `status=insufficient`
  - trace `status=partial_failure`
  - 前端节点黄色
  - 最终回答必须带 `missing_information`

### Timeout, Retry, And Cancellation Policy

第一阶段采用保守策略，避免 observability 语义被隐式重试污染：

- `llm` call
  - timeout: `30s`
  - retry: `0`
  - timeout 后记为 `failed`

- `tool` call
  - timeout: `15s`
  - retry: `1` 次，仅限网络型工具
  - 第一次失败但重试成功：
    - span `status=degraded`
    - `retry_count=1`
  - 重试后仍失败：
    - span `status=failed`

- 用户主动中断
  - 当前 active span 记为 `skipped`
  - trace 最终状态按已有产出决定，不额外标 `failed`

### Cancellation Status Precedence

若发生用户主动中断，trace 顶层状态按这个优先级聚合：

1. 如果已有 `final_answer`，保留原聚合状态，不改成 `cancelled`
2. 如果没有 `final_answer`，且最后一个 active span 被中断，则 trace `status=cancelled`
3. `cancelled` 不覆盖更早发生且已确定的 `failed`

## Research Result Contract

为避免 `ResearchAgent -> SummaryAgent -> final answer layer` 的边界继续模糊，第一阶段固定 `ResearchAgent` 输出 contract：

```python
class ResearchAgentResult(TypedDict):
    agent: Literal["ResearchAgent"]
    status: Literal["success", "failed", "insufficient", "degraded"]
    evidence_status: Literal["sufficient", "insufficient", "failed"]
    summary: str
    findings: list[str]
    risks: list[str]
    catalysts: list[str]
    missing_information: list[str]
    degraded_reason: str | None
    termination_reason: str | None
    rounds_used: int
    tool_calls: list[ToolResult]
```

`SummaryAgent` 只基于这个 contract 和其他 agent 的结构化结果生成最终回答，不额外发明新的事实字段。

`ResearchResultAssembler` 必须是确定性单元，接口固定为：

```python
class ResearchResultAssembler:
    def assemble(
        self,
        *,
        asset: str,
        terminal_state: ReActTerminalState,
        observations: list[Observation],
        tool_results: list[ToolResult],
    ) -> ResearchAgentResult: ...
```

第一阶段 derivation rules：

- `summary`
  - 来自 terminal state + observations 的压缩摘要
- `findings`
  - 来自成功 observation 的非重复事实条目
- `risks`
  - 来自 market/protocol observation 中的风险相关条目
- `catalysts`
  - 来自网页和结构化 observation 中的催化剂条目
- `missing_information`
  - 直接继承 terminal state
- `degraded_reason`
  - 若存在任一 degraded tool result，则拼接其 reason

### Existing Pipeline Mapping

第一阶段继续保留现有主链，不重写 `TaskResult` 与 `execution_summary` 的入口形式。映射规则固定如下：

- `ResearchAgentResult -> TaskResult.payload`
  - 原样放入 `payload`
- `ResearchAgentResult.summary -> TaskResult.summary`
- `ResearchAgentResult.status -> TaskResult.status`
- `ResearchAgentResult.evidence_status`
  - 映射到 `TaskResult.evidence_sufficient`
    - `sufficient -> true`
    - `insufficient -> false`
    - `failed -> false`

- `TaskResult.payload -> execution_summary`
  - `summary`
  - `missing_information`
  - `degraded_reason`
  - `evidence_status`

- `execution_summary + upstream TaskResult[] -> final_answer`
  - 继续由 `SummaryAgent` 负责生成

这样可以让新 runtime 与现有 `Planner -> Executor -> Agents -> SummaryAgent` 主链兼容，而不要求第一阶段一起重写 orchestrator。

## Typed End-To-End Example

为了把 contract 串实，第一阶段至少应能对应到这样的端到端对象：

```python
tool_spec = {
    "name": "get_klines",
    "server": "binance",
    "domain": "market",
    "description": "Fetch Binance klines",
    "usage_guidance": "Use when the agent needs timeframe-based price structure.",
    "input_schema": {"type": "object"},
    "output_schema": {"type": "object"},
    "executor_ref": "binance.get_klines",
    "source_type": "local",
    "audit_level": "basic",
    "replay_mode": "view_only",
}

tool_result = {
    "status": "success",
    "tool_name": "get_klines",
    "server": "binance",
    "domain": "market",
    "args": {"symbol": "BTCUSDT", "interval": "4h", "market_type": "spot"},
    "output": {},
    "output_summary": {"candles": 120, "source": "binance"},
    "error": None,
    "reason": None,
    "exception_type": None,
    "degraded": False,
    "metrics": {"input_bytes": 62, "output_bytes": 5120},
}

llm_span = {
    "kind": "llm",
    "status": "success",
    "metrics": {
        "prompt_tokens": 1280,
        "completion_tokens": 144,
        "total_tokens": 1424,
        "input_bytes": 6100,
        "output_bytes": 920,
    },
}

tool_span = {
    "kind": "tool",
    "status": "success",
    "attributes": {
        "tool_name": "get_klines",
        "tool_server": "binance",
        "tool_domain": "market",
        "args": {"symbol": "BTCUSDT", "interval": "4h", "market_type": "spot"},
        "result_preview": {"candles": 120, "source": "binance"},
        "exception_type": None,
        "retry_count": 0,
        "degraded": False,
    },
    "metrics": {"input_bytes": 62, "output_bytes": 5120},
}

research_result = {
    "agent": "ResearchAgent",
    "status": "success",
    "evidence_status": "sufficient",
    "summary": "BTC has both market structure and external evidence support.",
    "findings": ["4h trend remains constructive."],
    "risks": ["Need confirmation from broader market regime."],
    "catalysts": [],
    "missing_information": [],
    "degraded_reason": None,
    "termination_reason": "Evidence threshold met.",
    "rounds_used": 3,
    "tool_calls": [],
}
```

一个显式终止示例：

```python
terminal_state = {
    "termination_reason": "Evidence threshold met.",
    "rounds_used": 3,
    "observations": [
        {
            "tool_name": "get_klines",
            "status": "success",
            "summary": "4h trend remains constructive.",
            "structured_data": {"interval": "4h", "trend": "constructive"},
        },
        {
            "tool_name": "fetch_page",
            "status": "success",
            "summary": "Found roadmap and catalyst references.",
            "structured_data": {"source_type": "web_page"},
        },
    ],
    "successful_tools": ["get_klines", "fetch_page"],
    "failed_tools": [],
    "missing_information": [],
    "evidence_status": "sufficient",
}
```

`ResearchResultAssembler` 的输入就是：

- `terminal_state`
- 全部 normalized observations
- tool call records

它的输出是上面的 `research_result`。

## Testing Strategy

### Backend

第一阶段必须新增或扩展测试，覆盖：

- ReAct loop 的结构化动作解析
- 非法工具名或非法参数的拒绝逻辑
- tool span 的记录
- llm span token metrics 的记录
- tool payload bytes 的记录
- 异常 span 的记录
- trace summary totals 聚合
- 旧 trace 与新 trace 的兼容读取

### Frontend

前端至少覆盖：

- trace 概览条渲染
- 时间线节点状态颜色
- 失败节点自动定位
- detail panel 的四个 tab
- 旧 trace fallback 渲染

## Rollout Plan

建议按这个顺序交付：

1. 先引入统一 `ToolSpec / ToolRuntime / TraceRuntime`
2. 把 trace schema 升级到带 `spans + metrics_summary`
3. 让 `ResearchAgent` 切到真正单 LLM ReAct
4. 前端 `/traces` 切到时间线优先的新详情页

这份 phase-1 implementation plan 的边界到第 4 步结束为止。

“把更多工具逐步接到统一 MCP-oriented runtime” 属于 phase 2，不在本次 implementation plan 范围内。

这个顺序的理由是：

- trace 契约先稳定，后续 agent 改造不会反复改前端
- `ResearchAgent` 改完后就能立刻产出真实 tool-level trace
- 前端最后接稳定 contract，减少返工

## Success Criteria

第一阶段完成后，项目应满足这些标准：

- `ResearchAgent` 不再靠写死策略决定工具调用顺序
- trace 可展示 tool-level span
- trace 可看到 LLM token、tool bytes、耗时、错误
- `/traces` 页面能直接定位失败节点
- tool 接入 contract 对本地工具和 MCP 工具统一
- 现有 Binance 行情与 K 线能力继续可用，并能在 trace 中以 tool 调用形式体现

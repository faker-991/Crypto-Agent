# Agentic Planner Runtime Design

## Goal

把当前项目从“规则型 planner + 固定 task 映射”升级为“LLM planner + 工具型子 agent + 汇总层”的真实运行时通路。

目标链路：

```text
User Query
  -> PlannerAgent (LLM)
  -> choose: clarify / research_only / kline_only / mixed_analysis
  -> ResearchAgentTool and/or KlineAgentTool
     -> tool loop (max 3 rounds)
     -> evidence sufficiency check
  -> SummaryAgent
  -> Final Answer
  -> TraceLog
```

这次设计要求：

- `Planner` 本身由 LLM 生成计划，不再仅靠规则判断
- `ResearchAgent` 与 `KlineAgent` 必须实际调用工具
- 子 agent 在一次请求内允许最多 `3` 轮“工具调用 -> 结果检查 -> 再调用”
- 证据不足时必须明确停止，不允许硬编结论
- 单任务和多任务都统一经过 `SummaryAgent`
- trace 必须展示 planner 决策、子 agent 工具调用、反思和最终汇总

## Non-Goals

这次不做：

- 无限 replan 或无限工具循环
- 多个 agent 彼此对话
- 自动交易或下单
- 面向任意开放域任务的通用 agent 平台
- 高级并行调度
- 商业搜索 API 作为第一版必需项

## Current Problems

当前实现虽然已经从 router 迁到 planner/orchestrator，但仍然存在几个本质问题：

1. `Planner` 仍然主要是规则分流器，而不是真正的 LLM planner。
2. `Executor` 仍然通过 `task_type -> agent` 的硬编码映射在替 planner 做决策。
3. 单任务请求并不总是走完整汇总链路。
4. `ResearchAgent` 与 `KlineAgent` 更像固定 service 包装，而不是会实际调用多个工具并检查结果是否足够的子 agent。
5. trace 更像“执行结果回执”，而不是“规划与执行过程可审计日志”。

用户想要的是：

- 问 K 线，就真正走 K 线分析通路并返回 K 线型回答
- 问基本面，就真正走研究通路并返回研究型回答
- 问综合问题，就拆成多条通路后统一汇总
- 证据不足时明确停止

## Recommended Approach

采用三层运行时结构：

1. `PlannerAgent`
   LLM 驱动。负责决定当前问题该走哪条通路。

2. `Tool-backed Sub Agents`
   `ResearchAgent` 和 `KlineAgent` 作为可被 planner 调用的子 agent。它们不是简单函数，而是内部有工具循环和结果检查逻辑。

3. `SummaryAgent`
   所有面向用户的最终回答都统一从这里产出。它只基于子 agent 返回的结构化结果说话。

推荐原因：

- 比“Planner 直接调用所有底层工具”更容易维护
- 比“规则分流器 + service 调用”更接近真正 agent
- planner、子 agent、summary 的责任边界清楚
- trace 和调试成本可控

## Target Runtime Architecture

### High-Level Flow

```text
User Query
  -> ContextBuilder
  -> PlannerAgent (LLM)
     -> plan mode: clarify / research_only / kline_only / mixed_analysis
  -> Orchestrator
     -> invoke ResearchAgentTool and/or KlineAgentTool
  -> Sub-agent loop
     -> round 1
     -> round 2
     -> round 3 max
  -> SummaryAgent
  -> Final Answer
  -> Conversation writeback
  -> TraceLog
```

### Core Principles

- `PlannerAgent` 决定路径，不直接抓网页也不直接算指标
- `ResearchAgent` 和 `KlineAgent` 必须使用真实工具
- 子 agent 必须在每轮之后判断“证据是否足够”
- 单次用户请求内的工具循环上限是 `3`
- 如果证据不足，最终回答必须明确说明不足并停止
- `SummaryAgent` 不能补造证据，只能整理已有结果

## Planner Design

### Planner Responsibilities

`PlannerAgent` 负责：

- 理解用户意图
- 判断是否要澄清
- 决定走哪种模式
- 决定需要调用哪些子 agent
- 决定最后是否进入 `SummaryAgent`

第一版只允许四种模式：

- `clarify`
- `research_only`
- `kline_only`
- `mixed_analysis`

这保证 LLM planner 有灵活性，但不会无限发散。

### Planner Output

Planner 输出必须是结构化对象，至少包括：

- `mode`
- `goal`
- `requires_clarification`
- `clarification_question`
- `agents_to_invoke`
- `inputs`
- `reasoning_summary`

示例：

```json
{
  "mode": "kline_only",
  "goal": "Analyze BTC spot structure on 1d and 1w",
  "requires_clarification": false,
  "clarification_question": null,
  "agents_to_invoke": ["KlineAgent", "SummaryAgent"],
  "inputs": {
    "asset": "BTC",
    "timeframes": ["1d", "1w"],
    "market_type": "spot"
  },
  "reasoning_summary": "The user is asking about market structure and timeframes, so kline analysis is the primary path."
}
```

### Planner Constraints

- planner 不允许发明未知 agent
- planner 不允许绕过 `SummaryAgent` 直接面向用户输出
- planner 不能在第一版中自行增加第四个执行 agent
- planner 的自由度在“选择路径”和“填入调用输入”，而不是无限制生成工作流

## Sub-Agent Design

### Shared Contract

所有子 agent 统一返回：

```python
{
  "agent": "ResearchAgent" | "KlineAgent",
  "status": "success" | "insufficient" | "failed",
  "evidence_sufficient": bool,
  "summary": str,
  "findings": list,
  "missing_information": list[str],
  "tool_calls": list[dict],
  "raw_evidence": dict,
  "rounds_used": int
}
```

### ResearchAgent

#### Goal

ResearchAgent 负责围绕资产、叙事、基本面、风险和催化剂进行多轮搜索、抓取和总结。

#### Tool Set

第一版优先免费或免 key：

- `search_web(query)`
- `fetch_page(url)`
- `extract_market_snapshot(asset)`
- `extract_protocol_snapshot(asset)`
- `summarize_sources(sources)`

其中：

- `search_web` 用公开搜索能力，不强依赖商业搜索 API
- `extract_market_snapshot` / `extract_protocol_snapshot` 复用现有市场和协议上下文能力

#### Research Loop

ResearchAgent 每轮都必须显式记录：

- 本轮目标
- 选择调用哪些工具
- 工具返回了什么
- 哪些关键证据仍然缺失

建议流程：

```text
round 1:
  broad search

round 2:
  fetch relevant pages + extract structured evidence

round 3:
  targeted search/fetch for gaps
  or stop if evidence is sufficient
```

#### Search Budget

第一版约束：

- 最多 `4` 个搜索查询
- 最多抓取 `10` 个页面
- 最多 `3` 轮

#### Stop Rule

如果以下块缺失过多，则返回 `insufficient`：

- 项目/协议简介
- 市场或协议数据锚点
- 主要催化剂
- 主要风险
- 正反论据

ResearchAgent 不允许在证据不足时输出“值不值得拿”的强结论。

### KlineAgent

#### Goal

KlineAgent 负责基于真实行情和本地指标计算，形成结构化技术分析结论。

#### Tool Set

第一版接真实外部工具：

- `get_klines(asset, timeframe, market_type)`
- `get_ticker(asset, market_type)`
- `compute_indicators(candles, indicator_set)`
- `build_market_structure(candles, indicators)`

#### Indicator Set

第一版至少支持：

- `SMA/EMA`
- `RSI`
- `MACD`
- `Bollinger Bands`
- `ATR`
- 可选 `ADX`

#### Kline Loop

```text
round 1:
  get_klines + get_ticker

round 2:
  compute_indicators

round 3:
  if conflict or insufficient context:
    pull an extra timeframe or stop with insufficiency
```

#### Stop Rule

以下情况必须返回 `insufficient`：

- 核心周期行情数据不可用
- 指标无法计算或严重缺失
- 多周期结论冲突且无法通过补充周期收敛

KlineAgent 不允许在没有真实行情的情况下伪造技术结论。

## SummaryAgent Design

### Goal

`SummaryAgent` 是唯一面向用户产出最终回答的层。

### Responsibilities

- 接收一个或多个子 agent 结果
- 汇总关键证据
- 明确指出证据充分或不足
- 产出最终回答

### Rules

- 单任务也必须经过 `SummaryAgent`
- `SummaryAgent` 不允许发明不存在的证据
- 如果上游 agent 返回 `insufficient`，总结层必须保留该结论
- mixed 场景下，如果一侧充分、一侧不足，必须明确说明“哪部分不足”

## Tool Integration Strategy

### Research Tools

第一版优先真实可用且免费：

- 公开网页搜索
- 网页抓取/正文提取
- 现有 market/protocol snapshot

商业搜索 API 例如 Tavily 可以在第二阶段接入，但不作为第一版必需条件。

### Kline Tools

第一版直接接：

- Binance 公共行情接口
- 本地技术指标库

指标库优先级：

1. `TA-Lib`
2. 若部署环境不稳定，则用等价本地 Python 指标实现作兜底

## Trace Design

### Goal

trace 必须证明“planner 真在规划，子 agent 真在调用工具，summary 真在基于结果说话”。

### Required Trace Layers

1. `planner`
   - 原始问题
   - planner 目标
   - planner 模式选择
   - 调用哪些子 agent
   - 原因摘要

2. `sub-agent loop`
   - agent 名称
   - 第几轮
   - 本轮目标
   - 工具调用列表
   - 每个工具输入摘要
   - 每个工具输出摘要
   - 本轮自检结论

3. `summary`
   - 汇总输入
   - 采用了哪些证据
   - 哪些部分证据不足
   - 最终回答

4. `final outcome`
   - `success / clarify / insufficient / failed`
   - 总工具调用数
   - 总轮数

### Suggested Events

- `planner.started`
- `planner.completed`
- `agent.research.started`
- `agent.research.tool_called`
- `agent.research.tool_result`
- `agent.research.reflection`
- `agent.research.completed`
- `agent.kline.started`
- `agent.kline.tool_called`
- `agent.kline.tool_result`
- `agent.kline.reflection`
- `agent.kline.completed`
- `summary.started`
- `summary.completed`

## Safety and Failure Policy

- 最大工具反思轮数：`3`
- 任何上游数据源失败都要显式记录
- 证据不足时必须停止，不允许保守硬推结论
- 最终回答必须严格来自子 agent 结果
- 如果 planner 无法确定模式，优先澄清，不猜

## Phased Delivery

### Phase 1

打通真实链路：

- LLM `PlannerAgent`
- `ResearchAgent` 工具循环骨架
- `KlineAgent` 工具循环骨架
- 单任务与多任务统一走 `SummaryAgent`
- trace 记录 planner 决策和 agent 轮次

### Phase 2

强化 Kline：

- 接 Binance 公共行情
- 补齐核心指标
- 形成更稳定的结构化市场结论

### Phase 3

强化 Research：

- 多轮搜索和抓取
- 更好的证据提取
- 更清晰的证据充分性判断

### Phase 4

前端和 trace 展示收口：

- 明确显示 planner 决策
- 明确显示 agent 工具调用
- 明确显示证据是否足够

## Acceptance Criteria

以下行为都必须成立：

1. 问 `BTC 日线周线怎么看`
   - planner 选择 `kline_only`
   - 调用 `KlineAgent`
   - `KlineAgent` 实际调用行情和指标工具
   - 最终通过 `SummaryAgent` 给出 K 线回答

2. 问 `SUI 值不值得继续拿`
   - planner 选择 `research_only`
   - 调用 `ResearchAgent`
   - `ResearchAgent` 实际进行搜索、抓取和证据汇总
   - 证据足够时给出研究回答，不足时明确停止

3. 问 `SUI 值不值得继续拿，顺便看下走势`
   - planner 选择 `mixed_analysis`
   - 同时调用 `ResearchAgent` 与 `KlineAgent`
   - 最终统一走 `SummaryAgent`

4. 问题不明确
   - planner 返回 `clarify`
   - 不调用子 agent

5. 打开 trace
   - 能看见 planner 选择了什么路径
   - 能看见每个子 agent 调了哪些工具
   - 能看见每轮自检是否认为证据足够

## Open Questions

这版设计仍保留两个后续决策点：

1. 公开网页搜索的第一版实现选型
   - 直接搜索引擎 HTML 抓取
   - 第三方免 key 搜索封装
   - 后续再接 Tavily

2. 技术指标库的部署稳定性
   - 优先 `TA-Lib`
   - 若环境安装复杂，则提供本地纯 Python 兜底实现

## Recommendation

按这份设计推进。

原因：

- 它满足“planner 真规划、子 agent 真调用工具、结果不足就停止”的核心要求
- 它仍然保留可运行边界，不会在第一版就变成一个失控的通用 agent 平台
- 它能把当前系统从“规则编排器”升级为“可审计的 agentic runtime”

# Semantic Planner Design

## Goal

把当前项目里的 planner 从“LLM 决定模式 + 规则补 slot”升级成“LLM 语义解析为主、规则仅做 fallback 和校验”的规划器。

这次改造要解决的核心问题是：

- 用户明确说了 `1h线、4h线、给投资建议`
- planner 能识别“这是 K 线分析”
- 但 `timeframes` 仍然主要靠硬编码提取，导致 `1h` 这种表达漏掉

目标是让 planner 直接从问题语义中结构化产出：

- `asset`
- `timeframes`
- `market_type`
- `mode`
- `analysis_intent`
- `response_style`

而不是先用规则判断，再靠 `_extract_timeframes()` 兜时间周期。

## Non-Goals

这次不做：

- 重写 `ResearchAgent` / `KlineAgent` 的 ReAct runtime
- 新增更多 agent 类型
- 改 summary UI
- 做工具回放执行
- 把 planner 也改造成多轮 ReAct agent
- 改 Binance 市场数据链路

## Current Problems

当前 planner 的问题不在“完全没有 LLM”，而在“LLM 不是主 slot source”。

现状：

- `PlannerLLMService` 已经存在，能输出结构化 `PlannerDecision`
- 但 `planner.py` 里仍保留大量 fallback 语义提取逻辑
- `timeframes` 在 fallback 和 plan 构建时仍高度依赖 `_extract_timeframes()`

直接后果：

1. planner 只能稳定识别非常少的时间周期表达
2. `1h`、`15m`、`30m`、`2h` 等表达容易丢
3. “给建议”“看入场时机”这类输出意图没有被显式建模
4. 架构上已经有 tool-augmented agents，但 planner 仍像半规则解析器，层次不一致

## Recommended Approach

推荐采用：

`LLM semantic planning + schema normalization + heuristic fallback`

具体含义：

1. `PlannerLLMService` 成为主路径
   它负责从自然语言里语义解析出完整 `PlannerDecision.inputs`
2. `planner.py` 不再把 `_extract_timeframes()` 作为主逻辑
   规则提取只在 LLM 不可用、超时、返回非法结构时兜底
3. 增加一个轻量 normalization 层
   对 LLM 返回的 `timeframes / market_type / response_style` 做标准化和白名单校验

这个方案的优点：

- 和当前 agent/tool 架构一致
- 能直接覆盖 `1h线、4h线、小时线、周线` 这类自然表达
- 不需要把 planner 升级成复杂多轮 agent，也不会引入过大范围改动

## Target Architecture

规划路径调整为：

```text
User Query
  -> ContextBuilder
  -> PlannerLLMService (primary)
     -> semantic PlannerDecision
  -> PlannerNormalizer
     -> normalize asset / timeframes / market_type / response_style
  -> Planner
     -> validate or fallback
  -> Plan
  -> Executor
```

其中责任边界是：

- `PlannerLLMService`
  只负责语义理解和结构化输出
- `PlannerNormalizer`
  只负责把语义结果变成系统允许的稳定枚举和值
- `Planner`
  只负责：
  - 选择 `llm` 还是 `fallback`
  - 校验输出
  - 构建 `Plan`

## Planner Output Changes

当前 `PlannerDecision` 的顶层结构可以保留，但 `inputs` 的语义要更明确。

第一版建议标准化这些字段：

- `asset: str | None`
- `timeframes: list[str]`
- `market_type: "spot" | "futures"`
- `analysis_intent: "trend" | "entry" | "risk_review" | "mixed"`
- `response_style: "analysis" | "investment_advice" | "entry_setup"`

示例：

```json
{
  "mode": "kline_only",
  "goal": "Analyze BTC spot on 1h and 4h and provide a practical investment view.",
  "requires_clarification": false,
  "clarification_question": null,
  "agents_to_invoke": ["KlineAgent", "SummaryAgent"],
  "inputs": {
    "asset": "BTC",
    "timeframes": ["1h", "4h"],
    "market_type": "spot",
    "analysis_intent": "entry",
    "response_style": "investment_advice"
  },
  "reasoning_summary": "The user asked for multi-timeframe chart analysis plus actionable guidance."
}
```

## Normalization Rules

`PlannerNormalizer` 需要做这些规范化：

### Timeframes

允许值先限定在：

- `15m`
- `30m`
- `1h`
- `4h`
- `1d`
- `1w`

规则：

- 去重
- 保留用户提到的顺序
- 过滤非法值
- 如果 LLM 返回空：
  - 再退回 fallback 提取
  - fallback 也为空时再用 session 或默认值

### Market Type

语义映射：

- `现货` -> `spot`
- `合约` / `永续` / `期货` -> `futures`
- 未提及时默认 `spot`

### Response Style

语义映射：

- 普通“看看走势” -> `analysis`
- “能不能买 / 给建议 / 怎么看是否适合入手” -> `investment_advice`
- “入场点 / 止损 / 交易计划” -> `entry_setup`

这不是为了让 planner 直接给交易建议，而是把“用户要什么类型的回答”结构化传给下游 summary / answer generation。

## Fallback Strategy

规则 fallback 仍然保留，但角色要降级：

- LLM 不可用
- LLM 超时
- LLM 返回非法 JSON
- LLM 输出未通过 schema 校验

只有这些情况才进入 heuristic fallback。

fallback 中的 `_extract_timeframes()` 需要补齐基础支持，但它不再是主路径，只是兜底：

- `周线 -> 1w`
- `日线 -> 1d`
- `小时线 / 1h -> 1h`
- `4h -> 4h`
- `15m / 30m`

## Downstream Impact

这次不会改 executor 调度结构，但会让下游拿到更完整的 slots：

- `KlineAgent`
  会更稳定收到 `["1h", "4h"]` 这类多周期输入
- `SummaryAgent`
  会多拿到 `analysis_intent / response_style`
- `AnswerGenerationService`
  后续可以基于 `response_style` 调整答案语气，而不是只看 `missing_information`

第一版可以先只把这些字段传下去，即使暂时不完全消费，也先把 contract 建起来。

## Error Handling

planner 层需要明确记录这些状态：

- `planner_source = llm`
- `planner_source = fallback`
- `planner_fallback_reason = timeout | invalid_json | schema_invalid | not_configured`

这样 trace 页面里能直接看出：

- 这次是不是走了语义 planner
- 如果没走，是为什么退回规则 planner

## Testing Strategy

需要补的测试分三类：

1. `PlannerLLMService`
   - 能返回带 `1h/4h/response_style` 的结构化决策
   - 非法输出会返回 `None`

2. `Planner`
   - 当 LLM 返回 `1h + 4h` 时，最终 plan 保留这两个周期
   - 当 LLM 缺失 `timeframes` 时，才用 fallback 提取
   - 当问题是“给投资建议”时，plan 中保留 `response_style`

3. `Orchestrator`
   - 最终 task slots 与 execution summary 中能看到 planner 产出的标准化输入

## Acceptance Criteria

这次改造完成后，应满足：

- 问 `BTC 现货的1h线、4h线，然后给出投资建议`
  - planner 主路径产出 `timeframes=["1h","4h"]`
  - 不再因为硬编码缺失而丢掉 `1h`
- planner trace 能明确显示本次是 `llm` 还是 `fallback`
- fallback 仍然存在，但不再是时间周期理解的主路径
- 不影响现有 `research_only / kline_only / mixed_analysis` 三种主执行模式

## Rollout Plan

建议分两步：

1. 把 planner 改成 `LLM primary`
   - 加 normalizer
   - 保留 fallback
   - 补 `1h/15m/30m`

2. 再让 summary / answer generation 更明确消费 `response_style`

第一步就足以修掉当前你碰到的 “1h 被漏掉” 这个核心问题。

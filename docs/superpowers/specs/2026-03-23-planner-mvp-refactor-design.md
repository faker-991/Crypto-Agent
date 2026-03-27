# Crypto Agent Planner MVP Refactor Design

## Goal

在保留当前产品壳、前端页面、`memory/` 文件结构、`conversations`、`traces`、`watchlist`、`paper trading` 的前提下，把当前项目从 `RouterService -> agent` 的顶层路由架构，重构为：

```text
User Query
  -> ContextBuilder
  -> Planner
  -> Executor
      -> ResearchAgent
      -> KlineAgent
      -> SummaryAgent
  -> Final Response
```

这次改造要求：

- 彻底删除 `router` 模块及其语义
- 前后端命名统一改为 `planner / orchestrator`
- 保留现有页面和已有本地数据继续可用
- 只做 Planner MVP，不顺手扩展非必要能力

## Non-Goals

这次不做：

- 新开一个 repo 或重新搭一个新项目
- 自动交易或下单编排
- 并行任务调度
- 复杂 replan
- 多 agent 互相对话
- 重型长期 memory 检索
- 数据库化改造
- 前端整体重做

## Current State

当前系统顶层编排是典型的 router 驱动：

```text
User Query
  -> RouterService
  -> RouterAgent / RouterLLMService
  -> execute / clarify / fallback
  -> ResearchAgent or KlineAgent
```

当前已经和 router 绑定的关键位置包括：

- `backend/app/main.py`
  - 应用启动时直接注入 `RouterService`
- `backend/app/services/conversation_service.py`
  - `send_message()` 直接调用 `route_and_execute()`
- `backend/app/api/router.py`
  - 暴露 `/api/router/route` 和 `/api/router/execute`
- `frontend/components/router-chat.tsx`
  - 页面和文案都围绕 router 组织
- `frontend/lib/api.ts`
  - 暴露 `executeRouterQuery()` 和 `RouterExecutionResponse`
- `memory/traces/*.json`
  - trace 事件以 `router.*` 为主

这说明当前问题不是“加一个 planner 文件”就够了，而是要替换整个顶层编排语义。

## Why Not A New Project

不建议重开项目。

原因：

1. 现有前端页面已经可运行，且和本地 memory、conversation、trace 紧密绑定。
2. `watchlist`、`paper trading`、`/memory`、`/traces` 都已接入当前 backend。
3. 用户明确要求保留现有页面和已有本地数据，并且彻底删除 router 语义。
4. 如果新开项目，最终仍然要把 conversation、trace、memory、前端页面和辅助功能再接回一次，成本更高，收益更小。

推荐路径是：**同仓原地替换式重构**。

## Recommended Approach

采用“同仓换核”的方式：

- 保留 repo、前端布局、memory 文件结构和主要 domain service
- 新增 `orchestrator/` 与新的 planning schema
- 保留 `ResearchAgent` 和 `KlineAgent` 作为底层执行单元
- 新增 `SummaryAgent`
- 用 `OrchestratorService` 替代 `RouterService` 成为顶层入口
- 前端和 API 从 `router` 语义切到 `planner` / `orchestrator`
- 完成切换后彻底删除 router 相关模块和文案

不选“新开 repo”的原因已经在上一节说明。  
不选“长期并存 router 和 planner”的原因是用户要求最终彻底删除 router，而且前后端语义也要一起切掉。

## Target Architecture

### High-Level Flow

```text
User Message
  -> Planner API
  -> OrchestratorService
  -> ContextBuilder.build()
  -> PlanningContext
  -> Planner.plan()
  -> Plan
  -> Executor.execute()
  -> TaskResult[]
  -> SummaryAgent.summarize()
  -> PlannerExecutionResponse
  -> ConversationService writeback
  -> TraceLogService
```

### Core Principles

- `ContextBuilder` 只组装上下文，不做最终规划
- `Planner` 是唯一负责意图理解、follow-up 判断、任务拆解、clarify 判断的模块
- `Executor` 只执行任务，不做规划
- `SummaryAgent` 只总结结果，不做任务拆解
- 会话、trace、memory 都继续保留，只改编排内核和命名语义

## Module Design

### `backend/app/orchestrator/context_builder.py`

职责：

- 读取当前 query
- 读取 `session_state`
- 读取 recent task summaries
- 读取轻量 memory 摘要
- 读取系统 capabilities 和 constraints
- 生成 `PlanningContext`

约束：

- 不做最终 intent 判断
- 不做 task planning
- 不做 agent 路由

建议方法：

- `build(query: str, conversation_id: str | None = None) -> PlanningContext`

### `backend/app/orchestrator/planner.py`

职责：

- 理解单任务、复合任务、follow-up、unclear
- 判断是否需要澄清
- 产出结构化 `Plan`

Planner 是这次改造后的唯一顶层决策器。

建议方法：

- `plan(context: PlanningContext) -> Plan`

### `backend/app/orchestrator/executor.py`

职责：

- 按 `Plan.tasks` 顺序执行
- 根据 `task_type` 调用不同 agent
- 返回 `TaskResult[]`

MVP 中不做并行调度，只做顺序执行。

建议方法：

- `execute(plan: Plan) -> list[TaskResult]`

### `backend/app/orchestrator/orchestrator_service.py`

职责：

- 作为后端外部统一入口
- 串联 ContextBuilder、Planner、Executor、SummaryAgent、TraceLogService、SessionStateService
- 返回统一 `PlannerExecutionResponse`

它是 `RouterService` 的替代者，但不再使用 route 语义。

### `backend/app/agents/summary_agent.py`

职责：

- 接收 `TaskResult[]`
- 融合 research / kline 结果
- 生成最终 `final_answer`
- 生成稳定的 `execution_summary`

它不做规划，也不直接发起工具调用。

## Directory Layout

推荐目录调整为：

```text
backend/app/
  orchestrator/
    context_builder.py
    planner.py
    executor.py
    orchestrator_service.py

  agents/
    research_agent.py
    kline_agent.py
    summary_agent.py

  schemas/
    planning_context.py
    plan.py
    task.py
    task_result.py
    planner_response.py

  api/
    planner.py
```

现有这些模块在切换完成后应删除：

- `backend/app/services/router_service.py`
- `backend/app/agents/router_agent.py`
- `backend/app/services/router_llm_service.py`
- `backend/app/api/router.py`

## Schema Design

### `PlanningContext`

`PlanningContext` 是给 Planner 的唯一输入对象。

建议包含：

- `user_request`
  - `raw_query`
  - `normalized_goal`
  - `request_type`
- `session_context`
  - `current_asset`
  - `last_intent`
  - `last_timeframes`
  - `active_topic`
- `recent_context`
  - `recent_task_summaries`
- `memory_context`
  - `relevant_memories`
- `capabilities`
  - `available_agents`
  - `available_tools`
- `constraints`
  - `analysis_only`
  - `must_clarify_if_ambiguous`
  - `must_clarify_if_asset_missing`

原则：

- 只描述事实和约束
- 不提前写入执行结论

### `Task`

MVP 只支持三类任务：

- `research`
- `kline`
- `summary`

建议字段：

- `task_id`
- `task_type`
- `title`
- `slots`
- `depends_on`

### `Plan`

建议字段：

- `goal`
- `mode`
- `needs_clarification`
- `clarification_question`
- `tasks`

如果 `needs_clarification=True`，则 `tasks` 可以为空。

### `TaskResult`

建议字段：

- `task_id`
- `task_type`
- `agent`
- `status`
- `payload`
- `summary`

### `PlannerExecutionResponse`

建议替代当前 router execute response：

- `status`
  - `execute | clarify | failed`
- `plan`
- `task_results`
- `final_answer`
- `execution_summary`
- `trace_path`
- `events`

这样前端不再依赖 `route.type / route.agent / route.skill`。

## Planning Behavior

### Supported Request Types

本次 MVP 只支持：

1. 单任务 K 线分析  
   例：`看下 BTC 4h`

2. 单任务基础研究  
   例：`帮我研究一下 SUI 基本面`

3. 复合请求  
   例：`分析 SUI 值不值得继续拿，顺便看下周线和4h走势`

4. follow-up 请求  
   例：`那它周线呢`、`再结合基本面说一下`

### Clarification Rules

Planner 必须统一负责澄清判断。

需要澄清的典型情况：

- 缺资产且无法从 session 补全
- 请求目标不明确
- follow-up 但上下文不足
- 一个 query 中同时要求的动作超出 MVP 范围

### Follow-Up Handling

follow-up 不应单独做成一套特殊接口，而应体现在：

- `PlanningContext.user_request.request_type`
- `session_context`
- `recent_context`

处理方式：

- `ContextBuilder` 标记 `request_type=follow_up`
- `Planner` 结合 `session_context.current_asset`、`last_timeframes`、recent summaries 做推断
- 如果推断失败，再返回 clarify

## Executor Design

Executor 只做执行，不做顶层理解。

执行规则：

- `research` 任务调用 `ResearchAgent`
- `kline` 任务调用 `KlineAgent`
- `summary` 任务调用 `SummaryAgent`

MVP 中使用顺序执行：

- 先执行无依赖任务
- 再执行依赖 `research` / `kline` 的 `summary`

不做：

- 并行执行
- retry/replan
- agent 互相对话

## Conversation Integration

当前 `ConversationService.send_message()` 直接调用 `RouterService.route_and_execute()`。

目标改为：

```text
send_message()
  -> OrchestratorService.execute()
  -> answer_generation
  -> append conversation messages
```

保留：

- `ConversationMemoryService`
- conversation transcript 文件
- `answer_generation` 层

替换：

- `route_summary` 相关语义
- router 相关 fallback 文案

建议：

- 会话消息中的 `route_summary` 字段重命名为 `plan_summary` 或 `orchestration_summary`
- 如果本次为了降低前端改动量暂时保留结构相似字段，也必须去掉 router 命名

## API Changes

### Delete

- `/api/router/route`
- `/api/router/execute`

### Add

- `/api/planner/plan`
- `/api/planner/execute`

其中：

- `/api/planner/plan`
  - 用于返回纯规划结果，可选
- `/api/planner/execute`
  - 作为主聊天链路执行入口

当前前端和会话链路最终都应依赖 `/api/planner/execute`。

## Frontend Changes

目标是保留页面，不保留 router 语义。

需要改动：

- `frontend/components/router-chat.tsx`
  - 改名为 `planner-chat.tsx` 或 `agent-chat.tsx`
- `frontend/lib/api.ts`
  - 删除 `executeRouterQuery`
  - 新增 `executePlannerQuery`
  - 类型从 `RouterExecutionResponse` 改为 `PlannerExecutionResponse`
- 首页和聊天页文案中所有 `Router Chat`、`router execution`、`real router execution path` 全部替换
- `/traces` 页面中的 route 展示改为 plan/execution 展示

不建议：

- 为了这次重构同时重做聊天页面布局

原因：

- 当前问题是编排内核，不是 UI 结构
- 页面壳已经够用，没必要把风险扩散到视觉层

## Trace Changes

trace 继续保留，但语义要完全切换。

### Event Naming

旧事件：

- `router.classified`
- `router.clarify`
- `router.fallback`

新事件建议：

- `planner.context_built`
- `planner.plan_created`
- `planner.clarify`
- `executor.task_started`
- `executor.task_completed`
- `summary.completed`
- `answer_generation.started`
- `answer_generation.completed`

### Trace Payload Shape

旧 trace 顶层字段里的 `route` 应改成：

- `plan`
  或
- `orchestration`

推荐使用 `plan`，更直接。

同时保留：

- `timestamp`
- `user_query`
- `execution_summary`
- `events`

新增或强化：

- `task_results`
- `final_answer`

### Historical Trace Compatibility

为了保留已有 `/traces` 页面和旧数据可读性，允许 trace 读取层对旧格式做兼容展示，但新写入格式必须去掉 router 语义。

## Memory And State Compatibility

本次不重命名或破坏这些现有文件层：

- `memory/session/current_session.json`
- `memory/conversations/*.json`
- `memory/conversations/index.json`
- `memory/traces/*.json`
- `memory/assets/*.md|json`
- `memory/watchlist.json`
- `memory/paper_portfolio.json`
- `memory/paper_orders.json`

`SessionStateService` 可以继续复用，但字段语义需要从 router 时代逐步转成 planner 时代，例如：

- `last_intent`
  - 可以先保留，后续再评估是否改成更中性的字段
- `last_timeframes`
  - 继续保留
- `current_task`
  - 更适合在 Planner 时代继续使用
- `last_skill` / `last_agent`
  - 仍可保留，作为最近执行线索

原则是：

- 先保留兼容字段
- 再逐步去 router 语义
- 不打断当前本地数据继续可读

## Migration Plan

推荐迁移顺序：

1. 先新增 schema 和 `orchestrator/` 主链路
2. 新增 `SummaryAgent`
3. 让 `ConversationService` 切到 `OrchestratorService`
4. 新增 `/api/planner/*`
5. 前端聊天页、API client、文案统一去 router 化
6. trace 事件和 trace 展示切换到 planner 语义
7. 回归验证聊天、`/traces`、`/memory`、watchlist、paper trading
8. 最后删除 router 模块和残留命名

## Risks

### 1. Conversation Chain Regression

聊天主链路当前直接依赖 `RouterService`。  
如果切换顺序错误，首页会直接失去可用性。

### 2. Trace Viewer Regression

`/traces` 页面如果强依赖旧 `route` 结构，切 planner 后会出现展示断裂。

### 3. Frontend Naming Drift

如果只改 backend，不改前端 copy、类型名、组件名，会出现“内部是 planner，页面还叫 router”的混乱状态。

### 4. Over-Scoping

如果在这次改造里顺手把 watchlist update、report generation、thesis break、复杂 memory retrieval 都纳入 Planner MVP，会显著拉长周期并增加回归面。

## MVP Boundaries

本次只要求新的 Planner 主链稳定支持：

- 单任务 K 线
- 单任务研究
- 复合任务
- follow-up

其余自然语言能力不应成为本次重构的完成门槛。

`watchlist`、`paper trading`、`/memory`、`/traces` 页面必须继续保留，但不要求所有历史 router skill 都在 Planner MVP 第一版全部恢复。

## Testing Strategy

至少覆盖：

### Backend

- `ContextBuilder` 单测
- `Planner` 单测
  - single task
  - multi task
  - follow-up
  - clarify
- `Executor` 单测
- `OrchestratorService` 集成测试
- `ConversationService` 集成测试
- trace 写入格式测试

### Frontend

- 首页聊天链路能正常发消息
- 会话列表和 transcript 继续可读
- assistant 卡片能展示新 execution summary
- `/traces` 页面可读新 trace

## Final Recommendation

这次改造应在当前 repo 内执行，采用“原地替换式重构”：

- 保留产品壳和数据层
- 替换顶层编排内核
- 统一去 router 语义
- 最终彻底删除 router 相关模块、API、事件和前端文案

这条路径比“新开项目再迁回功能”更稳、更快，也更符合当前保留页面和历史数据的目标。

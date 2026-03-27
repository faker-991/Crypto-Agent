# Crypto Agent System Architecture

## 1. Overview

`crypto-agent` 是一个本地优先的加密研究工作台，目标不是做交易所级系统，而是把以下能力串起来：

- 自然语言提问
- planner 编排
- 研究与技术分析 agent 执行
- 本地文件型记忆
- 观察池与 paper trading
- trace 复盘
- 一个可直接查看状态的前端界面

整体采用轻量全栈架构：

- 后端：`FastAPI`
- 前端：`Next.js App Router`
- 持久化：本地 `markdown/json`
- 编排：`ContextBuilder -> Planner -> Executor -> SummaryAgent`

---

## 2. High-Level Architecture

```text
User
  ↓
Next.js Frontend
  ↓ HTTP
FastAPI Backend
  ├─ API Routers
  ├─ Orchestrator Layer
  ├─ Agent Layer
  ├─ Service Layer
  ├─ External Adapters
  └─ Local Memory Files
```

核心思路：

- 前端只负责展示和触发操作
- 后端 API 负责稳定的输入输出契约
- orchestrator 层负责单轮请求的规划、执行和结果汇总
- agent 层只负责研究、K 线和总结执行
- 所有状态尽量沉淀到 `memory/`，避免引入数据库复杂度

---

## 3. Backend Architecture

后端入口在 [backend/app/main.py](/home/akalaopaoer/code/crypto-agent/backend/app/main.py)。

应用启动时会初始化这些核心服务：

- `MemoryService`
- `PaperTradingService`
- `MarketDataService`
- `OrchestratorService`
- `TraceLogService`
- `SchedulerService`

然后通过 FastAPI dependency override 注入到各个 API router。

### 3.1 API Layer

API 层按领域拆分：

- `api/watchlist.py`
- `api/memory.py`
- `api/paper_trading.py`
- `api/planner.py`
- `api/research.py`
- `api/trace.py`
- `api/conversations.py`

职责边界：

- 接收 HTTP 请求
- 调用 service
- 返回 schema
- 不承载复杂业务决策

### 3.2 Orchestrator Layer

编排主链位于 `backend/app/orchestrator/`：

- `ContextBuilder`
  - 读取 session、recent summaries、memory preview
  - 组装 `PlanningContext`

- `Planner`
  - 把 query 转成 `Plan`
  - 输出 `execute / clarify / failed`
  - 产出 `Task[]`

- `Executor`
  - 顺序执行 `research`、`kline`、`summary`
  - 收集 `TaskResult[]`

- `OrchestratorService`
  - 对外统一入口
  - 负责串联 context、plan、execution、summary、trace、session writeback

### 3.3 Agent Layer

Agent 层按任务拆成三个核心 agent：

- `ResearchAgent`
  - 负责项目基本面、观察池 review、周报、thesis break 等研究任务
  - 会写入 `assets/*.md|json`、`journal/*.md`、`reports/weekly/*.md`

- `KlineAgent`
  - 负责 K 线技术分析
  - 输出多周期分析、MA、支撑阻力、breakout 等结论
  - 兼容式写回 asset metadata

- `SummaryAgent`
  - 汇总多个 `TaskResult`
  - 生成 `final_answer` 和 `execution_summary`

agent 不直接互相调用，而是由 `Executor` 协调。

### 3.4 Service Layer

服务层负责把 orchestrator、memory、外部数据源和 API 连接起来。

主要服务包括：

- `MarketDataService`
  - 聚合行情读取
  - 当前主要走 Binance 公共市场接口

- `PaperTradingService`
  - 维护模拟仓位和订单记录
  - 数据落在 `paper_portfolio.json` / `paper_orders.json`

- `TraceLogService`
  - 记录每次 planner 执行过程
  - 用于 `/traces` 页面回放

- `ConversationService`
  - 维护会话与消息持久化
  - 调用 `OrchestratorService` 和答案生成层

- `SchedulerService`
  - 启动时注册定时任务
  - 当前用于周报生成

### 3.5 External Adapter Layer

外部适配器放在 `backend/app/clients/`：

- `binance_market_adapter.py`
- `external_research_adapter.py`

职责：

- 封装第三方 HTTP 请求
- 降低上层对外部接口细节的依赖
- 保持服务层代码更稳定

---

## 4. Memory Architecture

项目的持久化核心不是数据库，而是 `memory/` 目录下的分层文件。

### 4.1 Layering

- Short-term memory
  - `memory/session/current_session.json`
  - 保存当前资产、最近意图、最近周期、当前任务、上一次 agent

- Conversation memory
  - `memory/conversations/index.json`
  - `memory/conversations/*.json`

- Long-term memory
  - `memory/MEMORY.md`
  - `memory/profile.json`
  - `memory/assets/*.md`
  - `memory/assets/*.json`
  - `memory/watchlist.json`
  - `memory/alerts.json`

- Episodic memory
  - `memory/journal/*.md`
  - 保存面向人类复盘的关键事件摘要

- Execution trace memory
  - `memory/traces/*.json`
  - 保存完整机器执行轨迹

### 4.2 Memory Services

围绕 memory 又拆成了更细的服务：

- `BootstrapService`
  - 确保所有默认文件和目录存在

- `SessionStateService`
  - 读写短期会话态

- `ProfileMemoryService`
  - 读写用户长期偏好

- `AssetMemoryService`
  - 读写 thesis markdown 和结构化 metadata
  - 兼容旧的 `memory/theses/` 读取

- `JournalMemoryService`
  - 追加和读取 journal 条目

- `ContextAssemblyService`
  - 为 planner、research、kline 组装运行时上下文

- `MemoryService`
  - 对外兼容 facade
  - 给 API 层提供稳定读取接口

### 4.3 Memory Read/Write Pattern

写入大致遵循下面的流向：

```text
Planner execution
  ↓
Domain service / agent writeback
  ↓
session / assets / journal / traces / reports
```

读取大致分两类：

- 前端读 API
  - `/api/memory`
  - `/api/memory/profile`
  - `/api/memory/assets`
  - `/api/memory/journal`
  - `/api/memory/context-preview`

- orchestrator / agent 读 context
  - 通过 `ContextAssemblyService` 做裁剪和拼装

---

## 5. Planner Execution Flow

用户输入一条自然语言命令后，主链路是：

```text
Frontend conversation input
  ↓
POST /api/planner/execute
  ↓
ContextBuilder
  ↓
Planner
  ↓
Executor
  ↓
ResearchAgent / KlineAgent / SummaryAgent
  ↓
write session / traces / memory updates
  ↓
return plan + task_results + final_answer
```

具体说明：

1. 前端把自然语言 query 发给 planner API 或 conversation API。
2. `ContextBuilder` 读取 session 和 recent context，组装 `PlanningContext`。
3. `Planner` 产出 `Plan`，决定执行还是澄清。
4. `Executor` 执行具体任务，收集 `TaskResult[]`。
5. `SummaryAgent` 生成统一总结。
6. `OrchestratorService` 回写 session、trace，以及必要的 asset/journal/report。
7. 返回前端结构化结果，前端据此展示执行摘要或追问。

---

## 6. Frontend Architecture

前端位于 `frontend/`，采用 Next.js App Router。

主要页面：

- `/`
  - dashboard
  - 观察池
  - paper trading
  - planner chat

- `/assets/[symbol]`
  - 资产详情
  - K 线图与技术分析结果

- `/memory`
  - 文件型 memory 预览

- `/traces`
  - planner 执行轨迹回放

前端职责：

- 获取 API 数据
- 展示 planner 结果、资产信息、trace
- 保持聊天、多会话和页面跳转体验
- 不承载后端编排逻辑

---

## 7. Trace And Observability

`TraceLogService` 会把每次 planner 执行落到 `memory/traces/*.json`。

trace 主要包含：

- 用户 query
- planner status
- plan
- task_results
- execution_summary
- final_answer
- events

历史 router-era trace 仍可读取，但新写入全部使用 planner-era 字段。

---

## 8. Design Principles

当前架构遵循这些原则：

- planner 负责决策，agent 负责执行
- 会话状态与运行时状态分层
- 外部接口失败必须可降级
- 本地文件优先，便于调试和复盘
- 前后端契约稳定，内部实现可演进

---

## 9. Current Characterization

这个项目当前更准确的表述是：

- 一个以 `Planner + Executor + ResearchAgent + KlineAgent + SummaryAgent` 为核心执行单元的 agent workflow
- 一个本地优先、可追踪、可复盘的加密研究工作台
- 一个强调工程边界和可观测性的 LLM 应用系统，而不是单纯聊天壳

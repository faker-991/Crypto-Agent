# Crypto Agent Memory Architecture Design

## Goal

在不破坏现有文件路径、API 路径和已通过测试行为的前提下，把当前项目的记忆系统重编排为一套兼容式长短期记忆架构。该架构需要覆盖：

- `Context Window` 的按需组装
- `Short-term Memory` 的会话态补全
- `Long-term Memory` 的分层持久化
- `Episodic Memory` 的事件沉淀与复盘

目标是让 Router、ResearchAgent、KlineAgent、report flow 都能稳定读写记忆，而不是继续把记忆逻辑零散分布在各个服务里。

## Non-Goals

这次不做：

- 向量数据库
- 全量市场数据仓库
- 全量聊天历史存储
- LangGraph 级别的记忆编排
- 删除或重命名现有记忆文件
- 改变现有 API 路径

## Current State

当前项目已经存在这些记忆文件：

- `memory/MEMORY.md`
- `memory/watchlist.json`
- `memory/paper_portfolio.json`
- `memory/paper_orders.json`
- `memory/session/current_session.json`
- `memory/assets/*.md|json`（由 ResearchAgent/KlineAgent 写入）
- `memory/reports/weekly/*.md`
- `memory/traces/*.json`

当前问题：

1. 短期记忆字段不完整，只够处理最简单的指代补全。
2. 长期记忆没有清晰分层，`profile / journal / alerts / assets` 还没成体系。
3. 当前没有统一的 `Context Window` 组装服务。
4. 关键研究事件只写 trace，没有沉淀为面向复盘的 journal。
5. 现有 `MemoryService` 同时承担多种职责，后续会越来越难维护。

## Recommended Approach

采用“轻量叠加式兼容重编排”：

- 保留现有文件路径与主接口
- 在原有 `memory/` 下补齐缺失层
- 新增分层 memory services
- 用一个统一 `ContextAssemblyService` 把短期态和长期态拼成 agent 所需上下文
- 保持 `RouterService`、`ResearchAgent`、`KlineAgent` 的外部调用方式不变

不选“内部重组 + 全兼容映射层”的原因是当前代码规模还不大，但链路已经多，过早引入一层完整适配只会增加复杂度。

## Memory Model

### 1. Context Window

`Context Window` 不是存储层，而是运行时组装层。每次给 agent 或 LLM 的上下文由以下内容按需拼接：

- 当前用户 query
- 当前任务类型（如 `asset_due_diligence` / `kline_analysis`）
- `session/current_session.json`
- `profile.json`
- 相关 `assets/{symbol}.md|json`
- `watchlist.json`
- 必要的 `journal` 摘要
- 必要的 `traces` 摘要

约束：

- 不允许全量注入历史
- 只注入与当前资产、当前任务、最近行为相关的内容
- 组装结果应是一个明确的数据结构，供后端内部使用；前端不直接依赖它

### 2. Short-term Memory

短期记忆继续使用：

- `memory/session/current_session.json`

结构扩展为：

```json
{
  "current_asset": "SUI",
  "last_intent": "asset_due_diligence",
  "last_timeframes": ["1d"],
  "last_report_type": null,
  "recent_assets": ["BTC", "ETH", "SUI"],
  "current_task": "evaluating whether to add SUI to watchlist",
  "last_skill": "protocol_due_diligence",
  "last_agent": "ResearchAgent"
}
```

用途：

- Router 补全“它 / 这个 / 再生成一下”
- Clarify 之后恢复上一个任务
- 将自然语言命令与前一个执行流衔接起来

### 3. Long-term Memory

长期记忆保留并补齐以下层：

- `memory/MEMORY.md`
- `memory/profile.json`
- `memory/assets/*.md`
- `memory/assets/*.json`
- `memory/watchlist.json`
- `memory/alerts.json`
- `memory/reports/weekly/*.md`
- `memory/paper_portfolio.json`
- `memory/paper_orders.json`

#### User Preference Memory

新增：

- `memory/profile.json`

用于保存中长期稳定偏好，如：

- `investment_style`
- `preferred_sectors`
- `decision_style`
- `risk_preference`
- `avoid`

#### Asset Thesis Memory

继续以 `memory/assets/*.md|json` 为主，不再依赖旧的 `memory/theses/` 路径作为写入主路径。

- `*.md` 保存研究正文
- `*.json` 保存结构化索引字段

建议结构字段至少包括：

- `asset`
- `sector`
- `status`
- `risk_level`
- `time_horizon`
- `thesis_score`
- `invalidated`
- `last_updated`
- `tags`

已有 `ResearchAgent` / `KlineAgent` 输出如果没有这些字段，允许先部分写入，再逐步补齐。

### 4. Episodic Memory

事件型记忆分两层：

- `memory/traces/*.json`
- `memory/journal/YYYY-MM-DD.md`

`traces` 保留机器执行细节。  
`journal` 面向人和复盘，记录：

- 为什么加入观察池
- 为什么下调 thesis
- 某次 review 的结论
- 某次报告里的重要变化

写 journal 的内容应短、解释性强，不复制完整 trace。

## Directory Layout

兼容后的推荐结构：

```text
memory/
├── MEMORY.md
├── profile.json
├── watchlist.json
├── alerts.json
├── paper_portfolio.json
├── paper_orders.json
├── session/
│   └── current_session.json
├── assets/
│   ├── BTC.md
│   ├── BTC.json
│   └── ...
├── journal/
│   ├── 2026-03-17.md
│   └── ...
├── reports/
│   └── weekly/
│       └── 2026-03-17-weekly.md
└── traces/
    └── 20260317T....json
```

## Service Design

### BootstrapService

继续保留，但职责改为“确保所有 memory 文件和目录存在”。  
需要补建：

- `profile.json`
- `alerts.json`
- `assets/`
- `journal/`
- `reports/weekly/`
- `traces/`

不允许覆盖已有文件内容。

### SessionStateService

保留路径和方法名，但扩展 schema 支持：

- `current_task`
- `last_skill`
- `last_agent`

`update_from_intent()` 之外，后续还需要支持从真实执行结果更新这几个字段。

### MemoryService

对外继续作为兼容 facade，保留现有 API 依赖方式。  
内部逐步委托给更细分的服务：

- `ProfileMemoryService`
- `AssetMemoryService`
- `JournalMemoryService`
- `ContextAssemblyService`

这样旧 API 不变，但实现变得可维护。

### ProfileMemoryService

负责：

- 读取/更新 `profile.json`
- 与 `MEMORY.md` 的长期偏好摘要保持一致，但不做强制双向同步

### AssetMemoryService

负责：

- 读写 `memory/assets/*.md|json`
- 标准化资产元数据字段
- 提供按资产获取 thesis 文本和结构化摘要的方法

### JournalMemoryService

负责：

- 读取/写入 `memory/journal/YYYY-MM-DD.md`
- 将关键执行结论追加成简洁条目

### ContextAssemblyService

新增的核心服务。负责为不同任务组装上下文：

- `build_router_context(...)`
- `build_research_context(asset=..., intent=...)`
- `build_kline_context(asset=..., timeframes=...)`

返回值应为结构化 dict，而不是直接拼 prompt 字符串。  
真正接 LLM 或 agent 时，由上层决定如何把该 dict 转成 prompt。

## Writeback Rules

### Router

每次成功执行后更新短期记忆：

- `current_asset`
- `last_intent`
- `last_timeframes`
- `current_task`
- `last_skill`
- `last_agent`

Clarify 时也可以更新最近资产，但不覆盖明确任务结论。

### ResearchAgent

在以下情况写长期记忆：

- `protocol_due_diligence`：写 `assets/{symbol}.md|json`
- `new_token_screening`：写 `assets/{symbol}.md|json`
- `thesis_break_detector`：写 journal 摘要（如果发现 weakening assets）
- `watchlist_weekly_review`：写 weekly report，并可追加 journal 摘要

### KlineAgent

继续写 `assets/{symbol}.md|json`，但只更新技术面部分或结构化字段，不应覆盖完整 thesis 正文。

### TraceLogService

保持现状。Trace 仍然是机器执行日志，不替代 journal。

## Compatibility Strategy

兼容要求如下：

1. 保留现有 API 路径：
   - `/api/memory`
   - `/api/memory/thesis/{symbol}`
   - 现有 watchlist / router / traces 路径
2. 保留现有 `memory/` 根目录不变
3. 保留 `session/current_session.json`
4. 保留 `assets/*.md|json`
5. 不删除旧文件
6. 不要求一次性迁移历史内容

兼容上允许的变化：

- `get_thesis()` 从 `memory/theses/` 切换为优先读取 `memory/assets/{symbol}.md`，旧路径仅作为兼容 fallback
- Bootstrap 补新文件
- Session schema 扩字段

## Migration Strategy

迁移采用“惰性迁移”：

- 启动时仅创建缺失目录和默认文件
- 读取 thesis 时优先 `assets/`，如旧 `theses/` 存在则 fallback
- 新的研究写回统一写入 `assets/`
- `profile.json` 和 `alerts.json` 若不存在则生成默认内容
- `journal/` 从空开始

不做一次性全量迁移脚本，除非后续真的出现大量旧数据。

## API Changes

现有 API 保留。新增 API 可以分阶段补：

- `GET /api/memory/profile`
- `GET /api/memory/assets`
- `GET /api/memory/journal`
- `GET /api/memory/context-preview`

这些都是增强接口，不应阻塞本次重编排的底层实现。

## Testing Strategy

至少新增以下测试：

1. Bootstrap 能创建新 memory 目录与默认文件
2. SessionState 扩展字段仍可读写
3. `get_thesis()` 优先读 `assets/`，兼容 fallback 到旧 `theses/`
4. Asset memory 读写不会破坏现有研究 agent 测试
5. Journal write append 行为正确
6. Context assembly 能按 asset / task 输出裁剪后的上下文
7. Router/Research/Kline 执行后能更新 short-term memory 新字段

## Risks

1. 如果直接让多个 agent 同时写 asset memory，可能出现覆盖问题。
   解决方式：先用“整文件重写 + 写入点收敛”的方式，避免并发写复杂化。

2. `assets/*.md` 被多个 agent 以不同格式写入，可能越来越乱。
   解决方式：在 `AssetMemoryService` 里统一模板，后续让 agent 写结构化字段，再渲染文本。

3. `journal` 写得太频繁会变成噪声。
   解决方式：只在关键事件写入，如加入观察池、thesis weakening、weekly report、研究结论变化。

4. `Context Window` 组装如果不控量，会重新演变成“全量历史注入”。
   解决方式：为每种任务只取必要子集，不提供“读取所有历史”的便捷接口。

## Recommended Build Order

1. Bootstrap 与目录补齐
2. Session schema 扩展
3. `MemoryService.get_thesis()` 改为 `assets/` 优先
4. 引入 `AssetMemoryService` 与 `JournalMemoryService`
5. Router / Research / Kline 写回新字段与 journal
6. 引入 `ContextAssemblyService`
7. 补 memory 增强 API

## Decision

采用兼容式重编排方案：

- 不动旧 API 路径
- 不删旧文件
- 保留现有 session / traces / assets 结构
- 在此基础上补齐 `profile / journal / alerts / context assembly`
- 让当前项目从“文件散点存储”升级为“分层文件型记忆架构”

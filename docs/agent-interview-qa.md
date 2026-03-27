# Agent 项目面试问答

基于项目：`crypto-agent`

当前真实架构：

- 前端：`Next.js`
- 后端：`FastAPI`
- 编排：`ContextBuilder -> Planner -> Executor -> SummaryAgent`
- 执行 agent：`ResearchAgent`、`KlineAgent`
- 持久化：本地 `markdown/json`
- 可观测性：`TraceLogService` + `/traces`

这份文档严格基于当前项目事实写，避免把历史 router 结构说成现状。

---

## 0. 先用一句话介绍项目

短答版：

`crypto-agent` 是一个本地优先的加密研究 Agent 工作台，核心目标是把自然语言提问、任务规划、研究与技术分析执行、本地记忆、Trace 复盘和前端可视化串成一条可执行链路。

展开版：

- 前端用 `Next.js`，后端用 `FastAPI`
- 顶层不是 router，而是 `ContextBuilder -> Planner -> Executor -> SummaryAgent`
- `ResearchAgent` 负责研究任务，`KlineAgent` 负责技术分析
- 持久化没有上数据库，主要落在本地 `markdown/json`
- 市场数据当前走 Binance 公共接口
- 系统支持自然语言提问、规划执行、结果回写、Trace 记录和前端查看

可以补一句体现工程取向的话：

> 我做这个项目时重点不是堆 Agent 概念，而是把“提问 -> 规划 -> 执行 -> 记忆 -> 复盘”做成一条真实可调试的工程链路。

---

## 1. 为什么选择做 Agent 项目？

短答版：

我选择做 Agent 项目，是因为我想做的不只是一个 LLM 包壳应用，而是一个能围绕真实任务做规划、调用能力、持久化上下文并可复盘的系统。

展开版：

- 普通聊天应用更偏问答产品，Agent 项目更接近任务执行系统
- 它要求我解决的不只是 prompt，而是：
  - 任务理解
  - 能力编排
  - 上下文管理
  - 失败降级
  - 可观测性
  - 持久化
- 我希望体现的核心价值不是“我会调 API”，而是：
  - 我能把大模型接到真实业务链路
  - 我能把不稳定的外部依赖做成稳定系统
  - 我知道 Agent 难点在工程边界和执行闭环

---

## 2. 讲下你做的 Agent 项目：核心目标、技术难点、你负责的模块及落地效果

短答版：

这个项目的核心目标，是做一个面向加密研究场景的本地 Agent 工作台。用户输入自然语言后，系统会先构建上下文，再由 planner 生成结构化计划，executor 调用研究或 K 线 agent 执行，summary agent 汇总结果，最后把结果写回本地 memory，并记录 trace 供前端复盘。

技术难点：

- 自然语言请求如何稳定映射为可执行 `Plan`
- 多任务执行如何保持清晰职责边界
- 市场数据链路如何避免假数据污染用户结论
- 文件型 memory 如何兼顾可读性和可维护性
- 整条执行链如何做到可追踪、可降级、可复盘

我负责的模块：

- planner/orchestrator 主链
- Kline 数据链与技术分析
- memory 分层
- trace 可观测性
- 前后端联调

落地效果：

- 已支持单任务研究
- 已支持单任务 K 线分析
- 已支持研究 + K 线复合任务
- 已支持 follow-up 和 clarify
- 已支持 Binance 行情/K 线接入
- 已支持 Trace 时间线和前端查看
- 已支持本地 memory 分层存储

---

## 3. 演示 Agent 项目实现细节

短答版：

我一般按一条真实链路来讲：用户在前端输入问题，后端先通过 `ContextBuilder` 组装上下文，再由 `Planner` 生成 `Plan`，如果能执行，就由 `Executor` 调用 `ResearchAgent` 或 `KlineAgent`。执行后把结果写回 session、assets 或 traces，最后由 `SummaryAgent` 汇总并返回前端。

关键流程：

```text
User Query
  -> ContextBuilder
  -> PlanningContext
  -> Planner
  -> Plan(tasks)
  -> Executor
  -> ResearchAgent / KlineAgent
  -> SummaryAgent
  -> session / traces / memory writeback
  -> frontend render
```

### 3.1 Planner 链路

- 入口是 `POST /api/planner/execute` 或 conversation API
- `ContextBuilder` 读取 `session/current_session.json`、recent summaries 和 memory preview
- `Planner` 输出 `goal`、`mode`、`needs_clarification`、`tasks`
- `Executor` 顺序执行 `Task[]`
- `SummaryAgent` 负责生成统一 `final_answer` 和 `execution_summary`

### 3.2 Kline 分析链路

- `Planner` 只决定要不要做 Kline 分析以及时间周期
- `KlineAgent` 接收结构化 slots，如 `asset`、`timeframes`、`market_type`
- `MarketDataService` 调 Binance 公共接口
- `KlineAnalysisService` 计算 MA、趋势、支撑阻力、breakout 等
- 如果数据不可用，会显式返回 degraded 状态

### 3.3 Trace 链路

- `TraceLogService` 会记录每次执行
- trace 里包含：
  - `status`
  - `plan`
  - `task_results`
  - `execution_summary`
  - `final_answer`
  - `events`
- `/traces` 页面能直接展示这些结构化数据

---

## 4. Agent 项目开发的核心框架有哪些？你用的是哪种？为什么不选其他框架？

短答版：

Agent 开发常见会涉及 LangChain、LlamaIndex、LangGraph 这类框架。我当前项目的主链没有直接依赖这些框架，而是基于 FastAPI + 自定义 orchestrator 实现，因为当前 MVP 更需要清晰边界和稳定契约。

### 4.1 LangChain

优点：

- 上手快
- tool 封装多
- 适合原型验证

局限：

- 容易把关键状态和执行边界藏起来
- 项目一复杂，调试成本会上升

### 4.2 LlamaIndex

优点：

- 更偏知识库和检索增强
- 文档索引能力强

局限：

- 不适合直接当顶层任务编排核心

### 4.3 LangGraph

优点：

- 适合复杂状态机、多步任务、重规划和分支控制

局限：

- 对当前 MVP 来说偏重
- 如果业务边界还没稳定，先引框架不一定比自定义编排更清楚

### 4.4 我的选择

我当前选择的是：

- `FastAPI` 做 API 契约
- 自定义 `ContextBuilder -> Planner -> Executor -> SummaryAgent`
- `ResearchAgent`、`KlineAgent` 做垂直任务执行

原因：

- 当前任务类型相对清晰
- 我更想先把状态边界、trace 和 memory 打稳
- 后面如果需要更复杂重规划，再迁到图式工作流会更自然

---

## 5. 市面上的主流智能体有哪些？优势、场景、局限性

可以这样答：

- AutoGPT / BabyAGI 类
  - 优势：自治感强
  - 场景：开放探索型任务
  - 局限：稳定性和成本问题大

- Tool-use Assistant 类
  - 优势：适合问答 + 工具调用
  - 场景：客服、办公助手、轻任务自动化
  - 局限：复杂多步状态不容易控

- LangGraph / 企业工作流 Agent
  - 优势：状态清晰、可控、适合工程落地
  - 场景：多步骤业务任务
  - 局限：前期建模成本高

然后补一句：

> 我的项目更接近“工程化可控 Agent”，不是完全自治型 Agent。

---

## 6. 了解其他的 Agent 范式吗？

### 6.1 反应式 Agent

- 输入来了直接根据规则或即时推理做动作
- 响应快，但长期规划弱

### 6.2 目标导向 Agent

- 先明确目标，再拆任务和执行
- 更接近我当前的 planner 架构

### 6.3 分层 Agent

- 顶层负责决策，底层负责执行
- 我当前就是这种模式

### 6.4 多 Agent 协作

- 多个 agent 分别持有能力并协同完成任务
- 我当前是中心化编排，不是自由协作式

---

## 7. Agent 项目的背景是什么？为什么做？市场上同类产品有哪些不足？

短答版：

这个项目的背景，是我希望解决一个更真实的研究场景，而不是做单轮聊天。用户研究币种时，会反复看技术面、基本面、历史结论和观察池状态，这天然需要执行链、memory 和复盘能力。

市场上常见不足：

- 很多产品只有聊天，没有执行闭环
- 很多产品能回答，但不能追踪结果怎么来的
- 很多产品有检索，没有结构化任务规划
- 很多产品没有本地优先的可调试 memory

---

## 8. Agent 推理模式有哪些？各自适用场景是什么？

可以这样分：

- 少样本推理
  - 适合结构比较固定的分类或抽取

- 链式推理
  - 适合需要多步逻辑展开的问题

- 工具增强推理
  - 适合依赖实时外部数据的任务

- 检索增强推理
  - 适合依赖历史知识、文档和记忆的任务

然后补一句：

> 在我这个项目里，最重要的不是让模型自由长推理，而是让 planner 先把任务边界定清楚，再在必要的地方接工具和上下文。

---

## 9. 推理模式的差异化设计思路？如何根据任务选择？

我的设计原则：

- 低风险、结构固定任务
  - 尽量规则化或结构化

- 依赖实时数据任务
  - 先执行工具，再总结

- 依赖历史上下文任务
  - 先读 session / recent summaries / memory preview

- 依赖综合判断任务
  - planner 拆成多个 task，再 summary 汇总

---

## 10. 推理模式的选择机制是什么？如何实现动态切换？

短答版：

当前不是“模型自由切换推理模式”，而是 planner 先做任务类型识别，再决定生成什么 plan。

### 第一层：Task 分流

- 是否是单任务还是多任务
- 是否缺资产，需要 clarify
- 是否是 follow-up，需要用 session 补全

### 第二层：Agent 分流

- `research` task -> `ResearchAgent`
- `kline` task -> `KlineAgent`
- `summary` task -> `SummaryAgent`

### 第三层：输出层分流

- 先给出结构化执行结果
- 如果 answer generation 可用，再生成自然语言答案

---

## 11. Agent skills 的定义、设计思路？如何让 Agent 高效调用 skills？

短答版：

我把“skill”理解成稳定、边界明确、可复用的能力单元，但当前项目主链没有把所有能力都包装成通用 skill runtime。

更实际的做法是：

- 用 planner 负责挑任务
- 用 executor 负责调能力
- 用 agent 或 service 承担具体能力

设计原则：

- 输入输出必须结构化
- 能力边界必须稳定
- 不让 agent 自由互相调用，避免状态失控

---

## 12. 多 Agent 执行策略的智能选择和切换机制设计

### 12.1 为什么不用自由协作式多 Agent

- 状态更难控
- trace 更难看
- 冲突和重复执行风险更高

### 12.2 当前选择机制

- `Planner` 做中心化决策
- `Executor` 按依赖顺序执行
- agent 只负责自己的任务，不直接对话

### 12.3 冲突解决

- 统一通过 `Task` 和 `TaskResult` 契约传递结果
- 统一由 orchestrator 写回 session 和 trace

### 12.4 以后如果扩展多 Agent

- 先让 task 更通用
- 再考虑并行执行和 replan
- 最后才考虑更强自治

---

## 13. 跨模块错误追踪的 Agent 知识库构建方案

可从工程角度答：

- 数据来源：
  - traces
  - conversations
  - journal
  - assets metadata

- 构建流程：
  - 收集执行失败案例
  - 按 task 类型、错误类型、外部依赖分类
  - 形成可检索的调试知识库或评估集

- 优化方向：
  - 增加 degraded 原因聚类
  - 增加 planner clarify case 分类
  - 增加 answer generation 失败案例库

---

## 14. 基于代码构建知识库的 Agent 设计

可以这样答：

- 数据来源：
  - 代码文件
  - 架构文档
  - trace 样本
  - 测试样例

- 构建流程：
  - 先按模块切块
  - 建立文件到职责的映射
  - 让检索优先返回高层设计，再返回细节实现

- 为什么不能直接全文检索：
  - 代码噪音大
  - 上下文很容易超长
  - 没有职责聚合时，回答会失真

---

## 15. 面试时建议主动强调的项目亮点

- 顶层从 router 重构到了 planner/orchestrator
- 规划、执行、总结分层，边界清楚
- memory 分层不是概念，而是真实文件结构
- trace 可直接回放 plan 和 task_results
- 外部依赖失败有显式 degraded 设计
- 前后端都能运行，不是 PPT 项目

---

## 16. 面试官可能继续追问的问题

### 16.1 你这个项目里，LLM 真正起什么作用？

主要在答案生成层，不是单点控制整条主链。

### 16.2 为什么不用数据库？

当前目标是本地优先、可调试和低复杂度；文件型存储更适合当前阶段。

### 16.3 你这个项目的 memory 为什么要分层？

因为 session、conversation、assets、journal、traces 的生命周期和用途不同。

### 16.4 怎么保证 Agent 不乱调用工具？

通过 planner 和 executor 中心化调度，agent 不直接互相调用。

### 16.5 如果 Binance 接口挂了怎么办？

显式 degraded，不伪造数据，同时把状态写进 trace 和前端展示。

### 16.6 你如何评估这个 Agent 项目做得好不好？

- clarify 命中率是否合理
- 任务执行成功率
- degraded 场景是否诚实暴露
- trace 是否能支撑调试
- 用户是否能在多轮会话里持续推进任务

### 16.7 你这个项目和普通 RAG 项目最大的区别是什么？

它不是只检索再回答，而是先规划再执行。

### 16.8 你项目里最难的坑是什么？

最难的是边界设计，不是模型接入。特别是规划、执行、会话状态和 trace 如何统一。

---

## 17. 如果面试官问“你项目还有哪些没做完？”

可以诚实回答：

- 还没有复杂 replan
- 还没有并行 task 执行
- 还没有更通用的多资产复合任务支持
- 还没有数据库和线上化能力
- 还没有把 answer generation 和评估闭环做得更系统

然后补一句：

> 但我觉得这些是自然演进问题，不是基础架构不成立的问题。当前主链已经能稳定支撑真实任务和前端展示。

---

## 18. 一段适合 3 分钟项目介绍的口语稿

> 我做了一个叫 `crypto-agent` 的本地优先加密研究 Agent 工作台。它的核心不是聊天，而是把“提问、规划、执行、记忆、复盘”串成一条真实可执行链路。技术上前端是 `Next.js`，后端是 `FastAPI`。  
>  
> 当前顶层不是 router，而是 `ContextBuilder -> Planner -> Executor -> SummaryAgent`。用户输入自然语言后，系统先读取 session、recent summaries 和 memory context，planner 再把请求拆成结构化任务。如果是研究任务，就调用 `ResearchAgent`；如果是 K 线任务，就调用 `KlineAgent`；如果是复合请求，就会先执行多个 task，再由 `SummaryAgent` 汇总。  
>  
> 整个过程中会调用 Binance 公共接口拿实时数据，把结果写回本地 memory，同时用 `TraceLogService` 记录完整执行轨迹，前端还能直接看 conversations、memory 和 traces。我重点做的是 planner 编排链、Kline 数据链、memory 分层和 trace 可观测性。这个项目让我更关注如何把 Agent 做成一个可调试、可降级、可持续迭代的工程系统，而不只是模型外壳。

---

## 19. 一段适合 30 秒电梯版介绍

> `crypto-agent` 是一个本地优先的加密研究 Agent 工作台。它不是单轮聊天，而是把自然语言提问转成结构化计划，再调用研究和 K 线能力执行，把结果写回 memory，并通过 trace 完整复盘。它的核心价值是规划、执行、记忆和可观测性连成闭环。

---

## 20. 面试时不要说过头的点

- 不要说“完全自治多 Agent”
- 不要说“Planner 已经很智能”
- 不要说“什么任务都能做”
- 不要说“LLM 负责整条链路”
- 不要说“已经是生产级系统”

---

## 21. 最后给你的准备建议

- 一定统一口径，用 planner/orchestrator 术语
- 多讲结构化计划、任务分解、显式降级、trace 可复盘
- 少讲“智能感”，多讲“工程闭环”
- 如果被问深一点，就把答案拉回：
  - 顶层如何规划
  - 底层如何执行
  - 状态如何维护
  - 失败如何降级
  - 结果如何复盘

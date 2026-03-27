# Agent 项目大厂面试 Mock

基于项目：`crypto-agent`

当前真实架构：

- 前端：`Next.js`
- 后端：`FastAPI`
- 编排主链：`ContextBuilder -> Planner -> Executor -> SummaryAgent`
- 执行单元：`ResearchAgent`、`KlineAgent`
- 持久化：本地 `markdown/json`
- 可观测性：`TraceLogService` + `/traces`

使用方式：

- 先自己口头回答
- 再对照“推荐答法”修正
- 最后看“危险答法”，避免把项目讲成概念堆砌

---

## 1. 一面高频题

### Q1. 先介绍一下你这个 Agent 项目

面试官为什么问：

- 看你能不能在 1 到 3 分钟内把项目讲清楚
- 看你讲的是系统链路还是功能堆砌

推荐答法：

> 我做的是一个本地优先的加密研究 Agent 工作台，目标不是做单轮聊天，而是把“提问、规划、执行、记忆、复盘”串成一条真实链路。技术上前端是 `Next.js`，后端是 `FastAPI`。  
>  
> 用户输入自然语言后，后端不会直接自由生成，而是先走 `ContextBuilder -> Planner -> Executor -> SummaryAgent`。`Planner` 负责把请求拆成结构化任务，`Executor` 再调用 `ResearchAgent` 或 `KlineAgent` 执行，最后由 `SummaryAgent` 汇总结果。  
>  
> 执行过程会调用 Binance 公共接口拿实时数据，把结果写回本地 memory，并通过 `TraceLogService` 落成 trace，前端可以直接看会话、结果和执行轨迹。我重点负责的是整体架构、planner 编排链、Kline 数据链、memory 分层和 trace 可观测性。

危险答法：

- “就是一个 AI 看币的网站”
- “用了很多 Agent”
- “本质上就是大模型问答”

---

### Q2. 你为什么要做这个 Agent 项目？

推荐答法：

> 我不想停留在 LLM Demo 层面，而是想做一个更接近真实工作流的系统。加密研究天然不是一次问答，而是要反复看 K 线、查基本面、更新观察池、回看历史结论，这要求系统既能规划执行，又能记忆上下文，还要可复盘。  
>  
> 所以我把重点放在工程链路，而不是模型包装。这个项目让我同时锻炼了编排、工具调用、状态管理、降级处理和可观测性。

---

### Q3. 你在项目里具体负责什么？

推荐答法：

> 我负责的是主链路和关键基础设施。  
>  
> 第一块是 planner 编排，把用户 query 变成 `Plan` 和 `Task[]`。  
> 第二块是 Kline 分析链，包括 Binance 行情接入、技术分析和结果组织。  
> 第三块是 memory 分层设计，包括 session、assets、journal、traces、conversations。  
> 第四块是 trace 可观测性，让每次执行都能回放。  
> 第五块是前后端联调，把首页 chat、资产页、memory 和 traces 页面接到真实数据。

危险答法：

- “我都做了”
- “我前后端算法全包”

---

### Q4. 你这个项目里的 Agent 和普通后端服务有什么区别？

推荐答法：

> 我区分得很明确。普通服务负责稳定能力，比如 `MemoryService`、`TraceLogService`、`MarketDataService`。Agent 则围绕目标任务执行，比如 `ResearchAgent` 负责研究任务，`KlineAgent` 负责技术分析，`SummaryAgent` 负责结果汇总。  
>  
> 更关键的是，Agent 不直接做顶层决策。顶层决策在 `Planner`，它负责判断用户到底要做什么、需不需要澄清、任务怎么拆。这样边界清楚，后面扩展多任务和 follow-up 时不会乱。

---

### Q5. 你为什么没直接用 LangChain 或 LangGraph？

推荐答法：

> 不是不用，而是这个阶段没必要先引入。我的 MVP 任务类型比较明确，主链路也能用自定义编排稳定表达：`ContextBuilder -> Planner -> Executor -> SummaryAgent`。  
>  
> 我更关心的是先把状态边界、trace、memory、前后端契约打稳。如果一开始就上通用框架，可能会更快搭 Demo，但会把很多关键边界藏起来。等后面任务依赖、重规划、并行执行更复杂时，再引入 LangGraph 这类框架会更合理。

---

## 2. 二面深挖题

### Q6. 你详细讲一下 Planner 链路

推荐答法：

> 主链路入口现在是 `POST /api/planner/execute`，或者由会话接口间接调用。  
>  
> 第一步，`ContextBuilder` 读取 session state、recent summaries 和 memory preview，组装成 `PlanningContext`。  
> 第二步，`Planner` 把自然语言 query 转成 `Plan`，里面会明确 `goal`、`mode`、`needs_clarification` 和 `tasks`。  
> 第三步，`Executor` 按 `depends_on` 顺序执行任务，调用 `ResearchAgent`、`KlineAgent` 或 `SummaryAgent`，每一步都返回结构化 `TaskResult`。  
> 第四步，`OrchestratorService` 汇总结果、写回 session、落 trace，并把最终结构化结果返回给会话层。  
>  
> 这个设计的重点是：规划、执行、总结分层，agent 之间不直接互相调，统一通过 orchestrator 串起来。

可补充的亮点：

- clarify 是 planner 的正常输出，不是失败
- follow-up 依赖 session state 补全上下文
- trace 里能看到 `plan`、`task_results`、`execution_summary`

---

### Q7. KlineAgent 是怎么工作的？

推荐答法：

> `KlineAgent` 的职责很聚焦，就是做技术分析，不负责理解用户意图。它接收的是 planner 已经拆好的结构化输入，比如 `asset`、`timeframes`、`market_type`。  
>  
> 执行时会调用 Binance 公共接口拉 K 线和 ticker，然后通过 `KlineAnalysisService` 做均线、趋势、支撑阻力、breakout 等分析，最后把多周期结果整理成结构化 payload。  
>  
> 如果外部数据不可用，它不会伪造结果，而是把 degraded 状态显式暴露出来，这样 summary 和前端都能诚实展示“当前数据不可用”。

---

### Q8. 你这个项目里的 memory 为什么这么设计？

推荐答法：

> 因为这个项目有明显的时间层次。  
>  
> `session/current_session.json` 解决的是短期 follow-up。  
> `conversations/*.json` 解决的是聊天历史。  
> `assets/*.md|json` 解决的是长期研究结论和结构化 metadata。  
> `journal/*.md` 解决的是人类可读复盘。  
> `traces/*.json` 解决的是机器执行轨迹。  
>  
> 我没有把这些混成一个大对象，因为它们的读写频率、可读性需求和生命周期都不一样。

---

### Q9. Trace 在你这个项目里到底起什么作用？

推荐答法：

> Trace 在我这里不是普通日志，而是完整执行链的结构化记录。它会保存用户 query、planner status、plan、task_results、execution_summary、events 和 final_answer。  
>  
> 它的价值有三点。第一，前端 `/traces` 页面可以直接回放。第二，调试时能看出问题出在规划、执行还是外部接口。第三，它能给后续评估和 prompt/plan 优化提供依据。

---

## 3. 压力追问题

### Q10. 你这个项目真的是 Agent 吗？感觉很多还是规则

推荐答法：

> 我会直接承认它是“工程化、约束较强的 Agent 系统”，不是自由自治型多智能体。  
>  
> 但我认为这并不弱。真实业务里，最重要的是稳定性、边界和可调试性。我的系统有自然语言输入、任务分解、工具调用、状态管理、结果汇总和可复盘链路，已经满足 Agent 系统的关键特征。  
>  
> 我刻意避免一上来就做完全开放式自治，因为那会显著提高冲突、幻觉和状态不一致风险。

---

### Q11. 你说有 skills，那 skills 到底落地了吗？

推荐答法：

> 这个项目现在的核心执行仍然是自定义 orchestrator + agent，不依赖通用 skill runtime。  
>  
> 我会把外部能力理解成两类：一类是项目内稳定服务，比如市场数据、memory、trace；另一类是外部扩展能力，比如未来可接的 skills。当前 MVP 重点先把主链路和工程边界打稳，而不是为了“看起来更像 Agent”把所有东西都包装成 skill。

---

### Q12. 你这个项目的 LLM 起的作用是不是很弱？

推荐答法：

> 我是刻意这么设计的。LLM 主要用在答案生成层，而不是拿它做整条主链的唯一真相。  
>  
> 原因很简单：研究和 K 线任务依赖实时数据和结构化执行，不能只靠模型自由生成。我把 LLM 放在一个更合适的位置上，让它负责把结构化结果变成更自然的回答，而规划和执行仍保持可控。

---

### Q13. 如果让你重做一次，你会推翻什么设计？

推荐答法：

> 我已经做过一次比较大的重构，就是把旧的 router 入口替换成 planner/orchestrator。  
>  
> 如果再重做一次，我会更早把“规划”和“答案生成”分离，同时更早定义统一的 `Plan`、`Task`、`TaskResult` 契约。这样多任务、trace、前端展示都会更自然，后期重构成本也更低。

---

## 4. 横向对比题

### Q14. 你这个项目和 RAG 项目的区别是什么？

推荐答法：

> RAG 更偏“取回知识然后回答”。我这个项目更偏“围绕目标任务做规划和执行”。  
>  
> 它当然也会用到检索和上下文拼装，但主链不是检索，而是 planner 先决定任务，然后 executor 调用研究、K 线等能力，再由 summary 汇总。  
>  
> 所以它比纯 RAG 多了规划、工具调用、状态管理和执行复盘。

---

### Q15. 你这个项目和工作流引擎有什么区别？

推荐答法：

> 工作流引擎通常是固定流程图，我这个项目的区别在于第一步是自然语言理解和任务分解。  
>  
> 用户不同表述会生成不同 `Plan`，有时单任务，有时多任务，有时先 clarify。也就是说，我不是把用户输入硬塞进固定 DAG，而是先生成一个面向当前请求的结构化计划，再执行它。

---

### Q16. 你这个项目和多智能体协作系统有什么差别？

推荐答法：

> 我当前不是自由协作式多智能体，而是中心化编排。  
>  
> `Planner` 做决策，`Executor` 做调度，`ResearchAgent`、`KlineAgent`、`SummaryAgent` 是执行单元。这样更适合 MVP，因为状态更统一，trace 更清楚，冲突更少。  
>  
> 以后如果任务复杂度继续上升，我会考虑让部分 agent 拥有更强的局部规划能力，但不会直接跳到完全自治。

---

## 5. 反问式问题

### Q17. 如果用户同时问“看下 BTC 现货和 ETH 合约，再结合我上周的判断给结论”，你系统会怎么处理？

推荐答法：

> 这类请求说明 planner 需要支持多资产、多 market_type 和历史上下文拼接。当前 MVP 主要稳定支持单资产下的 research、kline 和 follow-up，多资产复合请求还会是后续增强点。  
>  
> 如果让我设计扩展，我会先把 `Task.slots` 扩展成更通用的多资产结构，然后让 planner 生成多个 research/kline task，最后由 summary task 做汇总。

---

### Q18. 如果一个外部接口返回慢、另一个返回错，你怎么保证用户体验？

推荐答法：

> 我不会把外部失败隐藏掉，而是做显式降级。  
>  
> 一方面，执行结果和 trace 会标出 degraded 状态。另一方面，summary 和前端会告诉用户哪些结果是成功拿到的，哪些依赖当前不可用。这样用户至少能得到部分可信结果，而不是被假完整性误导。

---

## 6. 如何证明这不是 PPT 项目

可直接回答：

- 有真实可运行前端：首页、资产页、memory、traces
- 有真实后端 API：planner、conversations、research、memory、paper trading
- 会话、trace、memory 都落本地文件，可直接检查
- `npm run build` 和 backend pytest 可以过
- `/traces` 能看到完整 plan 和 task_results

你也可以补一句：

> 我这个项目最能证明真实性的不是截图，而是它的运行痕迹都可读，包括 conversation、trace 和 memory。

---

## 7. 面试官可能让你手绘的图

### 图 1. 系统总览图

```text
User
  ↓
Next.js Frontend
  ↓
FastAPI Backend
  ├─ Planner API / Conversation API
  ├─ Orchestrator
  │   ├─ ContextBuilder
  │   ├─ Planner
  │   ├─ Executor
  │   └─ SummaryAgent
  ├─ ResearchAgent / KlineAgent
  ├─ Memory / Trace / PaperTrading Services
  └─ Binance / External Research Adapters
```

### 图 2. Planner 执行图

```text
User Query
  ↓
PlanningContext
  ↓
Plan(tasks)
  ↓
Executor
  ↓
TaskResult[]
  ↓
SummaryAgent
  ↓
Final Answer + Trace
```

### 图 3. Memory 分层图

```text
session/         短期上下文
conversations/   会话历史
assets/          长期研究结论
journal/         人类复盘记录
traces/          机器执行轨迹
```

---

## 8. 你可以主动抛给面试官的亮点

- 我不是把 Agent 做成黑盒，而是把规划、执行、总结、trace 拆开
- 我把文件型 memory 分层，而不是把所有上下文塞进一个 JSON
- 我把外部依赖失败做成显式降级，而不是伪造成功结果
- 我做了会话、trace 和前端联动，系统是可运行可复盘的

---

## 9. 最危险的 8 句话

- “这个项目就是调 LLM API”
- “我们有很多 Agent 在协作”
- “主要靠模型理解”
- “用了框架所以开发很快”
- “memory 就是存聊天记录”
- “trace 就是日志”
- “如果接口挂了就先返回个默认值”
- “这个系统后面想接什么都行”

---

## 10. 15 分钟 mock 流程

1. 先用 Q1 做 2 分钟项目介绍
2. 再讲 Q6 的 planner 链路
3. 然后讲 Q8 的 memory 分层
4. 再讲 Q9 的 trace 价值
5. 最后准备 Q10、Q12、Q16 这类质疑题

---

## 11. 最后建议

- 不要再用 `RouterService`、`RouterAgent` 讲当前代码
- 一定强调当前架构是 planner/orchestrator 分层
- 多说“结构化计划、任务分解、显式降级、trace 可复盘”
- 少说“很智能”“很多 Agent”“自动推理很强”

你这个项目当前最有说服力的点，不是模型能力，而是工程边界清楚、链路真实、可运行可回放。

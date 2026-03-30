# Crypto Agent

一个本地优先的加密研究工作台，包含：

- `FastAPI` 后端
- `Next.js` 前端
- 基于文件的记忆系统
- `Planner -> Executor -> Agents` 执行链路
- 币安公开行情接口接入
- 自选列表与模拟交易台账
- 可读化 trace 查看页

项目目标不是做一个大而全的平台，而是提供一套可运行、可观察、可继续演化的 agent research skeleton。

## 当前能力

- 多会话聊天页，支持 planner 编排后的研究问答
- 资产实时工作台：`/assets/[symbol]`
- 币安现货/合约行情快照与 K 线
- 周期切换：`1m / 5m / 15m / 1h`
- 顶部默认前 20 资产选择器
- 只搜索币安可交易资产
- 本地 watchlist 持久化
- 本地 paper portfolio / paper orders 台账
- 文件型 memory：profile、asset thesis、journal、session、conversation、trace
- `/traces` 可读执行流程页
- `ResearchAgent` loop 过程展示
- 可选的 OpenAI-compatible answer generation

## 当前限制

- 没有数据库，状态主要落在 `memory/`
- 没有认证
- 没有真实下单
- `ResearchAgent` 已有 loop，其他 agent 仍偏 deterministic worker
- 默认资产前 20 目前是内置名单，不是实时市值榜
- 外部研究数据链路依赖当前网络环境

## 项目结构

```text
backend/   FastAPI、orchestrator、agents、services、tests
frontend/  Next.js 界面
memory/    本地记忆、会话、trace、资产 thesis、台账
docs/      设计和实现文档
scripts/   本地开发与验证脚本
```

## 核心页面

- `/`
  聊天首页。左侧是会话列表，右侧是大聊天区，整体更接近 GPT 的使用方式。

- `/assets/BTC`
  单资产实时工作台。支持顶部切换资产、分钟级别图表、实时价格、右侧行情信息。

- `/traces`
  执行轨迹浏览页。支持查看 planner 决策、agent 实际调用、研究 loop 轮次和最终结论。

## 技术栈

- 后端：`FastAPI`、`Pydantic v2`、`httpx`、`APScheduler`、`pytest`
- 前端：`Next.js 15`、`React 19`、`TypeScript`、`Tailwind CSS`
- 图表：`lightweight-charts`
- 行情源：币安公开接口

## 快速启动

### 1. 启动后端

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --app-dir .
```

后端地址：

```text
http://127.0.0.1:8000
```

### 2. 启动前端

```bash
cd frontend
npm install
cp .env.local.example .env.local
npm run dev
```

前端地址：

```text
http://127.0.0.1:3000
```

### 3. 一条命令启动

如果后端虚拟环境和前端依赖已经装好，可以直接运行：

```bash
./scripts/dev.sh
```

这个脚本会同时拉起：

- 后端 `127.0.0.1:8000`
- 前端 `127.0.0.1:3000`

## 环境变量

### 后端

`backend/.env.example` 当前支持：

```text
OPENAI_API_KEY=
OPENAI_MODEL=
OPENAI_BASE_URL=
OPENAI_TIMEOUT=
ROUTER_LLM_MODEL=
ROUTER_LLM_API_KEY=
ROUTER_LLM_BASE_URL=
ROUTER_LLM_TIMEOUT=
```

说明：

- 不配也能跑 planner、research、kline、trace
- 配了以后，可以在结构化执行结果之外再生成更自然的回答

### 前端

`frontend/.env.local.example`

```text
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
```

## 验证命令

一键验证：

```bash
./scripts/test.sh
```

它会运行：

- `pytest backend/tests -q`
- `npm run lint`
- `npm run build`

## API 概览

主要接口包括：

- `GET /api/health`
- `GET /api/conversations`
- `POST /api/conversations`
- `POST /api/conversations/{conversation_id}/messages`
- `GET /api/assets/discovery/top`
- `GET /api/assets/discovery/search?q=btc`
- `GET /api/assets/{symbol}/live?market=spot&timeframe=1m`
- `GET /api/traces`
- `GET /api/traces/{trace_id}`
- `GET /api/watchlist`
- `POST /api/watchlist`

## Memory 设计

这个项目的 memory 是文件型分层结构，不是数据库，也不是完整的向量检索系统。

主要目录：

- `memory/profile.json`
  用户偏好和长期设定

- `memory/MEMORY.md`
  长期文字记忆

- `memory/assets/*.md` / `memory/assets/*.json`
  资产 thesis 和结构化元数据

- `memory/watchlist.json`
  自选列表

- `memory/conversations/*.json`
  多会话聊天记录

- `memory/session/current_session.json`
  当前会话短期状态

- `memory/traces/*.json`
  planner 与 agent 执行轨迹

## 执行链路

当前主链路大致是：

1. 用户消息进入 conversation service
2. planner 根据 query、session state、recent summaries 产出任务
3. executor 顺序执行 `ResearchAgent`、`KlineAgent`、`SummaryAgent`
4. 结果写入 trace 和 conversation
5. 如果配置了 LLM answer layer，再把结构化结果转换成自然语言回复

其中：

- `ResearchAgent` 已支持有限轮次 loop，并在 `/traces` 中展示每轮观察、决策、动作和停止原因
- `KlineAgent` 主要负责时间周期行情和指标摘要
- `SummaryAgent` 负责合并研究结论和技术面结果

## 开发说明

- 前端 `Memory` 页面已经移除，但后端 memory 架构仍保留
- trace 页面已改成“最终结论 + 可读时间线 + Raw Trace”
- 资产页已改成实时工作台，不再展示旧的 `Research note` 和 `Other timeframes`
- 当前默认数据源以币安为主，适合本地开发和功能迭代

## 文档

更多背景可以看：

- [`docs/system-architecture.md`](docs/system-architecture.md)
- [`docs/agent-interview-qa.md`](docs/agent-interview-qa.md)
- [`docs/superpowers/specs/`](docs/superpowers/specs/)
- [`docs/superpowers/plans/`](docs/superpowers/plans/)

## License

当前仓库未单独声明开源许可证。如需开源，请补充 `LICENSE`。

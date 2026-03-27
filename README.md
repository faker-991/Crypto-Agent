# Crypto Agent

Personal crypto research workspace with:

- `FastAPI` backend
- `Next.js` frontend
- local markdown/json memory
- planner-orchestrated agent workflow
- Binance public market data adapter
- paper trading ledger
- trace logging and trace viewer

## Current Scope

Implemented today:

- watchlist add/remove
- paper trading portfolio and order logging
- asset detail page with Binance-backed kline chart, MAs, support, resistance
- planner flow with `ContextBuilder`, `Planner`, `Executor`, and `SummaryAgent`
- single-task research and kline execution
- multi-task research + kline + summary execution
- clarify-first handling for missing asset or underspecified follow-ups
- persistent multi-conversation chat history backed by local files
- post-execution LLM answer generation for conversational replies
- weekly report generation job
- trace logging and `/traces` UI
- CoinGecko / DefiLlama research context ingestion for part of research flows

Still intentionally lightweight:

- no database
- no auth
- no real trade execution
- no LangGraph orchestration yet
- planner decomposition is deterministic in MVP
- Binance skills runtime is not wired in yet; the project currently uses public HTTP adapters where possible

## Repo Layout

```text
backend/   FastAPI app, orchestrator, agents, services, tests
frontend/  Next.js app UI
memory/    local md/json memory, assets, reports, traces
scripts/   local dev and verification helpers
```

## Prerequisites

- Python 3.12+
- Node.js 20+
- npm

## Backend Setup

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Optional environment:

```bash
cp .env.example .env
```

Start backend:

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --app-dir .
```

Backend base URL:

```text
http://127.0.0.1:8000
```

## Frontend Setup

```bash
cd frontend
npm install
cp .env.local.example .env.local
```

Start frontend:

```bash
cd frontend
npm run dev
```

Frontend base URL:

```text
http://127.0.0.1:3000
```

## One-Command Dev

If your backend virtualenv already exists and frontend deps are already installed:

```bash
./scripts/dev.sh
```

This opens:

- backend on `127.0.0.1:8000`
- frontend on `127.0.0.1:3000`

Stop both with `Ctrl+C`.

## Verification

Run the full local verification bundle:

```bash
./scripts/test.sh
```

This runs:

- backend tests
- frontend lint
- frontend production build

## Planning And Answer Layers

Planner execution works without any LLM. The MVP planner is deterministic and produces:

- `execute`
- `clarify`
- `failed`

The same backend can optionally use an OpenAI-compatible answer-generation layer after structured execution. To enable that layer, set backend env vars:

```text
OPENAI_API_KEY=...
OPENAI_MODEL=...
```

Optional:

```text
OPENAI_BASE_URL=...
```

Behavior:

- the planner first builds structured context and tasks
- executor runs research and/or kline tasks
- summary agent produces a final structured result
- answer generation can upgrade the structured result into a more natural reply
- if answer generation fails, the UI still shows the structured planner result

## Key Pages

- `/` dashboard
- `/assets/BTC` asset detail
- `/memory` long-term memory
- `/traces` workflow trace browser

## Trace Logs

All planner runs write json traces under:

```text
memory/traces/
```

The UI trace browser reads those same files through backend APIs. Historical router-era traces remain readable in the trace browser, but new writes use planner-era fields.

## Memory Architecture

The project uses a layered file-backed memory model under `memory/`:

- short-term memory: `memory/session/current_session.json`
- conversation memory: `memory/conversations/index.json`, `memory/conversations/*.json`
- long-term memory: `memory/MEMORY.md`, `memory/profile.json`, `memory/assets/*.md`, `memory/assets/*.json`
- episodic memory: `memory/journal/*.md`
- execution traces: `memory/traces/*.json`

Backend services split responsibilities across:

- `MemoryService` for compatibility-facing reads
- `ProfileMemoryService` for user preferences
- `AssetMemoryService` for thesis markdown and asset metadata
- `JournalMemoryService` for human-readable review notes
- `ContextAssemblyService` for planner, research, and kline context payload assembly

The `/memory` page surfaces these layers through read-only APIs:

- `GET /api/memory`
- `GET /api/memory/profile`
- `GET /api/memory/assets`
- `GET /api/memory/journal`
- `GET /api/memory/context-preview`

## Notes

- Public Binance endpoints are used for current market data fetching.
- Research flows can enrich results with CoinGecko and DefiLlama context.
- APScheduler registers the weekly report job on backend startup.

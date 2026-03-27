# Minimal Fullstack Skeleton Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first runnable `crypto-agent` skeleton with a FastAPI backend, Next.js frontend, local file-backed memory, and minimal watchlist / thesis / paper-trading flows.

**Architecture:** The backend owns all file access and exposes a small REST API. The frontend renders three minimal pages against those APIs. Binance integration is not implemented in this first slice; instead, the adapter boundary is created so later work can plug in `spot`, `derivatives-trading-usds-futures`, and `alpha` without reshaping the app.

**Tech Stack:** FastAPI, Pydantic, pytest, Next.js App Router, TypeScript, Tailwind CSS

---

### Task 1: Scaffold Project Layout

**Files:**
- Create: `backend/app/main.py`
- Create: `backend/app/api/__init__.py`
- Create: `backend/app/api/watchlist.py`
- Create: `backend/app/api/memory.py`
- Create: `backend/app/api/paper_trading.py`
- Create: `backend/app/schemas/watchlist.py`
- Create: `backend/app/schemas/memory.py`
- Create: `backend/app/schemas/paper_trading.py`
- Create: `backend/app/services/memory_service.py`
- Create: `backend/app/services/paper_trading_service.py`
- Create: `backend/app/services/bootstrap_service.py`
- Create: `backend/app/clients/binance_market_adapter.py`
- Create: `backend/requirements.txt`
- Create: `backend/tests/test_watchlist_api.py`
- Create: `backend/tests/test_paper_trading_service.py`
- Create: `frontend/package.json`
- Create: `frontend/tsconfig.json`
- Create: `frontend/next.config.js`
- Create: `frontend/postcss.config.js`
- Create: `frontend/tailwind.config.ts`
- Create: `frontend/app/layout.tsx`
- Create: `frontend/app/page.tsx`
- Create: `frontend/app/assets/[symbol]/page.tsx`
- Create: `frontend/app/memory/page.tsx`
- Create: `frontend/app/globals.css`
- Create: `frontend/lib/api.ts`
- Create: `frontend/components/watchlist-card.tsx`
- Create: `frontend/components/paper-portfolio-card.tsx`
- Create: `memory/MEMORY.md`
- Create: `memory/watchlist.json`
- Create: `memory/paper_portfolio.json`
- Create: `memory/paper_orders.json`

- [ ] **Step 1: Create the directory structure**

Run: `mkdir -p backend/app/api backend/app/schemas backend/app/services backend/app/clients backend/tests frontend/app/assets/[symbol] frontend/components frontend/lib memory`
Expected: directories exist with no errors

- [ ] **Step 2: Add minimal backend, frontend, and memory files**

Expected: files exist and import paths are coherent

- [ ] **Step 3: Verify the tree looks correct**

Run: `find backend frontend memory -maxdepth 3 -type f | sort`
Expected: the planned starter files are present

### Task 2: Build File-Backed Backend Core

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/app/api/watchlist.py`
- Modify: `backend/app/api/memory.py`
- Modify: `backend/app/api/paper_trading.py`
- Modify: `backend/app/schemas/watchlist.py`
- Modify: `backend/app/schemas/memory.py`
- Modify: `backend/app/schemas/paper_trading.py`
- Modify: `backend/app/services/memory_service.py`
- Modify: `backend/app/services/paper_trading_service.py`
- Modify: `backend/app/services/bootstrap_service.py`
- Modify: `backend/app/clients/binance_market_adapter.py`
- Test: `backend/tests/test_watchlist_api.py`
- Test: `backend/tests/test_paper_trading_service.py`

- [ ] **Step 1: Write the failing backend tests**

Run: `pytest backend/tests/test_watchlist_api.py backend/tests/test_paper_trading_service.py -q`
Expected: FAIL because the API and services are not implemented yet

- [ ] **Step 2: Implement the smallest backend behavior**

Required behavior:
- bootstrap default memory files
- read and write watchlist JSON
- read thesis markdown if present
- return paper portfolio state
- record a simple paper trade and update cash / position
- expose a stub `binance_market_adapter` interface for future integration

- [ ] **Step 3: Re-run backend tests**

Run: `pytest backend/tests/test_watchlist_api.py backend/tests/test_paper_trading_service.py -q`
Expected: PASS

### Task 3: Build Minimal Frontend Pages

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/app/layout.tsx`
- Modify: `frontend/app/page.tsx`
- Modify: `frontend/app/assets/[symbol]/page.tsx`
- Modify: `frontend/app/memory/page.tsx`
- Modify: `frontend/app/globals.css`
- Modify: `frontend/lib/api.ts`
- Modify: `frontend/components/watchlist-card.tsx`
- Modify: `frontend/components/paper-portfolio-card.tsx`

- [ ] **Step 1: Add the frontend dependencies and app shell**

Required behavior:
- App Router setup
- global styles
- small navigation

- [ ] **Step 2: Implement the minimal pages**

Required behavior:
- dashboard shows watchlist and paper portfolio
- asset detail shows thesis placeholder and kline analysis placeholder
- memory page shows MEMORY.md summary

- [ ] **Step 3: Point the frontend at backend APIs**

Required behavior:
- central API helper
- environment-based backend base URL

### Task 4: Verify the Full Slice

**Files:**
- Modify: `backend/requirements.txt`
- Modify: `frontend/package.json`

- [ ] **Step 1: Install frontend dependencies**

Run: `npm install`
Expected: dependencies installed under `frontend/node_modules`

- [ ] **Step 2: Run backend tests**

Run: `pytest backend/tests -q`
Expected: PASS

- [ ] **Step 3: Run frontend validation**

Run: `npm run lint`
Expected: PASS or report only actionable lint failures

- [ ] **Step 4: Build the frontend**

Run: `npm run build`
Expected: Next.js production build succeeds

- [ ] **Step 5: Summarize remaining gaps**

Expected gaps:
- Binance skills are only represented by an adapter boundary
- Kline chart is placeholder data
- due_diligence / weekly_review skills are not implemented yet

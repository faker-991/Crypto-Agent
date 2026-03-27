# Conversation And LLM Answer Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a demo-ready conversational layer for `crypto-agent` with real LLM answer generation, multi-turn continuity, and locally persisted multi-conversation chat history while preserving the existing real Binance execution chain.

**Architecture:** Keep `RouterService` as the execution core and add a post-execution conversation layer around it. Introduce `ConversationMemoryService` for file-backed chat persistence, `ConversationService` for per-conversation orchestration, and `AnswerGenerationService` for LLM-based natural responses built only from structured execution results plus bounded context.

**Tech Stack:** Python, FastAPI, Pydantic, httpx, Next.js App Router, React, TypeScript, local JSON memory, pytest

---

## File Map

### Backend

**Create**
- `backend/app/schemas/conversation.py`
  - Conversation list/message/answer-generation schemas
- `backend/app/services/conversation_memory_service.py`
  - File-backed storage for conversation index and transcript files
- `backend/app/services/answer_generation_service.py`
  - Provider abstraction + OpenAI-compatible answer generation layer
- `backend/app/services/conversation_service.py`
  - Conversation orchestration around router execution and answer generation
- `backend/app/api/conversations.py`
  - Conversation create/list/read/send endpoints
- `backend/tests/test_conversation_memory_service.py`
- `backend/tests/test_answer_generation_service.py`
- `backend/tests/test_conversation_api.py`

**Modify**
- `backend/app/main.py`
  - Register conversation service and API router
- `backend/app/api/__init__.py`
  - Export conversations router if needed by package layout
- `backend/app/services/router_llm_service.py`
  - Reuse or extract provider bits needed by answer generation
- `backend/app/services/trace_log_service.py`
  - Support answer-generation events and trace detail fields
- `backend/app/services/session_state_service.py`
  - Verify current read/write contract still supports follow-up context needs

### Frontend

**Create**
- `frontend/components/conversation-sidebar.tsx`
  - Conversation list, create conversation button, selection UI
- `frontend/components/conversation-panel.tsx`
  - Active conversation transcript and message rendering

**Modify**
- `frontend/components/router-chat.tsx`
  - Replace single in-memory chat with persisted conversations UI
- `frontend/components/dashboard-client.tsx`
  - Adapt layout if router chat props/state change
- `frontend/lib/api.ts`
  - Add conversation list/create/read/send API clients and types

### Memory / Docs

**Create**
- `memory/conversations/` runtime directory created by backend services

**Modify**
- `README.md`
  - Document conversation and LLM answer capabilities once working

---

## Chunk 1: Conversation Persistence Backend

### Task 1: Define conversation schemas

**Files:**
- Create: `backend/app/schemas/conversation.py`
- Test: `backend/tests/test_conversation_memory_service.py`

- [ ] **Step 1: Write the failing test**

Create schema-focused tests covering:
- conversation index entry validation
- transcript message validation
- answer-generation status enum (`ready`, `unavailable`, `skipped`)

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest backend/tests/test_conversation_memory_service.py -q`
Expected: FAIL because schemas/service do not exist yet.

- [ ] **Step 3: Write minimal implementation**

Create `backend/app/schemas/conversation.py` with:
- `AnswerGenerationState`
- `ConversationMessage`
- `ConversationTranscript`
- `ConversationIndexItem`
- `ConversationIndex`

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest backend/tests/test_conversation_memory_service.py -q`
Expected: schema assertions pass.

### Task 2: Implement file-backed conversation memory service

**Files:**
- Create: `backend/app/services/conversation_memory_service.py`
- Modify: `backend/app/schemas/conversation.py`
- Test: `backend/tests/test_conversation_memory_service.py`

- [ ] **Step 1: Write the failing test**

Add tests for:
- creating a conversation initializes `index.json` and `<conversation_id>.json`
- listing conversations returns lightweight metadata only
- appending messages updates transcript and index metadata
- reloading service from disk preserves data

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest backend/tests/test_conversation_memory_service.py -q`
Expected: FAIL because service methods are missing.

- [ ] **Step 3: Write minimal implementation**

Implement `ConversationMemoryService` with methods:
- `list_conversations()`
- `create_conversation(title: str | None = None)`
- `read_conversation(conversation_id: str)`
- `append_messages(conversation_id: str, messages: list[ConversationMessage])`
- ensure directory and `index.json` bootstrap

Store files under:
- `memory/conversations/index.json`
- `memory/conversations/<conversation_id>.json`

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest backend/tests/test_conversation_memory_service.py -q`
Expected: PASS.

---

## Chunk 2: Answer Generation Backend

### Task 3: Define answer generation service contract

**Files:**
- Create: `backend/app/services/answer_generation_service.py`
- Test: `backend/tests/test_answer_generation_service.py`

- [ ] **Step 1: Write the failing test**

Add tests for:
- valid provider response -> `status="ready"`
- timeout/error -> `status="unavailable"`
- skipped flow -> `status="skipped"`
- returned object includes provider/model/used_context fields

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest backend/tests/test_answer_generation_service.py -q`
Expected: FAIL because service does not exist.

- [ ] **Step 3: Write minimal implementation**

Implement:
- provider abstraction that reuses OpenAI-compatible request shape
- `AnswerGenerationService.generate(...)`
- graceful timeout and malformed-output handling
- structured response object with:
  - `status`
  - `provider`
  - `model`
  - `answer_text`
  - `error`
  - `used_context`

Important constraint:
- answer generation must only use supplied structured execution + bounded context
- it must never invent extra tool calls

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest backend/tests/test_answer_generation_service.py -q`
Expected: PASS.

### Task 4: Support configurable timeout and provider reuse cleanly

**Files:**
- Modify: `backend/app/services/router_llm_service.py`
- Modify: `backend/app/services/answer_generation_service.py`
- Test: `backend/tests/test_router_llm_service.py`
- Test: `backend/tests/test_answer_generation_service.py`

- [ ] **Step 1: Write the failing test**

Add a test that answer generation and router classification can both consume configured timeout/model/base URL through environment-backed configuration without duplicating request-shape logic.

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest backend/tests/test_router_llm_service.py backend/tests/test_answer_generation_service.py -q`
Expected: FAIL on new assertions.

- [ ] **Step 3: Write minimal implementation**

Refactor shared OpenAI-compatible adapter behavior only as much as needed. Keep YAGNI:
- either expose a small shared client helper
- or keep two services thin but consistent

Do not rewrite the router classification service beyond what answer generation needs.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest backend/tests/test_router_llm_service.py backend/tests/test_answer_generation_service.py -q`
Expected: PASS.

---

## Chunk 3: Conversation Orchestration And API

### Task 5: Implement conversation service orchestration

**Files:**
- Create: `backend/app/services/conversation_service.py`
- Modify: `backend/app/services/router_service.py`
- Modify: `backend/app/services/trace_log_service.py`
- Test: `backend/tests/test_conversation_api.py`

- [ ] **Step 1: Write the failing test**

Add service/API-oriented tests covering:
- sending a user message appends a user transcript entry
- router execution result is attached to assistant message
- answer generation uses bounded context from:
  - recent messages
  - current execution
  - current session state
- answer-generation events are written into the trace

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest backend/tests/test_conversation_api.py -q`
Expected: FAIL because API/service does not exist.

- [ ] **Step 3: Write minimal implementation**

Implement `ConversationService` with methods:
- `create_conversation()`
- `list_conversations()`
- `get_conversation(conversation_id)`
- `send_message(conversation_id, user_message)`

Behavior of `send_message(...)`:
1. append user message
2. call `RouterService.route_and_execute(...)`
3. build bounded answer context from recent messages + session state + current execution
4. call `AnswerGenerationService`
5. append assistant message with:
   - natural answer
   - route summary
   - execution summary
   - answer generation payload
   - trace id

Update `TraceLogService` to accept extra answer-generation events.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest backend/tests/test_conversation_api.py -q`
Expected: PASS.

### Task 6: Expose conversation HTTP API

**Files:**
- Create: `backend/app/api/conversations.py`
- Modify: `backend/app/main.py`
- Possibly modify: `backend/app/api/__init__.py`
- Test: `backend/tests/test_conversation_api.py`

- [ ] **Step 1: Write the failing test**

Add API tests for:
- `GET /api/conversations`
- `POST /api/conversations`
- `GET /api/conversations/{id}`
- `POST /api/conversations/{id}/messages`

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest backend/tests/test_conversation_api.py -q`
Expected: FAIL because routes are missing.

- [ ] **Step 3: Write minimal implementation**

Add router endpoints and wire `ConversationService` in `backend/app/main.py` dependency overrides.

Keep response shapes stable and UI-friendly:
- conversation list returns sidebar-friendly metadata
- conversation detail returns transcript only
- send message returns updated assistant message payload and trace id

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest backend/tests/test_conversation_api.py -q`
Expected: PASS.

---

## Chunk 4: Frontend Conversation UI

### Task 7: Extend frontend API client and types

**Files:**
- Modify: `frontend/lib/api.ts`

- [ ] **Step 1: Add failing type-usage references in UI files**

Update UI components to reference future conversation API helpers so TypeScript/lint fails on missing exports.

- [ ] **Step 2: Run lint/type check to verify it fails**

Run: `cd frontend && npm run lint`
Expected: FAIL on missing conversation helpers/types.

- [ ] **Step 3: Write minimal implementation**

Add:
- conversation list types
- conversation detail types
- answer-generation payload type
- API helpers:
  - `listConversations()`
  - `createConversation()`
  - `fetchConversation(id)`
  - `sendConversationMessage(id, content)`

- [ ] **Step 4: Run lint to verify it passes**

Run: `cd frontend && npm run lint`
Expected: PASS or fail only on next UI tasks.

### Task 8: Build conversation sidebar and panel components

**Files:**
- Create: `frontend/components/conversation-sidebar.tsx`
- Create: `frontend/components/conversation-panel.tsx`
- Modify: `frontend/components/router-chat.tsx`

- [ ] **Step 1: Write the UI integration in a way that fails lint/type checks first**

Reference the new components from `router-chat.tsx` before they exist.

- [ ] **Step 2: Run lint to verify it fails**

Run: `cd frontend && npm run lint`
Expected: FAIL on missing files/exports.

- [ ] **Step 3: Write minimal implementation**

Implement:
- sidebar with conversation list + create conversation action
- message panel with transcript rendering
- assistant message sections for:
  - natural answer
  - execution summary
  - trace link
- conversation switching behavior

Replace in-memory `messages` state in `router-chat.tsx` with persisted conversation state fetched from backend.

- [ ] **Step 4: Run lint to verify it passes**

Run: `cd frontend && npm run lint`
Expected: PASS.

### Task 9: Preserve dashboard integration and UX

**Files:**
- Modify: `frontend/components/dashboard-client.tsx`
- Modify: `frontend/components/router-chat.tsx`

- [ ] **Step 1: Write a failing integration change**

Adjust dashboard usage to the new chat contract even if it temporarily breaks imports/props.

- [ ] **Step 2: Run lint to verify it fails**

Run: `cd frontend && npm run lint`
Expected: FAIL on prop/type mismatches.

- [ ] **Step 3: Write minimal implementation**

Ensure dashboard still renders watchlist/paper trading plus the new conversation UI without introducing duplicate state ownership.

- [ ] **Step 4: Run lint to verify it passes**

Run: `cd frontend && npm run lint`
Expected: PASS.

---

## Chunk 5: End-To-End Verification And Docs

### Task 10: Add answer-generation trace support verification

**Files:**
- Modify: `backend/tests/test_conversation_api.py`
- Modify: `backend/app/services/trace_log_service.py`

- [ ] **Step 1: Write a failing test**

Assert that a conversation send operation produces:
- execution trace events
- answer-generation trace events
- no fabricated answer when LLM is unavailable

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest backend/tests/test_conversation_api.py -q`
Expected: FAIL on missing trace detail.

- [ ] **Step 3: Write minimal implementation**

Add answer-generation event append logic with fields:
- provider
- model
- status
- used_context
- error
- latency_ms

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest backend/tests/test_conversation_api.py -q`
Expected: PASS.

### Task 11: Update README and perform full verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update docs**

Document:
- conversation list + multi-session support
- local conversation storage location
- answer generation status behavior
- current limitations (no planner, no autonomous tool loop)

- [ ] **Step 2: Run backend verification**

Run:
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest backend/tests/test_conversation_memory_service.py backend/tests/test_answer_generation_service.py backend/tests/test_conversation_api.py backend/tests/test_router_service.py backend/tests/test_kline_agent.py -q`
Expected: PASS.

- [ ] **Step 3: Run frontend verification**

Run:
- `cd frontend && npm run lint`
Expected: PASS.

- [ ] **Step 4: Run live demo checks**

Verify manually with HTTP/browser:
- create multiple conversations
- switch between them
- ask follow-up question in same conversation
- confirm assistant shows natural answer or explicit LLM unavailable state
- confirm trace link opens and shows answer-generation events
- confirm asset page still uses real Binance data

---

## Suggested Commit Boundaries

Use small commits after each major chunk:

1. `feat: add conversation persistence schemas and service`
2. `feat: add llm answer generation service`
3. `feat: add conversation orchestration and api`
4. `feat: add multi-conversation chat ui`
5. `docs: document conversation and llm answer flow`

## Execution Notes

- Keep router execution behavior stable; do not refactor route selection beyond what this plan requires.
- Do not introduce synthetic answers or placeholder chat content.
- Keep answer generation fact-grounded in structured execution summaries.
- Keep conversation storage file-backed and local; do not add a database in this phase.
- Preserve real Binance-only market behavior and current degraded/unavailable semantics.

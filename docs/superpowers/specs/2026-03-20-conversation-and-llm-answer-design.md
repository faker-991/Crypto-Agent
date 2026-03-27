# Conversation And LLM Answer Design

## 1. Goal

This phase upgrades `crypto-agent` from a single-turn execution console into a demo-ready conversational agent system while preserving the existing real-data execution chain.

The scope is intentionally limited to three capabilities:

- real LLM answer generation
- multi-turn conversation continuity
- multi-conversation local persistence

This phase does **not** include:

- autonomous planning
- autonomous tool selection loops
- MCP runtime execution closure
- database-backed persistence

## 2. Product Problem

The current project already supports:

- real Binance-backed kline and market analysis
- router execution
- trace visualization
- session-scoped short-term state

But it still has three demo-breaking gaps:

1. the homepage chat is still structurally a single-turn execution shell
2. answer text is mostly deterministic formatting, not true LLM-generated natural responses
3. chat history is not modeled as real conversations with persistence and switching

This creates a mismatch between the frontend shape and the actual product capability. The UI looks like a chat product, but the backend behavior is still closer to a command runner.

## 3. Recommended Approach

Use a **post-execution answer generation layer plus conversation service layer**.

High-level flow:

```text
User message
  -> ConversationService
  -> RouterService route/execute
  -> ConversationService assemble context
  -> AnswerGenerationService
  -> persist conversation message + execution result + answer
  -> TraceLogService
  -> Frontend conversation list / message panel
```

Why this approach:

- preserves the already-working router + agent + Binance chain
- adds natural conversation without rewriting the execution core
- keeps conversation, answer generation, execution, and trace responsibilities separated
- gives a stable base for later planner/tool-selection work

Rejected approaches:

- stuffing conversation logic into `RouterService`
  - too much coupling
  - poor long-term maintainability
- building a full conversation orchestrator in one step
  - too large for this phase
  - slows down delivery of a demo-ready version

## 4. Architecture

### 4.1 New Core Units

#### `ConversationMemoryService`

Responsible for local file-backed conversation persistence.

Responsibilities:

- create conversation records
- list conversations
- append messages to a conversation
- load a conversation transcript
- maintain lightweight conversation index metadata

#### `ConversationService`

Responsible for conversation-level orchestration.

Responsibilities:

- accept user message for a given conversation
- invoke router execution
- assemble answer-generation context
- persist user + assistant messages
- bind execution summaries and trace ids to assistant messages

#### `AnswerGenerationService`

Responsible for natural-language response generation.

Responsibilities:

- call an LLM provider using already-executed structured results
- generate natural replies using bounded context
- return standardized answer-generation state
- degrade transparently when LLM is unavailable

### 4.2 Existing Units That Remain

- `RouterService` remains the execution orchestrator
- `RouterAgent / ResearchAgent / KlineAgent` remain execution agents
- `TraceLogService` remains the machine-execution recording layer
- `SessionStateService` remains the short-term runtime state layer

## 5. Conversation Persistence Model

Use local file storage under `memory/conversations/`.

### 5.1 Files

```text
memory/conversations/index.json
memory/conversations/<conversation_id>.json
```

### 5.2 `index.json`

Stores conversation list metadata only.

Suggested fields per item:

- `conversation_id`
- `title`
- `created_at`
- `updated_at`
- `last_user_message`
- `message_count`

Purpose:

- fast conversation list loading
- avoids scanning full transcripts for sidebar rendering

### 5.3 `<conversation_id>.json`

Stores the full conversation transcript.

Suggested top-level fields:

- `conversation_id`
- `title`
- `created_at`
- `updated_at`
- `messages`

Suggested message fields:

- `id`
- `role` (`user`, `assistant`, optional `system`)
- `content`
- `created_at`
- `route_summary`
- `execution_summary`
- `answer_generation`
- `trace_id`

## 6. Memory Layering Model

Conversation persistence must not replace the existing layered memory model.

This phase keeps four distinct layers:

- `session`
  - current runtime short-term state
- `conversations`
  - user-visible chat history
- `traces`
  - machine execution records
- `assets/profile/watchlist/journal`
  - long-term domain memory

Rationale:

- conversation history is not the same as runtime state
- trace is not the same as chat
- long-term memory should remain domain-oriented instead of transcript-oriented

## 7. Multi-Turn Context Strategy

The system will not send full transcripts to the model.

Answer-generation context is assembled from three bounded sources:

### 7.1 Current Execution Context

Highest-priority fact source.

Includes:

- route summary
- agent / skill
- execution summary
- market summary
- provenance summary
- degraded / unavailable status

### 7.2 Recent Conversation Window

Only recent turns are included.

Initial recommendation:

- last `4-6` messages

Purpose:

- resolve follow-up questions like:
  - “那周线呢”
  - “继续看这个币”
  - “结合刚才再说说风险”

### 7.3 Session State

Uses existing `session/current_session.json`.

Includes:

- current asset
- recent intent
- recent timeframes
- current task
- last skill
- last agent

### 7.4 Context Rules

- current execution overrides historical conversation if conflict exists
- model must not invent unexecuted tool calls
- system should prefer explicit session state and recent messages for reference resolution
- raw large objects should be summarized before entering the answer prompt

## 8. Answer Generation Model

Answer generation is a strict post-execution layer.

Execution order:

```text
user message
  -> route/execute
  -> structured execution result
  -> AnswerGenerationService
  -> assistant natural response
```

### 8.1 Output Contract

Suggested answer-generation payload:

- `status`
  - `ready`
  - `unavailable`
  - `skipped`
- `provider`
- `model`
- `answer_text`
- `error`
- `used_context`
  - e.g. `execution`, `recent_messages`, `session_state`

### 8.2 Failure Semantics

#### `ready`

- model returned a usable answer
- frontend shows natural assistant response

#### `unavailable`

- missing config
- timeout
- HTTP failure
- empty content
- invalid result

Behavior:

- frontend explicitly shows that LLM answer generation is unavailable
- structured execution summary remains visible
- system does not pretend to have produced a natural answer

#### `skipped`

Used for non-execution flows such as:

- clarify
- fallback

## 9. Frontend Model

The homepage chat becomes a real conversation UI.

### 9.1 Layout

Two-panel layout:

- left: conversation list
- right: active conversation panel

### 9.2 Conversation List

Displays:

- title
- last updated time
- last user message summary
- create conversation action
- switch conversation action

### 9.3 Message Panel

Displays:

- user messages
- assistant natural answers
- execution summary per assistant response
- trace link per assistant response

### 9.4 Assistant Message Presentation

Each assistant message should carry:

1. natural-language answer
2. execution summary
3. trace entry point

The UI goal is not full chatbot polish. The goal is a demo-ready conversational execution product with transparency.

## 10. Trace Extensions

Add answer-generation events:

- `answer_generation.started`
- `answer_generation.completed`

Recommended detail fields:

- `provider`
- `model`
- `status`
- `used_context`
- `error`
- `latency_ms`

Do not expose full prompts in the trace UI.

Reasons:

- unnecessary UI noise
- internal implementation leakage
- higher cognitive load

## 11. Demo Acceptance Criteria

The phase is complete when all of the following are true:

1. users can create multiple conversations and switch between them
2. each conversation persists locally and survives backend restart
3. follow-up questions in the same conversation can reuse prior context
4. assistant responses are generated by an LLM when available
5. if LLM generation fails, the UI still shows structured execution summaries without fabricating responses
6. asset/page and router execution continue to rely on real Binance data only
7. trace shows both execution events and answer-generation events

## 12. Testing Strategy

### 12.1 Conversation Persistence Tests

- create conversation
- append user and assistant messages
- load conversation history
- list conversation metadata
- restart-safe persistence behavior

### 12.2 Answer Generation Tests

- `ready` path with valid provider response
- `unavailable` path for timeout / HTTP / malformed output
- `skipped` path for clarify/fallback flows
- structured execution remains intact when answer generation fails

### 12.3 Frontend Tests / Verification

- conversation list renders persisted conversations
- switching conversations does not leak messages
- refreshing the page preserves conversations
- assistant responses include natural answer + execution summary + trace link

## 13. Non-Goals For This Phase

These are explicitly deferred:

- planner-style autonomous task decomposition
- model-led tool selection loops
- autonomous follow-up execution chains
- full MCP runtime integration
- database storage
- advanced chat product features like sharing/searching/exporting

## 14. Why This Phase Matters

This phase moves the project from:

- “single-turn execution console with chat-like UI”

to:

- “demo-ready conversational agent with real data, persistent conversations, and transparent execution traces”

That is the right intermediate milestone before moving into planner autonomy and full tool-selection closure.

# Memory Architecture Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reorganize memory into a compatible long/short-term architecture without breaking existing files, APIs, or routing behavior.

**Architecture:** Keep existing file paths and public APIs, then layer in missing memory directories, richer session state, service decomposition, journal writeback, and a structured context-assembly service. Old code continues to call `MemoryService`, `SessionStateService`, `TraceLogService`, and agent methods, but those implementations become more complete internally.

**Tech Stack:** FastAPI, Pydantic, local markdown/json files, pytest, Next.js compatibility preserved

---

## File Map

**Create**

- `backend/app/services/profile_memory_service.py`
- `backend/app/services/asset_memory_service.py`
- `backend/app/services/journal_memory_service.py`
- `backend/app/services/context_assembly_service.py`
- `backend/tests/test_bootstrap_service.py`
- `backend/tests/test_asset_memory_service.py`
- `backend/tests/test_journal_memory_service.py`
- `backend/tests/test_context_assembly_service.py`
- `backend/tests/test_session_state_service.py`

**Modify**

- `backend/app/services/bootstrap_service.py`
- `backend/app/services/memory_service.py`
- `backend/app/services/session_state_service.py`
- `backend/app/services/router_service.py`
- `backend/app/agents/research_agent.py`
- `backend/app/agents/kline_agent.py`
- `backend/app/schemas/intent.py`
- `backend/app/api/memory.py`
- `frontend/lib/api.ts`
- `frontend/app/memory/page.tsx`
- `README.md`

**Existing test files likely updated**

- `backend/tests/test_research_agent.py`
- `backend/tests/test_router_execution.py`
- `backend/tests/test_router_service.py`

---

## Chunk 1: Bootstrap And Session Schema

### Task 1: Expand bootstrap coverage

**Files:**
- Modify: `backend/app/services/bootstrap_service.py`
- Test: `backend/tests/test_bootstrap_service.py`

- [ ] **Step 1: Write the failing bootstrap test**

```python
def test_bootstrap_creates_memory_architecture_files(tmp_path):
    BootstrapService(tmp_path).ensure_files()
    assert (tmp_path / "profile.json").exists()
    assert (tmp_path / "alerts.json").exists()
    assert (tmp_path / "assets").exists()
    assert (tmp_path / "journal").exists()
    assert (tmp_path / "reports" / "weekly").exists()
    assert (tmp_path / "traces").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest backend/tests/test_bootstrap_service.py -q`
Expected: FAIL because new files/dirs are not created yet.

- [ ] **Step 3: Write minimal implementation**

Update `BootstrapService.ensure_files()` to create:
- `profile.json`
- `alerts.json`
- `assets/`
- `journal/`
- `reports/weekly/`
- `traces/`

Do not overwrite existing files.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest backend/tests/test_bootstrap_service.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/bootstrap_service.py backend/tests/test_bootstrap_service.py
git commit -m "feat: extend memory bootstrap structure"
```

### Task 2: Expand session schema compatibly

**Files:**
- Modify: `backend/app/schemas/intent.py`
- Modify: `backend/app/services/session_state_service.py`
- Test: `backend/tests/test_session_state_service.py`

- [ ] **Step 1: Write the failing session state test**

```python
def test_session_state_persists_extended_fields(tmp_path):
    service = SessionStateService(tmp_path)
    state = service.write_state({
        "current_asset": "SUI",
        "last_intent": "asset_due_diligence",
        "last_timeframes": ["1d"],
        "last_report_type": None,
        "recent_assets": ["SUI"],
        "current_task": "reviewing SUI",
        "last_skill": "protocol_due_diligence",
        "last_agent": "ResearchAgent",
    })
    assert state.current_task == "reviewing SUI"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest backend/tests/test_session_state_service.py -q`
Expected: FAIL because schema lacks the new fields.

- [ ] **Step 3: Write minimal implementation**

Add these optional fields to `SessionState`:
- `current_task`
- `last_skill`
- `last_agent`

Ensure bootstrap defaults and read/write methods remain backward compatible.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest backend/tests/test_session_state_service.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/intent.py backend/app/services/session_state_service.py backend/tests/test_session_state_service.py
git commit -m "feat: extend session state memory fields"
```

---

## Chunk 2: Long-Term Memory Services

### Task 3: Add asset memory service and thesis path compatibility

**Files:**
- Create: `backend/app/services/asset_memory_service.py`
- Modify: `backend/app/services/memory_service.py`
- Test: `backend/tests/test_asset_memory_service.py`

- [ ] **Step 1: Write the failing asset memory tests**

Cover:
- reads `memory/assets/SUI.md` first
- falls back to `memory/theses/SUI.md` if assets file is missing
- reads `memory/assets/SUI.json` metadata

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest backend/tests/test_asset_memory_service.py -q`
Expected: FAIL because service does not exist yet.

- [ ] **Step 3: Write minimal implementation**

`AssetMemoryService` should:
- read thesis markdown from `assets/`
- fallback to `theses/`
- read/write asset metadata json
- expose helper methods used by `MemoryService` and agents

Update `MemoryService.get_thesis()` to delegate to this service without changing API output.

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest backend/tests/test_asset_memory_service.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/asset_memory_service.py backend/app/services/memory_service.py backend/tests/test_asset_memory_service.py
git commit -m "feat: add asset memory service with thesis fallback"
```

### Task 4: Add profile memory service

**Files:**
- Create: `backend/app/services/profile_memory_service.py`
- Modify: `backend/app/services/memory_service.py`
- Test: `backend/tests/test_bootstrap_service.py`

- [ ] **Step 1: Write the failing profile read test**

Test that default `profile.json` is readable and returns structured preference data.

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest backend/tests/test_bootstrap_service.py -q`
Expected: FAIL because profile defaults or accessors are missing.

- [ ] **Step 3: Write minimal implementation**

Create `ProfileMemoryService` with:
- `get_profile()`
- `update_profile()`

Keep `MemoryService` as the facade.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest backend/tests/test_bootstrap_service.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/profile_memory_service.py backend/app/services/memory_service.py backend/tests/test_bootstrap_service.py
git commit -m "feat: add profile memory service"
```

### Task 5: Add journal memory service

**Files:**
- Create: `backend/app/services/journal_memory_service.py`
- Test: `backend/tests/test_journal_memory_service.py`

- [ ] **Step 1: Write the failing journal append test**

Test that a dated journal file is created and appended with short entries.

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest backend/tests/test_journal_memory_service.py -q`
Expected: FAIL because journal service does not exist.

- [ ] **Step 3: Write minimal implementation**

Implement:
- `append_entry(date, title, body)`
- `read_day(date)`
- `list_recent_entries(limit)`

Keep output markdown-based and concise.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest backend/tests/test_journal_memory_service.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/journal_memory_service.py backend/tests/test_journal_memory_service.py
git commit -m "feat: add journal memory service"
```

---

## Chunk 3: Context Assembly

### Task 6: Introduce context assembly service

**Files:**
- Create: `backend/app/services/context_assembly_service.py`
- Test: `backend/tests/test_context_assembly_service.py`

- [ ] **Step 1: Write the failing context assembly tests**

Add tests for:
- router context includes session + profile summary
- research context includes session + asset metadata + watchlist
- kline context includes session + asset metadata + recent traces summary

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest backend/tests/test_context_assembly_service.py -q`
Expected: FAIL because service does not exist.

- [ ] **Step 3: Write minimal implementation**

Implement:
- `build_router_context(user_query)`
- `build_research_context(asset, intent)`
- `build_kline_context(asset, timeframes)`

Return structured dicts only. Do not generate prompts here.

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest backend/tests/test_context_assembly_service.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/context_assembly_service.py backend/tests/test_context_assembly_service.py
git commit -m "feat: add context assembly service"
```

---

## Chunk 4: Agent And Router Writeback

### Task 7: Update router session writeback

**Files:**
- Modify: `backend/app/services/router_service.py`
- Modify: `backend/app/services/session_state_service.py`
- Test: `backend/tests/test_router_execution.py`

- [ ] **Step 1: Write the failing router execution test**

Test that after execution:
- `current_task`
- `last_skill`
- `last_agent`

are persisted into `current_session.json`.

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest backend/tests/test_router_execution.py -q`
Expected: FAIL because those fields are not updated from executed route.

- [ ] **Step 3: Write minimal implementation**

After successful execution, have `RouterService` write:
- `current_task`
- `last_skill`
- `last_agent`

using a focused session update helper.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest backend/tests/test_router_execution.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/router_service.py backend/app/services/session_state_service.py backend/tests/test_router_execution.py
git commit -m "feat: persist executed router context in session state"
```

### Task 8: Add journal writeback for key research events

**Files:**
- Modify: `backend/app/agents/research_agent.py`
- Modify: `backend/tests/test_research_agent.py`

- [ ] **Step 1: Write the failing research journal tests**

Add tests that:
- `protocol_due_diligence` can append a journal event
- `thesis_break_detector` writes a weakening summary journal entry when assets are flagged
- `watchlist_weekly_review` or `generate_report` writes a review note

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest backend/tests/test_research_agent.py -q`
Expected: FAIL because journal writeback is not wired.

- [ ] **Step 3: Write minimal implementation**

Inject or instantiate `JournalMemoryService` inside `ResearchAgent` and write concise entries only for key events.

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest backend/tests/test_research_agent.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/agents/research_agent.py backend/tests/test_research_agent.py
git commit -m "feat: write key research events to journal"
```

### Task 9: Keep kline writeback compatible

**Files:**
- Modify: `backend/app/agents/kline_agent.py`
- Test: `backend/tests/test_kline_agent.py`

- [ ] **Step 1: Write the failing kline compatibility test**

Test that kline writes do not erase prior thesis content fields unexpectedly and continue to update `assets/*.json`.

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest backend/tests/test_kline_agent.py -q`
Expected: FAIL if overwrite logic is not memory-safe.

- [ ] **Step 3: Write minimal implementation**

Adjust `KlineAgent` writeback to merge or append technical context safely through asset memory helpers.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest backend/tests/test_kline_agent.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/agents/kline_agent.py backend/tests/test_kline_agent.py
git commit -m "feat: keep kline memory writeback compatible"
```

---

## Chunk 5: API And UI Enhancements

### Task 10: Add memory enhancement APIs

**Files:**
- Modify: `backend/app/api/memory.py`
- Modify: `backend/app/services/memory_service.py`
- Add tests in: `backend/tests/test_memory_api.py` or existing memory-related tests

- [ ] **Step 1: Write failing API tests**

Add coverage for:
- `GET /api/memory/profile`
- `GET /api/memory/assets`
- `GET /api/memory/journal`
- `GET /api/memory/context-preview`

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest backend/tests -q`
Expected: FAIL because endpoints do not exist.

- [ ] **Step 3: Write minimal implementation**

Expose read-only enhancement endpoints first. Keep old endpoints unchanged.

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest backend/tests -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/memory.py backend/app/services/memory_service.py backend/tests
git commit -m "feat: add memory profile journal and context preview APIs"
```

### Task 11: Surface richer memory in the frontend

**Files:**
- Modify: `frontend/lib/api.ts`
- Modify: `frontend/app/memory/page.tsx`

- [ ] **Step 1: Write a small UI/contract test or define response usage**

If no frontend test harness exists, define minimal TypeScript contract usage in code changes and verify through build.

- [ ] **Step 2: Run current frontend checks**

Run: `npm run lint`
Expected: PASS before changes.

- [ ] **Step 3: Write minimal implementation**

Update the memory page to show:
- long-term memory summary
- profile snapshot
- recent journal list
- maybe a small asset memory index

Do not turn this into a full dashboard rewrite.

- [ ] **Step 4: Verify frontend**

Run:
- `npm run lint`
- `npm run build`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/lib/api.ts frontend/app/memory/page.tsx
git commit -m "feat: expand memory page with layered memory views"
```

---

## Chunk 6: Documentation And Final Verification

### Task 12: Document the new memory architecture

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add memory architecture section**

Document:
- short-term memory
- long-term memory
- episodic memory
- context assembly
- key memory files

- [ ] **Step 2: Run final verification**

Run:
- `./scripts/test.sh`

Expected:
- backend tests pass
- frontend lint passes
- frontend build passes

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: document layered memory architecture"
```

---

Plan complete and saved to `docs/superpowers/plans/2026-03-17-memory-architecture-implementation.md`. Ready to execute?

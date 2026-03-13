# AI Test QA Tool — Full Restructure Implementation Plan

**Date:** 2026-03-12
**Scope:** UI restructure into multi-page app + Prompt-Driven Agent Mode + Auto-Evaluation + Clone/Re-run

---

## Overview

The current `ai_test` tool is a single-page monolith with no navigation, no routing, and no way for QA to describe what they want to test in plain language. This plan restructures it into a proper multi-page QA tool where:

- QA can navigate between distinct sections (Dashboard, Datasets, New Run, History)
- QA can describe what they want to test in plain text — the system uses that as instructions for an AI agent that converses with the bot
- Agent Mode shows the actual system prompt being used (editable, or fully customizable)
- After every run the AI automatically evaluates the conversation quality
- Any past run can be cloned and re-run with the same or tweaked settings

---

## Current State Analysis

| File | Lines | Problem |
|---|---|---|
| `static/index.html` | 112 | All 5 sections on one page, no navigation |
| `static/app.js` | 325 | All logic in one file, global functions, no routing |
| `static/styles.css` | 190 | Basic styles, no layout for multi-page |
| `app/runner.py` | 942 | 400-line `DEFAULT_CASE_LIBRARY` hardcoded inline, mixes data + logic |
| `app/ai_chat.py` | 211 | System prompts hardcoded, no way to pass custom prompts |
| `app/main.py` | 186 | No endpoint for agent list, no `custom_prompt` in run payload |

**Key gaps:**
- `run_agent_conversation_with_id` (`runner.py:830`) has no `custom_system_prompt` parameter
- `generate_next_user_message` (`ai_chat.py:151`) has no way to override the system prompt
- Run records don't store the prompt used — so clone/re-run is impossible
- No hash-based routing — you can't link to a run or a dataset
- `list_runs()` (`storage.py:141`) returns runs sorted by filename, no newest-first

---

## Desired End State

After this plan is complete:

1. The UI has 4 pages with a persistent nav: **Dashboard**, **Datasets**, **New Run**, **History**
2. On the New Run page — **Agent Mode** shows the persona's system prompt in an editable box, with a "Custom Mode" that clears it to a blank textarea
3. QA can type something like: *"Test appointment booking. User should ask about slots, book one, then try to reschedule. Bot must confirm each step."* — this becomes the agent's instruction
4. After the run completes, AI auto-evaluates the full conversation and shows verdict + reasoning per turn
5. History page shows all runs with pass rate, mode, agent, date — click any run to see full conversation details
6. Every run has a **Clone** button that opens New Run pre-filled with identical settings and prompt

---

## What We're NOT Doing

- No React/Vue/Svelte — staying with vanilla JS + hash routing
- No user auth or roles (future phase)
- No scheduled/cron runs (future phase)
- No multi-environment config UI (future phase)
- No real-time websocket streaming (polling every 2s is fine for now)
- No prompt-to-dataset-JSON generation (QA prompt goes straight to agent, no JSON step)
- No manual rubric writing — AI decides rubrics from the conversation

---

## Implementation Approach

Build in 5 phases, each independently testable. Backend changes first (Phase 1), then UI shell (Phase 2), then features on top (Phases 3-5). No external dependencies added.

---

## Phase 1: Backend — Clean Up & Extend APIs

### Overview
Move hardcoded data out of runner.py, extend the run start API to accept `custom_prompt`, make runs store the prompt used, add the agent list endpoint, fix run list ordering.

### Changes Required

#### 1. Extract DEFAULT_CASE_LIBRARY
**File:** `app/case_library.py` *(new file)*
**Changes:** Move the 400-line `DEFAULT_CASE_LIBRARY` dict from `runner.py` lines 166–575 into a dedicated module.

```python
# app/case_library.py
DEFAULT_CASE_LIBRARY = {
    "appointment": [...],
    "doctor": [...],
    # ... all existing entries
}
```

Then in `runner.py` replace inline dict with:
```python
from app.case_library import DEFAULT_CASE_LIBRARY
```

#### 2. Extend ai_chat.py to accept custom system prompt
**File:** `app/ai_chat.py`
**Changes:** `generate_next_user_message` accepts an optional `custom_system_prompt` parameter. If provided, it overrides the persona lookup entirely.

```python
async def generate_next_user_message(
    agent: str,
    history: List[Dict[str, str]],
    max_words: int = 25,
    custom_system_prompt: Optional[str] = None,   # NEW
) -> str:
    normalized = _normalize_agent(agent)
    system_prompt = custom_system_prompt or AGENT_SYSTEM_PROMPTS.get(
        normalized, AGENT_SYSTEM_PROMPTS["general"]
    )
    # rest unchanged
```

#### 3. Extend runner.py to accept and store custom_prompt
**File:** `app/runner.py`
**Changes:** `run_agent_conversation_with_id` gains a `custom_system_prompt` parameter. It is stored in `run_record` and passed through to `generate_next_user_message`.

```python
async def run_agent_conversation_with_id(
    run_id: str,
    dataset: Dict[str, Any],
    agent: str,
    max_turns: int,
    stop_event: Optional[asyncio.Event] = None,
    custom_system_prompt: Optional[str] = None,   # NEW
) -> Dict[str, Any]:
    run_record = {
        ...
        "custom_system_prompt": custom_system_prompt or "",   # NEW — stored for clone
    }
    ...
    user_message = await generate_next_user_message(
        agent, history, custom_system_prompt=custom_system_prompt  # NEW
    )
```

#### 4. Extend main.py — accept custom_prompt, add agent list endpoint
**File:** `app/main.py`
**Changes:**

```python
# In api_start_run:
custom_system_prompt = (payload.get("custom_system_prompt") or "").strip()

# Pass to runner:
await run_agent_conversation_with_id(
    run_id, dataset, agent, max_turns,
    stop_event=STOP_EVENTS.get(run_id),
    custom_system_prompt=custom_system_prompt or None,
)

# New endpoint — returns all agent names + their default prompts:
@app.get("/api/agents")
async def api_list_agents() -> List[Dict[str, Any]]:
    from app.ai_chat import AGENT_SYSTEM_PROMPTS, AGENT_ALIASES
    result = []
    seen = set()
    for alias, canonical in AGENT_ALIASES.items():
        if canonical not in seen:
            seen.add(canonical)
            result.append({
                "name": canonical,
                "aliases": [k for k, v in AGENT_ALIASES.items() if v == canonical],
                "system_prompt": AGENT_SYSTEM_PROMPTS.get(canonical, ""),
            })
    return result
```

#### 5. Fix list_runs() ordering
**File:** `app/storage.py`
**Changes:** Return newest runs first.

```python
def list_runs() -> List[Dict[str, Any]]:
    ...
    for path in sorted(RUNS_DIR.glob("*.json"), reverse=True):   # reverse=True
```

Also add `mode` and `agent` fields to the list response:
```python
runs.append({
    "run_id": ...,
    "dataset_id": ...,
    "status": ...,
    "mode": data.get("mode", "dataset"),    # NEW
    "agent": data.get("agent", ""),          # NEW
    "started_at": ...,
    "ended_at": ...,
    "case_count": ...,
    "custom_system_prompt": data.get("custom_system_prompt", ""),  # NEW
})
```

### Success Criteria

#### Automated Verification:
- [ ] Server starts without errors: `uvicorn app.main:app --port 9101`
- [ ] `GET /api/agents` returns list with `name`, `system_prompt` fields: `curl http://localhost:9101/api/agents`
- [ ] `POST /api/runs` with `custom_system_prompt` field succeeds: `curl -X POST http://localhost:9101/api/runs -d '{"mode":"agent","agent":"general","custom_system_prompt":"test","max_turns":1}'`
- [ ] Run record stored in `runs/` contains `custom_system_prompt` field
- [ ] `GET /api/runs` returns runs newest-first (check timestamps)

#### Manual Verification:
- [ ] `runner.py` no longer contains `DEFAULT_CASE_LIBRARY` — it imports from `case_library.py`
- [ ] Existing dataset mode and agent mode runs still work end-to-end

**Pause here for confirmation before Phase 2.**

---

## Phase 2: Multi-Page UI Shell with Navigation

### Overview
Replace the single-page layout with a 4-page app using hash-based routing (`#/`, `#/datasets`, `#/run`, `#/history`). Add persistent navigation. Split `app.js` into page modules.

### Changes Required

#### 1. New HTML structure
**File:** `static/index.html`
**Changes:** Replace current body with nav + router container. Each page is a `<div class="page-view">` that gets shown/hidden by the router.

```html
<body>
  <nav class="sidebar">
    <div class="nav-logo">AI Test QA</div>
    <a href="#/" class="nav-item" data-page="dashboard">Dashboard</a>
    <a href="#/datasets" class="nav-item" data-page="datasets">Datasets</a>
    <a href="#/run" class="nav-item" data-page="run">New Run</a>
    <a href="#/history" class="nav-item" data-page="history">History</a>
  </nav>

  <main class="content">
    <!-- Dashboard Page -->
    <div id="page-dashboard" class="page-view">
      <h1>Dashboard</h1>
      <div id="dashboard-stats" class="stats-grid"></div>
      <div id="dashboard-recent"></div>
    </div>

    <!-- Datasets Page -->
    <div id="page-datasets" class="page-view hidden">
      <h1>Datasets</h1>
      <div class="toolbar">
        <input id="newDatasetId" placeholder="New dataset id" />
        <button id="createDataset">+ Create</button>
        <button id="refreshDatasets">Refresh</button>
      </div>
      <div id="datasetList"></div>
      <div id="datasetEditorPanel" class="hidden">
        <h2 id="datasetEditorTitle">Edit Dataset</h2>
        <textarea id="datasetEditor" rows="20"></textarea>
        <div class="toolbar">
          <button id="saveDataset">Save</button>
          <button id="cancelEdit" class="secondary">Cancel</button>
        </div>
      </div>
    </div>

    <!-- New Run Page -->
    <div id="page-run" class="page-view hidden">
      <h1>New Run</h1>
      <!-- content built in Phase 3 -->
    </div>

    <!-- History Page -->
    <div id="page-history" class="page-view hidden">
      <h1>Run History</h1>
      <!-- content built in Phase 4 -->
    </div>
  </main>

  <script src="/static/router.js"></script>
  <script src="/static/api.js"></script>
  <script src="/static/pages/dashboard.js"></script>
  <script src="/static/pages/datasets.js"></script>
  <script src="/static/pages/run.js"></script>
  <script src="/static/pages/history.js"></script>
  <script src="/static/app.js"></script>
</body>
```

#### 2. Router module
**File:** `static/router.js` *(new file)*

```javascript
const ROUTES = {
  "/":         "dashboard",
  "/datasets": "datasets",
  "/run":      "run",
  "/history":  "history",
};

function getHash() {
  return window.location.hash.replace("#", "") || "/";
}

function navigate(hash) {
  window.location.hash = hash;
}

function renderRoute() {
  const hash = getHash();
  // handle /history/run-xxx for deep links
  const base = "/" + (hash.split("/")[1] || "");
  const pageId = ROUTES[base] || "dashboard";

  document.querySelectorAll(".page-view").forEach(el => el.classList.add("hidden"));
  document.getElementById(`page-${pageId}`).classList.remove("hidden");

  document.querySelectorAll(".nav-item").forEach(a => {
    a.classList.toggle("active", a.dataset.page === pageId);
  });

  // call page-specific mount function
  const mountFn = window[`mount_${pageId}`];
  if (typeof mountFn === "function") mountFn(hash);
}

window.addEventListener("hashchange", renderRoute);
window.addEventListener("load", renderRoute);
```

#### 3. API module
**File:** `static/api.js` *(new file)*
Centralise all `fetch` calls so page modules don't duplicate logic.

```javascript
const API = {
  async get(path) {
    const r = await fetch(path);
    if (!r.ok) throw new Error(await r.text());
    return r.json();
  },
  async post(path, body) {
    const r = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!r.ok) throw new Error(await r.text());
    return r.json();
  },
  async put(path, body) {
    const r = await fetch(path, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!r.ok) throw new Error(await r.text());
    return r.json();
  },
  datasets: {
    list: ()      => API.get("/api/datasets"),
    get: (id)     => API.get(`/api/datasets/${id}`),
    save: (id, d) => API.put(`/api/datasets/${id}`, d),
    create: (d)   => API.post("/api/datasets", d),
  },
  runs: {
    list: ()      => API.get("/api/runs"),
    get: (id)     => API.get(`/api/runs/${id}`),
    start: (body) => API.post("/api/runs", body),
    stop: (id)    => API.post(`/api/runs/${id}/stop`, {}),
  },
  agents: {
    list: ()      => API.get("/api/agents"),
  },
};
```

#### 4. Update styles for sidebar layout
**File:** `static/styles.css`
**Changes:** Add sidebar nav layout, hide/show page views, active nav state, stat cards, toolbar.

```css
/* Layout */
body { display: flex; min-height: 100vh; margin: 0; font-family: Arial, sans-serif; background: #f5f7fb; }

.sidebar {
  width: 200px; min-height: 100vh; background: #1e293b; color: #fff;
  display: flex; flex-direction: column; padding: 0; flex-shrink: 0;
}
.nav-logo { padding: 20px 16px; font-size: 15px; font-weight: 700; color: #f8fafc; border-bottom: 1px solid #334155; }
.nav-item { display: block; padding: 12px 16px; color: #94a3b8; text-decoration: none; font-size: 14px; }
.nav-item:hover, .nav-item.active { background: #334155; color: #f8fafc; }

.content { flex: 1; padding: 28px 32px; max-width: 1100px; overflow-y: auto; }
.content h1 { font-size: 20px; margin: 0 0 20px 0; }

.hidden { display: none !important; }

/* Stat cards */
.stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; margin-bottom: 24px; }
.stat-card { background: #fff; border-radius: 10px; padding: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
.stat-card .stat-value { font-size: 28px; font-weight: 700; }
.stat-card .stat-label { font-size: 12px; color: #6b7280; margin-top: 4px; }

/* Toolbar */
.toolbar { display: flex; gap: 8px; margin-bottom: 16px; flex-wrap: wrap; align-items: center; }
.toolbar input { padding: 8px; border: 1px solid #d1d5db; border-radius: 6px; font-size: 14px; }
button.secondary { background: #6b7280; }
button.secondary:hover { background: #4b5563; }
```

#### 5. Remove old app.js, create page stubs
**File:** `static/app.js` — reduce to just the init call
**Files:** `static/pages/dashboard.js`, `static/pages/datasets.js`, `static/pages/run.js`, `static/pages/history.js` *(new files, stub mount functions)*

### Success Criteria

#### Automated Verification:
- [ ] Server starts and serves `index.html`: `curl http://localhost:9101/`
- [ ] All 4 JS files load without 404: check browser network tab
- [ ] Navigating `#/`, `#/datasets`, `#/run`, `#/history` shows the correct page div

#### Manual Verification:
- [ ] Sidebar nav is visible on all pages
- [ ] Active page is highlighted in the nav
- [ ] No console errors on page load
- [ ] Layout looks clean, no broken styles from old CSS

**Pause here for confirmation before Phase 3.**

---

## Phase 3: New Run Page — Dataset Mode + Prompt-Driven Agent Mode

### Overview
Build the New Run page with two clearly separated tabs. Dataset Mode works like before. Agent Mode shows the selected persona's editable system prompt, and a "Custom Mode" that gives a blank textarea. QA types their instructions, hits Run.

### Changes Required

#### 1. New Run page HTML (inside `page-run` div)
**File:** `static/index.html` — replace `page-run` contents

```html
<div id="page-run" class="page-view hidden">
  <h1>New Run</h1>

  <!-- Mode tabs -->
  <div class="mode-tabs">
    <button class="tab-btn active" data-mode="dataset">Dataset Mode</button>
    <button class="tab-btn" data-mode="agent">Agent Mode</button>
  </div>

  <!-- Dataset Mode Panel -->
  <div id="panel-dataset" class="mode-panel card">
    <div class="field-group">
      <label>Dataset</label>
      <div class="row">
        <select id="runDatasetSelect"></select>
        <span id="runDatasetCaseCount" class="hint"></span>
      </div>
    </div>
    <div class="field-group">
      <label>Tag Filter <span class="hint">(comma separated, optional)</span></label>
      <input id="tagFilter" placeholder="e.g. appointment, smoke" />
    </div>
    <button id="startDatasetRun" class="btn-primary btn-large">▶ Start Dataset Run</button>
  </div>

  <!-- Agent Mode Panel -->
  <div id="panel-agent" class="mode-panel card hidden">
    <div class="field-group">
      <label>Persona</label>
      <div class="row">
        <select id="agentSelect"></select>
        <label class="toggle-label">
          <input type="checkbox" id="customModeToggle" />
          Custom Mode (blank prompt)
        </label>
      </div>
    </div>

    <div class="field-group">
      <label id="promptLabel">System Prompt <span class="hint">(editable — this is what the AI agent will follow)</span></label>
      <textarea id="agentPrompt" rows="8" placeholder="Describe how the AI user should behave and what to test..."></textarea>
      <div class="hint" id="promptHint">Tip: You can edit the preset prompt or switch to Custom Mode for full control.</div>
    </div>

    <div class="field-group">
      <label>Max Turns</label>
      <input id="maxTurns" type="number" min="1" max="20" value="5" style="width:80px" />
      <span class="hint">conversations turns with the bot</span>
    </div>

    <button id="startAgentRun" class="btn-primary btn-large">▶ Start Agent Run</button>
  </div>

  <!-- Live run status (shown after run starts) -->
  <div id="runStatusPanel" class="card hidden">
    <div class="run-status-header">
      <span id="activeRunStatus" class="status-badge"></span>
      <span id="activeRunId" class="hint"></span>
      <button id="stopRun" class="btn-danger">Stop</button>
    </div>
    <div id="liveRunReport"></div>
  </div>
</div>
```

#### 2. New Run page JavaScript
**File:** `static/pages/run.js`

```javascript
let _agents = [];
let _currentRunId = null;
let _pollTimer = null;

async function mount_run(hash) {
  // Load datasets and agents in parallel
  const [datasets, agents] = await Promise.all([
    API.datasets.list(),
    API.agents.list(),
  ]);
  _agents = agents;

  // Populate dataset select
  const dsSel = document.getElementById("runDatasetSelect");
  dsSel.innerHTML = datasets.map(d =>
    `<option value="${d.dataset_id}">${d.dataset_id} (${d.case_count} cases)</option>`
  ).join("");

  // Populate agent select
  const agSel = document.getElementById("agentSelect");
  agSel.innerHTML = agents.map(a =>
    `<option value="${a.name}">${a.name}</option>`
  ).join("");

  // If arriving via clone (hash = #/run?clone=run-xxx), pre-fill
  const params = new URLSearchParams(hash.split("?")[1] || "");
  if (params.get("clone")) {
    await _prefillFromRun(params.get("clone"));
  }

  _bindEvents();
}

function _loadAgentPrompt() {
  const agent = document.getElementById("agentSelect").value;
  const isCustom = document.getElementById("customModeToggle").checked;
  const textarea = document.getElementById("agentPrompt");
  if (isCustom) {
    textarea.value = "";
    textarea.placeholder = "Write your full instructions here. No preset applied.";
    document.getElementById("promptLabel").textContent = "Custom Prompt";
    document.getElementById("promptHint").textContent = "You have full control. Describe the user persona and what to test.";
  } else {
    const found = _agents.find(a => a.name === agent);
    textarea.value = found ? found.system_prompt : "";
    document.getElementById("promptLabel").textContent = "System Prompt (editable)";
    document.getElementById("promptHint").textContent = "Tip: You can edit this preset or switch to Custom Mode for full control.";
  }
}

async function _prefillFromRun(runId) {
  const run = await API.runs.get(runId);
  if (run.mode === "agent") {
    // Switch to agent tab
    _switchTab("agent");
    document.getElementById("agentSelect").value = run.agent || "general";
    const prompt = run.custom_system_prompt || "";
    if (prompt) {
      document.getElementById("customModeToggle").checked = true;
    }
    document.getElementById("agentPrompt").value = prompt;
    document.getElementById("maxTurns").value = run.max_turns || 5;
    _loadAgentPrompt();
  } else {
    _switchTab("dataset");
    document.getElementById("runDatasetSelect").value = run.dataset_id || "";
  }
}

function _switchTab(mode) {
  document.querySelectorAll(".tab-btn").forEach(b =>
    b.classList.toggle("active", b.dataset.mode === mode)
  );
  document.getElementById("panel-dataset").classList.toggle("hidden", mode !== "dataset");
  document.getElementById("panel-agent").classList.toggle("hidden", mode !== "agent");
}

function _bindEvents() {
  document.querySelectorAll(".tab-btn").forEach(btn =>
    btn.addEventListener("click", () => _switchTab(btn.dataset.mode))
  );
  document.getElementById("agentSelect").addEventListener("change", _loadAgentPrompt);
  document.getElementById("customModeToggle").addEventListener("change", _loadAgentPrompt);
  document.getElementById("startDatasetRun").addEventListener("click", _startDatasetRun);
  document.getElementById("startAgentRun").addEventListener("click", _startAgentRun);
  document.getElementById("stopRun").addEventListener("click", _stopRun);

  _loadAgentPrompt();
}

async function _startDatasetRun() {
  const datasetId = document.getElementById("runDatasetSelect").value;
  const tags = document.getElementById("tagFilter").value
    .split(",").map(t => t.trim()).filter(Boolean);
  const res = await API.runs.start({ mode: "dataset", dataset_id: datasetId, tags });
  _startPolling(res.run_id);
}

async function _startAgentRun() {
  const agent = document.getElementById("agentSelect").value;
  const customPrompt = document.getElementById("agentPrompt").value.trim();
  const maxTurns = parseInt(document.getElementById("maxTurns").value || "5", 10);
  const res = await API.runs.start({
    mode: "agent",
    agent,
    max_turns: maxTurns,
    custom_system_prompt: customPrompt,
  });
  _startPolling(res.run_id);
}

function _startPolling(runId) {
  _currentRunId = runId;
  document.getElementById("runStatusPanel").classList.remove("hidden");
  document.getElementById("activeRunId").textContent = runId;
  clearInterval(_pollTimer);
  _pollTimer = setInterval(async () => {
    const run = await API.runs.get(runId);
    renderRunReport(run, document.getElementById("liveRunReport"));
    const badge = document.getElementById("activeRunStatus");
    badge.textContent = run.status;
    badge.className = `status-badge status-${run.status}`;
    if (["completed", "failed", "stopped"].includes(run.status)) {
      clearInterval(_pollTimer);
    }
  }, 2000);
}

async function _stopRun() {
  if (_currentRunId) await API.runs.stop(_currentRunId);
}
```

### Success Criteria

#### Automated Verification:
- [ ] `GET /api/agents` returns agents with `system_prompt` field
- [ ] Agent Mode start run with custom prompt stores it in run JSON: check `runs/run-*.json`
- [ ] Dataset Mode run still completes normally

#### Manual Verification:
- [ ] Switching "Dataset Mode" / "Agent Mode" tabs shows the right panel
- [ ] Selecting a persona auto-fills the system prompt textarea
- [ ] Enabling "Custom Mode" clears the textarea and updates the label
- [ ] Editing the preset prompt and starting a run — verify in run JSON the edited prompt is stored
- [ ] Live status updates every ~2 seconds while run is in progress
- [ ] Stop button halts the run

**Pause here for confirmation before Phase 4.**

---

## Phase 4: History Page + Clone/Re-run

### Overview
Build the History page with a proper run list (newest first, shows mode/agent/pass rate), a full conversation view for agent runs, and a Clone button that deep-links back to New Run pre-filled with the original settings.

### Changes Required

#### 1. History page HTML
**File:** `static/index.html` — replace `page-history` contents

```html
<div id="page-history" class="page-view hidden">
  <h1>Run History</h1>
  <button id="refreshHistory" class="secondary">Refresh</button>

  <div id="runList" class="run-list"></div>

  <!-- Run detail panel (shown on click) -->
  <div id="runDetailPanel" class="card hidden">
    <div class="detail-header">
      <h2 id="detailRunId"></h2>
      <button id="cloneRunBtn" class="btn-primary">Clone & Re-run</button>
      <button id="closeDetail" class="secondary">Close</button>
    </div>
    <div id="runDetailReport"></div>
    <details style="margin-top:12px">
      <summary style="cursor:pointer;font-size:13px;color:#6b7280">Raw JSON</summary>
      <textarea id="runDetailRaw" rows="12" readonly></textarea>
    </details>
  </div>
</div>
```

#### 2. History page JavaScript
**File:** `static/pages/history.js`

```javascript
let _selectedRunId = null;

async function mount_history() {
  await _loadHistory();
  document.getElementById("refreshHistory").addEventListener("click", _loadHistory);
  document.getElementById("closeDetail").addEventListener("click", () => {
    document.getElementById("runDetailPanel").classList.add("hidden");
  });
  document.getElementById("cloneRunBtn").addEventListener("click", _cloneRun);
}

async function _loadHistory() {
  const runs = await API.runs.list();  // already sorted newest-first from Phase 1
  const list = document.getElementById("runList");
  list.innerHTML = runs.map(r => {
    const passRate = r.case_count > 0
      ? `${Math.round((r.passed_count || 0) / r.case_count * 100)}%` : "—";
    const modeLabel = r.mode === "agent"
      ? `Agent: ${r.agent || "?"}` : `Dataset: ${r.dataset_id || "?"}`;
    const date = r.started_at ? new Date(r.started_at).toLocaleString() : "—";
    return `
      <div class="run-card" data-run-id="${r.run_id}">
        <div class="run-card-left">
          <span class="status-badge status-${r.status}">${r.status}</span>
          <span class="run-card-mode">${modeLabel}</span>
        </div>
        <div class="run-card-center">
          <span class="run-card-date">${date}</span>
          <span class="run-card-id hint">${r.run_id}</span>
        </div>
        <div class="run-card-right">
          <span class="run-card-pass">${passRate} passed</span>
          <span class="hint">${r.case_count} turns</span>
        </div>
      </div>`;
  }).join("");

  list.querySelectorAll(".run-card").forEach(card => {
    card.addEventListener("click", () => _openRun(card.dataset.runId));
  });
}

async function _openRun(runId) {
  _selectedRunId = runId;
  const run = await API.runs.get(runId);
  document.getElementById("detailRunId").textContent = runId;
  document.getElementById("runDetailRaw").value = JSON.stringify(run, null, 2);
  renderRunReport(run, document.getElementById("runDetailReport"));
  document.getElementById("runDetailPanel").classList.remove("hidden");
  document.getElementById("runDetailPanel").scrollIntoView({ behavior: "smooth" });
}

function _cloneRun() {
  if (_selectedRunId) {
    navigate(`#/run?clone=${_selectedRunId}`);
  }
}
```

#### 3. Also add `passed_count` to list_runs() in storage.py
**File:** `app/storage.py`

```python
cases = data.get("cases", []) or []
passed = sum(
    1 for c in cases
    if (c.get("evaluation") or {}).get("pass") or c.get("status") == "completed"
)
runs.append({
    ...
    "passed_count": passed,   # NEW
})
```

### Success Criteria

#### Automated Verification:
- [ ] `GET /api/runs` response includes `mode`, `agent`, `passed_count` fields
- [ ] Clone link format `#/run?clone=run-xxx` is handled by `mount_run`

#### Manual Verification:
- [ ] History page shows runs newest-first
- [ ] Each run card shows status badge, mode, agent name, date, pass rate
- [ ] Clicking a card opens the detail panel with full report
- [ ] Clone button navigates to New Run and pre-fills the original prompt/settings
- [ ] For agent runs, the conversation turns (user + bot messages) are visible in the detail panel

**Pause here for confirmation before Phase 5.**

---

## Phase 5: Auto-Evaluation (AI Reviews Conversation After Run)

### Overview
After every agent run completes, automatically send the full conversation to OpenAI and ask it to evaluate how well the bot performed. The result is shown in the run detail view with a verdict and reasoning per turn. This replaces manual rubric writing.

### How it works
- Extend the existing `analytics.py` (or add a new `auto_eval.py`) to do per-turn evaluation
- After `run_agent_conversation_with_id` completes, call auto-eval
- Store results in `run_record["auto_eval"]`
- UI renders the auto-eval verdict in History detail view

### Changes Required

#### 1. New auto_eval.py
**File:** `app/auto_eval.py` *(new file)*

```python
import json
import logging
from typing import Any, Dict, List, Optional
import httpx
from app.config import OPENAI_API_KEY, OPENAI_MODEL

logger = logging.getLogger("ai_test.auto_eval")

async def auto_evaluate_run(run_record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Send the full agent conversation to OpenAI and get back:
    - overall_verdict: pass/fail
    - overall_reason: 1-2 sentences
    - turns: per-turn evaluation [{turn, pass, reason}]
    """
    if not OPENAI_API_KEY:
        return None

    cases = run_record.get("cases", [])
    if not cases:
        return None

    # Build conversation text for the prompt
    convo_lines = []
    for c in cases:
        user_msg = c.get("user_message", c.get("case_id", ""))
        bot_msg = (c.get("actual") or {}).get("bot_message", "") or c.get("error", "")
        turn = c.get("turn", "?")
        convo_lines.append(f"Turn {turn}\nUser: {user_msg}\nBot: {bot_msg}")

    system_prompt_used = run_record.get("custom_system_prompt", "")
    agent = run_record.get("agent", "")

    prompt = (
        f"You are evaluating a chatbot QA test run.\n"
        f"Agent persona / test instruction: {system_prompt_used or agent}\n\n"
        f"Conversation:\n" + "\n\n".join(convo_lines) + "\n\n"
        "Evaluate how well the bot performed. Return JSON with:\n"
        "{\n"
        '  "overall_verdict": "pass" | "fail",\n'
        '  "overall_reason": "one or two sentences",\n'
        '  "turns": [{"turn": 1, "pass": true, "reason": "..."}]\n'
        "}\n"
        "Be strict. If the bot gave wrong info, was unhelpful, or broke the flow, mark as fail."
    )

    body = {
        "model": OPENAI_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {"type": "json_object"},
        "temperature": 0,
    }
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.post("https://api.openai.com/v1/chat/completions", headers=headers, json=body)
            r.raise_for_status()
            content = r.json()["choices"][0]["message"]["content"]
            return json.loads(content)
    except Exception as exc:
        logger.exception("auto_eval failed: %s", exc)
        return None
```

#### 2. Call auto_eval after agent runs in runner.py
**File:** `app/runner.py`

```python
from app.auto_eval import auto_evaluate_run

# At the end of run_agent_conversation_with_id, after status = "completed":
auto_eval = await auto_evaluate_run(run_record)
if auto_eval:
    run_record["auto_eval"] = auto_eval
    update_run(run_id, run_record)
```

#### 3. Render auto_eval in the run detail report
**File:** `static/pages/history.js` and the shared `renderRunReport` function

After the existing case table, add an auto-eval section:

```javascript
function renderAutoEval(autoEval) {
  if (!autoEval) return "";
  const verdict = autoEval.overall_verdict === "pass";
  const turnRows = (autoEval.turns || []).map(t =>
    `<tr>
      <td>Turn ${t.turn}</td>
      <td><span class="${t.pass ? "check-pass" : "check-fail"}">${t.pass ? "✅ Pass" : "❌ Fail"}</span></td>
      <td style="font-size:12px;color:#4b5563">${t.reason || ""}</td>
    </tr>`
  ).join("");

  return `
    <div class="auto-eval-panel">
      <h3>AI Evaluation</h3>
      <div class="auto-eval-verdict ${verdict ? "verdict-pass" : "verdict-fail"}">
        ${verdict ? "✅" : "❌"} ${autoEval.overall_reason || ""}
      </div>
      ${turnRows ? `<table class="report-table"><thead><tr><th>Turn</th><th>Result</th><th>Reason</th></tr></thead><tbody>${turnRows}</tbody></table>` : ""}
    </div>`;
}
```

Add CSS for the new panel:
```css
.auto-eval-panel { margin-top: 20px; border-top: 1px solid #e5e7eb; padding-top: 16px; }
.auto-eval-panel h3 { font-size: 14px; font-weight: 700; margin: 0 0 10px 0; }
.auto-eval-verdict { padding: 10px 14px; border-radius: 8px; font-size: 13px; margin-bottom: 12px; }
.verdict-pass { background: #dcfce7; color: #15803d; }
.verdict-fail { background: #fee2e2; color: #b91c1c; }
```

### Success Criteria

#### Automated Verification:
- [ ] After agent run completes, run JSON contains `auto_eval` key: check `runs/run-*.json`
- [ ] `auto_eval` has `overall_verdict`, `overall_reason`, `turns` fields
- [ ] If `OPENAI_API_KEY` is missing, run still completes (auto_eval is skipped, not a crash)

#### Manual Verification:
- [ ] Agent run detail panel shows "AI Evaluation" section below the conversation table
- [ ] Per-turn pass/fail with reason is visible
- [ ] Overall verdict (pass/fail + reason) is prominently displayed
- [ ] Cloning a run with auto_eval results — new run starts fresh, not inheriting old eval

---

## Dashboard Page (Phase 2 completion)

**File:** `static/pages/dashboard.js`

Show quick stats (total runs, pass rate today, last run status) and a "Quick Start" button that goes to New Run.

```javascript
async function mount_dashboard() {
  const runs = await API.runs.list();
  const total = runs.length;
  const passed = runs.filter(r => r.status === "completed").length;
  const failed = runs.filter(r => r.status === "failed").length;
  const lastRun = runs[0];

  document.getElementById("dashboard-stats").innerHTML = `
    <div class="stat-card"><div class="stat-value">${total}</div><div class="stat-label">Total Runs</div></div>
    <div class="stat-card"><div class="stat-value stat-good">${passed}</div><div class="stat-label">Completed</div></div>
    <div class="stat-card"><div class="stat-value stat-bad">${failed}</div><div class="stat-label">Failed</div></div>
  `;

  document.getElementById("dashboard-recent").innerHTML = `
    <h2 style="font-size:15px;margin-bottom:12px">Recent Runs</h2>
    ${runs.slice(0, 5).map(r => `
      <div class="run-card" onclick="navigate('#/history')">
        <span class="status-badge status-${r.status}">${r.status}</span>
        <span style="font-size:13px;margin-left:8px">${r.mode === "agent" ? "Agent: " + r.agent : "Dataset: " + r.dataset_id}</span>
        <span class="hint" style="margin-left:auto">${r.started_at ? new Date(r.started_at).toLocaleString() : ""}</span>
      </div>`).join("")}
    <div style="margin-top:16px">
      <button class="btn-primary" onclick="navigate('#/run')">+ New Run</button>
    </div>
  `;
}
```

---

## Full File List After Implementation

```
static/
├── index.html          (restructured — nav + page divs)
├── styles.css          (extended — sidebar, cards, auto-eval)
├── router.js           (NEW — hash routing)
├── api.js              (NEW — all fetch calls)
├── app.js              (minimal — just init)
└── pages/
    ├── dashboard.js    (NEW)
    ├── datasets.js     (NEW — moved from app.js)
    ├── run.js          (NEW — New Run page with prompt UI)
    └── history.js      (NEW — run list + detail + clone)

app/
├── main.py             (extended — /api/agents endpoint, custom_system_prompt)
├── runner.py           (extended — custom_system_prompt param, auto_eval call)
├── ai_chat.py          (extended — custom_system_prompt param)
├── auto_eval.py        (NEW — per-turn AI evaluation)
├── case_library.py     (NEW — extracted from runner.py)
├── storage.py          (extended — passed_count, mode, agent in list)
├── config.py           (unchanged)
├── db.py               (unchanged)
├── analytics.py        (unchanged)
├── evaluator.py        (unchanged)
└── utils.py            (unchanged)
```

---

## Migration Notes

- All existing run JSON files in `runs/` remain valid — new fields (`custom_system_prompt`, `auto_eval`) are optional
- All existing dataset JSON files in `datasets/` remain unchanged
- The old `static/app.js` is replaced — no backward compatibility needed for the old UI
- `DEFAULT_CASE_LIBRARY` extraction from `runner.py` is a move, not a change — behaviour identical

---

## Testing Strategy

### After Phase 1:
```bash
# Start server
uvicorn app.main:app --reload --port 9101

# Check agent list
curl http://localhost:9101/api/agents | python -m json.tool

# Start agent run with custom prompt
curl -X POST http://localhost:9101/api/runs \
  -H "Content-Type: application/json" \
  -d '{"mode":"agent","agent":"general","max_turns":2,"custom_system_prompt":"Ask about appointment booking"}'

# Check run record has custom_system_prompt stored
cat runs/run-*.json | python -m json.tool | grep custom_system_prompt
```

### After Phase 3:
1. Open `http://localhost:9101/#/run`
2. Switch to Agent Mode
3. Select "appointment" persona — verify system prompt loads in textarea
4. Edit the prompt text
5. Enable Custom Mode — verify textarea clears
6. Start a run — verify `custom_system_prompt` in run JSON matches what was typed

### After Phase 5:
1. Complete an agent run
2. Open History → click the run
3. Verify "AI Evaluation" section appears with turn-by-turn verdict
4. Click Clone — verify New Run page opens with same prompt pre-filled

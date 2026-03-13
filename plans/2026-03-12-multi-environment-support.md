# Multi-Environment Support Implementation Plan

**Date:** 2026-03-12
**Scope:** Named Dev / QA / Prod environments — switchable on-the-fly from the UI, applied to every run

---

## Overview

Right now every connection value (webhook URL, admin ID, phone credentials) is a single global value read from `.env` at startup. To switch environments QA must edit `.env` and restart the server. This plan adds named environments stored as JSON files, a persistent in-sidebar environment switcher, and wires the active environment through the entire run pipeline so every run record knows exactly which environment it hit.

---

## Current State Analysis

### Where env values live today

| Value | Source in config.py | Consumed in runner.py |
|---|---|---|
| `WHATSAPP_WEBHOOK_BASE` | `os.getenv(...)` | `_post_webhook()` line 41 — **module-level constant**, not passed as argument |
| `DEFAULT_ADMIN_ID` | `os.getenv(...)` | `_execute_case()` line 248 — 3rd fallback after case → dataset defaults |
| `DEFAULT_USER_ID` | `os.getenv(...)` | `_execute_case()` line 247 |
| `DEFAULT_PHONE_NUMBER` | `os.getenv(...)` | `_execute_case()` line 257 |
| `DEFAULT_PHONE_NUMBER_ID` | `os.getenv(...)` | `_execute_case()` line 268 |
| `DEFAULT_DISPLAY_PHONE_NUMBER` | `os.getenv(...)` | `_execute_case()` line 271 |
| `DEFAULT_USER_NAME` | `os.getenv(...)` | `_execute_case()` line 255 — **note:** currently takes priority OVER dataset defaults |

### Current resolution order in `_execute_case` (runner.py:231)

```
case-level field  →  dataset.defaults  →  config.py DEFAULT_*
```

### Key architectural issues

1. `_post_webhook(userid, payload)` uses `WHATSAPP_WEBHOOK_BASE` directly from module scope — it must be refactored to accept a `webhook_base` param
2. `_execute_case` has no knowledge of an "environment" concept — it must receive an env dict and use it as the new middle layer
3. The entire call chain (`start_run → run_dataset_with_id → _execute_case`) needs an `env` parameter threaded through

### Storage pattern to follow

`storage.py` stores datasets as one JSON file per dataset in `datasets/`. We follow the exact same pattern for environments in `environments/`.

---

## Desired End State

After this plan is complete:

1. **`environments/` directory** contains `dev.json`, `qa.json`, `prod.json` (pre-seeded on first startup if empty)
2. **`GET/POST/PUT/DELETE /api/environments`** CRUD endpoints work
3. **`POST /api/runs`** accepts `environment_id` — runner resolves that environment's values and uses them
4. **Run records** store `environment_id` + `environment_name` so History can show which env was used
5. **Sidebar** has a persistent environment switcher (pill badge) — clicking shows a dropdown to switch. Active selection stored in `localStorage`
6. **New "Environments" page** (`#/environments`) — table of all environments with edit-in-place, create, delete
7. **Resolution order for every field:** `case` → `dataset.defaults` → `active_environment` → `config.py DEFAULT_*`

---

## What We're NOT Doing

- No MongoDB URI in environments (stays `.env` only)
- No auth / per-user environments
- No dataset schema changes — datasets stay as-is; env is a separate layer
- No automatic environment detection based on URL
- No "default environment" that gets pinned server-side — client selects via `environment_id` in run payload
- No React/Vue — stays vanilla JS

---

## Implementation Approach

Build in 3 phases, each independently verifiable:

1. **Phase 1** — Backend: env storage module + CRUD API + pre-seed
2. **Phase 2** — Backend: thread env through runner pipeline
3. **Phase 3** — Frontend: sidebar switcher + Environments page + wire to runs

---

## Phase 1: Backend — Environment Storage & CRUD API

### Overview

Create `app/env_storage.py` (parallel to `storage.py`), add 5 API endpoints to `main.py`, pre-seed on startup.

### Changes Required

#### 1. New `environments/` directory & seed files

**Directory:** `environments/` at project root (same level as `runs/`, `datasets/`)

Pre-seed content for `environments/dev.json`:
```json
{
  "env_id": "dev",
  "name": "Dev",
  "color": "slate",
  "webhook_base_url": "",
  "admin_id": "",
  "user_id": "",
  "phone_number_id": "",
  "display_phone_number": "",
  "contact_name": "Automation User",
  "country_code": "91"
}
```

`environments/qa.json` — same structure, `env_id: "qa"`, `name: "QA"`, `color: "blue"`
`environments/prod.json` — same structure, `env_id: "prod"`, `name: "Prod"`, `color: "red"`

The `color` field drives the badge colour in the sidebar: `slate` → grey, `blue` → blue, `amber` → amber, `red` → red, `green` → green.

#### 2. New `app/env_storage.py`

```python
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config import BASE_DIR

ENVIRONMENTS_DIR = Path(BASE_DIR) / "environments"

_SEEDS = [
    {"env_id": "dev",  "name": "Dev",  "color": "slate", "webhook_base_url": "", "admin_id": "", "user_id": "", "phone_number_id": "", "display_phone_number": "", "contact_name": "Automation User", "country_code": "91"},
    {"env_id": "qa",   "name": "QA",   "color": "blue",  "webhook_base_url": "", "admin_id": "", "user_id": "", "phone_number_id": "", "display_phone_number": "", "contact_name": "Automation User", "country_code": "91"},
    {"env_id": "prod", "name": "Prod", "color": "red",   "webhook_base_url": "", "admin_id": "", "user_id": "", "phone_number_id": "", "display_phone_number": "", "contact_name": "Automation User", "country_code": "91"},
]

def ensure_environments_dir() -> None:
    ENVIRONMENTS_DIR.mkdir(parents=True, exist_ok=True)
    # Pre-seed if empty
    if not any(ENVIRONMENTS_DIR.glob("*.json")):
        for seed in _SEEDS:
            _save_env_file(seed["env_id"], seed)

def _env_path(env_id: str) -> Path:
    return ENVIRONMENTS_DIR / f"{env_id}.json"

def _save_env_file(env_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    path = _env_path(env_id)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return data

def list_environments() -> List[Dict[str, Any]]:
    ensure_environments_dir()
    result = []
    for path in sorted(ENVIRONMENTS_DIR.glob("*.json")):
        try:
            with path.open("r", encoding="utf-8") as f:
                result.append(json.load(f))
        except Exception:
            continue
    return result

def load_environment(env_id: str) -> Dict[str, Any]:
    path = _env_path(env_id)
    if not path.exists():
        raise FileNotFoundError(f"Environment not found: {env_id}")
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)

def save_environment(env_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    ensure_environments_dir()
    data["env_id"] = env_id
    return _save_env_file(env_id, data)

def delete_environment(env_id: str) -> None:
    path = _env_path(env_id)
    if path.exists():
        path.unlink()
```

#### 3. Add CRUD endpoints to `app/main.py`

Add imports at top:
```python
from app.env_storage import (
    ensure_environments_dir,
    list_environments,
    load_environment,
    save_environment,
    delete_environment,
)
```

Update `startup_event`:
```python
@app.on_event("startup")
async def startup_event() -> None:
    ensure_storage_dirs()
    ensure_environments_dir()  # NEW
```

Add 5 new endpoints (after the existing `/api/runs` block):
```python
@app.get("/api/environments")
async def api_list_environments() -> List[Dict[str, Any]]:
    return list_environments()

@app.get("/api/environments/{env_id}")
async def api_get_environment(env_id: str) -> Dict[str, Any]:
    try:
        return load_environment(env_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="environment_not_found")

@app.post("/api/environments")
async def api_create_environment(request: Request) -> Dict[str, Any]:
    payload = await request.json()
    env_id = (payload.get("env_id") or "").strip().lower().replace(" ", "_")
    if not env_id:
        raise HTTPException(status_code=400, detail="env_id_required")
    payload["env_id"] = env_id
    return save_environment(env_id, payload)

@app.put("/api/environments/{env_id}")
async def api_update_environment(env_id: str, request: Request) -> Dict[str, Any]:
    payload = await request.json()
    payload["env_id"] = env_id
    return save_environment(env_id, payload)

@app.delete("/api/environments/{env_id}")
async def api_delete_environment(env_id: str) -> Dict[str, str]:
    try:
        delete_environment(env_id)
    except Exception:
        pass
    return {"deleted": env_id}
```

### Success Criteria

#### Automated Verification:
- [x] Server starts: `.venv/Scripts/uvicorn app.main:app --port 9101`
- [x] `environments/` is created and contains `dev.json`, `qa.json`, `prod.json` on first start
- [x] `GET /api/environments` returns 3 items: `curl http://localhost:9101/api/environments`
- [x] `PUT /api/environments/dev` with updated `webhook_base_url` persists to `environments/dev.json`
- [x] `POST /api/environments` with new env creates new JSON file
- [x] `DELETE /api/environments/custom` removes file

#### Manual Verification:
- [ ] `environments/` directory exists at project root after first startup
- [ ] Editing dev.json values via PUT reflects immediately on next GET

**Pause here before Phase 2.**

---

## Phase 2: Backend — Thread Environment Through Runner

### Overview

`_post_webhook` and `_execute_case` currently read env values from module-level constants. Add an `env` dict parameter to the run pipeline so the selected environment's values are used as the fallback layer between dataset defaults and config defaults.

### New resolution order

```
case-level field  →  dataset.defaults  →  env dict  →  config.py DEFAULT_*
```

For `webhook_base_url` specifically (since it's not per-case or per-dataset):
```
env dict  →  config.py WHATSAPP_WEBHOOK_BASE
```

### Changes Required

#### 1. `app/runner.py` — `_post_webhook`

**Current** (line 40–45):
```python
async def _post_webhook(userid: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    url = f"{WHATSAPP_WEBHOOK_BASE}/{userid}"
    ...
```

**New:**
```python
async def _post_webhook(
    userid: str,
    payload: Dict[str, Any],
    webhook_base: str = "",
) -> Dict[str, Any]:
    base = webhook_base or WHATSAPP_WEBHOOK_BASE
    url = f"{base}/{userid}"
    ...
```

#### 2. `app/runner.py` — `_execute_case` signature

Add `env` parameter:
```python
async def _execute_case(
    dataset: Dict[str, Any],
    case: Dict[str, Any],
    run_id: str,
    stop_event: Optional[asyncio.Event] = None,
    env: Optional[Dict[str, Any]] = None,      # NEW
) -> Dict[str, Any]:
    env = env or {}
    defaults = dataset.get("defaults", {}) or {}
    ...
```

#### 3. `app/runner.py` — `_execute_case` field resolution

Replace the existing resolution lines with env as middle layer:

```python
# userid / admin_id: case → dataset defaults → env → config
userid   = case.get("userid")   or defaults.get("userid")   or env.get("user_id")  or DEFAULT_USER_ID  or ""
admin_id = case.get("admin_id") or defaults.get("admin_id") or env.get("admin_id") or DEFAULT_ADMIN_ID or ""

# contact_name: dataset defaults → env → config (dataset takes priority over env here)
contact_name = defaults.get("contact_name") or env.get("contact_name") or DEFAULT_USER_NAME or "Automation User"

# phone: dataset defaults → env → config
fixed_phone = defaults.get("phone") or env.get("phone") or DEFAULT_PHONE_NUMBER or ""

phone_number_id = (
    defaults.get("phone_number_id", "")
    or env.get("phone_number_id", "")
    or DEFAULT_PHONE_NUMBER_ID
    or ""
)
display_phone_number = (
    defaults.get("display_phone_number", "")
    or env.get("display_phone_number", "")
    or DEFAULT_DISPLAY_PHONE_NUMBER
    or ""
)

# Pass webhook_base from env when calling _post_webhook
webhook_base = env.get("webhook_base_url", "") or WHATSAPP_WEBHOOK_BASE
...
webhook_response = await _post_webhook(userid, payload, webhook_base=webhook_base)
```

#### 4. `app/runner.py` — Thread `env` through `run_dataset_with_id` and `run_agent_conversation_with_id`

**`run_dataset_with_id` signature:**
```python
async def run_dataset_with_id(
    run_id: str,
    dataset: Dict[str, Any],
    tag_filter: Optional[List[str]] = None,
    stop_event: Optional[asyncio.Event] = None,
    env: Optional[Dict[str, Any]] = None,    # NEW
) -> Dict[str, Any]:
    ...
    run_record = {
        ...
        "environment_id":   (env or {}).get("env_id", ""),    # NEW
        "environment_name": (env or {}).get("name", ""),       # NEW
    }
    ...
    # In the case loop, pass env:
    result = await _execute_case(dataset, case, run_id, stop_event=stop_event, env=env)
```

**`run_agent_conversation_with_id` signature:**
```python
async def run_agent_conversation_with_id(
    run_id: str,
    dataset: Dict[str, Any],
    agent: str,
    max_turns: int,
    stop_event: Optional[asyncio.Event] = None,
    custom_system_prompt: Optional[str] = None,
    env: Optional[Dict[str, Any]] = None,    # NEW
) -> Dict[str, Any]:
    ...
    run_record = {
        ...
        "environment_id":   (env or {}).get("env_id", ""),    # NEW
        "environment_name": (env or {}).get("name", ""),       # NEW
    }
    ...
    # In the turn loop:
    result = await _execute_case(dataset, case, run_id, stop_event=stop_event, env=env)
```

#### 5. `app/runner.py` — `start_run` accepts env

```python
async def start_run(
    dataset: Dict[str, Any],
    tag_filter: Optional[List[str]] = None,
    mode: str = "dataset",
    agent: str = "",
    max_turns: int = 0,
    custom_system_prompt: Optional[str] = None,
    env: Optional[Dict[str, Any]] = None,    # NEW
) -> str:
    run_record = {
        ...
        "environment_id":   (env or {}).get("env_id", ""),
        "environment_name": (env or {}).get("name", ""),
    }
    ...
```

#### 6. `app/main.py` — `api_start_run` resolves env and passes it

```python
@app.post("/api/runs")
async def api_start_run(request: Request) -> Dict[str, Any]:
    payload = await request.json()
    ...
    environment_id = (payload.get("environment_id") or "").strip()

    # Resolve env dict — None if no environment_id provided (falls back to config)
    env: Optional[Dict[str, Any]] = None
    if environment_id:
        try:
            env = load_environment(environment_id)
        except FileNotFoundError:
            raise HTTPException(status_code=400, detail=f"environment_not_found: {environment_id}")

    run_id = await start_run(
        dataset, tags, mode=mode, agent=agent,
        max_turns=max_turns,
        custom_system_prompt=custom_system_prompt,
        env=env,    # NEW
    )
    ...
    async def _runner() -> None:
        if mode == "agent":
            await run_agent_conversation_with_id(
                run_id, dataset, agent, max_turns,
                stop_event=STOP_EVENTS.get(run_id),
                custom_system_prompt=custom_system_prompt,
                env=env,    # NEW
            )
        else:
            await run_dataset_with_id(
                run_id, dataset, tags,
                stop_event=STOP_EVENTS.get(run_id),
                env=env,    # NEW
            )
```

#### 7. `app/storage.py` — Include `environment_id` and `environment_name` in `list_runs()`

In `list_runs()`, add to the appended dict:
```python
"environment_id":   data.get("environment_id", ""),
"environment_name": data.get("environment_name", ""),
```

### Success Criteria

#### Automated Verification:
- [x] Server starts with no import errors
- [x] Start a run with `environment_id: "qa"` — run JSON contains `environment_id: "qa"`, `environment_name: "QA"`
- [x] Start a run without `environment_id` — run still completes (env=None falls back to config values)
- [x] `GET /api/runs` response includes `environment_id` and `environment_name` fields

#### Manual Verification:
- [ ] A run started against a QA environment URL actually hits the QA webhook (verify in server logs: `webhook_base=<qa_url>`)
- [ ] Dataset-level `defaults.admin_id` still overrides the env `admin_id` (case → dataset → env → config)
- [ ] Existing runs without `environment_id` still display correctly in History

**Pause here before Phase 3.**

---

## Phase 3: Frontend — Sidebar Switcher + Environments Page + Wire to Runs

### Overview

Three UI pieces: (1) a persistent environment badge/selector in the sidebar footer, (2) a new Environments management page, (3) `environment_id` sent with every run start and shown in History cards.

### Changes Required

#### 1. `static/api.js` — Add environments namespace

```javascript
environments: {
  list:   ()        => API.get("/api/environments"),
  get:    (id)      => API.get(`/api/environments/${id}`),
  save:   (id, d)   => API.put(`/api/environments/${id}`, d),
  create: (d)       => API.post("/api/environments", d),
  delete: (id)      => API._fetch(`/api/environments/${id}`, { method: "DELETE" }),
},
```

#### 2. `static/env.js` — New module: active environment state

```javascript
// Manages the active environment selection in localStorage.
// All pages import this via the global ENV object.
const ENV = (() => {
  const KEY = "ai_test_active_env";

  function getActiveId() {
    return localStorage.getItem(KEY) || "";
  }

  function setActiveId(id) {
    localStorage.setItem(KEY, id);
    document.dispatchEvent(new CustomEvent("env-changed", { detail: id }));
  }

  function getActiveEnv(environments) {
    const id = getActiveId();
    return environments.find(e => e.env_id === id) || environments[0] || null;
  }

  return { getActiveId, setActiveId, getActiveEnv };
})();
```

#### 3. `static/index.html` — Sidebar env switcher + Environments page + script tags

**In the sidebar, replace the `nav-footer` div:**
```html
<div class="nav-footer">
  <div class="nav-env-label">Environment</div>
  <div class="nav-env-switcher" id="navEnvSwitcher">
    <div class="nav-env-badge" id="navEnvBadge">
      <span class="nav-env-dot" id="navEnvDot"></span>
      <span id="navEnvName">—</span>
      <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>
    </div>
    <div class="nav-env-dropdown hidden" id="navEnvDropdown"></div>
  </div>
  <div class="nav-footer-badge">v2.0</div>
</div>
```

**Add nav item for Environments page:**
```html
<a href="#/environments" class="nav-item" data-page="environments">
  <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <circle cx="12" cy="12" r="3"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14"/><path d="M4.93 4.93a10 10 0 0 0 0 14.14"/>
  </svg>
  Environments
</a>
```

**Add Environments page div (after history page div):**
```html
<div id="page-environments" class="page-view hidden">
  <div class="page-header">
    <div>
      <h1>Environments</h1>
      <p class="page-subtitle">Configure Dev / QA / Prod connection settings</p>
    </div>
    <button id="createEnvBtn" class="btn-primary">
      <svg width="14" height="14" ...>...</svg>
      New Environment
    </button>
  </div>
  <div id="envList"></div>
  <div id="envEditorPanel" class="card hidden editor-panel">
    <div class="editor-panel-header">
      <div class="card-section-title" id="envEditorTitle">Edit Environment</div>
      <div class="toolbar" style="margin:0">
        <button id="saveEnv" class="btn-primary btn-sm">Save</button>
        <button id="cancelEnvEdit" class="btn-ghost btn-sm">Cancel</button>
      </div>
    </div>
    <div id="envEditorFields"></div>
  </div>
</div>
```

**Add script tags in `<head>` / before `</body>`:**
```html
<script src="/static/env.js"></script>
<script src="/static/pages/environments.js"></script>
```

#### 4. `static/router.js` — Add `/environments` route

```javascript
const ROUTES = {
  "/":             "dashboard",
  "/datasets":     "datasets",
  "/run":          "run",
  "/history":      "history",
  "/environments": "environments",   // NEW
};
```

#### 5. `static/pages/environments.js` — New page module

```javascript
let _envEditing = null;

async function mount_environments() {
  await _loadEnvList();
  document.getElementById("createEnvBtn").addEventListener("click", _createEnv);
  document.getElementById("saveEnv").addEventListener("click", _saveEnv);
  document.getElementById("cancelEnvEdit").addEventListener("click", _closeEnvEditor);
}

async function _loadEnvList() {
  const list = document.getElementById("envList");
  const envs = await API.environments.list();
  const activeId = ENV.getActiveId();

  list.innerHTML = envs.map(e => {
    const isActive = e.env_id === activeId;
    return `
      <div class="env-card ${isActive ? "env-card-active" : ""}" data-env-id="${e.env_id}">
        <div class="env-card-left">
          <span class="env-dot env-dot-${e.color || "slate"}"></span>
          <div>
            <span class="env-card-name">${e.name}</span>
            ${isActive ? `<span class="env-active-badge">Active</span>` : ""}
            <div class="hint">${e.webhook_base_url || "<no webhook URL set>"}</div>
          </div>
        </div>
        <div class="env-card-right">
          <button class="btn-sm btn-ghost" onclick="ENV.setActiveId('${e.env_id}'); _loadEnvList();">
            ${isActive ? "✓ Active" : "Set Active"}
          </button>
          <button class="btn-sm" onclick="_editEnv('${e.env_id}')">Edit</button>
          ${!["dev","qa","prod"].includes(e.env_id) ? `<button class="btn-sm btn-danger" onclick="_deleteEnv('${e.env_id}')">Delete</button>` : ""}
        </div>
      </div>`;
  }).join("") || `<p class="empty-hint">No environments yet.</p>`;
}

async function _editEnv(envId) {
  const e = await API.environments.get(envId);
  _envEditing = envId;
  document.getElementById("envEditorTitle").textContent = "Editing: " + e.name;
  document.getElementById("envEditorFields").innerHTML = _buildEnvForm(e);
  document.getElementById("envEditorPanel").classList.remove("hidden");
  document.getElementById("envEditorPanel").scrollIntoView({ behavior: "smooth" });
}

function _buildEnvForm(e) {
  const field = (label, key, placeholder) => `
    <div class="field-group">
      <label class="field-label">${label}</label>
      <input class="input-full env-field" data-key="${key}" value="${e[key] || ""}" placeholder="${placeholder}" />
    </div>`;
  return `
    ${field("Name", "name", "e.g. QA")}
    ${field("Webhook Base URL", "webhook_base_url", "https://qa.example.com/api/whatsapp/meta/webhook")}
    ${field("Admin ID", "admin_id", "MongoDB ObjectId of admin")}
    ${field("User ID", "user_id", "Same as admin ID usually")}
    ${field("Phone Number ID", "phone_number_id", "WhatsApp phone number ID")}
    ${field("Display Phone Number", "display_phone_number", "+91XXXXXXXXXX")}
    ${field("Default Contact Name", "contact_name", "Automation User")}
    ${field("Country Code", "country_code", "91")}
    <div class="field-group">
      <label class="field-label">Badge Color</label>
      <select class="env-field" data-key="color">
        ${["slate","blue","green","amber","red"].map(c =>
          `<option value="${c}" ${e.color === c ? "selected" : ""}>${c}</option>`
        ).join("")}
      </select>
    </div>`;
}

async function _saveEnv() {
  if (!_envEditing) return;
  const data = { env_id: _envEditing };
  document.querySelectorAll(".env-field").forEach(el => {
    data[el.dataset.key] = el.value.trim();
  });
  await API.environments.save(_envEditing, data);
  _closeEnvEditor();
  await _loadEnvList();
  _refreshSidebarEnv();
}

async function _createEnv() {
  const name = prompt("Environment name (e.g. Staging):");
  if (!name) return;
  const env_id = name.toLowerCase().replace(/\s+/g, "_");
  await API.environments.create({ env_id, name, color: "slate", webhook_base_url: "", admin_id: "", user_id: "", phone_number_id: "", display_phone_number: "", contact_name: "Automation User", country_code: "91" });
  await _loadEnvList();
}

async function _deleteEnv(envId) {
  if (!confirm(`Delete environment "${envId}"?`)) return;
  await API.environments.delete(envId);
  if (ENV.getActiveId() === envId) ENV.setActiveId("");
  await _loadEnvList();
  _refreshSidebarEnv();
}

function _closeEnvEditor() {
  document.getElementById("envEditorPanel").classList.add("hidden");
  _envEditing = null;
}
```

#### 6. `static/app.js` — Sidebar env switcher init

```javascript
// Initialise the sidebar env switcher on page load.
// Called once; listens for env-changed events to re-render.

async function _refreshSidebarEnv() {
  const envs = await API.environments.list();
  const active = ENV.getActiveEnv(envs);
  const badge = document.getElementById("navEnvBadge");
  const nameEl = document.getElementById("navEnvName");
  const dotEl  = document.getElementById("navEnvDot");
  if (!badge) return;
  nameEl.textContent = active ? active.name : "None";
  dotEl.className = `nav-env-dot env-dot-${active ? (active.color || "slate") : "slate"}`;
}

async function _buildEnvDropdown() {
  const envs = await API.environments.list();
  const dropdown = document.getElementById("navEnvDropdown");
  const activeId = ENV.getActiveId();
  dropdown.innerHTML = envs.map(e => `
    <div class="nav-env-option ${e.env_id === activeId ? "nav-env-option-active" : ""}"
         onclick="ENV.setActiveId('${e.env_id}'); _closeEnvDropdown();">
      <span class="env-dot env-dot-${e.color || "slate"}"></span>
      ${e.name}
    </div>`).join("");
  dropdown.innerHTML += `<div class="nav-env-option" onclick="navigate('#/environments'); _closeEnvDropdown();">⚙ Manage...</div>`;
}

function _closeEnvDropdown() {
  document.getElementById("navEnvDropdown").classList.add("hidden");
  _refreshSidebarEnv();
}

document.addEventListener("DOMContentLoaded", () => {
  _refreshSidebarEnv();

  document.getElementById("navEnvBadge").addEventListener("click", async () => {
    const dropdown = document.getElementById("navEnvDropdown");
    if (dropdown.classList.contains("hidden")) {
      await _buildEnvDropdown();
      dropdown.classList.remove("hidden");
    } else {
      _closeEnvDropdown();
    }
  });

  document.addEventListener("env-changed", _refreshSidebarEnv);

  // Close dropdown when clicking outside
  document.addEventListener("click", e => {
    if (!e.target.closest("#navEnvSwitcher")) _closeEnvDropdown();
  });
});
```

#### 7. `static/pages/run.js` — Send `environment_id` with run start

```javascript
// In _startDatasetRun:
const res = await API.runs.start({
  mode: "dataset",
  dataset_id: datasetId,
  tags,
  environment_id: ENV.getActiveId() || undefined,   // NEW
});

// In _startAgentRun:
const res = await API.runs.start({
  mode: "agent",
  agent,
  max_turns: maxTurns,
  custom_system_prompt: customPrompt || undefined,
  environment_id: ENV.getActiveId() || undefined,   // NEW
});
```

Also show the active env on the New Run page as a contextual reminder above the run buttons:

```javascript
// In mount_run, add after populating selects:
const envs = await API.environments.list();
const activeEnv = ENV.getActiveEnv(envs);
const envNotice = document.getElementById("activeEnvNotice");
if (envNotice && activeEnv) {
  envNotice.innerHTML = `
    <span class="env-dot env-dot-${activeEnv.color || "slate"}"></span>
    Running against: <b>${activeEnv.name}</b>
    ${activeEnv.webhook_base_url ? `<span class="hint">${activeEnv.webhook_base_url}</span>` : '<span class="hint warn">No webhook URL set</span>'}
    <a href="#/environments" class="hint" style="margin-left:auto">Change →</a>`;
  envNotice.classList.remove("hidden");
}
```

Add this div to `index.html` inside `page-run`, above the mode tabs:
```html
<div id="activeEnvNotice" class="env-notice hidden"></div>
```

#### 8. `static/pages/history.js` — Show env badge on run cards

In the run card HTML, add alongside the status badge:
```javascript
const envBadge = r.environment_name
  ? `<span class="env-badge env-badge-inline">${r.environment_name}</span>`
  : "";
// Insert after status-badge in the run-card-left div
```

#### 9. `static/styles.css` — New environment CSS

```css
/* ── Environment Dots ────────────────────────────── */
.env-dot {
  width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; display: inline-block;
}
.env-dot-slate  { background: var(--slate-400); }
.env-dot-blue   { background: var(--blue-500); }
.env-dot-green  { background: var(--green-600); }
.env-dot-amber  { background: var(--amber-600); }
.env-dot-red    { background: var(--red-600); }

/* ── Sidebar Env Switcher ────────────────────────── */
.nav-env-label {
  font-size: 10px; font-weight: 700; letter-spacing: 1px;
  text-transform: uppercase; color: var(--slate-600);
  padding: 12px 16px 4px;
}
.nav-env-switcher { position: relative; padding: 0 8px 12px; }
.nav-env-badge {
  display: flex; align-items: center; gap: 7px;
  padding: 8px 10px; border-radius: var(--radius-sm);
  background: rgba(255,255,255,0.07); cursor: pointer;
  font-size: 12.5px; font-weight: 600; color: #e2e8f0;
  transition: background 0.15s;
}
.nav-env-badge:hover { background: rgba(255,255,255,0.12); }
.nav-env-dropdown {
  position: absolute; bottom: 100%; left: 8px; right: 8px;
  background: var(--slate-700); border-radius: var(--radius-sm);
  box-shadow: var(--shadow-lg); overflow: hidden; z-index: 100;
}
.nav-env-option {
  display: flex; align-items: center; gap: 8px;
  padding: 9px 12px; font-size: 13px; color: #e2e8f0;
  cursor: pointer; transition: background 0.1s;
}
.nav-env-option:hover { background: rgba(255,255,255,0.1); }
.nav-env-option-active { color: #fff; font-weight: 600; }

/* ── Environment Notice (New Run page) ───────────── */
.env-notice {
  display: flex; align-items: center; gap: 8px;
  padding: 10px 14px; border-radius: var(--radius-sm);
  background: var(--slate-50); border: 1.5px solid var(--slate-200);
  font-size: 13px; color: var(--slate-700); margin-bottom: 14px;
}
.env-notice .warn { color: var(--amber-600); }

/* ── Environment Cards (Environments page) ───────── */
.env-card {
  background: var(--bg-card); border: 1.5px solid var(--slate-200);
  border-radius: var(--radius-md); padding: 14px 18px; margin-bottom: 8px;
  display: flex; align-items: center; justify-content: space-between;
  transition: box-shadow 0.15s;
}
.env-card-active { border-color: var(--blue-500); background: var(--blue-50); }
.env-card-left { display: flex; align-items: center; gap: 12px; }
.env-card-right { display: flex; align-items: center; gap: 8px; }
.env-card-name { font-weight: 700; font-size: 14px; color: var(--slate-900); }
.env-active-badge {
  display: inline-block; margin-left: 8px;
  background: var(--blue-100); color: var(--blue-700);
  font-size: 10px; font-weight: 700; text-transform: uppercase;
  letter-spacing: 0.4px; padding: 1px 7px; border-radius: var(--radius-full);
}
/* Inline env badge on history cards */
.env-badge-inline {
  font-size: 10px; font-weight: 700; text-transform: uppercase;
  letter-spacing: 0.4px; padding: 2px 7px; border-radius: var(--radius-full);
  background: var(--slate-100); color: var(--slate-600); border: 1px solid var(--slate-200);
}
```

### Success Criteria

#### Automated Verification:
- [x] `GET /api/environments` includes `dev`, `qa`, `prod`
- [x] `GET /api/runs` response includes `environment_id`, `environment_name` fields
- [x] All JS files pass syntax check (`env.js`, `pages/environments.js`, `app.js`, `run.js`, `history.js`)
- [ ] No console errors on any page (manual)

#### Manual Verification:
- [ ] Sidebar shows current active environment name + colored dot
- [ ] Clicking the env badge opens dropdown with all 3 environments
- [ ] Selecting an environment from dropdown updates the badge immediately
- [ ] Starting a run from New Run page — run JSON in `runs/` contains correct `environment_id`
- [ ] Run History cards show environment name badge
- [ ] Environments page shows all envs, active one highlighted
- [ ] Editing QA webhook URL + starting a run — server logs show the QA URL being hit
- [ ] Environment notice on New Run page shows "No webhook URL set" warning when env has empty URL

---

## Full File List After Implementation

```
app/
├── env_storage.py          (NEW — CRUD for environments)
├── main.py                 (extended — 5 new endpoints, env resolution in api_start_run)
├── runner.py               (extended — env dict threaded through all run functions)
├── storage.py              (extended — environment_id/name in list_runs)
├── config.py               (unchanged)
└── ...

environments/               (NEW directory)
├── dev.json
├── qa.json
└── prod.json

static/
├── env.js                  (NEW — ENV.getActiveId / setActiveId / getActiveEnv)
├── app.js                  (extended — sidebar env switcher init)
├── api.js                  (extended — API.environments namespace)
├── styles.css              (extended — env dots, switcher, notice, cards)
├── index.html              (extended — env switcher in sidebar, env notice in run page, environments page div)
├── router.js               (extended — /environments route)
└── pages/
    └── environments.js     (NEW — environments management page)
    └── history.js          (extended — env badge on run cards)
    └── run.js              (extended — environment_id in run start + env notice)
```

---

## Migration Notes

- All existing run JSON files remain valid — `environment_id` and `environment_name` will be empty strings for old runs, History displays them without badges (graceful degradation)
- `.env` values continue to work as the ultimate fallback — no breaking change if no environment is selected
- Pre-existing datasets with `admin_id` in `defaults` still override the environment (dataset wins over env)

---

## Testing Strategy

### After Phase 1:
```bash
.venv/Scripts/uvicorn app.main:app --reload --port 9101
curl http://localhost:9101/api/environments
curl -X PUT http://localhost:9101/api/environments/qa \
  -H "Content-Type: application/json" \
  -d '{"env_id":"qa","name":"QA","webhook_base_url":"https://qa.example.com/webhook","admin_id":"abc123"}'
curl http://localhost:9101/api/environments/qa
```

### After Phase 2:
```bash
# Start a run specifying QA environment — check run JSON for environment_id
curl -X POST http://localhost:9101/api/runs \
  -H "Content-Type: application/json" \
  -d '{"mode":"agent","agent":"general","max_turns":1,"environment_id":"qa"}'

# Verify run record
cat runs/run-*.json | python -m json.tool | grep environment
```

### After Phase 3:
1. Open `http://localhost:9101`
2. Sidebar shows current env badge (should default to first env)
3. Click badge → dropdown shows Dev / QA / Prod
4. Switch to QA → badge updates
5. Go to New Run → notice shows "Running against: QA"
6. Start a run → History card shows "QA" badge
7. Go to Environments page → see all 3, edit QA webhook URL, save
8. Start another run → server log shows QA URL

---

## Open Design Decisions (resolved)

| Decision | Choice | Reason |
|---|---|---|
| Where to store active env | `localStorage` (client) | Server doesn't need to know — it's per-browser session, not per-server |
| Prevent deletion of built-in envs | Dev/QA/Prod delete button hidden (not blocked server-side) | UX guard enough; can still recreate from template |
| What if no env selected | Falls back to `.env` config | Zero breaking change for existing workflows |
| Dataset defaults vs env | Dataset always wins over env | Dataset is more specific context; env is a global default |
| `contact_name` priority | dataset.defaults → env → config | Fixes the existing bug where `DEFAULT_USER_NAME` wrongly beat dataset defaults |

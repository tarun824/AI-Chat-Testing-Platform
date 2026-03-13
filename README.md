# AI Automation Runner

A FastAPI-based automation testing platform for WhatsApp AI chatbots. It simulates real user conversations, sends them through the WhatsApp webhook, polls MongoDB for bot responses, and evaluates the quality of those responses — all from a browser UI.

---

## Table of Contents

- [How It Works](#how-it-works)
- [Run Modes](#run-modes)
  - [Dataset Mode](#1-dataset-mode)
  - [Agent Mode](#2-agent-mode)
- [Evaluation System](#evaluation-system)
  - [Rule-Based Checks](#rule-based-checks)
  - [LLM-as-Judge](#llm-as-judge)
- [Agent Personas](#agent-personas)
- [Dataset Format](#dataset-format)
- [Environments](#environments)
- [Analytics](#analytics)
- [REST API](#rest-api)
- [Web UI](#web-ui)
- [Configuration](#configuration)
- [Setup & Run](#setup--run)
- [Directory Structure](#directory-structure)

---

## How It Works

```
User triggers a run (via UI or API)
        ↓
Runner builds WhatsApp webhook payload
        ↓
Resolves active environment (webhook URL, credentials)
        ↓
POST to WhatsApp webhook endpoint
        ↓
Poll MongoDB for bot response (with timeout)
        ↓
Evaluate: rule-based checks + optional LLM judge
        ↓
Save result to /runs/run-<uuid>.json (with environment_id)
        ↓
Optional: AI-generated analytics summary
```

Each run executes one or more **cases**. A case is a single user message sent to the bot. For each case, the runner:

1. Builds a WhatsApp-compatible JSON payload with a unique message ID and contact phone number.
2. POSTs the payload to the configured webhook URL (from the active environment, or `.env` fallback).
3. Resolves the contact in MongoDB's `phonebooks` collection.
4. Polls the `conversations` collection until a bot response newer than `started_at` appears (or timeout).
5. Measures response latency in milliseconds.
6. Runs evaluation checks against the bot's reply.
7. Saves the case result to the run record immediately (live update).

---

## Run Modes

### 1. Dataset Mode

Runs a list of predefined test cases from a JSON dataset file. Each case has a fixed input message and expected response criteria.

**How it executes:**
- Loads cases from `datasets/<dataset_id>.json`
- Filters by tags if a tag filter is provided
- Executes cases sequentially, one at a time
- Each case sends one message and waits for one bot reply
- Supports stop/cancel mid-run

**When to use:** Regression testing, verifying specific known flows, testing exact responses.

**Example flow:**
```
Load dataset "appointment" → 3 cases
  Case 1: "I want to book an appointment" → bot replies → evaluate
  Case 2: "Please reschedule my appointment" → bot replies → evaluate
  Case 3: "Cancel my appointment" → bot replies → evaluate
→ Run saved with all results
```

If a dataset has no `cases` defined, the runner auto-generates default cases from an internal library based on the `dataset_id` (e.g., dataset `appointment` maps to built-in appointment test cases).

---

### 2. Agent Mode

Uses OpenAI GPT-4o to simulate a realistic user persona in a multi-turn conversation. The AI generates each user message based on the conversation history so far.

**How it executes:**
- You pick an agent type (e.g., `appointment`, `negotiator`, `angry_user`)
- For each turn (up to `max_turns`, default 5):
  - OpenAI generates the next user message based on persona + conversation history
  - Message is sent to the webhook
  - Bot response is captured
  - Both sides are added to conversation history
  - Repeat for next turn
- Supports stop/cancel mid-run

**When to use:** Exploratory testing, testing multi-turn flows, checking how the bot handles varied and realistic conversations.

**Example flow (agent: appointment):**
```
Turn 1 → AI generates: "I want to book an appointment for next week"
         Bot replies: "Sure, what day works for you?"
Turn 2 → AI generates (based on history): "Actually, make it Tuesday morning"
         Bot replies: "Tuesday 10am is available. Shall I confirm?"
Turn 3 → AI generates: "Yes please"
         Bot replies: "Appointment confirmed for Tuesday 10am"
...up to max_turns
```

**API parameters for Agent Mode:**
```json
{
  "mode": "agent",
  "agent": "appointment",
  "max_turns": 5
}
```

---

## Evaluation System

Each case result contains an `evaluation` object with a `pass` boolean and a list of `checks`.

### Rule-Based Checks

Defined in the dataset's `expected` field per case. Two check types:

| Check | Description |
|---|---|
| `must_include` | Bot response MUST contain this text (case-insensitive) |
| `must_not_include` | Bot response MUST NOT contain this text (case-insensitive) |

If any check fails, `evaluation.pass` is `false`.

**Example dataset case:**
```json
{
  "id": "appointment_book",
  "webhook_payload": { ... },
  "expected": {
    "must_include": ["appointment", "confirmed"],
    "must_not_include": ["error", "sorry, I cannot"]
  }
}
```

**Result:**
```json
{
  "evaluation": {
    "pass": true,
    "checks": [
      { "type": "must_include", "value": "appointment", "pass": true },
      { "type": "must_include", "value": "confirmed", "pass": true },
      { "type": "must_not_include", "value": "error", "pass": true }
    ]
  }
}
```

---

### LLM-as-Judge

An optional semantic evaluation layer powered by OpenAI. Triggered when `expected.llm_judge` contains a rubric question.

**How it works:**
- Sends the user message, bot response, and rubric to GPT-4o
- GPT-4o evaluates step-by-step and returns `{ "pass": true/false, "reason": "..." }`
- Temperature is set to 0 for deterministic results
- A partial or vague bot answer is treated as a **fail** (strict evaluation)
- If LLM judge fails, overall `evaluation.pass` is forced to `false`
- If `OPENAI_API_KEY` is missing, the judge is skipped (`skipped: true`)

**Example:**
```json
{
  "expected": {
    "llm_judge": "Did the bot provide a specific appointment time and confirm the booking?"
  }
}
```

**Judge result attached to evaluation:**
```json
{
  "llm_judge": {
    "pass": true,
    "reason": "Bot clearly confirmed Tuesday 10am and stated the booking is done.",
    "skipped": false
  }
}
```

---

## Agent Personas

Used in **Agent Mode** to define how OpenAI generates user messages. Each persona has a unique behavioral constraint.

| Agent | Behavior |
|---|---|
| `appointment` | Books/reschedules appointments. Occasionally changes mind mid-conversation. |
| `appointment_nlp` | Same as appointment, aliased. |
| `patient_appointment` | Same as appointment, aliased. |
| `doctor` | Asks about a specific doctor's expertise for a named health issue. |
| `patient_query` | Asks about treatments, services, pricing, or clinic info. |
| `qna` | General questions: timings, location, contact, process. |
| `promotion` / `patient_promotion` | Asks about packages, offers, and discounts. |
| `care_coordinator` | Needs help coordinating a treatment plan or follow-up support. |
| `postops` | Asks about post-procedure pain, medication, and precautions. |
| `product` | Asks about ingredients or allergens. Tests factual accuracy. |
| `negotiator` | Price-sensitive customer. Uses phrases like "Too costly" or "Any discount?". Tests if bot gives unauthorized discounts. |
| `router` | Intentionally vague messages like "I need help". Tests cold-start routing. |
| `proactive_router` | Responds to a proactive outreach. |
| `summarizing` | Asks for a summary or recap. |
| `track_progress` | Asks for treatment progress updates. |
| `reminder` | Asks for appointment or medicine reminders. |
| `consent` | Asks about consent or agrees to proceed. |
| `media_success` / `media_sucess` | Frustrated user struggling to upload a file. |
| `partner` | Asks about partnership or referral programs. |
| `madhavbaug` | Asks about the Madhavbaug treatment program (mapped to general). |
| `angry_user` | Frustrated user with a delayed appointment. Tests de-escalation. |
| `typo_expert` | Sends queries with intentional typos. Tests NLP robustness. |
| `general` | Generic hospital user. Asks realistic follow-up questions. |

Messages are kept under 25 words and written in casual WhatsApp-style language.

---

## Dataset Format

Datasets are stored as JSON files in `datasets/`. Structure:

```json
{
  "dataset_id": "appointment",
  "defaults": {
    "userid": "<mongodb_user_id>",
    "admin_id": "<mongodb_admin_id>",
    "contact_name": "Test User",
    "country_code": "91",
    "poll_timeout_sec": 45,
    "poll_interval_ms": 1500,
    "unique_contact_per_case": true
  },
  "cases": [
    {
      "id": "book_appointment",
      "tags": ["appointment", "smoke"],
      "webhook_payload": {
        "object": "whatsapp_business_account",
        "entry": [
          {
            "changes": [
              {
                "value": {
                  "messages": [
                    {
                      "from": "919876543210",
                      "id": "wamid.test001",
                      "type": "text",
                      "text": { "body": "I want to book an appointment" }
                    }
                  ]
                }
              }
            ]
          }
        ]
      },
      "expected": {
        "must_include": ["appointment"],
        "must_not_include": ["error"],
        "llm_judge": "Did the bot acknowledge the appointment request and offer next steps?"
      }
    }
  ]
}
```

**Key fields:**

| Field | Required | Description |
|---|---|---|
| `dataset_id` | Yes | Unique identifier, matches filename |
| `defaults` | No | Shared config for all cases in this dataset |
| `defaults.unique_contact_per_case` | No | Generate a fresh phone number per case (default: `true`) |
| `cases` | No | List of test cases. If empty, default library cases are used |
| `case.id` | No | Identifier shown in results |
| `case.tags` | No | Used for filtering runs |
| `case.webhook_payload` | No | Full WhatsApp webhook JSON. If absent, a default text payload is built |
| `case.expected` | No | Evaluation criteria |

**Resolution order for credentials per case:**
```
case-level field  →  dataset.defaults  →  active environment  →  .env defaults
```
Dataset `defaults` always win over the active environment. This lets you pin specific credentials for a particular dataset while still getting the environment's webhook URL.

**Built-in dataset IDs (auto-generates default cases if `cases` is empty):**

`appointment`, `appointment_nlp`, `patient_appointment`, `patient_promotion`, `patient_query`, `doctor`, `qna`, `care_coordinator`, `postops`, `product`, `negotiator`, `partner`, `madhavbaug`, `router`, `proactive_router`, `summarizing`, `track_progress`, `reminder`, `media_success`, `consent`, `agents`, `mixed`

---

## Environments

The tool supports named environments (Dev, QA, Prod, or custom) so the QA team can switch the target server on-the-fly without editing `.env` or restarting.

### What an environment stores

| Field | Description |
|---|---|
| `name` | Display name (e.g. "Dev", "QA", "Prod") |
| `color` | Badge colour: `slate`, `blue`, `green`, `amber`, `red` |
| `webhook_base_url` | The URL test messages are POSTed to |
| `admin_id` | MongoDB ObjectId of the admin account |
| `user_id` | MongoDB ObjectId of the user account |
| `phone_number_id` | WhatsApp phone number ID |
| `display_phone_number` | WhatsApp display phone number |
| `phone_number` | SIM / test phone number (maps to `AI_TEST_PHONE_NUMBER`) |
| `contact_name` | Name shown in WhatsApp (maps to `AI_TEST_USER_NAME`) |
| `country_code` | Country dialling code (default: `91`) |

### Switching environments

The active environment is stored in `localStorage` (per browser). It persists across page refreshes and applies to every run started from that browser.

- **Sidebar** — a coloured badge shows the active environment at all times. Click it to switch.
- **New Run page** — a notice above the run buttons shows which environment will be targeted and warns if no webhook URL is set.
- **Environments page** (`#/environments`) — manage all environments: edit credentials, set active, create custom environments, delete non-built-in ones.

### How environments interact with datasets

Environments are a fallback layer, not an override. The resolution order for every credential value is:

```
case-level  →  dataset.defaults  →  active environment  →  .env defaults
```

If a dataset's `defaults` set `admin_id`, that value is always used regardless of the active environment. If `defaults.admin_id` is blank, the environment's `admin_id` is used. If neither is set, the `.env` default applies.

### Environment files

Environments are stored as JSON files in `environments/`. Three built-in files are pre-seeded on first startup: `dev.json`, `qa.json`, `prod.json`. Custom environments can be created from the UI and are stored as additional JSON files in the same directory.

### Run records

Every run stores `environment_id` and `environment_name`. History cards show an environment badge so you can see at a glance which environment each run targeted.

---

## Analytics

When `AI_TEST_ENABLE_ANALYTICS=true`, after every completed run (both modes), the full run record is sent to OpenAI for analysis. The response is saved back to the run under `run.analytics`.

**Returns a JSON object with:**
- `summary` — overall summary of the run
- `failures` — analysis of what failed and why
- `regressions` — patterns that might indicate regressions
- `suggestions` — recommended improvements to the bot

---

## REST API

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Health check |
| `GET` | `/api/datasets` | List all datasets |
| `GET` | `/api/datasets/{id}` | Get a dataset by ID |
| `POST` | `/api/datasets` | Create a new dataset |
| `PUT` | `/api/datasets/{id}` | Update an existing dataset |
| `POST` | `/api/datasets/{id}/cases` | Append a case to a dataset |
| `GET` | `/api/runs` | List all run records (includes `environment_id`, `environment_name`) |
| `GET` | `/api/runs/{run_id}` | Get a run by ID |
| `POST` | `/api/runs` | Start a new run |
| `POST` | `/api/runs/{run_id}/stop` | Stop a running run |
| `GET` | `/api/environments` | List all environments |
| `GET` | `/api/environments/{env_id}` | Get an environment by ID |
| `POST` | `/api/environments` | Create a new environment |
| `PUT` | `/api/environments/{env_id}` | Update an environment |
| `DELETE` | `/api/environments/{env_id}` | Delete an environment |

**Start run payload:**
```json
{
  "mode": "dataset",
  "dataset_id": "appointment",
  "tags": ["smoke"],
  "agent": "",
  "max_turns": 5,
  "environment_id": "qa"
}
```

`environment_id` is optional. If omitted, the run falls back to `.env` config values.

**Run statuses:** `queued` → `running` → `completed` / `failed` / `stopped`

---

## Web UI

Access at `http://127.0.0.1:9101/`

**Capabilities:**
- View all datasets in a list
- Edit dataset JSON directly in-browser
- Create new datasets
- Switch the active environment from the sidebar (persisted in localStorage)
- Start a run with mode selection (Dataset or Agent)
- Select agent persona and max turns (Agent Mode)
- Apply tag filters before running
- View live run status with turn counter (Agent Mode)
- Browse run history — each card shows environment badge, pass rate, AI eval verdict
- Drill into any run to see per-case results, latency, evaluation checks, and LLM judge reasoning
- Agent Mode runs display as a chat conversation thread
- Manage environments: create, edit, delete, set active

---

## Configuration

All configuration is via environment variables (`.env` file). Environment-specific values (webhook URL, credentials) can now be managed per-environment from the UI and will override these defaults at run time.

| Variable | Default | Description |
|---|---|---|
| `MONGO_URI` | *(required)* | MongoDB connection string |
| `MONGO_DB` | `prodoc` | MongoDB database name |
| `WHATSAPP_WEBHOOK_BASE` | `http://127.0.0.1:8001/api/whatsapp/meta/webhook` | Fallback webhook URL (overridden by active environment) |
| `AI_TEST_ADMIN_ID` | `` | Fallback MongoDB admin ObjectId |
| `AI_TEST_USER_ID` | `` | Fallback MongoDB user ObjectId |
| `AI_TEST_USER_NAME` | `` | Fallback contact name for test messages |
| `AI_TEST_PHONE_NUMBER` | `` | Fallback fixed phone number |
| `AI_TEST_PHONE_NUMBER_ID` | `` | Fallback WhatsApp phone number ID |
| `AI_TEST_DISPLAY_PHONE_NUMBER` | `` | Fallback WhatsApp display phone number |
| `AI_TEST_POLL_TIMEOUT_SECONDS` | `45` | Max seconds to wait for bot response per case |
| `AI_TEST_POLL_INTERVAL_MS` | `1500` | Polling interval in milliseconds |
| `AI_TEST_AGENT_MAX_TURNS` | `5` | Default max turns in Agent Mode |
| `AI_TEST_ENABLE_ANALYTICS` | `false` | Set to `true` to enable post-run AI analytics |
| `OPENAI_API_KEY` | `` | Required for Agent Mode and LLM judge |
| `OPENAI_MODEL` | `gpt-4o` | OpenAI model used for all AI features |
| `AI_TEST_DATASETS_DIR` | `./datasets` | Path to datasets directory |
| `AI_TEST_RUNS_DIR` | `./runs` | Path to runs directory |
| `AI_TEST_STATIC_DIR` | `./static` | Path to static files directory |

> **Tip:** For multi-environment workflows, set only `MONGO_URI` and `OPENAI_API_KEY` in `.env`. Configure webhook URLs and credentials per-environment from the Environments page in the UI.

---

## Setup & Run

**1. Clone and enter the project:**
```bash
cd ai_test
```

**2. Create and activate virtual environment:**
```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux/Mac
```

**3. Install dependencies:**
```bash
pip install -r requirements.txt
```

**4. Configure environment:**
```bash
cp .env.example .env
# Edit .env with your MongoDB URI and OpenAI key
# Webhook URLs and credentials can be configured per-environment from the UI
```

**5. Start the server:**
```bash
uvicorn app.main:app --reload --port 9101
```

**6. Open the UI:**
```
http://127.0.0.1:9101/
```

**7. Configure environments (first-time setup):**
- Go to `#/environments` or click the env badge in the sidebar
- Edit the Dev / QA / Prod entries with the correct webhook URLs and credentials for each environment
- Select the active environment from the sidebar before starting runs

---

## Directory Structure

```
ai_test/
├── app/
│   ├── main.py          # FastAPI app, routes, run lifecycle management
│   ├── runner.py        # Core execution: webhook POST, MongoDB polling, evaluation
│   ├── env_storage.py   # Environment CRUD (read/write environments/*.json)
│   ├── ai_chat.py       # OpenAI-powered persona message generation (Agent Mode)
│   ├── evaluator.py     # LLM-as-judge evaluation via OpenAI
│   ├── analytics.py     # Post-run AI analytics via OpenAI
│   ├── config.py        # Environment variable configuration
│   ├── db.py            # MongoDB async client (Motor)
│   ├── storage.py       # Dataset and run file persistence (JSON)
│   └── utils.py         # WhatsApp payload building and manipulation
├── datasets/
│   ├── agents/          # Agent-specific dataset JSON files
│   ├── golden/          # Golden dataset files
│   └── mixed/           # Mixed dataset files
├── environments/        # Named environment configs (auto-created on first run)
│   ├── dev.json
│   ├── qa.json
│   └── prod.json
├── runs/                # Run results saved as run-<uuid>.json
├── static/
│   ├── index.html       # Web UI shell (sidebar, page views)
│   ├── env.js           # Active environment state (localStorage)
│   ├── app.js           # Sidebar env switcher logic
│   ├── api.js           # API client (fetch wrappers)
│   ├── router.js        # Hash-based client-side router
│   ├── report.js        # Run report renderer (dataset table + agent chat thread)
│   ├── styles.css       # UI styles (design tokens + component styles)
│   └── pages/
│       ├── dashboard.js
│       ├── datasets.js
│       ├── run.js
│       ├── history.js
│       └── environments.js
├── .env                 # Environment variables (not committed)
├── .env.example         # Environment variable template
└── requirements.txt     # Python dependencies
```

# AI Automation Runner

This service runs dataset-driven automation against the WhatsApp webhook and
records results in JSON files.

## Setup

- Set env vars:
  - `MONGO_URI`
  - `MONGO_DB`
  - `WHATSAPP_WEBHOOK_BASE` (default: `your-whatsapp-webhook`)
  - `AI_TEST_POLL_TIMEOUT_SECONDS`
  - `AI_TEST_POLL_INTERVAL_MS`
  - `OPENAI_API_KEY` (optional)
  - `OPENAI_MODEL` (default: `gpt-4o`)

- Install dependencies:
  - `pip install -r requirements.txt`

- Run the API:
  - `uvicorn app.main:app --reload --port 9101`

## UI

Open `http://127.0.0.1:9101/` and use:

- Dataset list
- Dataset editor (JSON)
- Run automation and view results

## Data Layout

- `datasets/` for agent-wise and mixed JSON datasets
- `runs/` for run results (JSON)

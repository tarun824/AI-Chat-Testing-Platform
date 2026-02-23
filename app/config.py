import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()
BASE_DIR = Path(__file__).resolve().parents[1]

DATASETS_DIR = Path(os.getenv("AI_TEST_DATASETS_DIR", BASE_DIR / "datasets"))
RUNS_DIR = Path(os.getenv("AI_TEST_RUNS_DIR", BASE_DIR / "runs"))
STATIC_DIR = Path(os.getenv("AI_TEST_STATIC_DIR", BASE_DIR / "static"))

MONGO_URI = os.getenv("MONGO_URI", "")
MONGO_DB = os.getenv("MONGO_DB", "prodoc")

WHATSAPP_WEBHOOK_BASE = os.getenv(
    "WHATSAPP_WEBHOOK_BASE",
    "http://127.0.0.1:8001/api/whatsapp/meta/webhook",
)

DEFAULT_ADMIN_ID = os.getenv("AI_TEST_ADMIN_ID", "")
DEFAULT_USER_ID = os.getenv("AI_TEST_USER_ID", "")
DEFAULT_USER_NAME = os.getenv("AI_TEST_USER_NAME", "")
DEFAULT_PHONE_NUMBER = os.getenv("AI_TEST_PHONE_NUMBER", "")
DEFAULT_PHONE_NUMBER_ID = os.getenv("AI_TEST_PHONE_NUMBER_ID", "")
DEFAULT_DISPLAY_PHONE_NUMBER = os.getenv("AI_TEST_DISPLAY_PHONE_NUMBER", "")

DEFAULT_AGENT_MAX_TURNS = int(os.getenv("AI_TEST_AGENT_MAX_TURNS", "5"))

DEFAULT_POLL_TIMEOUT_SECONDS = int(
    os.getenv("AI_TEST_POLL_TIMEOUT_SECONDS", "45")
)
DEFAULT_POLL_INTERVAL_MS = int(os.getenv("AI_TEST_POLL_INTERVAL_MS", "1500"))

ENABLE_ANALYTICS = os.getenv("AI_TEST_ENABLE_ANALYTICS", "false").lower() == "true"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")

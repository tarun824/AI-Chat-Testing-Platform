import json
from datetime import datetime
from typing import Any, Dict, Optional

import httpx

from app.config import OPENAI_API_KEY, OPENAI_MODEL
from bson import ObjectId


def _json_default(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, ObjectId):
        return str(value)
    return str(value)


async def run_analytics(run_payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not OPENAI_API_KEY:
        return None

    prompt = {
        "role": "user",
        "content": (
            "Analyze this automation run. Return JSON with:\n"
            "summary, failures, regressions, suggestions.\n\n"
            f"RUN:\n{json.dumps(run_payload, ensure_ascii=True, default=_json_default)}"
        ),
    }

    body = {
        "model": OPENAI_MODEL,
        "messages": [prompt],
        "response_format": {"type": "json_object"},
        "temperature": 0,
    }

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=body,
        )
        response.raise_for_status()
        data = response.json()

    try:
        content = data["choices"][0]["message"]["content"]
        return json.loads(content)
    except Exception:
        return {"raw": data}

import json
import logging
from typing import Any, Dict

import httpx

from app.config import OPENAI_API_KEY, OPENAI_MODEL

logger = logging.getLogger("ai_test.evaluator")

_SYSTEM_PROMPT = (
    "You are a strict evaluator of chatbot responses. "
    "You will be given a user message, the bot's response, and an evaluation question. "
    "Think step by step first, then return JSON with exactly two fields: "
    '{"pass": true/false, "reason": "brief explanation"}. '
    "A pass means the bot clearly and correctly addressed the question. "
    "Do not be lenient — partial or vague answers are a fail."
)


async def llm_judge(
    user_message: str,
    bot_response: str,
    rubric: str,
) -> Dict[str, Any]:
    """Use OpenAI to semantically evaluate whether bot_response satisfies the rubric."""
    if not OPENAI_API_KEY:
        return {"pass": None, "reason": "no_openai_key", "skipped": True}

    if not bot_response or not bot_response.strip():
        return {"pass": False, "reason": "bot_response_empty", "skipped": False}

    user_prompt = (
        f"User message: {user_message}\n\n"
        f"Bot response: {bot_response}\n\n"
        f"Evaluation question: {rubric}\n\n"
        "Think step by step, then return JSON with 'pass' (boolean) and 'reason' (one sentence)."
    )

    payload = {
        "model": OPENAI_MODEL,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0,
    }

    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()

        content = data["choices"][0]["message"]["content"]
        result = json.loads(content)
        logger.info(
            "llm_judge.result rubric=%s pass=%s reason=%s",
            rubric[:60],
            result.get("pass"),
            result.get("reason", "")[:80],
        )
        return {
            "pass": bool(result.get("pass", False)),
            "reason": result.get("reason", ""),
            "skipped": False,
        }
    except Exception as exc:
        logger.exception("llm_judge.failed error=%s", exc)
        return {"pass": None, "reason": f"judge_error: {exc}", "skipped": True}

import json
import logging
from typing import Any, Dict, Optional

import httpx

from app.config import OPENAI_API_KEY, OPENAI_MODEL

logger = logging.getLogger("ai_test.auto_eval")


async def auto_evaluate_run(run_record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    After an agent run completes, send the full conversation to OpenAI and get back
    per-turn evaluation + an overall verdict. No manual rubric needed.
    Returns None if OpenAI is unavailable or there are no cases.
    """
    if not OPENAI_API_KEY:
        return None

    cases = run_record.get("cases", [])
    if not cases:
        return None

    convo_lines = []
    for c in cases:
        user_msg = c.get("user_message") or c.get("case_id", "")
        bot_msg = (c.get("actual") or {}).get("bot_message", "") or c.get("error", "no response")
        turn = c.get("turn", "?")
        convo_lines.append(f"Turn {turn}\nUser: {user_msg}\nBot: {bot_msg}")

    system_prompt_used = run_record.get("custom_system_prompt", "")
    agent = run_record.get("agent", "")
    context = system_prompt_used or f"Agent persona: {agent}"

    prompt = (
        f"You are evaluating a QA test run for an AI chatbot.\n"
        f"Test instruction / persona used: {context}\n\n"
        f"Full conversation:\n" + "\n\n".join(convo_lines) + "\n\n"
        "Evaluate how well the bot performed against the test instruction.\n"
        "Return JSON with exactly this structure:\n"
        "{\n"
        '  "overall_verdict": "pass" | "fail",\n'
        '  "overall_reason": "one or two sentences summarising the result",\n'
        '  "turns": [\n'
        '    {"turn": 1, "pass": true, "reason": "brief explanation"},\n'
        '    ...\n'
        '  ]\n'
        "}\n\n"
        "Be strict. If the bot gave wrong info, ignored the user, timed out, or broke the expected flow — mark as fail."
    )

    body = {
        "model": OPENAI_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {"type": "json_object"},
        "temperature": 0,
    }
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=body,
            )
            r.raise_for_status()
            content = r.json()["choices"][0]["message"]["content"]
            result = json.loads(content)
            logger.info(
                "auto_eval.done run_id=%s verdict=%s",
                run_record.get("run_id"),
                result.get("overall_verdict"),
            )
            return result
    except Exception as exc:
        logger.exception("auto_eval.failed run_id=%s error=%s", run_record.get("run_id"), exc)
        return None

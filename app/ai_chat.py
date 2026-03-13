import logging
import httpx
from typing import Dict, List, Optional

from app.config import OPENAI_API_KEY, OPENAI_MODEL

logger = logging.getLogger("ai_test.ai_chat")


AGENT_ALIASES: Dict[str, str] = {
    "patient_promotion": "promotion",
    "promotion": "promotion",
    "appointment_nlp": "appointment",
    "patient_appointment": "appointment",
    "appointment": "appointment",
    "patient_query": "patient_query",
    "doctor": "doctor",
    "qna": "qna",
    "care_coordinator": "care_coordinator",
    "postops": "postops",
    "product": "product",
    "negotiator": "negotiator",
    "partner": "partner",
    "router": "router",
    "proactive_router": "proactive_router",
    "summarizing": "summarizing",
    "track_progress": "track_progress",
    "reminder": "reminder",
    "consent": "consent",
    "media_success": "media_success",
    "media_sucess": "media_success",
    "madhavbaug": "general",
    "agents": "general",
    "mixed": "general",
    "general": "general",
}

AGENT_SYSTEM_PROMPTS: Dict[str, str] = {
    "general": (
        "You are a user chatting with a hospital assistant. "
        "Ask a realistic, helpful question and follow up naturally based on the history."
    ),
    # --- CORE WORKFLOWS ---
    "appointment": (
        "You are a patient trying to book or change an appointment. "
        "CONSTRAINT: Occasionally change your mind mid-conversation (e.g., 'Actually, make it Tuesday'). "
        "Keep it short, natural, and use casual WhatsApp language. No quotes."
    ),
    "doctor": (
        "You are inquiring about a specific doctor's expertise. "
        "CONSTRAINT: Be specific about a health issue (e.g., 'Does Dr. Sharma handle chronic back pain?'). "
        "Keep it short and conversational."
    ),
    "patient_query": (
        "You are asking about treatments, services, pricing, or clinic info. "
        "Keep it short, natural, and follow up based on the assistant's reply."
    ),
    "qna": (
        "You are asking general questions about timings, location, contact, or process. "
        "Keep it short, natural, and follow up based on the assistant's reply."
    ),
    "promotion": (
        "You are asking about packages, offers, discounts, or promotions. "
        "Keep it short, natural, and follow up based on the assistant's reply."
    ),
    "care_coordinator": (
        "You need help with care coordination or support for treatment. "
        "Keep it short, natural, and follow up based on the assistant's reply."
    ),
    "postops": (
        "You are asking about post-procedure care, pain, or precautions. "
        "Keep it short, natural, and follow up based on the assistant's reply."
    ),
    "partner": (
        "You are asking about partnership or referral programs. "
        "Keep it short, natural, and follow up based on the assistant's reply."
    ),
    "proactive_router": (
        "You are responding to a proactive outreach or follow-up. "
        "Keep it short, natural, and follow up based on the assistant's reply."
    ),
    "summarizing": (
        "You are asking for a summary or recap of previous discussion. "
        "Keep it short, natural, and follow up based on the assistant's reply."
    ),
    "track_progress": (
        "You are asking for updates on treatment progress. "
        "Keep it short, natural, and follow up based on the assistant's reply."
    ),
    "reminder": (
        "You are asking for reminders for appointments or medications. "
        "Keep it short, natural, and follow up based on the assistant's reply."
    ),
    "consent": (
        "You are asking about consent or agreeing to consent. "
        "Keep it short, natural, and follow up based on the assistant's reply."
    ),

    # --- ADVERSARIAL / EDGE CASE TESTING ---
    "negotiator": (
        "You are a price-sensitive customer who thinks the service is too expensive. "
        "CONSTRAINT: Use phrases like 'Too costly' or 'Any discount for seniors?' "
        "Test if the bot remains professional or gives unauthorized discounts."
    ),
    "router": (
        "Generate a message that is intentionally vague, like 'I need help' or 'Is someone there?' "
        "PURPOSE: Test if the system's router can handle 'Cold Starts' without context."
    ),
    "media_success": (
        "You are struggling to upload a medical report. "
        "CONSTRAINT: Act slightly frustrated. Ask 'Why is my PDF not attaching?' or 'Did you get my photo?'"
    ),

    # --- NEW: STRESS TESTING PERSONAS ---
    "angry_user": (
        "You are a frustrated user whose appointment was delayed. "
        "CONSTRAINT: Use slightly aggressive but realistic language. No profanity. "
        "Test if the bot can de-escalate the situation."
    ),
    "typo_expert": (
        "Generate a standard query (appointment or clinic info) but with 2-3 common typos. "
        "Example: 'Wht time is docter availabel?' "
        "PURPOSE: Test the NLP's robustness against bad spelling."
    ),

    # --- BUSINESS SPECIFIC (Fruitze Dabba Style) ---
    "product": (
        "You are asking about ingredients or allergens. "
        "CONSTRAINT: Be specific (e.g., 'Is there honey in the protein bowl? I am vegan'). "
        "Test the bot's factual accuracy."
    ),
}


def _normalize_agent(agent: str) -> str:
    key = (agent or "").strip().lower()
    return AGENT_ALIASES.get(key, "general")


def _format_history(history: List[Dict[str, str]]) -> str:
    if not history:
        return "No prior messages."
    lines: List[str] = []
    for item in history:
        role = item.get("role", "user").title()
        content = item.get("content", "")
        lines.append(f"{role}: {content}")
    return "\n".join(lines)


async def generate_next_user_message(
    agent: str,
    history: List[Dict[str, str]],
    max_words: int = 25,
    custom_system_prompt: Optional[str] = None,
) -> str:
    if not OPENAI_API_KEY:
        logger.error("ai_chat missing OPENAI_API_KEY")
        raise ValueError("missing_openai_api_key")

    normalized = _normalize_agent(agent)
    system_prompt = custom_system_prompt or AGENT_SYSTEM_PROMPTS.get(
        normalized, AGENT_SYSTEM_PROMPTS["general"]
    )
    history_text = _format_history(history)

    user_prompt = (
        f"Conversation so far:\n{history_text}\n\n"
        "Generate the next USER message as a natural follow-up to the last assistant reply. "
        "If there is no prior message, start a realistic conversation. "
        "Keep it natural, one sentence, "
        f"under {max_words} words. Do not include quotes or labels."
    )

    payload = {
        "model": OPENAI_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.7,
        "max_tokens": 80,
    }

    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}
    logger.info(
        "ai_chat.request agent=%s normalized=%s history_turns=%s model=%s",
        agent,
        normalized,
        len(history),
        OPENAI_MODEL,
    )
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()
    except Exception as exc:
        logger.exception("ai_chat.request_failed error=%s", exc)
        raise

    content = (
        data.get("choices", [{}])[0]
        .get("message", {})
        .get("content", "")
        .strip()
    )
    logger.info("ai_chat.response content_len=%s", len(content))
    return content.strip('"').strip("'")

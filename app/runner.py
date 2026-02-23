import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
from bson import ObjectId

from app.ai_chat import generate_next_user_message
from app.analytics import run_analytics
from app.config import (
    DEFAULT_ADMIN_ID,
    DEFAULT_DISPLAY_PHONE_NUMBER,
    DEFAULT_PHONE_NUMBER_ID,
    DEFAULT_POLL_INTERVAL_MS,
    DEFAULT_POLL_TIMEOUT_SECONDS,
    DEFAULT_PHONE_NUMBER,
    DEFAULT_USER_ID,
    DEFAULT_USER_NAME,
    ENABLE_ANALYTICS,
    WHATSAPP_WEBHOOK_BASE,
)
from app.db import get_collection, to_object_id
from app.storage import create_run, update_run
from app.utils import (
    apply_unique_message_and_contact,
    build_text_webhook_payload,
    extract_contact_phone,
    normalize_payload,
    set_phone_metadata,
)

logger = logging.getLogger("ai_test.runner")


async def _post_webhook(userid: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    url = f"{WHATSAPP_WEBHOOK_BASE}/{userid}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        return {"status_code": response.status_code, "data": response.json()}


class RunStopped(Exception):
    pass


def _raise_if_stopped(stop_event: Optional[asyncio.Event]) -> None:
    if stop_event and stop_event.is_set():
        raise RunStopped()


async def _wait_for_contact_id(
    admin_id: str,
    phone: str,
    timeout_sec: int,
    stop_event: Optional[asyncio.Event] = None,
) -> Optional[str]:
    phone_book = get_collection("phonebooks")
    start = datetime.now(timezone.utc)
    while (datetime.now(timezone.utc) - start).total_seconds() < timeout_sec:
        _raise_if_stopped(stop_event)
        contact = await phone_book.find_one(
            {"admin": to_object_id(admin_id), "phone": phone}
        )
        if contact and contact.get("_id"):
            return str(contact["_id"])
        await asyncio.sleep(0.5)
    return None


def _find_latest_bot_message(convo: Dict[str, Any], since: datetime) -> Optional[Dict[str, Any]]:
    chats = convo.get("chats", []) or []
    latest = None
    for chat in chats:
        try:
            if chat.get("type") != "bot":
                continue
            ts = chat.get("timestamp")
            if not ts:
                continue
            if isinstance(ts, str):
                ts = datetime.fromisoformat(ts)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if ts < since:
                continue
            latest = chat
        except Exception:
            continue
    return latest


async def _wait_for_bot_response(
    admin_id: str,
    contact_id: str,
    started_at: datetime,
    timeout_sec: int,
    poll_ms: int,
    stop_event: Optional[asyncio.Event] = None,
) -> Dict[str, Any]:
    conversation_collection = get_collection("conversations")
    start = datetime.now(timezone.utc)
    last_convo = None
    while (datetime.now(timezone.utc) - start).total_seconds() < timeout_sec:
        _raise_if_stopped(stop_event)
        convo = await conversation_collection.find_one(
            {
                "admin": to_object_id(admin_id),
                "contact_id": to_object_id(contact_id),
            }
        )
        if convo:
            last_convo = convo
            bot_message = _find_latest_bot_message(convo, started_at)
            if bot_message:
                return {
                    "conversation_id": str(convo.get("_id")),
                    "bot_message": bot_message.get("msg", ""),
                    "bot_message_raw": bot_message,
                }
        await asyncio.sleep(poll_ms / 1000)
    return {
        "conversation_id": str(last_convo.get("_id")) if last_convo else None,
        "bot_message": "",
        "bot_message_raw": None,
        "error": "timeout_waiting_for_bot",
    }


def _evaluate_case(expected: Dict[str, Any], actual: Dict[str, Any]) -> Dict[str, Any]:
    result = {"pass": True, "checks": []}
    bot_message = (actual.get("bot_message") or "").lower()
    must_include = expected.get("must_include", []) or []
    must_not_include = expected.get("must_not_include", []) or []

    for text in must_include:
        ok = text.lower() in bot_message
        result["checks"].append({"type": "must_include", "value": text, "pass": ok})
        if not ok:
            result["pass"] = False

    for text in must_not_include:
        ok = text.lower() not in bot_message
        result["checks"].append({"type": "must_not_include", "value": text, "pass": ok})
        if not ok:
            result["pass"] = False

    return result


def _resolve_case_tags(case: Dict[str, Any]) -> List[str]:
    return case.get("tags", []) or []


def _case_matches_tags(case: Dict[str, Any], tag_filter: List[str]) -> bool:
    if not tag_filter:
        return True
    case_tags = set(_resolve_case_tags(case))
    return all(tag in case_tags for tag in tag_filter)


DEFAULT_CASE_LIBRARY: Dict[str, List[Dict[str, Any]]] = {
    "appointment": [
        {
            "id": "appointment_book",
            "tags": ["appointment"],
            "text": "I want to book an appointment for next week.",
        },
        {
            "id": "appointment_reschedule",
            "tags": ["appointment"],
            "text": "Please reschedule my appointment to another day.",
        },
        {
            "id": "appointment_cancel",
            "tags": ["appointment"],
            "text": "Cancel my appointment, please.",
        },
    ],
    "appointment_nlp": [
        {
            "id": "appointment_nlp_monday",
            "tags": ["appointment_nlp", "appointment"],
            "text": "Book me for Monday morning if available.",
        },
        {
            "id": "appointment_nlp_followup",
            "tags": ["appointment_nlp", "appointment"],
            "text": "Schedule a follow-up appointment next week.",
        },
        {
            "id": "appointment_nlp_slots",
            "tags": ["appointment_nlp", "appointment"],
            "text": "What slots are open for consultation?",
        },
    ],
    "patient_appointment": [
        {
            "id": "patient_appointment_book",
            "tags": ["patient_appointment", "appointment"],
            "text": "I need an appointment with a doctor.",
        },
        {
            "id": "patient_appointment_change",
            "tags": ["patient_appointment", "appointment"],
            "text": "Can I change my appointment time?",
        },
        {
            "id": "patient_appointment_availability",
            "tags": ["patient_appointment", "appointment"],
            "text": "Is there any availability this week?",
        },
    ],
    "patient_promotion": [
        {
            "id": "patient_promotion_offers",
            "tags": ["patient_promotion", "promotion"],
            "text": "Do you have any IVF offers right now?",
        },
        {
            "id": "patient_promotion_packages",
            "tags": ["patient_promotion", "promotion"],
            "text": "Share your packages and pricing.",
        },
        {
            "id": "patient_promotion_discount",
            "tags": ["patient_promotion", "promotion"],
            "text": "Any discounts available this month?",
        },
    ],
    "patient_query": [
        {
            "id": "patient_query_fees",
            "tags": ["patient_query"],
            "text": "What are your consultation charges?",
        },
        {
            "id": "patient_query_services",
            "tags": ["patient_query"],
            "text": "What treatments do you provide?",
        },
        {
            "id": "patient_query_location",
            "tags": ["patient_query"],
            "text": "Where is your clinic located?",
        },
    ],
    "doctor": [
        {
            "id": "doctor_info",
            "tags": ["doctor"],
            "text": "Can you share details about your doctors?",
        },
        {
            "id": "doctor_experience",
            "tags": ["doctor"],
            "text": "How experienced are your doctors?",
        },
        {
            "id": "doctor_availability",
            "tags": ["doctor"],
            "text": "Which doctor is available this week?",
        },
    ],
    "qna": [
        {
            "id": "qna_timings",
            "tags": ["qna"],
            "text": "What are your clinic timings today?",
        },
        {
            "id": "qna_working_days",
            "tags": ["qna"],
            "text": "Are you open on Sundays?",
        },
        {
            "id": "qna_contact",
            "tags": ["qna"],
            "text": "How can I contact your clinic?",
        },
    ],
    "care_coordinator": [
        {
            "id": "care_coordinator_help",
            "tags": ["care_coordinator"],
            "text": "I need help coordinating my treatment plan.",
        },
        {
            "id": "care_coordinator_assign",
            "tags": ["care_coordinator"],
            "text": "Can you assign a care coordinator for me?",
        },
        {
            "id": "care_coordinator_followup",
            "tags": ["care_coordinator"],
            "text": "I need follow-up support for my treatment.",
        },
    ],
    "postops": [
        {
            "id": "postops_pain",
            "tags": ["postops"],
            "text": "I had a procedure yesterday and I am feeling pain.",
        },
        {
            "id": "postops_medication",
            "tags": ["postops"],
            "text": "What medicines should I take after surgery?",
        },
        {
            "id": "postops_precautions",
            "tags": ["postops"],
            "text": "Any precautions I should follow after the procedure?",
        },
    ],
    "product": [
        {
            "id": "product_pricing",
            "tags": ["product"],
            "text": "Share product pricing and details.",
        },
        {
            "id": "product_package",
            "tags": ["product"],
            "text": "Tell me about your IVF package.",
        },
        {
            "id": "product_brochure",
            "tags": ["product"],
            "text": "Do you have a brochure for your services?",
        },
    ],
    "negotiator": [
        {
            "id": "negotiator_price",
            "tags": ["negotiator"],
            "text": "Can you provide a better price for the package?",
        },
        {
            "id": "negotiator_discount",
            "tags": ["negotiator"],
            "text": "Is there any flexibility on pricing?",
        },
        {
            "id": "negotiator_offer",
            "tags": ["negotiator"],
            "text": "Match a lower quote I received elsewhere.",
        },
    ],
    "partner": [
        {
            "id": "partner_query",
            "tags": ["partner"],
            "text": "I want to partner with your clinic. How do we proceed?",
        },
        {
            "id": "partner_referral",
            "tags": ["partner"],
            "text": "Do you have a referral or partnership program?",
        },
        {
            "id": "partner_corporate",
            "tags": ["partner"],
            "text": "Interested in a corporate tie-up. Please share details.",
        },
    ],
    "madhavbaug": [
        {
            "id": "madhavbaug_about",
            "tags": ["madhavbaug"],
            "text": "Tell me about the Madhavbaug program.",
        },
        {
            "id": "madhavbaug_eligibility",
            "tags": ["madhavbaug"],
            "text": "Who is eligible for Madhavbaug treatment?",
        },
        {
            "id": "madhavbaug_pricing",
            "tags": ["madhavbaug"],
            "text": "What is the pricing for Madhavbaug services?",
        },
    ],
    "router": [
        {
            "id": "router_general",
            "tags": ["router"],
            "text": "Hello, I need help with my treatment.",
        },
        {
            "id": "router_confused",
            "tags": ["router"],
            "text": "I am not sure what I need. Can you help?",
        },
        {
            "id": "router_services",
            "tags": ["router"],
            "text": "Can you guide me on the next steps?",
        },
    ],
    "proactive_router": [
        {
            "id": "proactive_router_followup",
            "tags": ["proactive_router"],
            "text": "I missed your call. Please follow up.",
        },
        {
            "id": "proactive_router_offer",
            "tags": ["proactive_router", "promotion"],
            "text": "Are there any special offers for me?",
        },
        {
            "id": "proactive_router_schedule",
            "tags": ["proactive_router", "appointment"],
            "text": "Can you schedule a quick call with me?",
        },
    ],
    "summarizing": [
        {
            "id": "summarizing_chat",
            "tags": ["summarizing"],
            "text": "Please summarize my recent conversation.",
        },
        {
            "id": "summarizing_treatment",
            "tags": ["summarizing"],
            "text": "Summarize my treatment plan details.",
        },
        {
            "id": "summarizing_next_steps",
            "tags": ["summarizing"],
            "text": "Summarize the next steps for me.",
        },
    ],
    "track_progress": [
        {
            "id": "track_progress_status",
            "tags": ["track_progress"],
            "text": "Can you tell me my treatment progress status?",
        },
        {
            "id": "track_progress_update",
            "tags": ["track_progress"],
            "text": "Any update on my progress?",
        },
        {
            "id": "track_progress_report",
            "tags": ["track_progress"],
            "text": "Share my progress report.",
        },
    ],
    "reminder": [
        {
            "id": "reminder_request",
            "tags": ["reminder"],
            "text": "Please remind me about my appointment tomorrow.",
        },
        {
            "id": "reminder_medicine",
            "tags": ["reminder"],
            "text": "Set a reminder for my medicine schedule.",
        },
        {
            "id": "reminder_followup",
            "tags": ["reminder"],
            "text": "Remind me for my follow-up visit.",
        },
    ],
    "media_success": [
        {
            "id": "media_success_report",
            "tags": ["media_success"],
            "text": "I have uploaded my report.",
        },
        {
            "id": "media_success_document",
            "tags": ["media_success"],
            "text": "Please confirm if my document is received.",
        },
        {
            "id": "media_success_image",
            "tags": ["media_success"],
            "text": "I sent an image. Did you get it?",
        },
    ],
    "media_sucess": [
        {
            "id": "media_sucess_report",
            "tags": ["media_sucess"],
            "text": "I uploaded my lab report.",
        },
        {
            "id": "media_sucess_document",
            "tags": ["media_sucess"],
            "text": "Please check my uploaded files.",
        },
        {
            "id": "media_sucess_image",
            "tags": ["media_sucess"],
            "text": "I shared a document just now.",
        },
    ],
    "consent": [
        {
            "id": "consent_yes",
            "tags": ["consent"],
            "text": "Yes, I consent to the terms.",
        },
        {
            "id": "consent_info",
            "tags": ["consent"],
            "text": "Please explain the consent process.",
        },
        {
            "id": "consent_confirm",
            "tags": ["consent"],
            "text": "I agree to proceed.",
        },
    ],
    "agents": [
        {
            "id": "agents_appointment",
            "tags": ["agents", "appointment"],
            "text": "I want to book an appointment.",
        },
        {
            "id": "agents_query",
            "tags": ["agents", "patient_query"],
            "text": "Tell me about your services and pricing.",
        },
        {
            "id": "agents_promotion",
            "tags": ["agents", "promotion"],
            "text": "Do you have any offers?",
        },
    ],
    "mixed": [
        {
            "id": "mixed_query",
            "tags": ["mixed", "patient_query"],
            "text": "What are the consultation fees?",
        },
        {
            "id": "mixed_appointment",
            "tags": ["mixed", "appointment"],
            "text": "Book an appointment for next week.",
        },
        {
            "id": "mixed_promotion",
            "tags": ["mixed", "promotion"],
            "text": "Share your latest packages or offers.",
        },
    ],
    "default": [
        {
            "id": "default_ping",
            "tags": ["auto"],
            "text": "Hello, I need help.",
        },
        {
            "id": "default_info",
            "tags": ["auto"],
            "text": "Please share more information.",
        },
        {
            "id": "default_support",
            "tags": ["auto"],
            "text": "I want to talk to support.",
        },
    ],
}


def _default_case_text(dataset: Dict[str, Any], defaults: Dict[str, Any]) -> str:
    return defaults.get("default_text") or f"Automation ping for {dataset.get('dataset_id', 'dataset')}"


def _build_default_cases(
    dataset: Dict[str, Any],
    tag_filter: Optional[List[str]],
) -> List[Dict[str, Any]]:
    defaults = dataset.get("defaults", {}) or {}
    dataset_id = dataset.get("dataset_id", "dataset")
    specs = DEFAULT_CASE_LIBRARY.get(dataset_id) or DEFAULT_CASE_LIBRARY["default"]
    cases: List[Dict[str, Any]] = []
    for spec in specs:
        tags = spec.get("tags", []) or []
        if dataset_id and dataset_id not in tags:
            tags = tags + [dataset_id]
        cases.append(
            {
                "id": spec.get("id"),
                "tags": tags,
                "webhook_payload": build_text_webhook_payload(
                    spec.get("text") or _default_case_text(dataset, defaults),
                    defaults.get("contact_name", "Automation User"),
                ),
                "expected": spec.get("expected", {}) or {},
            }
        )
    if tag_filter:
        return [case for case in cases if _case_matches_tags(case, tag_filter)]
    return cases


def _build_default_case(
    dataset: Dict[str, Any],
    tag_filter: Optional[List[str]],
) -> Dict[str, Any]:
    defaults = dataset.get("defaults", {}) or {}
    tags = tag_filter or ["auto"]
    return {
        "id": f"default_{dataset.get('dataset_id', 'dataset')}",
        "tags": tags,
        "webhook_payload": build_text_webhook_payload(
            _default_case_text(dataset, defaults),
            defaults.get("contact_name", "Automation User"),
        ),
        "expected": defaults.get("expected", {}) or {},
    }


async def _resolve_whatsapp_numbers(admin_id: str) -> Dict[str, str]:
    whatsapp_channels = get_collection("whatsappchannels")
    doc = await whatsapp_channels.find_one(
        {"created_by": to_object_id(admin_id), "type": "meta"}
    )
    if not doc:
        return {"phone_number_id": "", "display_phone_number": ""}
    return {
        "phone_number_id": doc.get("phoneNumberId", "") or doc.get("phone_number_id", ""),
        "display_phone_number": doc.get("displayPhoneNumber", "")
        or doc.get("display_phone_number", ""),
    }


async def _execute_case(
    dataset: Dict[str, Any],
    case: Dict[str, Any],
    run_id: str,
    stop_event: Optional[asyncio.Event] = None,
) -> Dict[str, Any]:
    _raise_if_stopped(stop_event)
    defaults = dataset.get("defaults", {}) or {}
    payload = case.get("webhook_payload") or {}
    if not payload:
        payload = build_text_webhook_payload(
            _default_case_text(dataset, defaults),
            defaults.get("contact_name", "Automation User"),
        )
    payload = normalize_payload(payload)

    userid = case.get("userid") or defaults.get("userid") or DEFAULT_USER_ID or ""
    admin_id = case.get("admin_id") or defaults.get("admin_id") or DEFAULT_ADMIN_ID or ""
    if not admin_id and userid:
        admin_id = userid
    if not userid and admin_id:
        userid = admin_id

    unique_contact = bool(defaults.get("unique_contact_per_case", True))
    contact_name = DEFAULT_USER_NAME or defaults.get("contact_name", "Automation User")
    country_code = defaults.get("country_code", "91")
    fixed_phone = DEFAULT_PHONE_NUMBER or ""

    message_id, contact_phone = apply_unique_message_and_contact(
        payload,
        unique_contact=unique_contact,
        contact_name=contact_name,
        country_code=country_code,
        fixed_phone=fixed_phone,
    )

    phone_number_id = (
        defaults.get("phone_number_id", "") or DEFAULT_PHONE_NUMBER_ID or ""
    )
    display_phone_number = (
        defaults.get("display_phone_number", "") or DEFAULT_DISPLAY_PHONE_NUMBER or ""
    )

    if admin_id and (not phone_number_id or not display_phone_number):
        resolved = await _resolve_whatsapp_numbers(admin_id)
        if not phone_number_id:
            phone_number_id = resolved.get("phone_number_id", "")
        if not display_phone_number:
            display_phone_number = resolved.get("display_phone_number", "")
    set_phone_metadata(payload, phone_number_id, display_phone_number)

    if not userid:
        return {
            "case_id": case.get("id"),
            "status": "failed",
            "error": "missing_userid",
        }
    if not admin_id:
        return {
            "case_id": case.get("id"),
            "status": "failed",
            "error": "missing_admin_id",
        }

    _raise_if_stopped(stop_event)
    started_at = datetime.now(timezone.utc)

    try:
        webhook_response = await _post_webhook(userid, payload)
    except Exception as exc:
        return {
            "case_id": case.get("id"),
            "status": "failed",
            "error": f"webhook_error: {exc}",
        }

    _raise_if_stopped(stop_event)
    poll_timeout = int(defaults.get("poll_timeout_sec", DEFAULT_POLL_TIMEOUT_SECONDS))
    poll_interval = int(defaults.get("poll_interval_ms", DEFAULT_POLL_INTERVAL_MS))

    contact_id = await _wait_for_contact_id(
        admin_id, contact_phone, poll_timeout, stop_event=stop_event
    )
    if not contact_id:
        return {
            "case_id": case.get("id"),
            "status": "failed",
            "message_id": message_id,
            "contact_phone": contact_phone,
            "error": "contact_not_found",
        }

    actual = await _wait_for_bot_response(
        admin_id=admin_id,
        contact_id=contact_id,
        started_at=started_at,
        timeout_sec=poll_timeout,
        poll_ms=poll_interval,
        stop_event=stop_event,
    )

    expected = case.get("expected", {}) or {}
    evaluation = _evaluate_case(expected, actual)

    return {
        "case_id": case.get("id"),
        "status": "completed" if evaluation["pass"] else "failed",
        "message_id": message_id,
        "contact_phone": contact_phone,
        "contact_id": contact_id,
        "webhook_response": webhook_response,
        "expected": expected,
        "actual": actual,
        "evaluation": evaluation,
    }


async def run_dataset_with_id(
    run_id: str,
    dataset: Dict[str, Any],
    tag_filter: Optional[List[str]] = None,
    stop_event: Optional[asyncio.Event] = None,
) -> Dict[str, Any]:
    tag_filter = tag_filter or []

    run_record = {
        "run_id": run_id,
        "dataset_id": dataset.get("dataset_id"),
        "status": "running",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "ended_at": "",
        "filters": {"tags": tag_filter},
        "cases": [],
    }

    update_run(run_id, run_record)

    cases = dataset.get("cases", []) or []
    if not cases:
        cases = _build_default_cases(dataset, tag_filter)

    try:
        for case in cases:
            if not _case_matches_tags(case, tag_filter):
                continue
            result = await _execute_case(
                dataset, case, run_id, stop_event=stop_event
            )
            run_record["cases"].append(result)
            update_run(run_id, run_record)
    except RunStopped:
        run_record["status"] = "stopped"
        run_record["ended_at"] = datetime.now(timezone.utc).isoformat()
        update_run(run_id, run_record)
        return run_record

    run_record["status"] = "completed"
    run_record["ended_at"] = datetime.now(timezone.utc).isoformat()

    update_run(run_id, run_record)
    print("ENABLE_ANALYTICS", ENABLE_ANALYTICS)

    if ENABLE_ANALYTICS:
        print("Enabling analytics for ENABLE_ANALYTICS", run_record)
        analytics = await run_analytics(run_record)
        if analytics is not None:
            run_record["analytics"] = analytics
            update_run(run_id, run_record)

    return run_record


async def run_agent_conversation_with_id(
    run_id: str,
    dataset: Dict[str, Any],
    agent: str,
    max_turns: int,
    stop_event: Optional[asyncio.Event] = None,
) -> Dict[str, Any]:
    logger.info(
        "agent_mode.start run_id=%s agent=%s max_turns=%s",
        run_id,
        agent,
        max_turns,
    )
    run_record = {
        "run_id": run_id,
        "dataset_id": dataset.get("dataset_id"),
        "status": "running",
        "mode": "agent",
        "agent": agent,
        "max_turns": max_turns,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "ended_at": "",
        "filters": {"tags": []},
        "cases": [],
    }
    update_run(run_id, run_record)

    history: List[Dict[str, str]] = []
    defaults = dataset.get("defaults", {}) or {}
    contact_name = DEFAULT_USER_NAME or defaults.get("contact_name", "Automation User")

    try:
        for turn in range(max_turns):
            _raise_if_stopped(stop_event)
            user_message = await generate_next_user_message(agent, history)
            logger.info(
                "agent_mode.turn run_id=%s turn=%s user_message=%s",
                run_id,
                turn + 1,
                user_message,
            )
            case = {
                "id": f"turn_{turn + 1}",
                "tags": [agent, "agent"],
                "webhook_payload": build_text_webhook_payload(
                    user_message, contact_name
                ),
                "expected": {},
            }
            result = await _execute_case(
                dataset, case, run_id, stop_event=stop_event
            )
            result["user_message"] = user_message
            result["turn"] = turn + 1
            run_record["cases"].append(result)
            update_run(run_id, run_record)

            bot_message = result.get("actual", {}).get("bot_message") or ""
            history.append({"role": "user", "content": user_message})
            history.append({"role": "assistant", "content": bot_message})
    except RunStopped:
        logger.info("agent_mode.stopped run_id=%s", run_id)
        run_record["status"] = "stopped"
        run_record["ended_at"] = datetime.now(timezone.utc).isoformat()
        update_run(run_id, run_record)
        return run_record
    except Exception as exc:
        logger.exception("agent_mode.failed run_id=%s error=%s", run_id, exc)
        run_record["status"] = "failed"
        run_record["ended_at"] = datetime.now(timezone.utc).isoformat()
        run_record["error"] = f"agent_mode_error: {exc}"
        update_run(run_id, run_record)
        return run_record

    logger.info("agent_mode.completed run_id=%s turns=%s", run_id, max_turns)
    run_record["status"] = "completed"
    run_record["ended_at"] = datetime.now(timezone.utc).isoformat()
    update_run(run_id, run_record)

    if ENABLE_ANALYTICS:
        logger.info("agent_mode.analytics_start run_id=%s", run_id)
        analytics = await run_analytics(run_record)
        if analytics is not None:
            run_record["analytics"] = analytics
            update_run(run_id, run_record)
            logger.info("agent_mode.analytics_done run_id=%s", run_id)
    return run_record


async def start_run(
    dataset: Dict[str, Any],
    tag_filter: Optional[List[str]] = None,
    mode: str = "dataset",
    agent: str = "",
    max_turns: int = 0,
) -> str:
    run_id = f"run-{uuid.uuid4().hex}"
    run_record = {
        "run_id": run_id,
        "dataset_id": dataset.get("dataset_id"),
        "status": "queued",
        "mode": mode,
        "agent": agent,
        "max_turns": max_turns,
        "started_at": "",
        "ended_at": "",
        "filters": {"tags": tag_filter or []},
        "cases": [],
    }
    create_run(run_id, run_record)
    return run_id

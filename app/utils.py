import copy
import json
import random
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Tuple


def deep_copy(value: Any) -> Any:
    return copy.deepcopy(value)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def now_unix() -> str:
    return str(int(time.time()))


def generate_message_id() -> str:
    return f"wamid.{uuid.uuid4().hex}"


def generate_phone_number(country_code: str = "91") -> str:
    digits = "".join(str(random.randint(0, 9)) for _ in range(10))
    return f"{country_code}{digits}"


def try_parse_json(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return value
    return value


def ensure_payload_shape(payload: Dict[str, Any]) -> Dict[str, Any]:
    if "entry" not in payload:
        payload["entry"] = []
    if not payload["entry"]:
        payload["entry"].append({})
    entry = payload["entry"][0]
    if "changes" not in entry:
        entry["changes"] = []
    if not entry["changes"]:
        entry["changes"].append({})
    change = entry["changes"][0]
    if "value" not in change:
        change["value"] = {}
    value = change["value"]
    if "messages" not in value:
        value["messages"] = []
    if not value["messages"]:
        value["messages"].append({})
    if "contacts" not in value:
        value["contacts"] = []
    if not value["contacts"]:
        value["contacts"].append({"profile": {}})
    if "metadata" not in value:
        value["metadata"] = {}
    return payload


def extract_contact_phone(payload: Dict[str, Any]) -> str:
    try:
        return payload["entry"][0]["changes"][0]["value"]["contacts"][0]["wa_id"]
    except Exception:
        return ""


def set_contact_phone(payload: Dict[str, Any], phone: str) -> None:
    value = payload["entry"][0]["changes"][0]["value"]
    value["contacts"][0]["wa_id"] = phone
    value["messages"][0]["from"] = phone


def set_contact_name(payload: Dict[str, Any], name: str) -> None:
    value = payload["entry"][0]["changes"][0]["value"]
    profile = value["contacts"][0].setdefault("profile", {})
    profile["name"] = name


def set_phone_metadata(payload: Dict[str, Any], phone_number_id: str, display_phone: str) -> None:
    metadata = payload["entry"][0]["changes"][0]["value"].setdefault("metadata", {})
    if phone_number_id:
        metadata["phone_number_id"] = phone_number_id
    if display_phone:
        metadata["display_phone_number"] = display_phone


def set_message_id(payload: Dict[str, Any], message_id: str) -> None:
    payload["entry"][0]["changes"][0]["value"]["messages"][0]["id"] = message_id


def set_message_timestamp(payload: Dict[str, Any], timestamp: str) -> None:
    payload["entry"][0]["changes"][0]["value"]["messages"][0]["timestamp"] = timestamp


def set_message_text(payload: Dict[str, Any], text: str) -> None:
    message = payload["entry"][0]["changes"][0]["value"]["messages"][0]
    text_block = message.setdefault("text", {})
    text_block["body"] = text
    message["type"] = "text"


def get_message_text(payload: Dict[str, Any]) -> str:
    try:
        return payload["entry"][0]["changes"][0]["value"]["messages"][0]["text"]["body"]
    except Exception:
        return ""


def normalize_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    normalized = deep_copy(payload)
    ensure_payload_shape(normalized)
    return normalized


def build_text_webhook_payload(text: str, contact_name: str) -> Dict[str, Any]:
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "automation",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {},
                            "contacts": [
                                {"profile": {"name": contact_name}, "wa_id": ""}
                            ],
                            "messages": [
                                {
                                    "from": "",
                                    "id": "",
                                    "timestamp": "",
                                    "text": {"body": text},
                                    "type": "text",
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }


def apply_unique_message_and_contact(
    payload: Dict[str, Any],
    unique_contact: bool,
    contact_name: str,
    country_code: str,
    fixed_phone: str = "",
) -> Tuple[str, str]:
    message_id = generate_message_id()
    set_message_id(payload, message_id)
    set_message_timestamp(payload, now_unix())

    if fixed_phone:
        phone = fixed_phone
        set_contact_phone(payload, phone)
    elif unique_contact or not extract_contact_phone(payload):
        phone = generate_phone_number(country_code=country_code)
        set_contact_phone(payload, phone)
    else:
        phone = extract_contact_phone(payload)

    if contact_name:
        set_contact_name(payload, contact_name)

    return message_id, phone

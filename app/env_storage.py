import json
from pathlib import Path
from typing import Any, Dict, List

from app.config import BASE_DIR

ENVIRONMENTS_DIR = Path(BASE_DIR) / "environments"

_SEEDS: List[Dict[str, Any]] = [
    {
        "env_id": "dev",
        "name": "Dev",
        "color": "slate",
        "webhook_base_url": "",
        "admin_id": "",
        "user_id": "",
        "phone_number": "",
        "phone_number_id": "",
        "display_phone_number": "",
        "contact_name": "Automation User",
        "country_code": "91",
    },
    {
        "env_id": "qa",
        "name": "QA",
        "color": "blue",
        "webhook_base_url": "",
        "admin_id": "",
        "user_id": "",
        "phone_number": "",
        "phone_number_id": "",
        "display_phone_number": "",
        "contact_name": "Automation User",
        "country_code": "91",
    },
    {
        "env_id": "prod",
        "name": "Prod",
        "color": "red",
        "webhook_base_url": "",
        "admin_id": "",
        "user_id": "",
        "phone_number": "",
        "phone_number_id": "",
        "display_phone_number": "",
        "contact_name": "Automation User",
        "country_code": "91",
    },
]


def ensure_environments_dir() -> None:
    ENVIRONMENTS_DIR.mkdir(parents=True, exist_ok=True)
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

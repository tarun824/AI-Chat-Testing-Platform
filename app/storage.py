import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from bson import ObjectId

from app.config import BASE_DIR, DATASETS_DIR, RUNS_DIR


def ensure_storage_dirs() -> None:
    DATASETS_DIR.mkdir(parents=True, exist_ok=True)
    RUNS_DIR.mkdir(parents=True, exist_ok=True)


def _load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _json_default(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, ObjectId):
        return str(value)
    return str(value)


def _save_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=True, default=_json_default)


def _dataset_search_dirs() -> List[Path]:
    fallback_dir = BASE_DIR / "datasets"
    if fallback_dir == DATASETS_DIR:
        return [DATASETS_DIR]
    return [DATASETS_DIR, fallback_dir]


def _relative_dataset_path(path: Path) -> str:
    for base_dir in _dataset_search_dirs():
        try:
            return str(path.relative_to(base_dir))
        except ValueError:
            continue
    return path.name


def list_dataset_files() -> List[Path]:
    ensure_storage_dirs()
    files: Dict[str, Path] = {}
    for base_dir in _dataset_search_dirs():
        if not base_dir.exists():
            continue
        for path in base_dir.rglob("*.json"):
            if path.is_file():
                files[str(path.resolve())] = path
    return [files[key] for key in sorted(files.keys())]


def list_datasets() -> List[Dict[str, Any]]:
    datasets = []
    for path in list_dataset_files():
        try:
            data = _load_json(path)
            dataset_id = data.get("dataset_id") or path.stem
            datasets.append(
                {
                    "dataset_id": dataset_id,
                    "name": data.get("name", ""),
                    "tags": data.get("tags", []),
                    "case_count": len(data.get("cases", []) or []),
                    "path": _relative_dataset_path(path),
                }
            )
        except Exception:
            continue
    return datasets


def find_dataset_path(dataset_id: str) -> Optional[Path]:
    for path in list_dataset_files():
        try:
            data = _load_json(path)
            if data.get("dataset_id") == dataset_id:
                return path
        except Exception:
            continue
    return None


def load_dataset(dataset_id: str) -> Dict[str, Any]:
    path = find_dataset_path(dataset_id)
    if not path:
        raise FileNotFoundError(f"Dataset not found: {dataset_id}")
    data = _load_json(path)
    data["_path"] = str(path)
    return data


def save_dataset(dataset_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    path = find_dataset_path(dataset_id)
    if not path:
        path = DATASETS_DIR / f"{dataset_id}.json"
    data["dataset_id"] = dataset_id
    _save_json(path, data)
    data["_path"] = str(path)
    return data


def create_run(run_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    ensure_storage_dirs()
    path = RUNS_DIR / f"{run_id}.json"
    _save_json(path, data)
    return data


def update_run(run_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    path = RUNS_DIR / f"{run_id}.json"
    _save_json(path, data)
    return data


def load_run(run_id: str) -> Dict[str, Any]:
    path = RUNS_DIR / f"{run_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"Run not found: {run_id}")
    try:
        return _load_json(path)
    except json.JSONDecodeError as exc:
        return {
            "run_id": run_id,
            "status": "failed",
            "error": "run_file_corrupt",
            "details": str(exc),
        }


def list_runs() -> List[Dict[str, Any]]:
    ensure_storage_dirs()
    runs = []
    for path in sorted(RUNS_DIR.glob("*.json")):
        try:
            data = _load_json(path)
            runs.append(
                {
                    "run_id": data.get("run_id", path.stem),
                    "dataset_id": data.get("dataset_id", ""),
                    "status": data.get("status", ""),
                    "started_at": data.get("started_at", ""),
                    "ended_at": data.get("ended_at", ""),
                    "case_count": len(data.get("cases", []) or []),
                }
            )
        except Exception:
            continue
    return runs

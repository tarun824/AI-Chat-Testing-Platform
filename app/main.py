import asyncio
import logging
from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import DEFAULT_AGENT_MAX_TURNS, STATIC_DIR
from app.env_storage import (
    ensure_environments_dir,
    list_environments,
    load_environment,
    save_environment,
    delete_environment,
)
from app.runner import (
    run_agent_conversation_with_id,
    run_dataset_with_id,
    start_run,
)
from app.storage import (
    ensure_storage_dirs,
    list_datasets,
    load_dataset,
    save_dataset,
    list_runs,
    load_run,
    update_run,
)

def _configure_logging() -> None:
    root_logger = logging.getLogger()
    if not root_logger.handlers:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(name)s %(message)s",
        )
    logging.getLogger("ai_test").setLevel(logging.INFO)
    logging.getLogger("ai_test.main").setLevel(logging.INFO)
    logging.getLogger("ai_test.runner").setLevel(logging.INFO)
    logging.getLogger("ai_test.ai_chat").setLevel(logging.INFO)


_configure_logging()
logger = logging.getLogger("ai_test.main")

app = FastAPI(title="AI Automation Runner")
RUNNING_TASKS: Dict[str, asyncio.Task] = {}
STOP_EVENTS: Dict[str, asyncio.Event] = {}


@app.on_event("startup")
async def startup_event() -> None:
    ensure_storage_dirs()
    ensure_environments_dir()


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/api/agents")
async def api_list_agents() -> List[Dict[str, Any]]:
    from app.ai_chat import AGENT_SYSTEM_PROMPTS, AGENT_ALIASES
    seen: set = set()
    result = []
    for alias, canonical in AGENT_ALIASES.items():
        if canonical not in seen:
            seen.add(canonical)
            result.append({
                "name": canonical,
                "aliases": [k for k, v in AGENT_ALIASES.items() if v == canonical],
                "system_prompt": AGENT_SYSTEM_PROMPTS.get(canonical, ""),
            })
    return result


@app.get("/api/datasets")
async def api_list_datasets() -> List[Dict[str, Any]]:
    return list_datasets()


@app.get("/api/datasets/{dataset_id}")
async def api_get_dataset(dataset_id: str) -> Dict[str, Any]:
    try:
        return load_dataset(dataset_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="dataset_not_found")


@app.post("/api/datasets")
async def api_create_dataset(request: Request) -> Dict[str, Any]:
    payload = await request.json()
    dataset_id = payload.get("dataset_id")
    if not dataset_id:
        raise HTTPException(status_code=400, detail="dataset_id_required")
    return save_dataset(dataset_id, payload)


@app.put("/api/datasets/{dataset_id}")
async def api_update_dataset(dataset_id: str, request: Request) -> Dict[str, Any]:
    payload = await request.json()
    payload["dataset_id"] = dataset_id
    return save_dataset(dataset_id, payload)


@app.post("/api/datasets/{dataset_id}/cases")
async def api_add_case(dataset_id: str, request: Request) -> Dict[str, Any]:
    payload = await request.json()
    dataset = load_dataset(dataset_id)
    cases = dataset.get("cases", []) or []
    cases.append(payload)
    dataset["cases"] = cases
    return save_dataset(dataset_id, dataset)


@app.get("/api/runs")
async def api_list_runs() -> List[Dict[str, Any]]:
    return list_runs()


@app.get("/api/runs/{run_id}")
async def api_get_run(run_id: str) -> Dict[str, Any]:
    try:
        return load_run(run_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="run_not_found")


@app.post("/api/runs")
async def api_start_run(request: Request) -> Dict[str, Any]:
    payload = await request.json()
    mode = (payload.get("mode") or "dataset").lower()
    dataset_id = payload.get("dataset_id")
    tags = payload.get("tags", []) or []
    agent = (payload.get("agent") or "").strip()
    max_turns = int(payload.get("max_turns") or DEFAULT_AGENT_MAX_TURNS)
    custom_system_prompt = (payload.get("custom_system_prompt") or "").strip() or None
    environment_id = (payload.get("environment_id") or "").strip()

    if mode not in ["dataset", "agent"]:
        raise HTTPException(status_code=400, detail="invalid_mode")

    if mode == "dataset" and not dataset_id:
        raise HTTPException(status_code=400, detail="dataset_id_required")
    if mode == "agent" and not agent:
        raise HTTPException(status_code=400, detail="agent_required")

    if dataset_id:
        dataset = load_dataset(dataset_id)
    else:
        dataset = {"dataset_id": "agent_mode", "defaults": {}, "cases": []}

    # Resolve environment — None falls back to config.py DEFAULT_* values
    env: Dict[str, Any] | None = None
    if environment_id:
        try:
            env = load_environment(environment_id)
        except FileNotFoundError:
            raise HTTPException(status_code=400, detail=f"environment_not_found: {environment_id}")

    run_id = await start_run(
        dataset, tags, mode=mode, agent=agent,
        max_turns=max_turns, custom_system_prompt=custom_system_prompt,
        env=env,
    )
    logger.info(
        "run.start mode=%s run_id=%s dataset_id=%s agent=%s max_turns=%s tags=%s env=%s",
        mode,
        run_id,
        dataset.get("dataset_id"),
        agent,
        max_turns,
        tags,
        environment_id or "none",
    )
    STOP_EVENTS[run_id] = asyncio.Event()

    async def _runner() -> None:
        try:
            if mode == "agent":
                await run_agent_conversation_with_id(
                    run_id,
                    dataset,
                    agent,
                    max_turns,
                    stop_event=STOP_EVENTS.get(run_id),
                    custom_system_prompt=custom_system_prompt,
                    env=env,
                )
            else:
                await run_dataset_with_id(
                    run_id, dataset, tags,
                    stop_event=STOP_EVENTS.get(run_id),
                    env=env,
                )
        finally:
            RUNNING_TASKS.pop(run_id, None)
            STOP_EVENTS.pop(run_id, None)

    RUNNING_TASKS[run_id] = asyncio.create_task(_runner())
    return {"run_id": run_id}


@app.post("/api/runs/{run_id}/stop")
async def api_stop_run(run_id: str) -> Dict[str, Any]:
    event = STOP_EVENTS.get(run_id)
    if not event:
        raise HTTPException(status_code=404, detail="run_not_running")
    event.set()
    logger.info("run.stop_requested run_id=%s", run_id)
    try:
        run_record = load_run(run_id)
        run_record["status"] = "stopping"
        update_run(run_id, run_record)
    except FileNotFoundError:
        pass
    return {"run_id": run_id, "status": "stopping"}


@app.get("/api/environments")
async def api_list_environments() -> List[Dict[str, Any]]:
    return list_environments()


@app.get("/api/environments/{env_id}")
async def api_get_environment(env_id: str) -> Dict[str, Any]:
    try:
        return load_environment(env_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="environment_not_found")


@app.post("/api/environments")
async def api_create_environment(request: Request) -> Dict[str, Any]:
    payload = await request.json()
    env_id = (payload.get("env_id") or "").strip().lower().replace(" ", "_")
    if not env_id:
        raise HTTPException(status_code=400, detail="env_id_required")
    payload["env_id"] = env_id
    return save_environment(env_id, payload)


@app.put("/api/environments/{env_id}")
async def api_update_environment(env_id: str, request: Request) -> Dict[str, Any]:
    payload = await request.json()
    payload["env_id"] = env_id
    return save_environment(env_id, payload)


@app.delete("/api/environments/{env_id}")
async def api_delete_environment(env_id: str) -> Dict[str, str]:
    try:
        delete_environment(env_id)
    except Exception:
        pass
    return {"deleted": env_id}


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(str(STATIC_DIR / "index.html"))

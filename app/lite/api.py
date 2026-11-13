from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse

from app.lite.schemas import (
    ConversationCreate,
    FunctionInvocation,
    MessageCreate,
    ObservationCreate,
    PlantCreate,
    PlantUpdate,
    SqlQuery,
    TaskComplete,
    TaskCreate,
    ZoneCreate,
    ZoneUpdate,
)
from app.lite.store import GardenStore

router = APIRouter()


def get_store(request: Request) -> GardenStore:
    return request.app.state.store


def require_api_token(request: Request) -> None:
    token = getattr(request.app.state.settings, "api_token", None)
    if not token:
        return
    submitted = request.headers.get("x-garden-token") or request.query_params.get("api_token")
    if submitted != token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid API token.",
        )


api_router = APIRouter(prefix="/api/v1", dependencies=[Depends(require_api_token)])


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, set):
        return [_jsonable(item) for item in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _ok(data: Any, *, status_code: int = status.HTTP_200_OK) -> JSONResponse:
    return JSONResponse(_jsonable(data), status_code=status_code)


def _lookup_plant(store: GardenStore, identifier: str) -> dict[str, Any]:
    try:
        return store.get_plant(identifier)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


def _lookup_task(store: GardenStore, task_id: str) -> dict[str, Any]:
    try:
        return store.get_task(task_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


def _lookup_conversation(store: GardenStore, conversation_id: str) -> dict[str, Any]:
    try:
        return store.get_conversation(conversation_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/", include_in_schema=False)
def root(request: Request, store: GardenStore = Depends(get_store)) -> JSONResponse:
    return _ok(
        {
            "app_name": request.app.state.settings.app_name,
            "backend": "duckdb",
            "database_path": store.database_path,
            "functions": store.function_catalog(),
            "dashboard": store.dashboard(),
        },
    )


@router.get("/health/live", include_in_schema=False)
def health_live() -> JSONResponse:
    return _ok({"status": "ok"})


@router.get("/health/ready", include_in_schema=False)
def health_ready(store: GardenStore = Depends(get_store)) -> JSONResponse:
    if not store.ping():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="DuckDB not ready.",
        )
    return _ok({"status": "ready", "backend": "duckdb", "database_path": store.database_path})


@api_router.get("/functions")
def list_functions(store: GardenStore = Depends(get_store)) -> JSONResponse:
    return _ok({"functions": store.function_catalog()})


@api_router.post("/functions/{function_name}")
def invoke_function(
    function_name: str,
    payload: FunctionInvocation,
    store: GardenStore = Depends(get_store),
) -> JSONResponse:
    try:
        result = store.invoke(function_name, payload.payload)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except (LookupError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _ok({"function": function_name, "result": result})


@api_router.get("/schema")
def schema_snapshot(store: GardenStore = Depends(get_store)) -> JSONResponse:
    return _ok(store.schema_snapshot())


@api_router.get("/dashboard")
def dashboard(store: GardenStore = Depends(get_store)) -> JSONResponse:
    return _ok(store.dashboard())


@api_router.post("/query")
def query_sql(payload: SqlQuery, store: GardenStore = Depends(get_store)) -> JSONResponse:
    try:
        rows = store.read_only_query(payload.sql, payload.params)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _ok({"rows": rows, "row_count": len(rows)})


@api_router.get("/plants")
def list_plants(request: Request, store: GardenStore = Depends(get_store)) -> JSONResponse:
    params = request.query_params
    plants = store.list_plants(
        query=params.get("query"),
        status=params.get("status"),
        include_archived=str(params.get("include_archived", "")).lower() in {"1", "true", "yes"},
        limit=int(params.get("limit", 50)),
    )
    return _ok({"plants": plants, "count": len(plants)})


@api_router.get("/zones")
def list_zones(request: Request, store: GardenStore = Depends(get_store)) -> JSONResponse:
    params = request.query_params
    zones = store.list_zones(
        query=params.get("query"),
        limit=int(params.get("limit", 50)),
    )
    return _ok({"zones": zones, "count": len(zones)})


@api_router.post("/zones")
def create_zone(payload: ZoneCreate, store: GardenStore = Depends(get_store)) -> JSONResponse:
    try:
        zone = store.create_zone(payload.model_dump(exclude_none=True))
    except (LookupError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _ok(zone, status_code=status.HTTP_201_CREATED)


@api_router.get("/zones/{identifier}")
def get_zone(identifier: str, store: GardenStore = Depends(get_store)) -> JSONResponse:
    try:
        zone = store.get_zone(identifier)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _ok(zone)


@api_router.patch("/zones/{identifier}")
def patch_zone(
    identifier: str,
    payload: ZoneUpdate,
    store: GardenStore = Depends(get_store),
) -> JSONResponse:
    try:
        zone = store.update_zone(identifier, payload.model_dump(exclude_none=True))
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _ok(zone)


@api_router.post("/plants")
def create_plant(payload: PlantCreate, store: GardenStore = Depends(get_store)) -> JSONResponse:
    try:
        plant = store.create_plant(payload.model_dump(exclude_none=True))
    except (LookupError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _ok(plant, status_code=status.HTTP_201_CREATED)


@api_router.get("/plants/{identifier}")
def get_plant(identifier: str, store: GardenStore = Depends(get_store)) -> JSONResponse:
    plant = _lookup_plant(store, identifier)
    return _ok(plant)


@api_router.patch("/plants/{identifier}")
def patch_plant(
    identifier: str,
    payload: PlantUpdate,
    store: GardenStore = Depends(get_store),
) -> JSONResponse:
    try:
        plant = store.update_plant(identifier, payload.model_dump(exclude_none=True))
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _ok(plant)


@api_router.post("/plants/{identifier}/observations")
def post_observation(
    identifier: str,
    payload: ObservationCreate,
    store: GardenStore = Depends(get_store),
) -> JSONResponse:
    body = payload.model_dump(exclude_none=True)
    body["plant"] = identifier
    try:
        observation = store.record_observation(body)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _ok(observation, status_code=status.HTTP_201_CREATED)


@api_router.get("/tasks")
def list_tasks(request: Request, store: GardenStore = Depends(get_store)) -> JSONResponse:
    params = request.query_params
    tasks = store.list_tasks(
        plant=params.get("plant"),
        zone=params.get("zone"),
        status=params.get("status"),
        limit=int(params.get("limit", 50)),
    )
    return _ok({"tasks": tasks, "count": len(tasks)})


@api_router.post("/tasks")
def create_task(payload: TaskCreate, store: GardenStore = Depends(get_store)) -> JSONResponse:
    try:
        task = store.create_task(payload.model_dump(exclude_none=True))
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _ok(task, status_code=status.HTTP_201_CREATED)


@api_router.post("/tasks/{task_id}/complete")
def complete_task(
    task_id: str,
    payload: TaskComplete,
    store: GardenStore = Depends(get_store),
) -> JSONResponse:
    _lookup_task(store, task_id)
    try:
        task = store.complete_task(task_id, payload.model_dump(exclude_none=True))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _ok(task)


@api_router.get("/conversations")
def list_conversations(request: Request, store: GardenStore = Depends(get_store)) -> JSONResponse:
    params = request.query_params
    conversations = store.list_conversations(limit=int(params.get("limit", 50)))
    return _ok({"conversations": conversations, "count": len(conversations)})


@api_router.post("/conversations")
def create_conversation(
    payload: ConversationCreate,
    store: GardenStore = Depends(get_store),
) -> JSONResponse:
    conversation = store.create_conversation(payload.model_dump(exclude_none=True))
    return _ok(conversation, status_code=status.HTTP_201_CREATED)


@api_router.get("/conversations/{conversation_id}")
def get_conversation(conversation_id: str, store: GardenStore = Depends(get_store)) -> JSONResponse:
    conversation = _lookup_conversation(store, conversation_id)
    return _ok(conversation)


@api_router.post("/conversations/{conversation_id}/messages")
def append_message(
    conversation_id: str,
    payload: MessageCreate,
    store: GardenStore = Depends(get_store),
) -> JSONResponse:
    try:
        message = store.append_message(conversation_id, payload.model_dump(exclude_none=True))
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _ok(message, status_code=status.HTTP_201_CREATED)

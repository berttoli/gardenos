from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Literal

from app.common.ids import new_uuid_str


def _import_duckdb() -> Any:
    try:
        import duckdb  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover - exercised only when dependency is missing
        raise RuntimeError(
            "DuckDB support is not installed. "
            "Install the `duckdb` package to use the lite backend.",
        ) from exc
    return duckdb


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _new_id() -> str:
    return new_uuid_str()


def _clean_text(value: Any | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _coerce_float(value: Any | None) -> float | None:
    text = _clean_text(value)
    if text is None:
        return None
    return float(text)


def _coerce_int(value: Any | None) -> int | None:
    text = _clean_text(value)
    if text is None:
        return None
    return int(text)


def _coerce_date(value: Any | None) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    return date.fromisoformat(str(value))


def _coerce_datetime(value: Any | None, default: datetime | None = None) -> datetime | None:
    if value is None or value == "":
        return default
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    return datetime.fromisoformat(str(value))


def _json_text(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str)


def _rows(cursor: Any) -> list[dict[str, Any]]:
    columns = [description[0] for description in (cursor.description or [])]
    return [dict(zip(columns, row, strict=False)) for row in cursor.fetchall()]


def _first_row(cursor: Any) -> dict[str, Any] | None:
    rows = _rows(cursor)
    return rows[0] if rows else None


@dataclass(frozen=True, slots=True)
class FunctionSpec:
    name: str
    kind: Literal["query", "mutation"]
    description: str
    payload_hint: str


FUNCTION_CATALOG: tuple[FunctionSpec, ...] = (
    FunctionSpec(
        name="dashboard",
        kind="query",
        description="Return the main garden summary, recent activity, and queue snapshots.",
        payload_hint="{}",
    ),
    FunctionSpec(
        name="schema",
        kind="query",
        description="Return the DuckDB schema snapshot for UI or chat introspection.",
        payload_hint="{}",
    ),
    FunctionSpec(
        name="list_zones",
        kind="query",
        description="Return garden zones with plant and task counts.",
        payload_hint='{"query": "woodland", "limit": 20}',
    ),
    FunctionSpec(
        name="get_zone",
        kind="query",
        description="Return one zone record plus its current counts.",
        payload_hint='{"identifier": "West woodland"}',
    ),
    FunctionSpec(
        name="search",
        kind="query",
        description="Search plants, observations, tasks, and messages with a single query string.",
        payload_hint='{"query": "maple"}',
    ),
    FunctionSpec(
        name="list_plants",
        kind="query",
        description="Return filtered plant rows with counts and latest observation dates.",
        payload_hint='{"query": "maple", "status": "active", "limit": 20}',
    ),
    FunctionSpec(
        name="get_plant",
        kind="query",
        description="Return one plant plus its observations, tasks, and event history.",
        payload_hint='{"identifier": "AP-GT-001"}',
    ),
    FunctionSpec(
        name="create_plant",
        kind="mutation",
        description="Insert a plant and emit a creation event.",
        payload_hint='{"scientific_name": "Acer palmatum", "display_id": "AP-GT-002"}',
    ),
    FunctionSpec(
        name="update_plant",
        kind="mutation",
        description="Update a plant in place and emit a change event.",
        payload_hint='{"notes": "Repotted yesterday"}',
    ),
    FunctionSpec(
        name="record_observation",
        kind="mutation",
        description="Record an observation row and add an event ledger entry.",
        payload_hint='{"plant": "AP-GT-001", "summary": "Leaves look strong"}',
    ),
    FunctionSpec(
        name="create_task",
        kind="mutation",
        description="Create a task row for the open queue.",
        payload_hint='{"title": "Water greenhouse bench"}',
    ),
    FunctionSpec(
        name="complete_task",
        kind="mutation",
        description="Mark a task complete and keep the history in the event log.",
        payload_hint='{"task_id": "uuid", "notes": "Handled by hand"}',
    ),
    FunctionSpec(
        name="create_conversation",
        kind="mutation",
        description="Create a durable chat thread for later UI or automation.",
        payload_hint='{"title": "Garden planner"}',
    ),
    FunctionSpec(
        name="append_message",
        kind="mutation",
        description="Append a message to a chat thread.",
        payload_hint='{"role": "user", "content": "Show me the watering queue"}',
    ),
    FunctionSpec(
        name="create_zone",
        kind="mutation",
        description="Create or seed a property zone record.",
        payload_hint='{"name": "West woodland", "sun_exposure": "part shade"}',
    ),
    FunctionSpec(
        name="update_zone",
        kind="mutation",
        description="Update a zone record in place.",
        payload_hint='{"identifier": "West woodland", "notes": "North edge"}',
    ),
    FunctionSpec(
        name="query",
        kind="query",
        description="Run a read-only SQL query against DuckDB for open interaction.",
        payload_hint='{"sql": "select * from v_dashboard_summary"}',
    ),
)


class GardenStore:
    schema_version = "2026-07-lite-2"

    def __init__(self, database_path: Path) -> None:
        self.database_path = Path(database_path).expanduser()

    @contextmanager
    def connection(self) -> Any:
        duckdb = _import_duckdb()
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = duckdb.connect(str(self.database_path))
        try:
            yield connection
        finally:
            connection.close()

    def initialize(self, *, seed: bool = True) -> None:
        with self.connection() as connection:
            self._apply_schema(connection)
            self._set_meta(connection, "schema_version", self.schema_version)
            if seed and self._count(connection, "plants") == 0:
                self._seed_demo_data(connection)
            connection.commit()

    def ping(self) -> bool:
        with self.connection() as connection:
            connection.execute("SELECT 1")
            return True

    def function_catalog(self) -> list[dict[str, Any]]:
        return [asdict(spec) for spec in FUNCTION_CATALOG]

    def invoke(self, name: str, payload: Mapping[str, Any] | None = None) -> Any:
        body = dict(payload or {})
        match name:
            case "dashboard":
                return self.dashboard()
            case "schema":
                return self.schema_snapshot()
            case "list_zones":
                return self.list_zones(
                    query=_clean_text(body.get("query")),
                    limit=_coerce_int(body.get("limit")) or 50,
                )
            case "get_zone":
                identifier = _clean_text(body.get("identifier"))
                if identifier is None:
                    raise ValueError("identifier is required")
                return self.get_zone(identifier)
            case "search":
                return self.search(
                    query=_clean_text(body.get("query")) or "",
                    limit=_coerce_int(body.get("limit")) or 20,
                )
            case "list_plants":
                return self.list_plants(
                    query=_clean_text(body.get("query")),
                    status=_clean_text(body.get("status")),
                    include_archived=bool(body.get("include_archived", False)),
                    limit=_coerce_int(body.get("limit")) or 50,
                )
            case "get_plant":
                identifier = _clean_text(body.get("identifier"))
                if identifier is None:
                    raise ValueError("identifier is required")
                return self.get_plant(identifier)
            case "create_plant":
                return self.create_plant(body)
            case "update_plant":
                identifier = _clean_text(body.get("identifier"))
                if identifier is None:
                    raise ValueError("identifier is required")
                return self.update_plant(identifier, body)
            case "record_observation":
                return self.record_observation(body)
            case "create_task":
                return self.create_task(body)
            case "complete_task":
                task_id = _clean_text(body.get("task_id"))
                if task_id is None:
                    raise ValueError("task_id is required")
                return self.complete_task(task_id, body)
            case "create_conversation":
                return self.create_conversation(body)
            case "append_message":
                conversation_id = _clean_text(body.get("conversation_id"))
                if conversation_id is None:
                    raise ValueError("conversation_id is required")
                return self.append_message(conversation_id, body)
            case "create_zone":
                return self.create_zone(body)
            case "update_zone":
                identifier = _clean_text(body.get("identifier"))
                if identifier is None:
                    raise ValueError("identifier is required")
                return self.update_zone(identifier, body)
            case "query":
                sql = _clean_text(body.get("sql"))
                if sql is None:
                    raise ValueError("sql is required")
                return self.read_only_query(sql, body.get("params"))
            case _:
                raise KeyError(f"Unknown function: {name}")

    def schema_snapshot(self) -> dict[str, Any]:
        with self.connection() as connection:
            tables = self._query_all(
                connection,
                """
                SELECT table_name, table_type
                FROM information_schema.tables
                WHERE table_schema = 'main'
                ORDER BY table_type, table_name
                """,
            )
            columns = self._query_all(
                connection,
                """
                SELECT
                  table_name,
                  column_name,
                  data_type,
                  is_nullable,
                  column_default,
                  ordinal_position
                FROM information_schema.columns
                WHERE table_schema = 'main'
                ORDER BY table_name, ordinal_position
                """,
            )
            meta = self._query_all(
                connection,
                "SELECT key, value FROM meta ORDER BY key",
            )
        return {
            "schema_version": self.schema_version,
            "tables": tables,
            "columns": columns,
            "meta": meta,
        }

    def dashboard(self) -> dict[str, Any]:
        with self.connection() as connection:
            summary = self._query_one(connection, "SELECT * FROM v_dashboard_summary") or {}
            recent_plants = self._query_all(
                connection,
                """
                SELECT *
                FROM v_active_plants
                ORDER BY updated_at DESC, display_id
                LIMIT 6
                """,
            )
            open_tasks = self._query_all(
                connection,
                """
                SELECT *
                FROM v_open_tasks
                ORDER BY priority DESC, COALESCE(due_at, updated_at) ASC
                LIMIT 8
                """,
            )
            recent_observations = self._query_all(
                connection,
                """
                SELECT
                  o.id,
                  o.plant_id,
                  p.display_id AS plant_display_id,
                  p.common_name AS plant_common_name,
                  o.observed_at,
                  o.observation_type,
                  o.summary,
                  o.notes,
                  o.health_score,
                  o.moisture,
                  o.temperature,
                  o.created_at
                FROM observations o
                LEFT JOIN plants p ON p.id = o.plant_id
                ORDER BY o.observed_at DESC, o.created_at DESC
                LIMIT 8
                """,
            )
            recent_activity = self._query_all(
                connection,
                """
                SELECT happened_at, kind, subject, details, entity_id
                FROM (
                  SELECT
                    happened_at,
                    kind,
                    subject,
                    details,
                    entity_id
                  FROM (
                    SELECT
                      happened_at,
                      'event' AS kind,
                      entity_type || '.' || event_type AS subject,
                      payload_json AS details,
                      entity_id
                    FROM events
                    UNION ALL
                    SELECT
                      observed_at AS happened_at,
                      'observation' AS kind,
                      COALESCE(summary, 'Observation') AS subject,
                      COALESCE(notes, '') AS details,
                      plant_id AS entity_id
                    FROM observations
                    UNION ALL
                    SELECT
                      COALESCE(completed_at, skipped_at, updated_at, created_at) AS happened_at,
                      'task' AS kind,
                      title AS subject,
                      COALESCE(notes, '') AS details,
                      COALESCE(plant_id, '') AS entity_id
                    FROM tasks
                    UNION ALL
                    SELECT
                      created_at AS happened_at,
                      'message' AS kind,
                      role || ' message' AS subject,
                      content AS details,
                      conversation_id AS entity_id
                    FROM messages
                  )
                )
                ORDER BY happened_at DESC
                LIMIT 12
                """,
            )
        return {
            "summary": summary,
            "recent_plants": recent_plants,
            "open_tasks": open_tasks,
            "recent_observations": recent_observations,
            "recent_activity": recent_activity,
        }

    def list_zones(
        self,
        *,
        query: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if query is not None:
            like = f"%{query.strip().lower()}%"
            clauses.append(
                """
                (
                  lower(l.name) LIKE ?
                  OR lower(COALESCE(l.description, '')) LIKE ?
                  OR lower(COALESCE(l.notes, '')) LIKE ?
                )
                """.strip(),
            )
            params.extend([like, like, like])
        sql = """
            SELECT
              l.id,
              l.name,
              l.location_type,
              l.parent_id,
              l.description,
              l.sun_exposure,
              l.soil_type,
              l.drainage,
              l.moisture_tendency,
              l.slope,
              l.wind_exposure,
              l.irrigation_availability,
              l.coordinates_json,
              l.photo_path,
              l.notes,
              l.created_at,
              l.updated_at,
              COALESCE(plant_counts.plant_count, 0) AS plant_count,
              COALESCE(task_counts.task_count, 0) AS task_count
            FROM locations l
            LEFT JOIN (
              SELECT location_id, COUNT(*) AS plant_count
              FROM plants
              WHERE location_id IS NOT NULL
              GROUP BY location_id
            ) plant_counts ON plant_counts.location_id = l.id
            LEFT JOIN (
              SELECT location_id, COUNT(*) AS task_count
              FROM tasks
              WHERE location_id IS NOT NULL
              GROUP BY location_id
            ) task_counts ON task_counts.location_id = l.id
        """
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY l.name LIMIT ?"
        params.append(limit)
        with self.connection() as connection:
            return self._query_all(connection, sql, params)

    def get_zone(self, identifier: str) -> dict[str, Any]:
        with self.connection() as connection:
            zone = self._query_one(
                connection,
                """
                SELECT
                  l.id,
                  l.name,
                  l.location_type,
                  l.parent_id,
                  l.description,
                  l.sun_exposure,
                  l.soil_type,
                  l.drainage,
                  l.moisture_tendency,
                  l.slope,
                  l.wind_exposure,
                  l.irrigation_availability,
                  l.coordinates_json,
                  l.photo_path,
                  l.notes,
                  l.created_at,
                  l.updated_at,
                  COALESCE(plant_counts.plant_count, 0) AS plant_count,
                  COALESCE(task_counts.task_count, 0) AS task_count
                FROM locations l
                LEFT JOIN (
                  SELECT location_id, COUNT(*) AS plant_count
                  FROM plants
                  WHERE location_id IS NOT NULL
                  GROUP BY location_id
                ) plant_counts ON plant_counts.location_id = l.id
                LEFT JOIN (
                  SELECT location_id, COUNT(*) AS task_count
                  FROM tasks
                  WHERE location_id IS NOT NULL
                  GROUP BY location_id
                ) task_counts ON task_counts.location_id = l.id
                WHERE lower(l.id) = lower(?) OR lower(l.name) = lower(?)
                LIMIT 1
                """,
                [identifier, identifier],
            )
        if zone is None:
            raise LookupError(f"Zone not found: {identifier}")
        return zone

    def create_zone(self, data: Mapping[str, Any]) -> dict[str, Any]:
        name = _clean_text(data.get("name"))
        if name is None:
            raise ValueError("name is required")
        zone_type = _clean_text(data.get("zone_type")) or "zone"
        coordinates = data.get("coordinates")
        zone_id = _new_id()
        now = _utc_now()
        with self.connection() as connection:
            connection.execute(
                """
                INSERT INTO locations (
                  id,
                  name,
                  location_type,
                  parent_id,
                  description,
                  sun_exposure,
                  soil_type,
                  drainage,
                  moisture_tendency,
                  slope,
                  wind_exposure,
                  irrigation_availability,
                  coordinates_json,
                  photo_path,
                  notes,
                  created_at,
                  updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    zone_id,
                    name,
                    zone_type,
                    _clean_text(data.get("parent_id")),
                    _clean_text(data.get("description")),
                    _clean_text(data.get("sun_exposure")),
                    _clean_text(data.get("soil_type")),
                    _clean_text(data.get("drainage")),
                    _clean_text(data.get("moisture_tendency")),
                    _clean_text(data.get("slope")),
                    _clean_text(data.get("wind_exposure")),
                    _clean_text(data.get("irrigation_availability")),
                    _json_text(coordinates) if coordinates is not None else None,
                    _clean_text(data.get("photo_path")),
                    _clean_text(data.get("notes")),
                    now,
                    now,
                ],
            )
            connection.commit()
        return self.get_zone(zone_id)

    def update_zone(self, identifier: str, data: Mapping[str, Any]) -> dict[str, Any]:
        with self.connection() as connection:
            zone = self._query_one(
                connection,
                (
                    "SELECT id, name FROM locations "
                    "WHERE lower(id) = lower(?) OR lower(name) = lower(?) LIMIT 1"
                ),
                [identifier, identifier],
            )
            if zone is None:
                raise LookupError(f"Zone not found: {identifier}")
            assignments: list[str] = []
            params: list[Any] = []
            if "name" in data and _clean_text(data.get("name")) is not None:
                assignments.append("name = ?")
                params.append(_clean_text(data.get("name")))
            if "zone_type" in data and _clean_text(data.get("zone_type")) is not None:
                assignments.append("location_type = ?")
                params.append(_clean_text(data.get("zone_type")))
            if "parent_id" in data:
                assignments.append("parent_id = ?")
                params.append(_clean_text(data.get("parent_id")))
            if "description" in data:
                assignments.append("description = ?")
                params.append(_clean_text(data.get("description")))
            if "sun_exposure" in data:
                assignments.append("sun_exposure = ?")
                params.append(_clean_text(data.get("sun_exposure")))
            if "soil_type" in data:
                assignments.append("soil_type = ?")
                params.append(_clean_text(data.get("soil_type")))
            if "drainage" in data:
                assignments.append("drainage = ?")
                params.append(_clean_text(data.get("drainage")))
            if "moisture_tendency" in data:
                assignments.append("moisture_tendency = ?")
                params.append(_clean_text(data.get("moisture_tendency")))
            if "slope" in data:
                assignments.append("slope = ?")
                params.append(_clean_text(data.get("slope")))
            if "wind_exposure" in data:
                assignments.append("wind_exposure = ?")
                params.append(_clean_text(data.get("wind_exposure")))
            if "irrigation_availability" in data:
                assignments.append("irrigation_availability = ?")
                params.append(_clean_text(data.get("irrigation_availability")))
            if "coordinates" in data:
                assignments.append("coordinates_json = ?")
                coordinates = data.get("coordinates")
                params.append(_json_text(coordinates) if coordinates is not None else None)
            if "photo_path" in data:
                assignments.append("photo_path = ?")
                params.append(_clean_text(data.get("photo_path")))
            if "notes" in data:
                assignments.append("notes = ?")
                params.append(_clean_text(data.get("notes")))
            if not assignments:
                return self.get_zone(str(zone["id"]))
            params.extend([_utc_now(), zone["id"]])
            connection.execute(
                f"""
                UPDATE locations
                SET {", ".join(assignments)}, updated_at = ?
                WHERE id = ?
                """,
                params,
            )
            connection.commit()
        return self.get_zone(str(zone["id"]))

    def _resolve_location_id(
        self,
        connection: Any,
        data: Mapping[str, Any],
        *,
        default_type: str = "area",
    ) -> str | None:
        return self._ensure_location(
            connection,
            location_id=_clean_text(data.get("location_id")) or _clean_text(data.get("zone_id")),
            location_name=_clean_text(data.get("location_name"))
            or _clean_text(data.get("zone_name")),
            location_type=_clean_text(data.get("location_type"))
            or _clean_text(data.get("zone_type"))
            or default_type,
        )

    def search(self, *, query: str, limit: int = 20) -> dict[str, Any]:
        search = query.strip().lower()
        if not search:
            return {"query": query, "plants": [], "observations": [], "messages": []}
        like = f"%{search}%"
        with self.connection() as connection:
            plants = self._query_all(
                connection,
                """
                SELECT
                  p.id,
                  p.display_id,
                  p.scientific_name,
                  p.common_name,
                  p.status,
                  p.notes,
                  p.updated_at
                FROM plants p
                WHERE
                  lower(p.display_id) LIKE ?
                  OR lower(p.scientific_name) LIKE ?
                  OR lower(COALESCE(p.common_name, '')) LIKE ?
                  OR lower(COALESCE(p.notes, '')) LIKE ?
                ORDER BY p.updated_at DESC, p.display_id
                LIMIT ?
                """,
                [like, like, like, like, limit],
            )
            observations = self._query_all(
                connection,
                """
                SELECT
                  o.id,
                  o.plant_id,
                  p.display_id AS plant_display_id,
                  o.observed_at,
                  o.summary,
                  o.notes
                FROM observations o
                LEFT JOIN plants p ON p.id = o.plant_id
                WHERE lower(COALESCE(o.summary, '')) LIKE ?
                  OR lower(COALESCE(o.notes, '')) LIKE ?
                ORDER BY o.observed_at DESC
                LIMIT ?
                """,
                [like, like, limit],
            )
            messages = self._query_all(
                connection,
                """
                SELECT
                  m.id,
                  m.conversation_id,
                  c.title AS conversation_title,
                  m.role,
                  m.content,
                  m.created_at
                FROM messages m
                LEFT JOIN conversations c ON c.id = m.conversation_id
                WHERE lower(m.content) LIKE ?
                ORDER BY m.created_at DESC
                LIMIT ?
                """,
                [like, limit],
            )
        return {
            "query": query,
            "plants": plants,
            "observations": observations,
            "messages": messages,
        }

    def list_plants(
        self,
        *,
        query: str | None = None,
        status: str | None = None,
        include_archived: bool = False,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if not include_archived:
            clauses.append("p.archived_at IS NULL")
        if status is not None:
            clauses.append("lower(p.status) = lower(?)")
            params.append(status)
        if query is not None:
            like = f"%{query.strip().lower()}%"
            clauses.append(
                """
                (
                  lower(p.display_id) LIKE ?
                  OR lower(p.scientific_name) LIKE ?
                  OR lower(COALESCE(p.common_name, '')) LIKE ?
                  OR lower(COALESCE(p.notes, '')) LIKE ?
                )
                """.strip(),
            )
            params.extend([like, like, like, like])
        sql = """
            SELECT
              p.id,
              p.display_id,
              p.scientific_name,
              p.common_name,
              p.status,
              p.acquisition_type,
              p.accession_date,
              p.source_name,
              p.source_reference,
              p.location_id,
              l.name AS zone_name,
              l.name AS location_name,
              p.container_id,
              c.identifier AS container_identifier,
              p.notes,
              p.archived_at,
              p.created_at,
              p.updated_at,
              COALESCE(obs.observation_count, 0) AS observation_count,
              obs.last_observed_at
            FROM plants p
            LEFT JOIN locations l ON l.id = p.location_id
            LEFT JOIN containers c ON c.id = p.container_id
            LEFT JOIN (
              SELECT plant_id, COUNT(*) AS observation_count, MAX(observed_at) AS last_observed_at
              FROM observations
              GROUP BY plant_id
            ) obs ON obs.plant_id = p.id
        """
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY p.updated_at DESC, p.display_id LIMIT ?"
        params.append(limit)
        with self.connection() as connection:
            return self._query_all(connection, sql, params)

    def get_plant(self, identifier: str) -> dict[str, Any]:
        plant = self._fetch_plant(identifier)
        if plant is None:
            raise LookupError(f"Plant not found: {identifier}")
        with self.connection() as connection:
            observations = self._query_all(
                connection,
                """
                SELECT
                  id,
                  plant_id,
                  observed_at,
                  observation_type,
                  summary,
                  notes,
                  health_score,
                  moisture,
                  temperature,
                  location_id,
                  created_at
                FROM observations
                WHERE plant_id = ?
                ORDER BY observed_at DESC, created_at DESC
                """,
                [plant["id"]],
            )
            tasks = self._query_all(
                connection,
                """
                SELECT
                  id,
                  title,
                  task_type,
                  priority,
                  due_at,
                  completed_at,
                  skipped_at,
                  notes,
                  created_at,
                  updated_at
                FROM tasks
                WHERE plant_id = ?
                ORDER BY COALESCE(due_at, updated_at) DESC, created_at DESC
                """,
                [plant["id"]],
            )
            events = self._query_all(
                connection,
                """
                SELECT
                  id,
                  entity_type,
                  entity_id,
                  event_type,
                  payload_json,
                  happened_at
                FROM events
                WHERE entity_type = 'plant' AND entity_id = ?
                ORDER BY happened_at DESC
                """,
                [plant["id"]],
            )
        return {
            "plant": plant,
            "observations": observations,
            "tasks": tasks,
            "events": events,
        }

    def create_plant(self, data: Mapping[str, Any]) -> dict[str, Any]:
        with self.connection() as connection:
            plant_id = self._create_plant_in_connection(connection, data)
            connection.commit()
        return self.get_plant(plant_id)

    def update_plant(self, identifier: str, data: Mapping[str, Any]) -> dict[str, Any]:
        plant = self._fetch_plant(identifier)
        if plant is None:
            raise LookupError(f"Plant not found: {identifier}")
        assignments: list[str] = []
        params: list[Any] = []
        if "scientific_name" in data and _clean_text(data.get("scientific_name")) is not None:
            assignments.append("scientific_name = ?")
            params.append(_clean_text(data.get("scientific_name")))
        if "common_name" in data:
            assignments.append("common_name = ?")
            params.append(_clean_text(data.get("common_name")))
        if "status" in data and _clean_text(data.get("status")) is not None:
            assignments.append("status = ?")
            params.append(_clean_text(data.get("status")))
        if "acquisition_type" in data and _clean_text(data.get("acquisition_type")) is not None:
            assignments.append("acquisition_type = ?")
            params.append(_clean_text(data.get("acquisition_type")))
        if "accession_date" in data:
            assignments.append("accession_date = ?")
            params.append(_coerce_date(data.get("accession_date")))
        if "source_name" in data:
            assignments.append("source_name = ?")
            params.append(_clean_text(data.get("source_name")))
        if "source_reference" in data:
            assignments.append("source_reference = ?")
            params.append(_clean_text(data.get("source_reference")))
        if (
            "location_name" in data
            or "location_id" in data
            or "zone_name" in data
            or "zone_id" in data
            or "zone_type" in data
            or "location_type" in data
        ):
            assignments.append("_location_marker_ = ?")
            params.append(data)
        if "container_identifier" in data or "container_id" in data:
            assignments.append("_container_marker_ = ?")
            params.append(
                (
                    _clean_text(data.get("container_id")),
                    _clean_text(data.get("container_identifier")),
                ),
            )
        if "notes" in data:
            assignments.append("notes = ?")
            params.append(_clean_text(data.get("notes")))
        if "archived_at" in data:
            assignments.append("archived_at = ?")
            params.append(_coerce_datetime(data.get("archived_at")))
        if not assignments:
            return self.get_plant(identifier)
        with self.connection() as connection:
            resolved_assignments: list[str] = []
            resolved_params: list[Any] = []
            for assignment, value in zip(assignments, params, strict=False):
                if assignment == "_location_marker_ = ?":
                    location_id = self._resolve_location_id(connection, value)
                    resolved_assignments.append("location_id = ?")
                    resolved_params.append(location_id)
                elif assignment == "_container_marker_ = ?":
                    container_id = self._ensure_container(
                        connection,
                        container_id=value[0],
                        container_identifier=value[1],
                    )
                    resolved_assignments.append("container_id = ?")
                    resolved_params.append(container_id)
                else:
                    resolved_assignments.append(assignment)
                    resolved_params.append(value)
            resolved_params.extend([_utc_now(), plant["id"]])
            sql = f"""
                UPDATE plants
                SET {", ".join(resolved_assignments)}, updated_at = ?
                WHERE id = ?
            """
            connection.execute(sql, resolved_params)
            self._append_event(
                connection,
                entity_type="plant",
                entity_id=plant["id"],
                event_type="updated",
                payload={key: self._event_value(value) for key, value in data.items()},
            )
            connection.commit()
        return self.get_plant(identifier)

    def record_observation(self, data: Mapping[str, Any]) -> dict[str, Any]:
        with self.connection() as connection:
            observation_id = self._record_observation_in_connection(connection, data)
            connection.commit()
        return self._get_observation(observation_id)

    def list_tasks(
        self,
        *,
        plant: str | None = None,
        zone: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if plant is not None:
            plant_row = self._fetch_plant(plant)
            if plant_row is None:
                raise LookupError(f"Plant not found: {plant}")
            clauses.append("t.plant_id = ?")
            params.append(plant_row["id"])
        if status is not None:
            normalized = status.strip().lower()
            if normalized in {"open", "queued", "pending"}:
                clauses.append("t.completed_at IS NULL AND t.skipped_at IS NULL")
            elif normalized in {"complete", "completed"}:
                clauses.append("t.completed_at IS NOT NULL")
            elif normalized in {"skipped", "skip"}:
                clauses.append("t.skipped_at IS NOT NULL")
            else:
                clauses.append("lower(t.status) = lower(?)")
                params.append(status)
        if zone is not None:
            clauses.append(
                "(lower(COALESCE(l.id, '')) = lower(?) OR lower(COALESCE(l.name, '')) = lower(?))",
            )
            params.extend([zone, zone])
        sql = """
            SELECT
              t.id,
              t.title,
              t.task_type,
              t.priority,
              t.plant_id,
              p.display_id AS plant_display_id,
              t.location_id,
              l.name AS zone_name,
              l.name AS location_name,
              t.due_at,
              t.completed_at,
              t.skipped_at,
              t.status,
              t.notes,
              t.created_at,
              t.updated_at
            FROM tasks t
            LEFT JOIN plants p ON p.id = t.plant_id
            LEFT JOIN locations l ON l.id = t.location_id
        """
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += (
            " ORDER BY t.completed_at IS NULL DESC, t.priority DESC, "
            "COALESCE(t.due_at, t.updated_at) ASC LIMIT ?"
        )
        params.append(limit)
        with self.connection() as connection:
            return self._query_all(connection, sql, params)

    def create_task(self, data: Mapping[str, Any]) -> dict[str, Any]:
        title = _clean_text(data.get("title"))
        if title is None:
            raise ValueError("title is required")
        plant_id = None
        plant_identifier = _clean_text(data.get("plant"))
        if plant_identifier is not None:
            plant = self._fetch_plant(plant_identifier)
            if plant is None:
                raise LookupError(f"Plant not found: {plant_identifier}")
            plant_id = plant["id"]
        with self.connection() as connection:
            task_id = self._create_task_in_connection(connection, data, plant_id=plant_id)
            connection.commit()
        return self.get_task(task_id)

    def get_task(self, task_id: str) -> dict[str, Any]:
        with self.connection() as connection:
            task = self._query_one(
                connection,
                """
                SELECT
                  t.id,
                  t.title,
                  t.task_type,
                  t.priority,
                  t.plant_id,
                  p.display_id AS plant_display_id,
                  t.location_id,
                  l.name AS zone_name,
                  l.name AS location_name,
                  t.due_at,
                  t.completed_at,
                  t.skipped_at,
                  t.status,
                  t.notes,
                  t.created_at,
                  t.updated_at
                FROM tasks t
                LEFT JOIN plants p ON p.id = t.plant_id
                LEFT JOIN locations l ON l.id = t.location_id
                WHERE t.id = ?
                """,
                [task_id],
            )
        if task is None:
            raise LookupError(f"Task not found: {task_id}")
        return task

    def complete_task(self, task_id: str, data: Mapping[str, Any] | None = None) -> dict[str, Any]:
        self.get_task(task_id)
        completed_at = _coerce_datetime((data or {}).get("completed_at"), default=_utc_now())
        notes = _clean_text((data or {}).get("notes"))
        now = _utc_now()
        with self.connection() as connection:
            connection.execute(
                """
                UPDATE tasks
                SET completed_at = ?,
                    status = 'complete',
                    notes = COALESCE(?, notes),
                    updated_at = ?
                WHERE id = ?
                """,
                [completed_at, notes, now, task_id],
            )
            self._append_event(
                connection,
                entity_type="task",
                entity_id=task_id,
                event_type="completed",
                payload={
                    "completed_at": completed_at.isoformat() if completed_at else None,
                    "notes": notes,
                },
                happened_at=now,
            )
            connection.commit()
        return self.get_task(task_id)

    def create_conversation(self, data: Mapping[str, Any]) -> dict[str, Any]:
        title = _clean_text(data.get("title")) or "Garden chat"
        with self.connection() as connection:
            conversation_id = self._create_conversation_in_connection(
                connection,
                {
                    "title": title,
                    "description": _clean_text(data.get("description")),
                },
            )
            connection.commit()
        return self.get_conversation(conversation_id)

    def list_conversations(self, *, limit: int = 50) -> list[dict[str, Any]]:
        with self.connection() as connection:
            return self._query_all(
                connection,
                """
                SELECT
                  c.id,
                  c.title,
                  c.description,
                  c.created_at,
                  c.updated_at,
                  COUNT(m.id) AS message_count,
                  MAX(m.created_at) AS last_message_at
                FROM conversations c
                LEFT JOIN messages m ON m.conversation_id = c.id
                GROUP BY c.id, c.title, c.description, c.created_at, c.updated_at
                ORDER BY c.updated_at DESC, c.created_at DESC
                LIMIT ?
                """,
                [limit],
            )

    def get_conversation(self, conversation_id: str) -> dict[str, Any]:
        with self.connection() as connection:
            conversation = self._query_one(
                connection,
                """
                SELECT
                  id,
                  title,
                  description,
                  created_at,
                  updated_at
                FROM conversations
                WHERE id = ?
                """,
                [conversation_id],
            )
            if conversation is None:
                raise LookupError(f"Conversation not found: {conversation_id}")
            messages = self._query_all(
                connection,
                """
                SELECT
                  id,
                  conversation_id,
                  role,
                  content,
                  metadata_json,
                  created_at
                FROM messages
                WHERE conversation_id = ?
                ORDER BY created_at ASC
                """,
                [conversation_id],
            )
        return {"conversation": conversation, "messages": messages}

    def append_message(self, conversation_id: str, data: Mapping[str, Any]) -> dict[str, Any]:
        role = _clean_text(data.get("role"))
        content = _clean_text(data.get("content"))
        if role is None:
            raise ValueError("role is required")
        if content is None:
            raise ValueError("content is required")
        if role not in {"system", "user", "assistant"}:
            raise ValueError("role must be system, user, or assistant")
        now = _utc_now()
        with self.connection() as connection:
            conversation = self._query_one(
                connection,
                "SELECT id FROM conversations WHERE id = ?",
                [conversation_id],
            )
            if conversation is None:
                raise LookupError(f"Conversation not found: {conversation_id}")
            message_id = self._append_message_in_connection(
                connection,
                conversation_id,
                {
                    "role": role,
                    "content": content,
                    "metadata": data.get("metadata") or {},
                },
            )
            connection.execute(
                """
                UPDATE conversations
                SET updated_at = ?
                WHERE id = ?
                """,
                [now, conversation_id],
            )
            connection.commit()
        with self.connection() as connection:
            message = self._query_one(
                connection,
                """
                SELECT
                  id,
                  conversation_id,
                  role,
                  content,
                  metadata_json,
                  created_at
                FROM messages
                WHERE id = ?
                """,
                [message_id],
            )
        if message is None:
            raise RuntimeError("Message was not persisted")
        return message

    def read_only_query(
        self,
        sql: str,
        params: Sequence[Any] | None = None,
    ) -> list[dict[str, Any]]:
        if not self._is_readonly_sql(sql):
            raise ValueError("Only read-only SQL statements are allowed.")
        with self.connection() as connection:
            return self._query_all(connection, sql, list(params or []))

    def _apply_schema(self, connection: Any) -> None:
        schema_statements = (
            """
            CREATE TABLE IF NOT EXISTS meta (
              key VARCHAR PRIMARY KEY,
              value VARCHAR NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS locations (
              id VARCHAR PRIMARY KEY,
              name VARCHAR NOT NULL UNIQUE,
              location_type VARCHAR NOT NULL DEFAULT 'area',
              parent_id VARCHAR,
              description VARCHAR,
              sun_exposure VARCHAR,
              soil_type VARCHAR,
              drainage VARCHAR,
              moisture_tendency VARCHAR,
              slope VARCHAR,
              wind_exposure VARCHAR,
              irrigation_availability VARCHAR,
              coordinates_json VARCHAR,
              photo_path VARCHAR,
              notes VARCHAR,
              created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
              updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS containers (
              id VARCHAR PRIMARY KEY,
              identifier VARCHAR NOT NULL UNIQUE,
              container_type VARCHAR,
              material VARCHAR,
              notes VARCHAR,
              created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
              updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS plants (
              id VARCHAR PRIMARY KEY,
              display_id VARCHAR NOT NULL UNIQUE,
              scientific_name VARCHAR NOT NULL,
              common_name VARCHAR,
              status VARCHAR NOT NULL DEFAULT 'active',
              acquisition_type VARCHAR NOT NULL DEFAULT 'unknown',
              accession_date DATE,
              source_name VARCHAR,
              source_reference VARCHAR,
              location_id VARCHAR,
              container_id VARCHAR,
              notes VARCHAR,
              archived_at TIMESTAMP,
              created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
              updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS observations (
              id VARCHAR PRIMARY KEY,
              plant_id VARCHAR NOT NULL,
              observed_at TIMESTAMP NOT NULL,
              observation_type VARCHAR NOT NULL DEFAULT 'routine',
              summary VARCHAR,
              notes VARCHAR,
              health_score DOUBLE,
              moisture DOUBLE,
              temperature DOUBLE,
              location_id VARCHAR,
              created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS tasks (
              id VARCHAR PRIMARY KEY,
              title VARCHAR NOT NULL,
              task_type VARCHAR NOT NULL DEFAULT 'custom',
              priority INTEGER NOT NULL DEFAULT 3,
              plant_id VARCHAR,
              location_id VARCHAR,
              due_at TIMESTAMP,
              completed_at TIMESTAMP,
              skipped_at TIMESTAMP,
              status VARCHAR NOT NULL DEFAULT 'open',
              notes VARCHAR,
              created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
              updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS conversations (
              id VARCHAR PRIMARY KEY,
              title VARCHAR NOT NULL,
              description VARCHAR,
              created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
              updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS messages (
              id VARCHAR PRIMARY KEY,
              conversation_id VARCHAR NOT NULL,
              role VARCHAR NOT NULL,
              content VARCHAR NOT NULL,
              metadata_json VARCHAR NOT NULL DEFAULT '{}',
              created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS events (
              id VARCHAR PRIMARY KEY,
              entity_type VARCHAR NOT NULL,
              entity_id VARCHAR NOT NULL,
              event_type VARCHAR NOT NULL,
              payload_json VARCHAR NOT NULL DEFAULT '{}',
              happened_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """,
        )
        for statement in schema_statements:
            connection.execute(statement)
        alter_statements = (
            "ALTER TABLE locations ADD COLUMN IF NOT EXISTS sun_exposure VARCHAR",
            "ALTER TABLE locations ADD COLUMN IF NOT EXISTS soil_type VARCHAR",
            "ALTER TABLE locations ADD COLUMN IF NOT EXISTS drainage VARCHAR",
            "ALTER TABLE locations ADD COLUMN IF NOT EXISTS moisture_tendency VARCHAR",
            "ALTER TABLE locations ADD COLUMN IF NOT EXISTS slope VARCHAR",
            "ALTER TABLE locations ADD COLUMN IF NOT EXISTS wind_exposure VARCHAR",
            "ALTER TABLE locations ADD COLUMN IF NOT EXISTS irrigation_availability VARCHAR",
            "ALTER TABLE locations ADD COLUMN IF NOT EXISTS coordinates_json VARCHAR",
            "ALTER TABLE locations ADD COLUMN IF NOT EXISTS photo_path VARCHAR",
            "ALTER TABLE locations ADD COLUMN IF NOT EXISTS notes VARCHAR",
            "ALTER TABLE tasks ADD COLUMN IF NOT EXISTS location_id VARCHAR",
        )
        for statement in alter_statements:
            connection.execute(statement)
        view_statements = (
            """
            CREATE OR REPLACE VIEW v_active_plants AS
            SELECT
              p.id,
              p.display_id,
              p.scientific_name,
              p.common_name,
              p.status,
              p.acquisition_type,
              p.accession_date,
              p.source_name,
              p.source_reference,
              p.location_id,
              l.name AS zone_name,
              l.name AS location_name,
              p.container_id,
              c.identifier AS container_identifier,
              p.notes,
              p.archived_at,
              p.created_at,
              p.updated_at,
              COALESCE(obs.observation_count, 0) AS observation_count,
              obs.last_observed_at
            FROM plants p
            LEFT JOIN locations l ON l.id = p.location_id
            LEFT JOIN containers c ON c.id = p.container_id
            LEFT JOIN (
              SELECT plant_id, COUNT(*) AS observation_count, MAX(observed_at) AS last_observed_at
              FROM observations
              GROUP BY plant_id
            ) obs ON obs.plant_id = p.id
            WHERE p.archived_at IS NULL
            """,
            """
            CREATE OR REPLACE VIEW v_open_tasks AS
            SELECT
              t.id,
              t.title,
              t.task_type,
              t.priority,
              t.plant_id,
              p.display_id AS plant_display_id,
              t.location_id,
              l.name AS zone_name,
              l.name AS location_name,
              t.due_at,
              t.completed_at,
              t.skipped_at,
              t.status,
              t.notes,
              t.created_at,
              t.updated_at
            FROM tasks t
            LEFT JOIN plants p ON p.id = t.plant_id
            LEFT JOIN locations l ON l.id = t.location_id
            WHERE t.completed_at IS NULL AND t.skipped_at IS NULL
            """,
            """
            CREATE OR REPLACE VIEW v_dashboard_summary AS
            SELECT
              (SELECT COUNT(*) FROM plants WHERE archived_at IS NULL) AS active_plants,
              (SELECT COUNT(*) FROM plants WHERE archived_at IS NOT NULL) AS archived_plants,
              (SELECT COUNT(*) FROM locations) AS locations,
              (SELECT COUNT(*) FROM containers) AS containers,
              (SELECT COUNT(*) FROM observations) AS observations_total,
              (
                SELECT COUNT(*)
                FROM observations
                WHERE observed_at >= CURRENT_TIMESTAMP - INTERVAL '30 days'
              ) AS observations_30d,
              (
                SELECT COUNT(*)
                FROM tasks
                WHERE completed_at IS NULL AND skipped_at IS NULL
              ) AS open_tasks,
              (SELECT COUNT(*) FROM tasks WHERE completed_at IS NOT NULL) AS completed_tasks,
              (SELECT COUNT(*) FROM conversations) AS conversations,
              (SELECT COUNT(*) FROM messages) AS messages,
              (SELECT MAX(observed_at) FROM observations) AS last_observation_at,
              (SELECT MAX(happened_at) FROM events) AS last_event_at
            """,
        )
        for statement in view_statements:
            connection.execute(statement)

    def _seed_demo_data(self, connection: Any) -> None:
        greenhouse_id = self._ensure_location(
            connection,
            location_name="Greenhouse Bench",
            location_type="bench",
        )
        orchard_id = self._ensure_location(
            connection,
            location_name="Orchard Row",
            location_type="orchard",
        )
        loop_pot_id = self._ensure_container(
            connection,
            container_identifier="Loop Pot A",
            container_type="loop",
        )
        nursery_pot_id = self._ensure_container(
            connection,
            container_identifier="Nursery Pot 10in",
            container_type="pot",
        )
        demo_plants = (
            {
                "display_id": "AP-GT-001",
                "scientific_name": "Acer palmatum",
                "common_name": "Japanese maple",
                "status": "quarantine",
                "acquisition_type": "purchased",
                "location_id": greenhouse_id,
                "container_id": loop_pot_id,
                "notes": "Seeded demo specimen for the Garden OS home network.",
            },
            {
                "display_id": "SAL-001",
                "scientific_name": "Salix babylonica",
                "common_name": "Willow",
                "status": "active",
                "acquisition_type": "found",
                "location_id": orchard_id,
                "container_id": nursery_pot_id,
                "notes": "Fast-growing benchmark plant for the analytics views.",
            },
            {
                "display_id": "HERB-001",
                "scientific_name": "Salvia rosmarinus",
                "common_name": "Rosemary",
                "status": "active",
                "acquisition_type": "gifted",
                "location_id": greenhouse_id,
                "container_id": nursery_pot_id,
                "notes": "Useful for showing multiple active plants in the dashboard.",
            },
        )
        for plant in demo_plants:
            self._create_plant_in_connection(connection, plant)
        self._record_observation_in_connection(
            connection,
            {
                "plant": "AP-GT-001",
                "observed_at": _utc_now(),
                "summary": "Foliage is stable after repotting.",
                "notes": "Mild leaf curl at the edges, but overall strong.",
                "health_score": 82,
                "moisture": 47,
                "temperature": 22.5,
                "location_name": "Greenhouse Bench",
            },
        )
        self._record_observation_in_connection(
            connection,
            {
                "plant": "SAL-001",
                "observed_at": _utc_now(),
                "summary": "New growth is visible on the tips.",
                "notes": "Needs a deeper watering cycle next week.",
                "health_score": 88,
                "moisture": 58,
                "temperature": 24.0,
                "location_name": "Orchard Row",
            },
        )
        self._create_task_in_connection(
            connection,
            {
                "title": "Water greenhouse bench",
                "plant": "AP-GT-001",
                "task_type": "water",
                "priority": 4,
                "due_at": _utc_now(),
                "notes": "Seeded demo task.",
            },
        )
        self._create_task_in_connection(
            connection,
            {
                "title": "Check orchard row moisture",
                "plant": "SAL-001",
                "task_type": "inspect",
                "priority": 3,
                "due_at": _utc_now(),
                "notes": "Seeded demo task.",
            },
        )
        conversation_id = self._create_conversation_in_connection(
            connection,
            {
                "title": "Garden notebook",
                "description": "Offline chat thread for future UI or automation work.",
            },
        )
        self._append_message_in_connection(
            connection,
            conversation_id,
            {
                "role": "assistant",
                "content": "DuckDB backend initialized and seeded.",
                "metadata": {"source": "bootstrap"},
            },
        )

    def _count(self, connection: Any, table_name: str) -> int:
        row = self._query_one(connection, f"SELECT COUNT(*) AS count FROM {table_name}") or {}
        return int(row.get("count", 0))

    def _set_meta(self, connection: Any, key: str, value: str) -> None:
        connection.execute("DELETE FROM meta WHERE key = ?", [key])
        connection.execute("INSERT INTO meta (key, value) VALUES (?, ?)", [key, value])

    def _query_all(
        self,
        connection: Any,
        sql: str,
        params: Sequence[Any] | None = None,
    ) -> list[dict[str, Any]]:
        cursor = connection.execute(sql, list(params or []))
        return _rows(cursor)

    def _query_one(
        self,
        connection: Any,
        sql: str,
        params: Sequence[Any] | None = None,
    ) -> dict[str, Any] | None:
        cursor = connection.execute(sql, list(params or []))
        return _first_row(cursor)

    def _fetch_plant(self, identifier: str) -> dict[str, Any] | None:
        with self.connection() as connection:
            return self._query_one(
                connection,
                """
                SELECT
                  p.id,
                  p.display_id,
                  p.scientific_name,
                  p.common_name,
                  p.status,
                  p.acquisition_type,
                  p.accession_date,
                  p.source_name,
                  p.source_reference,
                  p.location_id,
                  l.name AS zone_name,
                  l.name AS location_name,
                  p.container_id,
                  c.identifier AS container_identifier,
                  p.notes,
                  p.archived_at,
                  p.created_at,
                  p.updated_at
                FROM plants p
                LEFT JOIN locations l ON l.id = p.location_id
                LEFT JOIN containers c ON c.id = p.container_id
                WHERE lower(p.id) = lower(?) OR lower(p.display_id) = lower(?)
                LIMIT 1
                """,
                [identifier, identifier],
            )

    def _get_conversation_id_by_title(self, connection: Any, title: str) -> str:
        row = self._query_one(
            connection,
            "SELECT id FROM conversations WHERE title = ? ORDER BY created_at DESC LIMIT 1",
            [title],
        )
        if row is None:
            raise LookupError(f"Conversation not found: {title}")
        return str(row["id"])

    def _create_plant_in_connection(self, connection: Any, data: Mapping[str, Any]) -> str:
        scientific_name = _clean_text(data.get("scientific_name"))
        if scientific_name is None:
            raise ValueError("scientific_name is required")
        display_id = _clean_text(data.get("display_id")) or self._generate_display_id(connection)
        location_id = self._resolve_location_id(connection, data)
        container_id = self._ensure_container(
            connection,
            container_id=_clean_text(data.get("container_id")),
            container_identifier=_clean_text(data.get("container_identifier")),
        )
        plant_id = _new_id()
        now = _utc_now()
        connection.execute(
            """
            INSERT INTO plants (
              id,
              display_id,
              scientific_name,
              common_name,
              status,
              acquisition_type,
              accession_date,
              source_name,
              source_reference,
              location_id,
              container_id,
              notes,
              archived_at,
              created_at,
              updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                plant_id,
                display_id,
                scientific_name,
                _clean_text(data.get("common_name")),
                _clean_text(data.get("status")) or "active",
                _clean_text(data.get("acquisition_type")) or "unknown",
                _coerce_date(data.get("accession_date")),
                _clean_text(data.get("source_name")),
                _clean_text(data.get("source_reference")),
                location_id,
                container_id,
                _clean_text(data.get("notes")),
                _coerce_datetime(data.get("archived_at")),
                now,
                now,
            ],
        )
        self._append_event(
            connection,
            entity_type="plant",
            entity_id=plant_id,
            event_type="created",
            payload={
                "display_id": display_id,
                "scientific_name": scientific_name,
                "status": _clean_text(data.get("status")) or "active",
            },
            happened_at=now,
        )
        return plant_id

    def _record_observation_in_connection(self, connection: Any, data: Mapping[str, Any]) -> str:
        plant_identifier = _clean_text(data.get("plant"))
        if plant_identifier is None:
            raise ValueError("plant is required")
        plant = self._query_one(
            connection,
            (
                "SELECT id FROM plants "
                "WHERE lower(id) = lower(?) OR lower(display_id) = lower(?) LIMIT 1"
            ),
            [plant_identifier, plant_identifier],
        )
        if plant is None:
            raise LookupError(f"Plant not found: {plant_identifier}")
        observed_at = _coerce_datetime(data.get("observed_at"), default=_utc_now())
        location_id = self._resolve_location_id(connection, data)
        observation_id = _new_id()
        now = _utc_now()
        connection.execute(
            """
            INSERT INTO observations (
              id,
              plant_id,
              observed_at,
              observation_type,
              summary,
              notes,
              health_score,
              moisture,
              temperature,
              location_id,
              created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                observation_id,
                str(plant["id"]),
                observed_at,
                _clean_text(data.get("observation_type")) or "routine",
                _clean_text(data.get("summary")),
                _clean_text(data.get("notes")),
                _coerce_float(data.get("health_score")),
                _coerce_float(data.get("moisture")),
                _coerce_float(data.get("temperature")),
                location_id,
                now,
            ],
        )
        self._append_event(
            connection,
            entity_type="plant",
            entity_id=str(plant["id"]),
            event_type="observation_recorded",
            payload={
                "observation_id": observation_id,
                "observed_at": observed_at.isoformat() if observed_at else None,
                "summary": _clean_text(data.get("summary")),
            },
            happened_at=now,
        )
        return observation_id

    def _create_task_in_connection(
        self,
        connection: Any,
        data: Mapping[str, Any],
        *,
        plant_id: str | None = None,
    ) -> str:
        title = _clean_text(data.get("title"))
        if title is None:
            raise ValueError("title is required")
        task_type = _clean_text(data.get("task_type")) or "custom"
        priority = _coerce_int(data.get("priority")) or 3
        due_at = _coerce_datetime(data.get("due_at"))
        notes = _clean_text(data.get("notes"))
        location_id = self._resolve_location_id(connection, data, default_type="zone")
        task_id = _new_id()
        now = _utc_now()
        connection.execute(
            """
            INSERT INTO tasks (
              id,
              title,
              task_type,
              priority,
              plant_id,
              location_id,
              due_at,
              status,
              notes,
              created_at,
              updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                task_id,
                title,
                task_type,
                priority,
                plant_id,
                location_id,
                due_at,
                "open",
                notes,
                now,
                now,
            ],
        )
        self._append_event(
            connection,
            entity_type="task",
            entity_id=task_id,
            event_type="created",
            payload={"title": title, "plant_id": plant_id},
            happened_at=now,
        )
        return task_id

    def _create_conversation_in_connection(
        self,
        connection: Any,
        data: Mapping[str, Any],
    ) -> str:
        title = _clean_text(data.get("title")) or "Garden chat"
        conversation_id = _new_id()
        now = _utc_now()
        connection.execute(
            """
            INSERT INTO conversations (
              id,
              title,
              description,
              created_at,
              updated_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            [
                conversation_id,
                title,
                _clean_text(data.get("description")),
                now,
                now,
            ],
        )
        self._append_event(
            connection,
            entity_type="conversation",
            entity_id=conversation_id,
            event_type="created",
            payload={"title": title},
            happened_at=now,
        )
        return conversation_id

    def _append_message_in_connection(
        self,
        connection: Any,
        conversation_id: str,
        data: Mapping[str, Any],
    ) -> str:
        message_id = _new_id()
        now = _utc_now()
        connection.execute(
            """
            INSERT INTO messages (
              id,
              conversation_id,
              role,
              content,
              metadata_json,
              created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                message_id,
                conversation_id,
                _clean_text(data.get("role")) or "user",
                _clean_text(data.get("content")) or "",
                _json_text(data.get("metadata") or {}),
                now,
            ],
        )
        self._append_event(
            connection,
            entity_type="conversation",
            entity_id=conversation_id,
            event_type="message_appended",
            payload={
                "role": _clean_text(data.get("role")) or "user",
                "content": _clean_text(data.get("content")) or "",
            },
            happened_at=now,
        )
        return message_id

    def _get_observation(self, observation_id: str) -> dict[str, Any]:
        with self.connection() as connection:
            observation = self._query_one(
                connection,
                """
                SELECT
                  o.id,
                  o.plant_id,
                  p.display_id AS plant_display_id,
                  o.observed_at,
                  o.observation_type,
                  o.summary,
                  o.notes,
                  o.health_score,
                  o.moisture,
                  o.temperature,
                  o.location_id,
                  o.created_at
                FROM observations o
                LEFT JOIN plants p ON p.id = o.plant_id
                WHERE o.id = ?
                """,
                [observation_id],
            )
        if observation is None:
            raise RuntimeError("Observation was not persisted")
        return observation

    def _generate_display_id(self, connection: Any) -> str:
        row = self._query_one(
            connection,
            """
            SELECT COALESCE(
              MAX(CAST(regexp_extract(display_id, '(\\d+)$', 1) AS INTEGER)),
              0
            ) AS last_value
            FROM plants
            WHERE display_id LIKE 'GDN-%'
            """,
        )
        last_value = int((row or {}).get("last_value", 0))
        return f"GDN-{last_value + 1:04d}"

    def _ensure_location(
        self,
        connection: Any,
        *,
        location_id: str | None = None,
        location_name: str | None = None,
        location_type: str = "area",
    ) -> str | None:
        if location_id is not None:
            return location_id
        if location_name is None:
            return None
        row = self._query_one(
            connection,
            "SELECT id FROM locations WHERE lower(name) = lower(?) LIMIT 1",
            [location_name],
        )
        if row is not None:
            return str(row["id"])
        new_location_id = _new_id()
        now = _utc_now()
        connection.execute(
            """
            INSERT INTO locations (
              id,
              name,
              location_type,
              created_at,
              updated_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            [new_location_id, location_name, location_type, now, now],
        )
        return new_location_id

    def _ensure_container(
        self,
        connection: Any,
        *,
        container_id: str | None = None,
        container_identifier: str | None = None,
        container_type: str = "pot",
    ) -> str | None:
        if container_id is not None:
            return container_id
        if container_identifier is None:
            return None
        row = self._query_one(
            connection,
            "SELECT id FROM containers WHERE lower(identifier) = lower(?) LIMIT 1",
            [container_identifier],
        )
        if row is not None:
            return str(row["id"])
        new_container_id = _new_id()
        now = _utc_now()
        connection.execute(
            """
            INSERT INTO containers (
              id,
              identifier,
              container_type,
              created_at,
              updated_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            [new_container_id, container_identifier, container_type, now, now],
        )
        return new_container_id

    def _append_event(
        self,
        connection: Any,
        *,
        entity_type: str,
        entity_id: str,
        event_type: str,
        payload: Mapping[str, Any],
        happened_at: datetime | None = None,
    ) -> None:
        connection.execute(
            """
            INSERT INTO events (
              id,
              entity_type,
              entity_id,
              event_type,
              payload_json,
              happened_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                _new_id(),
                entity_type,
                entity_id,
                event_type,
                _json_text(payload),
                happened_at or _utc_now(),
            ],
        )

    def _event_value(self, value: Any) -> Any:
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, date):
            return value.isoformat()
        if isinstance(value, dict):
            return {key: self._event_value(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._event_value(item) for item in value]
        return value

    def _is_readonly_sql(self, sql: str) -> bool:
        normalized = sql.strip().lower()
        if not normalized or ";" in normalized:
            return False
        return normalized.startswith(
            (
                "select",
                "with",
                "describe",
                "explain",
                "show",
            ),
        )

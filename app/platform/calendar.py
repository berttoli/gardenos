from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.care.models import TaskDefinition, TaskOccurrence
from app.care.updaters import TaskScopeProjection, resolve_task_scope_projection
from app.plants.models import Plant
from app.platform.models import AutomationRun, AutomationVersion, ScheduleRule, ScopeNode

WEEKDAY_BY_NAME = {
    "MO": 0,
    "TU": 1,
    "WE": 2,
    "TH": 3,
    "FR": 4,
    "SA": 5,
    "SU": 6,
}


@dataclass(frozen=True, slots=True)
class ParsedRecurrenceRule:
    frequency: str
    interval: int = 1
    count: int | None = None
    until: datetime | None = None
    byday: tuple[int, ...] = ()
    bymonthday: tuple[int, ...] = ()
    bymonth: tuple[int, ...] = ()


@dataclass(frozen=True, slots=True)
class CalendarProjectionEntry:
    id: str
    kind: str
    title: str
    start_at: datetime
    end_at: datetime | None
    status: str
    scope_node_id: str | None
    source_kind: str
    source_id: str
    timezone: str | None
    metadata: dict[str, Any]


def _clean_text(value: Any | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _parse_int_list(value: str | None) -> tuple[int, ...]:
    text = _clean_text(value)
    if text is None:
        return ()
    entries: list[int] = []
    for part in text.split(","):
        item = part.strip()
        if not item:
            continue
        entries.append(int(item))
    return tuple(entries)


def _parse_weekdays(value: str | None) -> tuple[int, ...]:
    text = _clean_text(value)
    if text is None:
        return ()

    weekdays: list[int] = []
    for item in text.split(","):
        token = item.strip().upper()
        if not token:
            continue
        token = token[-2:]
        if token not in WEEKDAY_BY_NAME:
            raise ValueError(f"Invalid BYDAY value: {item}.")
        weekdays.append(WEEKDAY_BY_NAME[token])
    return tuple(sorted(set(weekdays)))


def _parse_rrule_datetime(value: str | None) -> datetime | None:
    text = _clean_text(value)
    if text is None:
        return None

    if text.endswith("Z") and "T" in text:
        parsed = datetime.strptime(text, "%Y%m%dT%H%M%SZ")
        return parsed.replace(tzinfo=UTC)

    if "T" in text and len(text) == 15:
        parsed = datetime.strptime(text, "%Y%m%dT%H%M%S")
        return parsed.replace(tzinfo=UTC)

    if len(text) == 8 and text.isdigit():
        parsed_date = datetime.strptime(text, "%Y%m%d").date()
        return datetime.combine(parsed_date, time.min, tzinfo=UTC)

    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:  # pragma: no cover - validated through API tests
        raise ValueError(f"Invalid UNTIL value: {text}.") from exc

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def parse_rrule(raw: str | None) -> ParsedRecurrenceRule | None:
    text = _clean_text(raw)
    if text is None:
        return None

    fields: dict[str, str] = {}
    for chunk in text.split(";"):
        token = chunk.strip()
        if not token:
            continue
        if "=" not in token:
            raise ValueError(f"Invalid RRULE token: {token}.")
        key, value = token.split("=", 1)
        fields[key.strip().upper()] = value.strip()

    frequency = fields.get("FREQ")
    if not frequency:
        raise ValueError("RRULE requires FREQ.")

    normalized_frequency = frequency.strip().upper()
    if normalized_frequency not in {"HOURLY", "MINUTELY", "DAILY", "WEEKLY", "MONTHLY", "YEARLY"}:
        raise ValueError(f"Unsupported RRULE FREQ: {normalized_frequency}.")

    interval = int(fields.get("INTERVAL", "1"))
    if interval < 1:
        raise ValueError("RRULE INTERVAL must be positive.")

    count = fields.get("COUNT")
    until = fields.get("UNTIL")

    parsed = ParsedRecurrenceRule(
        frequency=normalized_frequency,
        interval=interval,
        count=int(count) if count is not None else None,
        until=_parse_rrule_datetime(until),
        byday=_parse_weekdays(fields.get("BYDAY")),
        bymonthday=_parse_int_list(fields.get("BYMONTHDAY")),
        bymonth=tuple(
            month for month in _parse_int_list(fields.get("BYMONTH")) if 1 <= month <= 12
        ),
    )

    if parsed.count is not None and parsed.count < 1:
        raise ValueError("RRULE COUNT must be positive.")

    return parsed


def _timezone_for_name(name: str | None) -> ZoneInfo:
    timezone_name = _clean_text(name)
    if timezone_name is None:
        return ZoneInfo("UTC")

    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:  # pragma: no cover - depends on host tzdata
        return ZoneInfo("UTC")


def _normalize_datetime(value: datetime, zone: ZoneInfo) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=zone)
    return value.astimezone(zone)


def _utc_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _schedule_anchor(schedule_rule: ScheduleRule, zone: ZoneInfo) -> datetime:
    raw_anchor = schedule_rule.rule_json.get("start_at") or schedule_rule.rule_json.get("dtstart")
    if isinstance(raw_anchor, str):
        try:
            anchor = datetime.fromisoformat(raw_anchor)
        except ValueError:
            anchor = None
        else:
            return _normalize_datetime(anchor, zone)
    elif isinstance(raw_anchor, datetime):
        return _normalize_datetime(raw_anchor, zone)

    if schedule_rule.next_run_at is not None:
        return _normalize_datetime(schedule_rule.next_run_at, zone)

    return _normalize_datetime(schedule_rule.created_at, zone)


def _rule_duration_minutes(rule_json: dict[str, Any], default_minutes: int) -> int:
    value = rule_json.get("duration_minutes")
    if value is None:
        return default_minutes
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return default_minutes


def _matches_day_level(
    candidate: datetime,
    anchor: datetime,
    spec: ParsedRecurrenceRule,
) -> bool:
    candidate_date = candidate.date()
    anchor_date = anchor.date()
    days_since_anchor = (candidate_date - anchor_date).days
    if days_since_anchor < 0:
        return False

    if spec.frequency == "DAILY":
        if days_since_anchor % spec.interval != 0:
            return False
    elif spec.frequency == "WEEKLY":
        weeks_since_anchor = days_since_anchor // 7
        if weeks_since_anchor % spec.interval != 0:
            return False
        if spec.byday and candidate.weekday() not in spec.byday:
            return False
        if not spec.byday and candidate.weekday() != anchor.weekday():
            return False
    elif spec.frequency == "MONTHLY":
        months_since_anchor = (candidate.year - anchor.year) * 12 + candidate.month - anchor.month
        if months_since_anchor < 0 or months_since_anchor % spec.interval != 0:
            return False
        if spec.bymonth and candidate.month not in spec.bymonth:
            return False
        if spec.bymonthday and candidate.day not in spec.bymonthday:
            return False
        if spec.byday and candidate.weekday() not in spec.byday:
            return False
    elif spec.frequency == "YEARLY":
        years_since_anchor = candidate.year - anchor.year
        if years_since_anchor < 0 or years_since_anchor % spec.interval != 0:
            return False
        if spec.bymonth and candidate.month not in spec.bymonth:
            return False
        if spec.bymonthday and candidate.day not in spec.bymonthday:
            return False
        if spec.byday and candidate.weekday() not in spec.byday:
            return False
    else:
        return False

    if (
        spec.bymonth
        and spec.frequency != "MONTHLY"
        and candidate.month not in spec.bymonth
    ):
        return False
    if (
        spec.bymonthday
        and spec.frequency not in {"MONTHLY", "YEARLY"}
        and candidate.day not in spec.bymonthday
    ):
        return False
    if (
        spec.byday
        and spec.frequency not in {"WEEKLY", "MONTHLY", "YEARLY"}
        and candidate.weekday() not in spec.byday
    ):
        return False
    return True


def _iter_recurrence_candidates(
    anchor: datetime,
    spec: ParsedRecurrenceRule,
    *,
    start_at: datetime,
    end_at: datetime,
    limit: int,
) -> list[datetime]:
    results: list[datetime] = []
    if limit <= 0:
        return results

    if spec.frequency in {"HOURLY", "MINUTELY"}:
        if spec.frequency == "HOURLY":
            step = timedelta(hours=spec.interval)
        else:
            step = timedelta(minutes=spec.interval)
        candidate = anchor
        while candidate <= end_at and len(results) < limit:
            if candidate >= start_at:
                if spec.until is not None and candidate > spec.until:
                    break
                results.append(candidate)
                if spec.count is not None and len(results) >= spec.count:
                    break
            candidate += step
        return results

    cursor = datetime.combine(
        anchor.date(),
        anchor.timetz().replace(tzinfo=None),
        tzinfo=anchor.tzinfo,
    )
    if cursor < anchor:
        cursor = anchor
    one_day = timedelta(days=1)
    hard_limit = max(limit * 400, 400)
    iterations = 0

    while cursor <= end_at and len(results) < limit and iterations < hard_limit:
        iterations += 1
        if cursor >= start_at and _matches_day_level(cursor, anchor, spec):
            if spec.until is not None and cursor > spec.until:
                break
            results.append(cursor)
            if spec.count is not None and len(results) >= spec.count:
                break
        cursor += one_day

    return results


def calculate_schedule_rule_next_run(
    schedule_rule: ScheduleRule,
    *,
    reference_at: datetime | None = None,
) -> datetime | None:
    if schedule_rule.paused_at is not None:
        return schedule_rule.next_run_at

    if schedule_rule.next_run_at is not None and reference_at is None:
        return schedule_rule.next_run_at

    rule = parse_rrule(schedule_rule.rrule)
    if rule is None:
        return schedule_rule.next_run_at

    zone = _timezone_for_name(schedule_rule.timezone)
    anchor = _schedule_anchor(schedule_rule, zone)
    reference = _normalize_datetime(reference_at or anchor, zone)
    projected = _iter_recurrence_candidates(
        anchor,
        rule,
        start_at=reference,
        end_at=reference + timedelta(days=365 * 5),
        limit=1,
    )
    return projected[0] if projected else None


def _scope_ids_with_descendants(session: Session, scope_node_id: str | None) -> set[str] | None:
    if scope_node_id is None:
        return None

    nodes = list(session.scalars(select(ScopeNode)).all())
    children: dict[str | None, list[ScopeNode]] = {}
    for node in nodes:
        children.setdefault(node.parent_id, []).append(node)

    root = session.get(ScopeNode, scope_node_id)
    if root is None:
        return set()

    result: set[str] = set()

    def walk(node: ScopeNode) -> None:
        result.add(node.id)
        for child in children.get(node.id, []):
            walk(child)

    walk(root)
    return result


def _calendar_entry_id(prefix: str, source_id: str, start_at: datetime) -> str:
    return f"{prefix}:{source_id}:{start_at.isoformat()}"


def _project_schedule_rule(
    session: Session,
    schedule_rule: ScheduleRule,
    *,
    window_start: datetime,
    window_end: datetime,
    limit: int,
) -> list[CalendarProjectionEntry]:
    if schedule_rule.paused_at is not None:
        return []

    zone = _timezone_for_name(schedule_rule.timezone)
    anchor = _schedule_anchor(schedule_rule, zone)
    duration_minutes = _rule_duration_minutes(schedule_rule.rule_json, 30)
    title = schedule_rule.calendar_label
    if title is None and schedule_rule.automation_definition is not None:
        title = schedule_rule.automation_definition.name
    if title is None and schedule_rule.automation_version is not None:
        automation_definition = schedule_rule.automation_version.automation_definition
        if automation_definition is not None:
            title = automation_definition.name
    if title is None and schedule_rule.task_definition_id is not None:
        task_definition = session.get(TaskDefinition, schedule_rule.task_definition_id)
        title = task_definition.title if task_definition is not None else None
    if title is None:
        title = "Scheduled action"

    rule = parse_rrule(schedule_rule.rrule)
    if rule is None:
        if schedule_rule.next_run_at is None:
            return []
        start_at = _normalize_datetime(schedule_rule.next_run_at, zone)
        if start_at < window_start or start_at > window_end:
            return []
        return [
            CalendarProjectionEntry(
                id=_calendar_entry_id("schedule", schedule_rule.id, start_at),
                kind="schedule",
                title=title,
                start_at=start_at,
                end_at=start_at + timedelta(minutes=duration_minutes),
                status="scheduled",
                scope_node_id=schedule_rule.scope_node_id,
                source_kind="schedule_rule",
                source_id=schedule_rule.id,
                timezone=schedule_rule.timezone,
                metadata={
                    "trigger_kind": schedule_rule.trigger_kind,
                    "calendar_label": schedule_rule.calendar_label,
                    "rule": schedule_rule.rule_json,
                    "rrule": schedule_rule.rrule,
                },
            ),
        ]

    occurrences = _iter_recurrence_candidates(
        anchor,
        rule,
        start_at=window_start,
        end_at=window_end,
        limit=limit,
    )

    return [
        CalendarProjectionEntry(
            id=_calendar_entry_id("schedule", schedule_rule.id, occurrence),
            kind="schedule",
            title=title,
            start_at=occurrence,
            end_at=occurrence + timedelta(minutes=duration_minutes),
            status="paused" if schedule_rule.paused_at is not None else "scheduled",
            scope_node_id=schedule_rule.scope_node_id,
            source_kind="schedule_rule",
            source_id=schedule_rule.id,
            timezone=schedule_rule.timezone,
            metadata={
                "trigger_kind": schedule_rule.trigger_kind,
                "calendar_label": schedule_rule.calendar_label,
                "rule": schedule_rule.rule_json,
                "rrule": schedule_rule.rrule,
                "next_run_at": schedule_rule.next_run_at.isoformat()
                if schedule_rule.next_run_at is not None
                else None,
            },
        )
        for occurrence in occurrences
    ]


def _project_task_occurrence(
    task_occurrence: TaskOccurrence,
    *,
    scope_projection: TaskScopeProjection | None = None,
) -> CalendarProjectionEntry:
    task_definition = task_occurrence.task_definition
    plant = task_occurrence.plant
    scope_projection = scope_projection or TaskScopeProjection(
        scope_node=None,
        source_kind=None,
        source_id=None,
    )
    duration_minutes = task_definition.estimated_minutes if task_definition else None
    duration = timedelta(minutes=duration_minutes or 15)
    scheduled_for = _utc_datetime(task_occurrence.scheduled_for)
    status = "completed"
    if task_occurrence.completed_at is None and task_occurrence.skipped_at is None:
        status = "overdue" if scheduled_for < datetime.now(UTC) else "scheduled"
    elif task_occurrence.skipped_at is not None:
        status = "skipped"

    location_id = plant.current_location_id if plant and plant.current_location_id else None
    title = task_definition.title if task_definition else "Task"
    return CalendarProjectionEntry(
        id=_calendar_entry_id("task", task_occurrence.id, scheduled_for),
        kind="task",
        title=title,
        start_at=scheduled_for,
        end_at=scheduled_for + duration,
        status=status,
        scope_node_id=scope_projection.scope_node_id,
        source_kind="task_occurrence",
        source_id=task_occurrence.id,
        timezone=None,
        metadata={
            "task_definition_id": task_occurrence.task_definition_id,
            "plant_id": task_occurrence.plant_id,
            "location_id": location_id,
            "task_type": task_definition.task_type if task_definition else None,
            "performed_by": task_occurrence.performed_by,
            "completion_notes": task_occurrence.completion_notes,
            **scope_projection.as_dict(),
        },
    )


def _project_automation_run(run: AutomationRun) -> CalendarProjectionEntry:
    automation_version = run.automation_version
    automation_definition = automation_version.automation_definition
    scope_node_id = run.scope_node_id or automation_definition.scope_node_id
    start_at = _utc_datetime(run.started_at or run.created_at)
    end_at = _utc_datetime(run.ended_at) if run.ended_at is not None else None
    if end_at is None:
        end_at = start_at + timedelta(minutes=20)

    return CalendarProjectionEntry(
        id=_calendar_entry_id("run", run.id, start_at),
        kind="automation",
        title=automation_definition.name,
        start_at=start_at,
        end_at=end_at,
        status=run.status,
        scope_node_id=scope_node_id,
        source_kind="automation_run",
        source_id=run.id,
        timezone=None,
        metadata={
            "automation_version_id": run.automation_version_id,
            "schedule_rule_id": run.schedule_rule_id,
            "triggered_by": run.triggered_by,
            "reason": run.reason,
            "change_set_id": run.change_set_id,
            "event_count": len(run.events),
        },
    )


def serialize_calendar_projection_entry(entry: CalendarProjectionEntry) -> dict[str, Any]:
    return {
        "id": entry.id,
        "kind": entry.kind,
        "title": entry.title,
        "start_at": entry.start_at.isoformat(),
        "end_at": entry.end_at.isoformat() if entry.end_at else None,
        "status": entry.status,
        "scope_node_id": entry.scope_node_id,
        "source_kind": entry.source_kind,
        "source_id": entry.source_id,
        "timezone": entry.timezone,
        "metadata": entry.metadata,
    }


def build_calendar_projection(
    session: Session,
    *,
    start_at: datetime,
    end_at: datetime,
    scope_node_id: str | None = None,
    limit: int = 200,
) -> dict[str, Any]:
    scope_ids = _scope_ids_with_descendants(session, scope_node_id)
    if scope_ids is not None and not scope_ids:
        return {
            "window": {
                "start_at": start_at.isoformat(),
                "end_at": end_at.isoformat(),
                "scope_node_id": scope_node_id,
            },
            "summary": {
                "entry_count": 0,
                "schedule_entry_count": 0,
                "task_entry_count": 0,
                "automation_entry_count": 0,
                "truncated": False,
            },
            "entries": [],
        }

    schedule_rules = list(
        session.scalars(
            select(ScheduleRule)
            .options(selectinload(ScheduleRule.automation_definition))
            .options(
                selectinload(ScheduleRule.automation_version).selectinload(
                    AutomationVersion.automation_definition,
                ),
            )
            .order_by(ScheduleRule.next_run_at.is_(None), ScheduleRule.next_run_at.asc()),
        ).all()
    )
    task_occurrences = list(
        session.scalars(
            select(TaskOccurrence)
            .options(
                selectinload(TaskOccurrence.task_definition),
                selectinload(TaskOccurrence.plant).selectinload(Plant.current_location),
            )
            .order_by(TaskOccurrence.scheduled_for.asc()),
        ).all()
    )
    automation_runs = list(
        session.scalars(
            select(AutomationRun)
            .options(
                selectinload(AutomationRun.events),
                selectinload(AutomationRun.automation_version).selectinload(
                    AutomationVersion.automation_definition,
                ),
            )
            .order_by(AutomationRun.created_at.desc()),
        ).all()
    )

    entries: list[CalendarProjectionEntry] = []
    schedule_entry_count = 0
    task_entry_count = 0
    automation_entry_count = 0

    for schedule_rule in schedule_rules:
        if scope_ids is not None and schedule_rule.scope_node_id not in scope_ids:
            continue
        projected = _project_schedule_rule(
            session,
            schedule_rule,
            window_start=start_at,
            window_end=end_at,
            limit=max(1, limit - len(entries)),
        )
        if not projected:
            continue
        schedule_entry_count += len(projected)
        entries.extend(projected)
        if len(entries) >= limit:
            break

    if len(entries) < limit:
        for task_occurrence in task_occurrences:
            task_definition = task_occurrence.task_definition
            task_projection = resolve_task_scope_projection(
                session,
                task_definition,
                plant=task_occurrence.plant,
            )
            if scope_ids is not None and task_projection.scope_node_id not in scope_ids:
                continue

            scheduled_for = _utc_datetime(task_occurrence.scheduled_for)
            if scheduled_for < start_at or scheduled_for > end_at:
                continue
            entries.append(
                _project_task_occurrence(
                    task_occurrence,
                    scope_projection=task_projection,
                ),
            )
            task_entry_count += 1
            if len(entries) >= limit:
                break

    if len(entries) < limit:
        for run in automation_runs:
            scope_id = (
                run.scope_node_id
                or run.automation_version.automation_definition.scope_node_id
            )
            if scope_ids is not None and scope_id is not None and scope_id not in scope_ids:
                continue
            projected = _project_automation_run(run)
            if projected.start_at < start_at or projected.start_at > end_at:
                continue
            entries.append(projected)
            automation_entry_count += 1
            if len(entries) >= limit:
                break

    entries.sort(key=lambda item: (item.start_at, item.kind, item.title.casefold()))

    return {
        "window": {
            "start_at": start_at.isoformat(),
            "end_at": end_at.isoformat(),
            "scope_node_id": scope_node_id,
        },
        "summary": {
            "entry_count": len(entries),
            "schedule_entry_count": schedule_entry_count,
            "task_entry_count": task_entry_count,
            "automation_entry_count": automation_entry_count,
            "truncated": len(entries) >= limit,
        },
        "entries": [serialize_calendar_projection_entry(item) for item in entries],
    }

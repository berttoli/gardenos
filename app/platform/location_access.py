from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.forms import optional_str
from app.platform.models import ScopeNode


def exact_location_scope_ids(session: Session) -> dict[str, str]:
    """Return only unambiguous, explicit location-to-scope bindings.

    Names and slugs are display values, not authorization identifiers. A location
    with no binding, or bindings to multiple scopes, grants no scoped access.
    """
    candidates: dict[str, set[str]] = {}
    for node in session.scalars(select(ScopeNode)):
        location_id = optional_str(node.metadata_json.get("source_location_id"))
        if location_id is not None:
            candidates.setdefault(location_id, set()).add(node.id)
    return {
        location_id: next(iter(scope_ids))
        for location_id, scope_ids in candidates.items()
        if len(scope_ids) == 1
    }

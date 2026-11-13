from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.access.services import PrincipalContext
from app.common.forms import optional_str
from app.platform.models import ScopeNode


def _scope_nodes(session: Session) -> list[ScopeNode]:
    return list(session.scalars(select(ScopeNode)).all())


def _scope_maps(
    session: Session,
) -> tuple[dict[str, ScopeNode], dict[str | None, list[ScopeNode]]]:
    nodes = _scope_nodes(session)
    nodes_by_id = {node.id: node for node in nodes}
    children_by_parent: dict[str | None, list[ScopeNode]] = defaultdict(list)
    for node in nodes:
        children_by_parent[node.parent_id].append(node)
    return nodes_by_id, children_by_parent


def _descendant_ids(
    root_id: str,
    nodes_by_id: dict[str, ScopeNode],
    children_by_parent: dict[str | None, list[ScopeNode]],
) -> set[str]:
    root = nodes_by_id.get(root_id)
    if root is None:
        return set()

    result: set[str] = set()

    def walk(node: ScopeNode) -> None:
        result.add(node.id)
        for child in children_by_parent.get(node.id, []):
            walk(child)

    walk(root)
    return result


def _ancestor_with_type(
    node: ScopeNode,
    *,
    allowed_types: Iterable[str],
    nodes_by_id: dict[str, ScopeNode],
) -> ScopeNode | None:
    allowed = set(allowed_types)
    current = node
    while current.parent_id is not None:
        parent = nodes_by_id.get(current.parent_id)
        if parent is None:
            return None
        if parent.scope_type in allowed:
            return parent
        current = parent
    return None


def _nursery_descendants(
    node: ScopeNode,
    children_by_parent: dict[str | None, list[ScopeNode]],
) -> list[ScopeNode]:
    results: list[ScopeNode] = []

    def walk(current: ScopeNode) -> None:
        for child in children_by_parent.get(current.id, []):
            if child.scope_type == "nursery":
                results.append(child)
            walk(child)

    walk(node)
    return results


def _principal_scope_root_ids(
    session: Session,
    principal: PrincipalContext,
    *,
    nodes_by_id: dict[str, ScopeNode] | None = None,
    children_by_parent: dict[str | None, list[ScopeNode]] | None = None,
) -> tuple[str, ...]:
    if nodes_by_id is None or children_by_parent is None:
        nodes_by_id, children_by_parent = _scope_maps(session)

    if principal.is_admin:
        return tuple(
            sorted(
                node.id
                for node in nodes_by_id.values()
                if node.parent_id is None
            )
        )

    root_ids: set[str] = set()
    for scope_id in principal.scope_ids:
        node = nodes_by_id.get(scope_id)
        if node is None:
            continue

        if node.scope_type in {"organization", "nursery"}:
            root_ids.add(node.id)
            continue

        if node.scope_type == "folder":
            nursery_descendants = _nursery_descendants(node, children_by_parent)
            if nursery_descendants:
                root_ids.update(child.id for child in nursery_descendants)
                continue
            root_ids.add(node.id)
            continue

        if node.scope_type in {"site", "zone"}:
            ancestor = _ancestor_with_type(
                node,
                allowed_types={"nursery", "organization"},
                nodes_by_id=nodes_by_id,
            )
            root_ids.add(ancestor.id if ancestor is not None else node.id)
            continue

        ancestor = _ancestor_with_type(
            node,
            allowed_types={"nursery", "organization"},
            nodes_by_id=nodes_by_id,
        )
        root_ids.add(ancestor.id if ancestor is not None else node.id)

    return tuple(sorted(root_ids))


def resolve_visible_scope_ids(
    session: Session,
    principal: PrincipalContext,
    *,
    scope_node_id: str | None = None,
) -> set[str] | None:
    normalized_scope_node_id = optional_str(scope_node_id)
    nodes_by_id, children_by_parent = _scope_maps(session)

    if principal.is_admin:
        if normalized_scope_node_id is None:
            return None
        requested = nodes_by_id.get(normalized_scope_node_id)
        if requested is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Scope node not found.",
            )
        return _descendant_ids(requested.id, nodes_by_id, children_by_parent)

    allowed_root_ids = _principal_scope_root_ids(
        session,
        principal,
        nodes_by_id=nodes_by_id,
        children_by_parent=children_by_parent,
    )
    allowed_ids: set[str] = set()
    for root_id in allowed_root_ids:
        allowed_ids.update(_descendant_ids(root_id, nodes_by_id, children_by_parent))

    if normalized_scope_node_id is None:
        return allowed_ids

    requested = nodes_by_id.get(normalized_scope_node_id)
    if requested is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scope node not found.",
        )

    requested_ids = _descendant_ids(requested.id, nodes_by_id, children_by_parent)
    if not requested_ids.issubset(allowed_ids):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scope node not found.",
        )
    return requested_ids

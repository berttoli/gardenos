#!/usr/bin/env python3
from __future__ import annotations

import argparse
import http.client
import json
import os
import ssl
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from http.cookies import SimpleCookie
from pathlib import Path
from secrets import token_hex
from typing import Any, Literal
from urllib.parse import urlparse

ResultStatus = Literal["passed", "failed", "skipped"]


@dataclass(frozen=True)
class HTTPResponseData:
    status: int
    reason: str
    headers: dict[str, str]
    text: str
    json: Any | None = None


@dataclass(frozen=True)
class ProbeResult:
    name: str
    status: ResultStatus
    severity: str
    summary: str
    evidence: dict[str, Any] = field(default_factory=dict)
    patch_hints: tuple[str, ...] = ()


@dataclass(frozen=True)
class ReleaseInfo:
    source: str
    reference: str | None
    released_at: str | None
    age_days: float | None
    stale: bool


@dataclass(frozen=True)
class AuthState:
    username: str
    is_admin: bool
    csrf_token: str
    initial_cookie: str | None
    rotated_cookie: str | None


@dataclass(frozen=True)
class DrillContext:
    base_url: str
    api_host: str
    browser_origin: str
    evil_host: str
    evil_origin: str
    username: str | None
    password: str | None
    session_cookie_name: str
    rate_limit_attempts: int
    timeout: float
    insecure: bool
    stale_days: int


class DrillConnectionError(RuntimeError):
    pass


class DrillClient:
    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = 10.0,
        insecure: bool = False,
        static_headers: dict[str, str] | None = None,
    ) -> None:
        parsed = urlparse(base_url if "://" in base_url else f"http://{base_url}")
        scheme = parsed.scheme or "http"
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or (443 if scheme == "https" else 80)
        self.scheme = scheme
        self.host = host
        self.port = port
        self.timeout = timeout
        self.insecure = insecure
        self.base_path = parsed.path.rstrip("/")
        self.cookies = SimpleCookie()
        self.static_headers = dict(static_headers or {})

    def clone(self, *, static_headers: dict[str, str] | None = None) -> DrillClient:
        combined = dict(self.static_headers)
        if static_headers:
            combined.update(static_headers)
        return DrillClient(
            self.base_url,
            timeout=self.timeout,
            insecure=self.insecure,
            static_headers=combined,
        )

    @property
    def base_url(self) -> str:
        port_part = (
            f":{self.port}"
            if (
                (self.scheme == "http" and self.port != 80)
                or (self.scheme == "https" and self.port != 443)
            )
            else ""
        )
        base_path = self.base_path or ""
        return f"{self.scheme}://{self.host}{port_part}{base_path}"

    def cookie_value(self, name: str) -> str | None:
        morsel = self.cookies.get(name)
        return morsel.value if morsel is not None else None

    def request(
        self,
        method: str,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        json_body: Any | None = None,
        body: bytes | str | None = None,
        host_header: str | None = None,
        origin: str | None = None,
    ) -> HTTPResponseData:
        request_headers: dict[str, str] = {
            "Accept": "application/json",
            "User-Agent": "GardenOS-Security-Drill/0.1",
        }
        request_headers.update(self.static_headers)
        if headers:
            request_headers.update(headers)
        if host_header:
            request_headers["Host"] = host_header
        if origin:
            request_headers["Origin"] = origin
        cookie_header = self._cookie_header()
        if cookie_header:
            request_headers["Cookie"] = cookie_header

        raw_body = b""
        if json_body is not None:
            raw_body = json.dumps(json_body, separators=(",", ":"), ensure_ascii=True).encode(
                "utf-8"
            )
            request_headers.setdefault("Content-Type", "application/json")
        elif body is not None:
            raw_body = body.encode("utf-8") if isinstance(body, str) else body
        if raw_body:
            request_headers["Content-Length"] = str(len(raw_body))
        elif method.upper() in {"POST", "PUT", "PATCH", "DELETE"}:
            request_headers.setdefault("Content-Length", "0")

        resolved_path = self._resolve_path(path)
        connection = self._connection()
        try:
            connection.putrequest(
                method.upper(),
                resolved_path,
                skip_host=True,
                skip_accept_encoding=True,
            )
            for key, value in request_headers.items():
                connection.putheader(key, value)
            connection.endheaders(raw_body if raw_body else None)
            response = connection.getresponse()
            data = response.read()
            headers_map = {key.lower(): value for key, value in response.getheaders()}
            self._store_cookies(response.getheaders())
            text = data.decode("utf-8", errors="replace")
            parsed_json: Any | None = None
            content_type = headers_map.get("content-type", "").lower()
            if "application/json" in content_type and text:
                try:
                    parsed_json = json.loads(text)
                except json.JSONDecodeError:
                    parsed_json = None
            return HTTPResponseData(
                status=response.status,
                reason=response.reason,
                headers=headers_map,
                text=text,
                json=parsed_json,
            )
        except (OSError, http.client.HTTPException, TimeoutError) as exc:
            raise DrillConnectionError(str(exc)) from exc
        finally:
            connection.close()

    def _connection(self) -> http.client.HTTPConnection:
        if self.scheme == "https":
            context = (
                ssl._create_unverified_context() if self.insecure else ssl.create_default_context()
            )
            return http.client.HTTPSConnection(
                self.host,
                self.port,
                timeout=self.timeout,
                context=context,
            )
        return http.client.HTTPConnection(self.host, self.port, timeout=self.timeout)

    def _resolve_path(self, path: str) -> str:
        request_path = path if path.startswith("/") else f"/{path}"
        if not self.base_path:
            return request_path
        return f"{self.base_path}{request_path}"

    def _cookie_header(self) -> str | None:
        if not self.cookies:
            return None
        pairs = [f"{morsel.key}={morsel.value}" for morsel in self.cookies.values()]
        return "; ".join(pairs) if pairs else None

    def _store_cookies(self, response_headers: list[tuple[str, str]]) -> None:
        for key, value in response_headers:
            if key.lower() == "set-cookie":
                self.cookies.load(value)


def _truncate(text: str, limit: int = 240) -> str:
    normalized = " ".join(text.split())
    return normalized if len(normalized) <= limit else f"{normalized[:limit]}..."


def _response_excerpt(response: HTTPResponseData) -> dict[str, Any]:
    return {
        "status": response.status,
        "reason": response.reason,
        "content_type": response.headers.get("content-type"),
        "body": _truncate(response.text),
    }


def _pass(
    name: str,
    summary: str,
    *,
    evidence: dict[str, Any] | None = None,
) -> ProbeResult:
    return ProbeResult(
        name=name,
        status="passed",
        severity="info",
        summary=summary,
        evidence=evidence or {},
    )


def _skip(
    name: str,
    summary: str,
    *,
    evidence: dict[str, Any] | None = None,
) -> ProbeResult:
    return ProbeResult(
        name=name,
        status="skipped",
        severity="info",
        summary=summary,
        evidence=evidence or {},
    )


def _fail(
    name: str,
    summary: str,
    *,
    severity: str = "high",
    evidence: dict[str, Any] | None = None,
    patch_hints: tuple[str, ...] = (),
) -> ProbeResult:
    return ProbeResult(
        name=name,
        status="failed",
        severity=severity,
        summary=summary,
        evidence=evidence or {},
        patch_hints=patch_hints,
    )


def _json_field(data: Any, *keys: str) -> Any:
    value = data
    for key in keys:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def _parse_iso_datetime(text: str) -> datetime:
    normalized = text.strip()
    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _git_output(repo_root: Path, *args: str) -> str | None:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None
    text = completed.stdout.strip()
    return text or None


def _resolve_release_info(
    repo_root: Path,
    *,
    release_date: str | None,
    stale_days: int,
) -> ReleaseInfo:
    source = "git"
    reference = _git_output(repo_root, "describe", "--tags", "--always", "--dirty")
    release_at: datetime | None = None

    if release_date:
        source = "explicit"
        reference = release_date
        try:
            release_at = _parse_iso_datetime(release_date)
        except ValueError as exc:
            raise SystemExit(f"Invalid release date: {release_date}") from exc
    else:
        git_release = _git_output(repo_root, "log", "-1", "--format=%cI")
        if git_release:
            try:
                release_at = _parse_iso_datetime(git_release)
            except ValueError:
                release_at = None

    if release_at is None:
        return ReleaseInfo(
            source=source,
            reference=reference,
            released_at=None,
            age_days=None,
            stale=True,
        )

    age_days = max(0.0, (datetime.now(UTC) - release_at).total_seconds() / 86400)
    return ReleaseInfo(
        source=source,
        reference=reference,
        released_at=release_at.isoformat(),
        age_days=age_days,
        stale=age_days >= stale_days,
    )


def _select_mode(mode_arg: str, release: ReleaseInfo, stale_days: int) -> tuple[str, str]:
    if mode_arg == "baseline":
        return "baseline", "forced baseline mode"
    if mode_arg == "deep":
        return "deep", "forced deep mode"
    if release.age_days is None:
        return "deep", "release age unavailable; defaulting to deep mode"
    if release.age_days >= stale_days:
        return "deep", f"release age {release.age_days:.1f} days >= {stale_days}"
    return "baseline", f"release age {release.age_days:.1f} days < {stale_days}"


def _resolve_credentials() -> tuple[str | None, str | None]:
    username = os.getenv("GARDENOS_DRILL_USERNAME") or os.getenv("ADMIN_USERNAME")
    password = os.getenv("GARDENOS_DRILL_PASSWORD") or os.getenv("ADMIN_PASSWORD")
    return username or None, password or None


def _build_context(args: argparse.Namespace) -> DrillContext:
    username, password = _resolve_credentials()
    return DrillContext(
        base_url=args.base_url,
        api_host=args.api_host,
        browser_origin=args.browser_origin,
        evil_host=args.evil_host,
        evil_origin=args.evil_origin,
        username=args.username or username,
        password=args.password or password,
        session_cookie_name=args.session_cookie_name,
        rate_limit_attempts=args.rate_limit_attempts,
        timeout=args.timeout,
        insecure=args.insecure,
        stale_days=args.stale_days,
    )


def _run_unauthenticated_probes(client: DrillClient, ctx: DrillContext) -> list[ProbeResult]:
    probes: list[ProbeResult] = []
    routes: list[tuple[str, str, dict[str, Any] | None]] = [
        ("GET", "/api/v1/plants", None),
        ("GET", "/api/v1/tasks", None),
        ("GET", "/api/v1/conversations", None),
        ("POST", "/api/v1/plants", {"scientific_name": "Acer palmatum"}),
        ("POST", "/api/v1/conversations", {"title": "Security drill"}),
        ("POST", "/api/v1/onboarding/drafts", None),
        ("PATCH", "/api/v1/onboarding/drafts/example-token/steps/1", {"step": 1}),
        ("POST", "/api/v1/conversations/example-token/messages", {"content": "hi"}),
    ]
    for method, path, payload in routes:
        name = f"unauthenticated_{method.lower()}_{path.replace('/', '_').strip('_')}"
        try:
            response = client.request(method, path, json_body=payload, host_header=ctx.api_host)
        except DrillConnectionError as exc:
            probes.append(
                _fail(
                    name,
                    f"Unable to reach {path}: {exc}",
                    evidence={"method": method, "path": path},
                    patch_hints=("compose.yaml", "infra/traefik/dynamic.yml"),
                ),
            )
            continue
        if response.status == 401:
            probes.append(
                _pass(
                    name,
                    f"{method} {path} stayed behind authentication.",
                    evidence={"expected_status": 401, **_response_excerpt(response)},
                ),
            )
        else:
            probes.append(
                _fail(
                    name,
                    f"{method} {path} returned {response.status} instead of 401.",
                    evidence={"expected_status": 401, **_response_excerpt(response)},
                    patch_hints=("app/dependencies.py", "app/api/v1/router.py"),
                ),
            )
    return probes


def _run_origin_probes(client: DrillClient, ctx: DrillContext) -> list[ProbeResult]:
    probes: list[ProbeResult] = []

    allowed = client.request(
        "GET",
        "/api/v1/auth/context",
        host_header=ctx.api_host,
        origin=ctx.browser_origin,
    )
    allow_origin = allowed.headers.get("access-control-allow-origin")
    allow_credentials = allowed.headers.get("access-control-allow-credentials")
    if allowed.status == 200 and allow_origin == ctx.browser_origin and allow_credentials == "true":
        probes.append(
            _pass(
                "allowed_origin",
                f"{ctx.browser_origin} is accepted as a browser origin.",
                evidence={
                    "expected_origin": ctx.browser_origin,
                    "allow_origin": allow_origin,
                    "allow_credentials": allow_credentials,
                    **_response_excerpt(allowed),
                },
            ),
        )
    else:
        probes.append(
            _fail(
                "allowed_origin",
                f"{ctx.browser_origin} was not echoed back as an allowed browser origin.",
                evidence={
                    "expected_origin": ctx.browser_origin,
                    "allow_origin": allow_origin,
                    "allow_credentials": allow_credentials,
                    **_response_excerpt(allowed),
                },
                patch_hints=("app/main.py", "app/config.py"),
            ),
        )

    denied = client.request(
        "GET",
        "/api/v1/auth/context",
        host_header=ctx.api_host,
        origin=ctx.evil_origin,
    )
    if denied.headers.get("access-control-allow-origin") is None:
        probes.append(
            _pass(
                "untrusted_origin",
                f"{ctx.evil_origin} did not receive CORS access.",
                evidence={
                    "origin": ctx.evil_origin,
                    "allow_origin": None,
                    **_response_excerpt(denied),
                },
            ),
        )
    else:
        probes.append(
            _fail(
                "untrusted_origin",
                f"{ctx.evil_origin} was reflected in CORS headers.",
                evidence={
                    "origin": ctx.evil_origin,
                    "allow_origin": denied.headers.get("access-control-allow-origin"),
                    **_response_excerpt(denied),
                },
                patch_hints=("app/main.py", "app/config.py"),
            ),
        )

    return probes


def _run_host_probes(client: DrillClient, ctx: DrillContext) -> list[ProbeResult]:
    probes: list[ProbeResult] = []

    trusted = client.request("GET", "/health/live", host_header=ctx.api_host)
    if trusted.status == 200:
        probes.append(
            _pass(
                "trusted_host",
                f"{ctx.api_host} was accepted by the ingress trust boundary.",
                evidence={"host": ctx.api_host, **_response_excerpt(trusted)},
            ),
        )
    else:
        probes.append(
            _fail(
                "trusted_host",
                f"{ctx.api_host} returned {trusted.status} instead of 200.",
                evidence={"host": ctx.api_host, **_response_excerpt(trusted)},
                patch_hints=("app/main.py", "compose.yaml", "infra/traefik/dynamic.yml"),
            ),
        )

    denied = client.request("GET", "/health/live", host_header=ctx.evil_host)
    if denied.status == 400:
        probes.append(
            _pass(
                "untrusted_host",
                f"{ctx.evil_host} was rejected by TrustedHostMiddleware.",
                evidence={"host": ctx.evil_host, **_response_excerpt(denied)},
            ),
        )
    else:
        probes.append(
            _fail(
                "untrusted_host",
                f"{ctx.evil_host} returned {denied.status} instead of 400.",
                evidence={"host": ctx.evil_host, **_response_excerpt(denied)},
                patch_hints=("app/main.py", "compose.yaml", "infra/traefik/dynamic.yml"),
            ),
        )

    return probes


def _authenticate_admin(
    client: DrillClient, ctx: DrillContext
) -> tuple[list[ProbeResult], AuthState | None]:
    probes: list[ProbeResult] = []
    if not ctx.username or not ctx.password:
        probes.append(
            _skip(
                "login_session",
                "Skipped authenticated probes because no drill credentials were provided.",
                evidence={
                    "hint": (
                        "Set GARDENOS_DRILL_USERNAME and GARDENOS_DRILL_PASSWORD, or "
                        "ADMIN_USERNAME and ADMIN_PASSWORD."
                    ),
                },
            ),
        )
        return probes, None

    session = client.request("GET", "/api/v1/auth/session", host_header=ctx.api_host)
    if session.status != 200 or not isinstance(session.json, dict):
        probes.append(
            _fail(
                "login_session",
                "Could not obtain an initial CSRF token.",
                evidence=_response_excerpt(session),
                patch_hints=("app/api/v1/auth.py", "app/security.py"),
            ),
        )
        return probes, None

    csrf_token = session.json.get("csrf_token")
    if not isinstance(csrf_token, str) or not csrf_token:
        probes.append(
            _fail(
                "login_session",
                "The CSRF token endpoint returned an empty token.",
                evidence={"session_payload": session.json, **_response_excerpt(session)},
                patch_hints=("app/security.py",),
            ),
        )
        return probes, None

    initial_cookie = client.cookie_value(ctx.session_cookie_name)
    login = client.request(
        "POST",
        "/api/v1/auth/login",
        host_header=ctx.api_host,
        json_body={
            "username": ctx.username,
            "password": ctx.password,
            "csrf_token": csrf_token,
            "next": "//evil.example",
        },
    )
    login_payload = login.json if isinstance(login.json, dict) else {}
    authenticated = bool(login_payload.get("authenticated"))
    rotated_cookie = client.cookie_value(ctx.session_cookie_name)
    refreshed = client.request("GET", "/api/v1/auth/session", host_header=ctx.api_host)
    refreshed_payload = refreshed.json if isinstance(refreshed.json, dict) else {}
    refreshed_csrf = refreshed_payload.get("csrf_token")

    if login.status != 200 or not authenticated:
        probes.append(
            _fail(
                "login_session",
                "Configured drill credentials could not log in.",
                evidence={
                    "username": ctx.username,
                    **_response_excerpt(login),
                    "login_payload": login_payload,
                },
                patch_hints=("app/api/v1/auth.py", "app/auth/services.py"),
            ),
        )
        return probes, None

    if rotated_cookie and initial_cookie and rotated_cookie != initial_cookie:
        probes.append(
            _pass(
                "session_rotation",
                "Login rotated the session cookie.",
                evidence={
                    "cookie_name": ctx.session_cookie_name,
                    "initial_cookie": initial_cookie,
                    "rotated_cookie": rotated_cookie,
                    **_response_excerpt(login),
                },
            ),
        )
    else:
        probes.append(
            _fail(
                "session_rotation",
                "Login did not rotate the session cookie.",
                evidence={
                    "cookie_name": ctx.session_cookie_name,
                    "initial_cookie": initial_cookie,
                    "rotated_cookie": rotated_cookie,
                    **_response_excerpt(login),
                },
                patch_hints=("app/main.py", "app/api/v1/auth.py"),
            ),
        )

    next_url = login_payload.get("next_url")
    if next_url == "/":
        probes.append(
            _pass(
                "login_next_sanitized",
                "Open-redirect payload was collapsed to /.",
                evidence={"requested_next": "//evil.example", "next_url": next_url},
            ),
        )
    else:
        probes.append(
            _fail(
                "login_next_sanitized",
                "Login accepted an unsafe next URL.",
                severity="medium",
                evidence={
                    "requested_next": "//evil.example",
                    "next_url": next_url,
                    "login_payload": login_payload,
                },
                patch_hints=("app/api/v1/auth.py",),
            ),
        )

    context_response = client.request("GET", "/api/v1/auth/context", host_header=ctx.api_host)
    context_payload = context_response.json if isinstance(context_response.json, dict) else {}
    principal = (
        context_payload.get("principal")
        if isinstance(context_payload.get("principal"), dict)
        else {}
    )
    if context_payload.get("authenticated") is True and principal.get("kind") == "user":
        probes.append(
            _pass(
                "auth_context_after_login",
                "Authenticated session was visible to the auth context endpoint.",
                evidence={
                    "authenticated": context_payload.get("authenticated"),
                    "principal_kind": principal.get("kind"),
                    "principal_is_admin": principal.get("is_admin"),
                },
            ),
        )
    else:
        probes.append(
            _fail(
                "auth_context_after_login",
                "The auth context endpoint did not reflect the logged-in session.",
                evidence={
                    "context_payload": context_payload,
                    **_response_excerpt(context_response),
                },
                patch_hints=("app/api/v1/auth.py", "app/access/dependencies.py"),
            ),
        )

    if not isinstance(refreshed_csrf, str) or not refreshed_csrf:
        probes.append(
            _fail(
                "csrf_refresh",
                "Could not refresh a CSRF token after login.",
                evidence={"session_payload": refreshed_payload, **_response_excerpt(refreshed)},
                patch_hints=("app/security.py", "app/api/v1/auth.py"),
            ),
        )
        return probes, None

    return (
        probes,
        AuthState(
            username=ctx.username,
            is_admin=bool(principal.get("is_admin")),
            csrf_token=refreshed_csrf,
            initial_cookie=initial_cookie,
            rotated_cookie=rotated_cookie,
        ),
    )


def _run_csrf_probes(client: DrillClient, ctx: DrillContext, auth: AuthState) -> list[ProbeResult]:
    probes: list[ProbeResult] = []

    write_response = client.request(
        "POST",
        "/api/v1/plants",
        host_header=ctx.api_host,
        json_body={"scientific_name": "Acer palmatum"},
    )
    if write_response.status == 403:
        probes.append(
            _pass(
                "csrf_write_protection",
                "Authenticated writes still required an X-CSRF-Token header.",
                evidence=_response_excerpt(write_response),
            ),
        )
    else:
        probes.append(
            _fail(
                "csrf_write_protection",
                f"Authenticated writes returned {write_response.status} instead of 403.",
                evidence=_response_excerpt(write_response),
                patch_hints=("app/dependencies.py", "app/api/v1/auth.py"),
            ),
        )

    logout_response = client.request(
        "POST",
        "/api/v1/auth/logout",
        host_header=ctx.api_host,
        json_body={},
    )
    if logout_response.status == 403:
        probes.append(
            _pass(
                "csrf_logout_protection",
                "Logout also required the CSRF header.",
                evidence=_response_excerpt(logout_response),
            ),
        )
    else:
        probes.append(
            _fail(
                "csrf_logout_protection",
                f"Logout returned {logout_response.status} instead of 403.",
                evidence=_response_excerpt(logout_response),
                patch_hints=("app/dependencies.py", "app/api/v1/auth.py"),
            ),
        )

    return probes


def _run_service_token_probe(
    client: DrillClient,
    ctx: DrillContext,
    auth: AuthState,
) -> list[ProbeResult]:
    probes: list[ProbeResult] = []
    if not auth.is_admin:
        probes.append(
            _skip(
                "service_token_boundary",
                "Skipped the service-token privilege boundary probe because the drill login "
                "was not admin-capable.",
                evidence={"username": auth.username, "is_admin": auth.is_admin},
            ),
        )
        return probes

    token_label = f"security-drill-{token_hex(4)}"
    token_service_account = "garden-automation"
    create_response = client.request(
        "POST",
        f"/api/v1/access/service-accounts/{token_service_account}/tokens",
        host_header=ctx.api_host,
        headers={"X-CSRF-Token": auth.csrf_token},
        json_body={"label": token_label},
    )
    create_payload = create_response.json if isinstance(create_response.json, dict) else {}
    token_record = (
        create_payload.get("token_record")
        if isinstance(create_payload.get("token_record"), dict)
        else {}
    )
    token_value = create_payload.get("token")
    token_id = token_record.get("id")

    if (
        create_response.status != 201
        or not isinstance(token_value, str)
        or not token_value
        or not token_id
    ):
        probes.append(
            _fail(
                "service_token_mint",
                "Could not mint a temporary service-account token for the drill.",
                evidence={
                    "service_account": token_service_account,
                    "payload": create_payload,
                    **_response_excerpt(create_response),
                },
                patch_hints=("app/api/v1/access.py", "app/access/services.py"),
            ),
        )
        return probes

    token_client = DrillClient(
        ctx.base_url,
        timeout=ctx.timeout,
        insecure=ctx.insecure,
        static_headers={"Authorization": f"Bearer {token_value}"},
    )
    try:
        auth_context_response = token_client.request(
            "GET",
            "/api/v1/auth/context",
            host_header=ctx.api_host,
        )
        auth_context_payload = (
            auth_context_response.json if isinstance(auth_context_response.json, dict) else {}
        )
        principal = (
            auth_context_payload.get("principal")
            if isinstance(auth_context_payload.get("principal"), dict)
            else {}
        )
        if (
            auth_context_response.status == 200
            and principal.get("kind") == "service_account"
            and principal.get("auth_method") == "service_token"
        ):
            probes.append(
                _pass(
                    "service_token_authenticates",
                    "A temporary service token was recognized as a service account.",
                    evidence={
                        "principal_kind": principal.get("kind"),
                        "auth_method": principal.get("auth_method"),
                        "service_account_slug": principal.get("service_account_slug"),
                    },
                ),
            )
        else:
            probes.append(
                _fail(
                    "service_token_authenticates",
                    "The service token did not authenticate as a service account.",
                    evidence={
                        "payload": auth_context_payload,
                        **_response_excerpt(auth_context_response),
                    },
                    patch_hints=("app/access/dependencies.py", "app/access/services.py"),
                ),
            )

        deny_response = token_client.request(
            "POST",
            "/api/v1/access/service-accounts",
            host_header=ctx.api_host,
            json_body={
                "slug": f"blocked-{token_hex(3)}",
                "name": "Blocked Drill Account",
            },
        )
        if deny_response.status == 403:
            probes.append(
                _pass(
                    "service_token_admin_boundary",
                    "The service token could not create a new service account.",
                    evidence=_response_excerpt(deny_response),
                ),
            )
        else:
            probes.append(
                _fail(
                    "service_token_admin_boundary",
                    (
                        f"The service token returned {deny_response.status} instead of 403 "
                        "on an admin-only route."
                    ),
                    severity="critical",
                    evidence=_response_excerpt(deny_response),
                    patch_hints=("app/api/v1/access.py", "app/access/dependencies.py"),
                ),
            )
    finally:
        cleanup_response = client.request(
            "DELETE",
            f"/api/v1/access/service-accounts/{token_service_account}/tokens/{token_id}",
            host_header=ctx.api_host,
            headers={"X-CSRF-Token": auth.csrf_token},
        )
        if cleanup_response.status == 200:
            probes.append(
                _pass(
                    "service_token_cleanup",
                    "The temporary drill token was revoked after use.",
                    evidence={
                        "service_account": token_service_account,
                        **_response_excerpt(cleanup_response),
                    },
                ),
            )
        else:
            probes.append(
                _fail(
                    "service_token_cleanup",
                    "The temporary drill token could not be revoked.",
                    severity="medium",
                    evidence={
                        "service_account": token_service_account,
                        "token_id": token_id,
                        **_response_excerpt(cleanup_response),
                    },
                    patch_hints=("app/api/v1/access.py", "app/access/services.py"),
                ),
            )

    return probes


def _run_rate_limit_probe(client: DrillClient, ctx: DrillContext) -> list[ProbeResult]:
    probes: list[ProbeResult] = []
    csrf_response = client.request("GET", "/api/v1/auth/session", host_header=ctx.api_host)
    csrf_payload = csrf_response.json if isinstance(csrf_response.json, dict) else {}
    csrf_token = csrf_payload.get("csrf_token")
    if not isinstance(csrf_token, str) or not csrf_token:
        probes.append(
            _fail(
                "rate_limit_setup",
                "Could not acquire a CSRF token for the rate-limit probe.",
                evidence={"session_payload": csrf_payload, **_response_excerpt(csrf_response)},
                patch_hints=("app/api/v1/auth.py", "app/security.py"),
            ),
        )
        return probes

    for attempt in range(ctx.rate_limit_attempts):
        username = f"drill-{attempt}"
        response = client.request(
            "POST",
            "/api/v1/auth/login",
            host_header=ctx.api_host,
            json_body={
                "username": username,
                "password": "incorrect-password",
                "csrf_token": csrf_token,
            },
        )
        if response.status == 401:
            probes.append(
                _pass(
                    f"rate_limit_attempt_{attempt + 1}",
                    "A bogus login attempt was rejected.",
                    evidence={"attempt": attempt + 1, **_response_excerpt(response)},
                ),
            )
        else:
            probes.append(
                _fail(
                    f"rate_limit_attempt_{attempt + 1}",
                    f"Login attempt {attempt + 1} returned {response.status} instead of 401.",
                    evidence={"attempt": attempt + 1, **_response_excerpt(response)},
                    patch_hints=("app/api/v1/auth.py", "app/core/rate_limit.py"),
                ),
            )

    final_response = client.request(
        "POST",
        "/api/v1/auth/login",
        host_header=ctx.api_host,
        json_body={
            "username": "drill-final",
            "password": "incorrect-password",
            "csrf_token": csrf_token,
        },
    )
    if final_response.status == 429:
        probes.append(
            _pass(
                "rate_limit_host_bucket",
                "The host-wide login bucket blocked the final brute-force attempt.",
                evidence=_response_excerpt(final_response),
            ),
        )
    else:
        probes.append(
            _fail(
                "rate_limit_host_bucket",
                f"The final brute-force attempt returned {final_response.status} instead of 429.",
                evidence=_response_excerpt(final_response),
                patch_hints=("app/api/v1/auth.py", "app/core/rate_limit.py"),
            ),
        )

    return probes


def _run_drill(
    client: DrillClient,
    ctx: DrillContext,
    *,
    release_info: ReleaseInfo,
    mode: str,
) -> tuple[list[ProbeResult], AuthState | None]:
    probes: list[ProbeResult] = []
    auth_state: AuthState | None = None

    probes.extend(_run_unauthenticated_probes(client, ctx))
    probes.extend(_run_host_probes(client, ctx))
    probes.extend(_run_origin_probes(client, ctx))

    auth_probes, auth_state = _authenticate_admin(client, ctx)
    probes.extend(auth_probes)

    if auth_state is not None:
        probes.extend(_run_csrf_probes(client, ctx, auth_state))
        if mode == "deep":
            probes.extend(_run_service_token_probe(client, ctx, auth_state))
    elif mode == "deep":
        probes.append(
            _skip(
                "service_token_boundary",
                "Skipped the deep privilege-boundary probe because authenticated drill "
                "credentials were unavailable.",
            ),
        )

    probes.extend(
        _run_rate_limit_probe(
            DrillClient(ctx.base_url, timeout=ctx.timeout, insecure=ctx.insecure), ctx
        )
    )
    return probes, auth_state


def _count_results(probes: list[ProbeResult]) -> dict[str, int]:
    counts = {"passed": 0, "failed": 0, "skipped": 0, "total": len(probes)}
    for probe in probes:
        counts[probe.status] += 1
    return counts


def _render_summary(
    *,
    mode: str,
    mode_reason: str,
    release_info: ReleaseInfo,
    stale_days: int,
    counts: dict[str, int],
    report_path: Path,
    auth_state: AuthState | None,
) -> None:
    print(f"GardenOS security drill finished in {mode} mode.")
    print(f"Mode selection: {mode_reason}.")
    if release_info.released_at is not None and release_info.age_days is not None:
        print(f"Release age: {release_info.age_days:.1f} days (stale threshold {stale_days})")
    else:
        print("Release age: unavailable")
    print(
        "Probe counts: "
        f"{counts['passed']} passed, {counts['failed']} failed, {counts['skipped']} skipped, "
        f"{counts['total']} total",
    )
    if auth_state is not None:
        print(f"Authenticated drill user: {auth_state.username} (admin={auth_state.is_admin})")
    print(f"Report written to: {report_path}")


def _report_payload(
    *,
    started_at: datetime,
    finished_at: datetime,
    repo_root: Path,
    base_url: str,
    api_host: str,
    browser_origin: str,
    mode: str,
    mode_reason: str,
    release_info: ReleaseInfo,
    probes: list[ProbeResult],
    auth_state: AuthState | None,
    ctx: DrillContext,
) -> dict[str, Any]:
    counts = _count_results(probes)
    git_ref = _git_output(repo_root, "rev-parse", "--short", "HEAD")
    git_branch = _git_output(repo_root, "branch", "--show-current")
    findings = [asdict(probe) for probe in probes if probe.status == "failed"]
    return {
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "duration_seconds": round((finished_at - started_at).total_seconds(), 3),
        "base_url": base_url,
        "api_host": api_host,
        "browser_origin": browser_origin,
        "mode": mode,
        "mode_reason": mode_reason,
        "release": asdict(release_info) | {"stale_days": ctx.stale_days},
        "git": {
            "commit": git_ref,
            "branch": git_branch,
        },
        "auth": None
        if auth_state is None
        else {
            "username": auth_state.username,
            "is_admin": auth_state.is_admin,
            "session_cookie_name": ctx.session_cookie_name,
            "session_cookie_rotated": auth_state.rotated_cookie != auth_state.initial_cookie,
        },
        "counts": counts,
        "findings": findings,
        "probes": [asdict(probe) for probe in probes],
    }


def _write_report(report_dir: Path, report: dict[str, Any], mode: str) -> Path:
    report_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    report_path = report_dir / f"security-drill-{timestamp}-{mode}.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return report_path


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the offline GardenOS security drill against the local ingress.",
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv("GARDENOS_DRILL_BASE_URL", "http://127.0.0.1:8000"),
        help="Connection target for the drill client.",
    )
    parser.add_argument(
        "--api-host",
        default=os.getenv("GARDENOS_DRILL_API_HOST", "api.gardenos.example.test"),
        help="Host header to present to the backend.",
    )
    parser.add_argument(
        "--browser-origin",
        default=os.getenv("GARDENOS_DRILL_BROWSER_ORIGIN", "http://gardenos.example.test"),
        help="Origin to use for the CORS probe.",
    )
    parser.add_argument(
        "--evil-host",
        default=os.getenv("GARDENOS_DRILL_EVIL_HOST", "evil.example.com"),
        help="Host header that should be rejected.",
    )
    parser.add_argument(
        "--evil-origin",
        default=os.getenv("GARDENOS_DRILL_EVIL_ORIGIN", "http://evil.example.com"),
        help="Origin that should not be granted CORS access.",
    )
    parser.add_argument(
        "--username",
        default=os.getenv("GARDENOS_DRILL_USERNAME") or os.getenv("ADMIN_USERNAME"),
        help="Admin-capable username for authenticated probes.",
    )
    parser.add_argument(
        "--password",
        default=os.getenv("GARDENOS_DRILL_PASSWORD") or os.getenv("ADMIN_PASSWORD"),
        help="Password for the drill username.",
    )
    parser.add_argument(
        "--session-cookie-name",
        default=os.getenv("SESSION_COOKIE_NAME", "garden_os_session"),
        help="Session cookie name used to check rotation.",
    )
    parser.add_argument(
        "--rate-limit-attempts",
        type=int,
        default=int(os.getenv("LOGIN_RATE_LIMIT_ATTEMPTS", "5")),
        help="Number of failed logins to consume before the final host-bucket check.",
    )
    parser.add_argument(
        "--stale-days",
        type=int,
        default=int(os.getenv("GARDENOS_DRILL_STALE_DAYS", "7")),
        help="Threshold after which the drill automatically switches to deep mode.",
    )
    parser.add_argument(
        "--mode",
        choices=("auto", "baseline", "deep"),
        default=os.getenv("GARDENOS_DRILL_MODE", "auto"),
        help="Control whether the drill runs the baseline or deep probe set.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=float(os.getenv("GARDENOS_DRILL_TIMEOUT", "10")),
        help="Socket timeout in seconds.",
    )
    parser.add_argument(
        "--report-dir",
        type=Path,
        default=Path(os.getenv("GARDENOS_DRILL_REPORT_DIR", "reports/security-drills")),
        help="Directory for JSON drill reports.",
    )
    parser.add_argument(
        "--release-date",
        default=os.getenv("GARDENOS_RELEASE_DATE"),
        help="Explicit release timestamp in ISO-8601 format.",
    )
    parser.add_argument(
        "--insecure",
        action=argparse.BooleanOptionalAction,
        default=os.getenv("GARDENOS_DRILL_INSECURE", "").strip().lower()
        in {"1", "true", "yes", "on"},
        help="Disable TLS verification when the base URL uses HTTPS.",
    )
    parser.add_argument(
        "--fail-on-findings",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Exit non-zero if any probe fails.",
    )
    return parser


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    parser = _build_parser()
    args = parser.parse_args()
    ctx = _build_context(args)

    release_info = _resolve_release_info(
        repo_root,
        release_date=args.release_date,
        stale_days=ctx.stale_days,
    )
    mode, mode_reason = _select_mode(args.mode, release_info, ctx.stale_days)

    started_at = datetime.now(UTC)
    client = DrillClient(
        ctx.base_url,
        timeout=ctx.timeout,
        insecure=ctx.insecure,
    )

    probes, auth_state = _run_drill(
        client,
        ctx,
        release_info=release_info,
        mode=mode,
    )

    finished_at = datetime.now(UTC)
    report = _report_payload(
        started_at=started_at,
        finished_at=finished_at,
        repo_root=repo_root,
        base_url=ctx.base_url,
        api_host=ctx.api_host,
        browser_origin=ctx.browser_origin,
        mode=mode,
        mode_reason=mode_reason,
        release_info=release_info,
        probes=probes,
        auth_state=auth_state,
        ctx=ctx,
    )
    report_path = _write_report(args.report_dir, report, mode)
    counts = report["counts"]

    _render_summary(
        mode=mode,
        mode_reason=mode_reason,
        release_info=release_info,
        stale_days=ctx.stale_days,
        counts=counts,
        report_path=report_path,
        auth_state=auth_state,
    )

    if counts["failed"] and args.fail_on_findings:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

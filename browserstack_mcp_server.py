"""
BrowserStack MCP server for the Repro / step_reproduction_app project.

Exposes read, tagging, and deletion tools over the BrowserStack Automate REST API
so an AI agent (Claude Desktop, claude.ai custom connector, etc.) can inspect
running/completed builds and sessions, pull logs/steps/network data, and clean
up old sessions or builds.

Deliberately does NOT expose a "stop build/session" tool: BrowserStack's public
Automate REST API has no documented way to forcibly terminate an in-progress
session or build. A live Selenium session only ends when the test's own
WebDriver calls quit(), or BrowserStack's own idle/session timeout fires. See
README.md for details.

This module reuses the pure BrowserStack-fetching functions already written in
app.py (fetch_session, fetch_logs, parse_steps, extract_eux_bo_url, etc.) so the
logic here stays in sync with the existing Flask app rather than drifting from
a second, hand-copied implementation. Importing app.py does NOT start its Flask
server (guarded by `if __name__ == "__main__"`), and this process is independent
from wherever app.py's Flask server actually runs, so overriding module-level
flags like IS_SERVERLESS here has no effect on that deployment.

Run locally (stdio, for Claude Desktop's local MCP config):
    python browserstack_mcp_server.py --stdio

Run as a remote HTTP server (Streamable HTTP transport):
    python browserstack_mcp_server.py
    # listens on 0.0.0.0:$PORT (default 8000)

Required env vars:
    AUTOMATION_BS_USER   BrowserStack username
    AUTOMATION_BS_PASS   BrowserStack access key

Strongly recommended env var when running as a remote HTTP server:
    MCP_API_KEY          Shared bearer token. Without it, ANYONE who finds the
                          server's URL can list, tag, and delete your builds
                          and sessions. If unset, the server logs a loud
                          warning at startup and runs with no auth.
"""

from __future__ import annotations

import builtins
import os
import sys
from typing import Annotated, Optional

import requests
from pydantic import Field

# `app.py` lives next to this file. Python automatically puts the running
# script's own directory at the front of sys.path, so this import resolves
# regardless of the process's current working directory.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# --- CRITICAL for stdio transport (--stdio mode) ---
# app.py liberally uses print() for debug logging (fine for a Flask app's
# console). Over stdio, stdout is the ONLY channel carrying JSON-RPC messages
# to the client -- a single stray print() corrupts the protocol stream and
# looks like a dropped connection. app.py prints a line at import time, before
# we can patch anything, so stdout is redirected to stderr just for the import.
_real_stdout = sys.stdout
sys.stdout = sys.stderr
try:
    import app as bsapp  # noqa: E402  (import after sys.path tweak, by design)
finally:
    sys.stdout = _real_stdout

# app.py's functions call bare print() (name lookup: local -> module globals ->
# builtins). Injecting a `print` into app's own module namespace shadows the
# builtin for every print() call made from inside app.py's functions during
# tool execution, without touching sys.stdout globally -- which stdio mode
# needs untouched to talk to the client, and which the HTTP mode doesn't use
# for protocol messages anyway.
bsapp.print = lambda *a, **k: builtins.print(*a, **{**k, "file": sys.stderr})

from mcp.server.fastmcp import FastMCP  # noqa: E402

# This MCP server does lightweight JSON round-trips only (no video embedding,
# no HTML rendering), so the memory-safety gate app.py applies on serverless
# hosts doesn't apply here. This assignment only affects THIS process's copy
# of the imported module, not the separate process running the real Flask app.
bsapp.IS_SERVERLESS = False

BS_AUTOMATE_BASE = "https://api.browserstack.com/automate"

mcp = FastMCP(
    name="browserstack-qa",
    instructions=(
        "Tools for inspecting and managing WalkMe QA Automate (Selenium) builds "
        "and sessions on BrowserStack: list running/completed builds, drill into "
        "a session's logs/steps/errors/network calls, find the last successful "
        "run of a test, tag a session's pass/fail result, and delete stale "
        "sessions or builds. There is no tool to stop a currently running "
        "session/build -- BrowserStack's public API does not support that."
    ),
)


# ---------------------------------------------------------------------------
# Internal helpers (plain functions; not exposed to the MCP client directly)
# ---------------------------------------------------------------------------

def _auth() -> tuple[str, str]:
    if not bsapp.BS_USERNAME or not bsapp.BS_ACCESS_KEY:
        raise RuntimeError(
            "BrowserStack credentials not configured on this server. "
            "Set AUTOMATION_BS_USER and AUTOMATION_BS_PASS."
        )
    return (bsapp.BS_USERNAME, bsapp.BS_ACCESS_KEY)


def _slim_build(build: dict) -> dict:
    return {
        "hashed_id": build.get("hashed_id"),
        "name": build.get("name"),
        "status": build.get("status"),
        "duration_seconds": build.get("duration"),
        "public_url": build.get("public_url"),
    }


def _slim_session(session: dict) -> dict:
    return {
        "hashed_id": session.get("hashed_id"),
        "name": session.get("name"),
        "status": session.get("status"),
        "browser": session.get("browser"),
        "browser_version": session.get("browser_version"),
        "os": session.get("os"),
        "os_version": session.get("os_version"),
        "duration_seconds": session.get("duration"),
        "public_url": session.get("public_url"),
    }


LOG_TYPE_ENDPOINTS = {
    "text": "logs",
    "selenium": "seleniumlogs",
    "console": "consolelogs",
    "appium": "appiumlogs",
}

MAX_LOG_CHARS = 200_000


# ---------------------------------------------------------------------------
# Read tools
# ---------------------------------------------------------------------------

@mcp.tool()
def list_builds(
    status: Annotated[
        Optional[str],
        Field(description="Filter by build status: running, done, failed, or timeout. Omit for all."),
    ] = None,
    limit: Annotated[int, Field(description="Max builds to return (1-100).", ge=1, le=100)] = 25,
    offset: Annotated[int, Field(description="Pagination offset.", ge=0)] = 0,
) -> dict:
    """List recent BrowserStack Automate builds, optionally filtered by status (e.g. running)."""
    try:
        params: dict = {"limit": limit, "offset": offset}
        if status:
            params["status"] = status
        r = requests.get(f"{BS_AUTOMATE_BASE}/builds.json", auth=_auth(), params=params, timeout=30)
        r.raise_for_status()
        builds = [_slim_build(item.get("automation_build", {})) for item in r.json()]
        return {"count": len(builds), "builds": builds}
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def resolve_build_id(
    build_name_or_hash: Annotated[
        str, Field(description="Build name (e.g. '20260412-064121-6903a') or 40-char hashed build ID.")
    ],
) -> dict:
    """Resolve a build name to its BrowserStack hashed build ID(s). A name can match multiple builds."""
    try:
        hashed_ids = bsapp.get_all_hashed_build_ids(build_name_or_hash)
        return {"input": build_name_or_hash, "hashed_build_ids": hashed_ids, "count": len(hashed_ids)}
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def list_build_sessions(
    build_id: Annotated[str, Field(description="Build hashed ID (use resolve_build_id if you only have a name).")],
    status: Annotated[
        Optional[str],
        Field(description="Filter by session status: running, passed, failed, error, timeout. Omit for all."),
    ] = None,
    limit: Annotated[int, Field(description="Max sessions to return (1-100).", ge=1, le=100)] = 25,
    offset: Annotated[int, Field(description="Pagination offset.", ge=0)] = 0,
) -> dict:
    """List sessions within a specific BrowserStack build."""
    try:
        params: dict = {"limit": limit, "offset": offset}
        if status:
            params["status"] = status
        r = requests.get(
            f"{BS_AUTOMATE_BASE}/builds/{build_id}/sessions.json", auth=_auth(), params=params, timeout=60
        )
        r.raise_for_status()
        sessions = [_slim_session(item.get("automation_session", {})) for item in r.json()]
        return {"build_id": build_id, "count": len(sessions), "sessions": sessions}
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def get_session(
    session_id: Annotated[str, Field(description="Session hashed ID.")],
) -> dict:
    """Get full details for one BrowserStack session, including a cleaned-up error reason if it failed."""
    try:
        session = bsapp.fetch_session(session_id)
        error_reason = None
        if session.get("status") in ("failed", "error", "timeout"):
            error_reason, _ = bsapp.extract_error_details(session)
        return {**session, "clean_error_reason": error_reason}
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def get_session_logs(
    session_id: Annotated[str, Field(description="Session hashed ID.")],
    log_type: Annotated[
        str,
        Field(description="One of: text (Selenium command log), selenium, console, appium."),
    ] = "text",
) -> dict:
    """Fetch a raw log stream for a session (large logs are truncated to ~200KB)."""
    try:
        suffix = LOG_TYPE_ENDPOINTS.get(log_type)
        if not suffix:
            return {"error": f"log_type must be one of {list(LOG_TYPE_ENDPOINTS)}"}
        r = requests.get(f"{BS_AUTOMATE_BASE}/sessions/{session_id}/{suffix}", auth=_auth(), timeout=30)
        r.raise_for_status()
        text = r.text or ""
        return {
            "session_id": session_id,
            "log_type": log_type,
            "truncated": len(text) > MAX_LOG_CHARS,
            "content": text[:MAX_LOG_CHARS],
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def get_walkme_network_logs(
    session_id: Annotated[str, Field(description="Session hashed ID.")],
) -> dict:
    """Fetch this session's network log (HAR), filtered to WalkMe-related requests only."""
    try:
        entries = bsapp.fetch_walkme_network_logs(session_id)
        return {"session_id": session_id, "count": len(entries), "requests": entries}
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def find_last_successful_run(
    test_name: Annotated[str, Field(description="Test name, e.g. 'test_18_swt_auto_2[SAP_concur]_5537'.")],
    current_session_id: Annotated[
        Optional[str], Field(description="Session ID to exclude from the search (usually the failing one).")
    ] = None,
    current_build_id: Annotated[
        Optional[str], Field(description="Build ID to search first before scanning other recent builds.")
    ] = None,
) -> dict:
    """Search recent builds for the last passing run of the same test (exact name + project match)."""
    try:
        result = bsapp.find_last_successful_run(test_name, current_session_id, current_build_id)
        return result or {"found": False, "test_name": test_name}
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def get_reproduction_summary(
    session_url_or_id: Annotated[
        str, Field(description="A full BrowserStack session URL, or just a session hashed ID.")
    ],
    include_last_successful_run: Annotated[
        bool,
        Field(description="Also search recent builds for the last passing run of this test (slower)."),
    ] = False,
) -> dict:
    """
    One-shot debugging summary for a session: status, browser/OS, cleaned error reason,
    parsed reproduction steps, EUX BO deep link, and filtered WalkMe network requests.
    This is the same data app.py's HTML reproduction page is built from, returned as JSON.
    """
    try:
        if session_url_or_id.startswith("http"):
            session_id, build_id, auth_token = bsapp.extract_session_info(session_url_or_id)
            if not session_id:
                return {"error": "Could not extract a session ID from that URL."}
        else:
            session_id, build_id, auth_token = session_url_or_id, None, None

        session = bsapp.fetch_session(session_id, auth_token)
        test_name = session.get("name", "")
        build_id = build_id or session.get("build_hashed_id") or session.get("build_id")
        build_name = bsapp.fetch_build_name(build_id) if build_id else ""

        logs = bsapp.fetch_logs(session_id, auth_token)
        steps = bsapp.parse_steps(logs) if logs else []
        error_reason, _ = bsapp.extract_error_details(session)
        eux_bo_url = bsapp.extract_eux_bo_url(logs, test_name)
        network_requests = bsapp.fetch_walkme_network_logs(session_id, auth_token)

        result = {
            "session_id": session_id,
            "build_id": build_id,
            "build_name": build_name,
            "test_name": test_name,
            "status": session.get("status"),
            "browser": session.get("browser"),
            "browser_version": session.get("browser_version"),
            "os": session.get("os"),
            "os_version": session.get("os_version"),
            "duration_seconds": session.get("duration"),
            "public_url": session.get("public_url"),
            "video_url": session.get("video_url"),
            "error_reason": error_reason if session.get("status") in ("failed", "error", "timeout") else None,
            "step_count": len(steps),
            "steps": steps,
            "eux_bo_url": eux_bo_url,
            "walkme_network_request_count": len(network_requests),
            "walkme_network_requests": network_requests,
        }

        if include_last_successful_run and test_name:
            result["last_successful_run"] = bsapp.find_last_successful_run(test_name, session_id, build_id)

        return result
    except Exception as e:
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# Tagging / deletion tools
# ---------------------------------------------------------------------------

@mcp.tool()
def update_session_status(
    session_id: Annotated[str, Field(description="Session hashed ID.")],
    status: Annotated[str, Field(description="'passed' or 'failed'.")],
    reason: Annotated[Optional[str], Field(description="Optional note, max 256 chars, no escape sequences.")] = None,
) -> dict:
    """
    Tag a session's result after the fact (BrowserStack's PUT /sessions endpoint).
    This only updates metadata shown in the dashboard -- it does not stop or affect
    execution of a still-running session.
    """
    try:
        if status not in ("passed", "failed"):
            return {"error": "status must be 'passed' or 'failed'"}
        payload = {"status": status}
        if reason:
            payload["reason"] = reason[:256]
        r = requests.put(f"{BS_AUTOMATE_BASE}/sessions/{session_id}.json", auth=_auth(), json=payload, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def delete_session(
    session_id: Annotated[str, Field(description="Session hashed ID.")],
) -> dict:
    """Permanently delete one session's record from BrowserStack. Cannot be undone."""
    try:
        r = requests.delete(f"{BS_AUTOMATE_BASE}/sessions/{session_id}.json", auth=_auth(), timeout=30)
        if r.status_code == 404:
            return {"status": "not_found", "session_id": session_id}
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def delete_failed_sessions_in_build(
    build_id: Annotated[
        str, Field(description="Build name or hashed ID. If a name matches multiple builds, all are processed.")
    ],
) -> dict:
    """Bulk-delete every non-passed, non-running session (failed/error/timeout) in a build or builds matching this name."""
    try:
        return bsapp.delete_failed_sessions(build_id)
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def delete_build(
    build_id: Annotated[str, Field(description="Build hashed ID.")],
    confirm: Annotated[
        bool, Field(description="Must be true to actually delete. Deletes the build AND all its sessions.")
    ] = False,
) -> dict:
    """Permanently delete a build and every session inside it. Cannot be undone. Requires confirm=true."""
    try:
        if not confirm:
            return {
                "status": "not_deleted",
                "message": "Pass confirm=true to permanently delete this build and ALL sessions in it. This cannot be undone.",
            }
        r = requests.delete(f"{BS_AUTOMATE_BASE}/builds/{build_id}.json", auth=_auth(), timeout=30)
        if r.status_code == 404:
            return {"status": "not_found", "build_id": build_id}
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def delete_builds(
    build_ids: Annotated[list[str], Field(description="Up to 5 build hashed IDs.")],
    confirm: Annotated[
        bool, Field(description="Must be true to actually delete. Deletes each build AND all its sessions.")
    ] = False,
) -> dict:
    """Permanently delete up to 5 builds (and all their sessions) in one call. Cannot be undone. Requires confirm=true."""
    try:
        if len(build_ids) > 5:
            return {"error": "BrowserStack allows deleting at most 5 builds per call."}
        if not confirm:
            return {
                "status": "not_deleted",
                "message": f"Pass confirm=true to permanently delete {len(build_ids)} build(s) and ALL their sessions. This cannot be undone.",
            }
        r = requests.delete(
            f"{BS_AUTOMATE_BASE}/builds",
            auth=_auth(),
            params=[("buildId", b) for b in build_ids],
            timeout=30,
        )
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# Entrypoint: stdio (local Claude Desktop) or Streamable HTTP (remote/hosted)
# ---------------------------------------------------------------------------

def _build_http_app():
    """Wrap the MCP ASGI app with a bearer-token check and a plain health route."""
    from starlette.applications import Starlette
    from starlette.middleware import Middleware
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.responses import PlainTextResponse
    from starlette.routing import Mount, Route

    api_key = os.environ.get("MCP_API_KEY")
    if not api_key:
        print(
            "WARNING: MCP_API_KEY is not set. This server is running with NO "
            "authentication. Anyone who finds its URL can list, tag, and "
            "delete your BrowserStack builds and sessions.",
            file=sys.stderr,
        )

    class BearerAuthMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            if not api_key or request.url.path == "/healthz":
                return await call_next(request)
            if request.headers.get("authorization") != f"Bearer {api_key}":
                return PlainTextResponse("Unauthorized", status_code=401)
            return await call_next(request)

    async def healthz(request):
        return PlainTextResponse("ok")

    # streamable_http_app() is the current transport; sse_app() is kept as a
    # fallback for older `mcp` SDK versions still pinned somewhere.
    if hasattr(mcp, "streamable_http_app"):
        mcp_asgi_app = mcp.streamable_http_app()
    else:
        mcp_asgi_app = mcp.sse_app()

    # The FastMCP ASGI app manages a session manager that needs its lifespan
    # (startup/shutdown) events to actually run -- otherwise every request
    # fails with "Task group is not initialized. Make sure to use run()".
    # Mounting it with Starlette's Mount does NOT forward lifespan events on
    # its own, so the outer app's lifespan is pointed at the sub-app's.
    return Starlette(
        routes=[Route("/healthz", healthz), Mount("/", app=mcp_asgi_app)],
        middleware=[Middleware(BearerAuthMiddleware)],
        lifespan=mcp_asgi_app.router.lifespan_context,
    )


if __name__ == "__main__":
    if "--stdio" in sys.argv:
        mcp.run(transport="stdio")
    else:
        import uvicorn

        port = int(os.environ.get("PORT", 8000))
        uvicorn.run(_build_http_app(), host="0.0.0.0", port=port)

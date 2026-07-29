"""Entry point for Chainlit backend.

This file imports all modules from the backend/ package and registers
Chainlit handlers. Chainlit expects this file as the main module.

Run with: chainlit run app.py
"""

import os
import socketio

_original_async_server_init = socketio.AsyncServer.__init__

def _patched_async_server_init(self, *args, **kwargs):
    kwargs.setdefault("ping_timeout", 120)
    kwargs.setdefault("ping_interval", 25)
    kwargs.setdefault("cors_allowed_origins", "*")
    return _original_async_server_init(self, *args, **kwargs)

socketio.AsyncServer.__init__ = _patched_async_server_init

from dotenv import load_dotenv
load_dotenv()

import requests
import chainlit as cl
from crewai import LLM
from chainlit import server as _cl_server
from fastapi import Request
from fastapi.responses import JSONResponse
import base64
import re
import uuid

from backend.globals import *
from backend.utils import _sanitize_error, _debug
from backend.tools.search import search_web
from backend.tools.media import generate_image, generate_video
from backend.tools.audio import text_to_speech, transcribe_audio, analyze_image
from backend.llm.manager import LLMManager, _is_rate_limit_error
from backend.llm.rotator import FreeModelRotator
from backend.llm.catalog import ModelCatalog
from backend.llm.discovery import ModelDiscoveryService
from backend.llm.selector import ModelSelector
from backend.media.manager import MediaGenerationManager
from backend.agents.capability import CapabilityRegistry, CapabilityResolver
from backend.agents.tool_registry import ToolRegistry
from backend.agents.registry import AgentRegistry
from backend.agents.task_store import TaskStore
from backend.agents.chat_store import ChatStore
from backend.agents.factory import AgentFactory
from backend.core.secretary import CentralManager
CentralSecretary = CentralManager  # backward compat alias for tests
from backend.core.orchestrator import ExecutionOrchestrator
from backend.core.messenger import StateMessenger
from backend.attachment.processor import process_attachment, process_url
from backend.attachment.security import check_model_modality_support, llm_manager_tier_check
from backend.attachment.url import classify_url, _is_localhost_url, download_with_limit
from backend.handlers.chat import on_chat_start, on_message, execute_multi_agent_task, execute_task_with_agent, get_messenger
from backend.handlers.actions import (
    on_action_create_agent,
    on_action_accept,
    on_action_reject,
    on_action_cancel,
    on_action_add_agent_form,
    on_action_edit_agent_form,
    on_action_delete_agent,
    on_action_assign_task_form,
    on_action_agent_feedback,
    on_action_confirm_tuning,
    on_action_reject_tuning,
    on_action_create_team,
    on_action_update_team,
    on_action_delete_team,
    on_action_delete_chat_session,
    on_action_config_agent,
)
from backend.auth.dev_login import DevLoginProvider
from backend.auth.system81 import System81AuthProvider
from backend.auth.user_store import UserStore
from backend.auth.session import SessionManager

# Constants needed by tests and handlers
URL_REGEX = r'https?://[^\s<>"{}|\\^`]+'
from backend.attachment.url import MAX_URL_DOWNLOAD_SIZE, AUDIO_FORMAT_MAP, MAX_TEXT_LENGTH

# ============================================================
# HTTP upload endpoint
# ============================================================
# Legacy fallback directory — used when no auth token (dev mode)
_LEGACY_ATTACH_DIR = os.path.join(os.path.dirname(__file__), "public", "attachments")
os.makedirs(_LEGACY_ATTACH_DIR, exist_ok=True)


@_cl_server.app.post("/api/upload")
async def _http_upload_file(request: Request):
    """Receive a file upload via HTTP and return a URL."""
    try:
        content_type = request.headers.get("content-type", "")
        if content_type.startswith("multipart/form-data"):
            form = await request.form()
            uploaded_file = form.get("file")
            if not uploaded_file:
                return JSONResponse({"error": "No file provided"}, status_code=400)
            file_name = uploaded_file.filename or "upload"
            file_mime = uploaded_file.content_type or "application/octet-stream"
            file_bytes = await uploaded_file.read()
        else:
            body = await request.json()
            file_data = body.get("file_data", "")
            file_name = body.get("file_name", "upload")
            file_mime = body.get("file_mime", "application/octet-stream")
            if not file_data:
                return JSONResponse({"error": "No file_data provided"}, status_code=400)
            file_bytes = base64.b64decode(file_data.split(",")[-1] if "," in file_data else file_data)

        # Per-user isolation: extract user_id from auth token and save to data/users/{uid}/attachments/
        # — prevents cross-user data leakage when multiple users share the same server.
        auth_header = request.headers.get("authorization", "")
        user_id = None
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            user_id = _session_mgr.verify_token(token)

        if user_id:
            attach_dir = os.path.join(user_data_dir(user_id), "attachments")
            url_prefix = "/api/media/attachments"
        else:
            attach_dir = _LEGACY_ATTACH_DIR
            url_prefix = "/public/attachments"

        safe_name = re.sub(r'[^a-zA-Z0-9._-]', '_', file_name)
        unique_name = f"{uuid.uuid4().hex[:8]}_{safe_name}"
        filepath = os.path.join(attach_dir, unique_name)
        with open(filepath, "wb") as f:
            f.write(file_bytes)
        file_url = f"{url_prefix}/{unique_name}"
        print(f"[UPLOAD] Saved {file_name} → {file_url} (user={user_id or 'dev'})", flush=True)
        return JSONResponse({"url": file_url, "name": file_name, "mime": file_mime})
    except Exception as e:
        print(f"[UPLOAD] Failed: {_sanitize_error(e)}", flush=True)
        return JSONResponse({"error": _sanitize_error(e)}, status_code=500)


# Mount static files only if the public directory exists and isn't already mounted
if os.path.exists(os.path.join(os.path.dirname(__file__), "public")):
    _public_dir = os.path.join(os.path.dirname(__file__), "public")
    _mount_point = "/public"
    _already_mounted = False
    for r in _cl_server.app.routes:
        try:
            if hasattr(r, "path") and _mount_point == str(r.path):
                _already_mounted = True
                break
        except Exception:
            continue
    if not _already_mounted:
        from fastapi.staticfiles import StaticFiles
        _cl_server.app.mount(_mount_point, StaticFiles(directory=_public_dir), name="public")

# Mount frontend dist if it exists (serves SPA at root)
_frontend_dist = os.path.join(os.path.dirname(__file__), "frontend", "dist")
if os.path.exists(_frontend_dist):
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse

    @_cl_server.app.get("/")
    async def _serve_frontend_root():
        return FileResponse(os.path.join(_frontend_dist, "index.html"))

    _cl_server.app.mount("/assets", StaticFiles(directory=os.path.join(_frontend_dist, "assets")), name="frontend-assets")
    print(f"[FRONTEND] Serving from {_frontend_dist}", flush=True)

# ============================================================
# Auth endpoints
# ============================================================
_use_dev_login = os.getenv("USE_DEV_LOGIN", "false").lower() == "true"
_auth_provider = DevLoginProvider() if _use_dev_login else System81AuthProvider()
_user_store = UserStore()
_session_mgr = SessionManager()


@_cl_server.app.get("/api/auth/login-url")
async def _auth_login_url():
    """Return the external OAuth login URL (if the provider supports redirect)."""
    url = _auth_provider.get_login_url()
    return JSONResponse({"login_url": url or ""})

# Chainlit registers a catch-all `GET /{full_path:path}` route when
# `chainlit.server` is imported, before this route is added — Starlette
# matches in registration order, so the catch-all would otherwise shadow
# this route and serve the SPA HTML instead of JSON. Move this route ahead
# of the catch-all so it actually gets matched.
_login_url_route = _cl_server.app.router.routes.pop()
_included_router_idx = next(
    i for i, r in enumerate(_cl_server.app.router.routes)
    if type(r).__name__ == "_IncludedRouter"
)
_cl_server.app.router.routes.insert(_included_router_idx, _login_url_route)


@_cl_server.app.post("/api/auth/login")
async def _auth_login(request: Request):
    """Login with username/password or a System81/OAuth token."""
    try:
        body = await request.json()
        user = await _auth_provider.authenticate(body)
        if not user:
            return JSONResponse({"error": "Authentication failed"}, status_code=401)
        profile = _user_store.get_or_create(user)
        token = _session_mgr.create_session(user.user_id)
        return JSONResponse({
            "token": token,
            "user": {
                "user_id": profile["user_id"],
                "username": profile["username"],
                "email": profile.get("email", ""),
                "provider": profile.get("provider", "dev"),
                "avatar_url": profile.get("avatar_url", ""),
            },
        })
    except Exception as e:
        print(f"[AUTH] Login failed: {_sanitize_error(e)}", flush=True)
        return JSONResponse({"error": _sanitize_error(e)}, status_code=500)


@_cl_server.app.post("/api/auth/verify")
async def _auth_verify(request: Request):
    """Verify a session token."""
    try:
        body = await request.json()
        token = body.get("token", "")
        user_id = _session_mgr.verify_token(token)
        if not user_id:
            return JSONResponse({"valid": False}, status_code=401)
        profile = _user_store.get_by_id(user_id)
        if not profile:
            return JSONResponse({"valid": False}, status_code=401)
        return JSONResponse({
            "valid": True,
            "user": {
                "user_id": profile["user_id"],
                "username": profile["username"],
                "email": profile.get("email", ""),
                "provider": profile.get("provider", "dev"),
                "avatar_url": profile.get("avatar_url", ""),
            },
        })
    except Exception as e:
        print(f"[AUTH] Verify failed: {_sanitize_error(e)}", flush=True)
        return JSONResponse({"valid": False}, status_code=401)


@_cl_server.app.post("/api/auth/logout")
async def _auth_logout(request: Request):
    """Revoke a session token."""
    try:
        body = await request.json()
        token = body.get("token", "")
        _session_mgr.revoke_session(token)
        return JSONResponse({"success": True})
    except Exception as e:
        print(f"[AUTH] Logout failed: {_sanitize_error(e)}", flush=True)
        return JSONResponse({"error": _sanitize_error(e)}, status_code=500)

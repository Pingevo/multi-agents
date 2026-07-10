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
from backend.core.secretary import CentralSecretary
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
)

# Constants needed by tests and handlers
URL_REGEX = r'https?://[^\s<>"{}|\\^`\[\]]+'
from backend.attachment.url import MAX_URL_DOWNLOAD_SIZE, AUDIO_FORMAT_MAP, MAX_TEXT_LENGTH

# ============================================================
# HTTP upload endpoint
# ============================================================
_ATTACH_DIR = os.path.join(os.path.dirname(__file__), "public", "attachments")
os.makedirs(_ATTACH_DIR, exist_ok=True)


@_cl_server.app.post("/api/upload")
async def _http_upload_file(request: Request):
    """Receive a file upload via HTTP and return a public URL."""
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

        safe_name = re.sub(r'[^a-zA-Z0-9._-]', '_', file_name)
        unique_name = f"{uuid.uuid4().hex[:8]}_{safe_name}"
        filepath = os.path.join(_ATTACH_DIR, unique_name)
        with open(filepath, "wb") as f:
            f.write(file_bytes)
        file_url = f"/public/attachments/{unique_name}"
        print(f"[UPLOAD] Saved {file_name} → {file_url}", flush=True)
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

import asyncio
import contextvars
import json
import os
import random
import re
import threading
import time
import traceback
import uuid
from datetime import datetime
from urllib.parse import quote as url_quote

import io
import base64

import socketio
from fastapi import FastAPI, UploadFile, File, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

_original_async_server_init = socketio.AsyncServer.__init__

def _patched_async_server_init(self, *args, **kwargs):
    kwargs.setdefault("ping_timeout", 120)
    kwargs.setdefault("ping_interval", 25)
    return _original_async_server_init(self, *args, **kwargs)

socketio.AsyncServer.__init__ = _patched_async_server_init

import chainlit as cl
import requests
from dotenv import load_dotenv
from crewai import Agent, Task, Crew, Process, LLM
from crewai.tools import tool
from crewai.events import crewai_event_bus
from crewai.events.types.agent_events import AgentExecutionStartedEvent, AgentExecutionCompletedEvent
from crewai.events.types.tool_usage_events import ToolUsageStartedEvent, ToolUsageFinishedEvent
from crewai.events.types.task_events import TaskStartedEvent, TaskCompletedEvent
from pydantic import BaseModel

from schemas import (
    PlanAgentItem, ResultAgentItem, AgentProgressEntry,
    ChatReplyText, ChatReplyPlanValidationError, ChatReplyPlan, ChatReplyProgress, ChatReplyAgentProgress,
    ChatReplyResult, ChatReplyImageApproval, ChatReplyImageResult,
    ChatReplyModelCatalog, ModelCatalogItem,
    ChatReplyAudioResult, ChatReplyTranscriptionResult, ChatReplyVideoResult, ChatReplyFileResult,
    StatePayload, chat_reply,
)


# Load .env so that LLM_PROVIDER, LLM_BASE_URL, LLM_API_KEY etc. are available.
load_dotenv()

import re as _re

def _sanitize_error(e) -> str:
    """Sanitize error messages to prevent API key leakage in logs."""
    msg = str(e)
    msg = _re.sub(r'sk-or-[A-Za-z0-9\-_]+', 'sk-or-***', msg)
    msg = _re.sub(r'Bearer [A-Za-z0-9\-_]+', 'Bearer ***', msg)
    msg = _re.sub(r'api_key=[A-Za-z0-9\-_]+', 'api_key=***', msg)
    msg = _re.sub(r'key=[A-Za-z0-9\-_]+', 'key=***', msg)
    return msg[:500]

def _debug(*args, **kwargs):
    """Print only when DEBUG_MODE=true."""
    if os.getenv("DEBUG_MODE", "false").lower() == "true":
        print(*args, **kwargs)


# ============================================================
# State Management
# ============================================================
STATE_IDLE = "IDLE"
STATE_ASSESSING = "ASSESSING"
STATE_GATHERING_REQUIREMENTS = "GATHERING_REQUIREMENTS"
STATE_PLANNING = "PLANNING"
STATE_CREATING_AGENT = "CREATING_AGENT"
STATE_AWAITING_APPROVAL = "AWAITING_APPROVAL"
STATE_EXECUTING = "EXECUTING"

AGENT_REGISTRY_FILE = os.path.join(os.path.dirname(__file__), "agent_registry.json")
TASK_REGISTRY_FILE = os.path.join(os.path.dirname(__file__), "task_registry.json")
CHAT_SESSIONS_FILE = os.path.join(os.path.dirname(__file__), "chat_sessions.json")


# ============================================================
# Global callback for progress updates from tools
# ============================================================
_progress_callback = None
_media_gen_manager = None
_media_tool_results = []  # Captures tool results directly (not agent final answer)
_thread_local = threading.local()  # Per-thread storage for agent name (parallel-safe)
_search_model = ""  # AI-selected OpenRouter search model (set per run)


# ============================================================
# Tools (built-in only)
# ============================================================


@tool
def search_web(query: str) -> str:
    """Search the web for current information using OpenRouter (AI-selected search model)."""
    global _progress_callback, _search_model
    if _progress_callback:
        _progress_callback(50, "🔍 กำลังค้นหาข้อมูลจากเว็บ...")

    if not query or not query.strip():
        return "กรุณาระบุคำค้นหา"

    llm_mgr = LLMManager()
    search_model = _search_model or "perplexity/sonar"

    try:
        llm = LLM(
            model=f"openrouter/{search_model}" if not search_model.startswith("openrouter/") else search_model,
            base_url=llm_mgr.base_url,
            api_key=llm_mgr.api_key,
            temperature=0.3,
            max_retries=0,
        )
        result = llm.call(f"Search the web for: {query}\n\nProvide factual, up-to-date information with sources if possible.")
        if _progress_callback:
            _progress_callback(80, "🧠 กำลังประมวลผลข้อมูล...")
        return result
    except Exception as e:
        return f"เกิดข้อผิดพลาดระหว่างค้นหา: {_sanitize_error(e)} กรุณาลองใหม่อีกครั้ง"


@tool
def generate_image(prompt: str) -> str:
    """Generate an image from a text prompt using AI image generation.

    Call this tool when you need to create any visual, illustration, poster, or image.
    The prompt should be in English and visually descriptive.
    The prompt will be reviewed by the user before generation to control costs.
    Returns a confirmation that the prompt is ready for user approval.
    """
    global _progress_callback, _media_tool_results
    agent_name = getattr(_thread_local, 'agent_name', '')
    if not prompt or not prompt.strip():
        return "Error: Empty prompt for image generation"
    prompt_clean = prompt.strip()
    prompt_hash = hash(prompt_clean.lower()[:200])
    existing = {hash(r.get("prompt", "")[:200].lower()) for r in _media_tool_results if r.get("type") == "image"}
    if prompt_hash in existing:
        print(f"[DEDUP] Skipping duplicate image prompt: {prompt_clean[:80]}...", flush=True)
        return f"[IMAGE_PROMPT_READY]\nPrompt: {prompt_clean}"
    if _progress_callback:
        _progress_callback(100, "✅ เขียน prompt รูปภาพเสร็จแล้ว — รอผู้ใช้อนุมัติ")
    image_model = _media_gen_manager.image_model if _media_gen_manager else ""
    _media_tool_results.append({"type": "image", "prompt": prompt_clean, "agent_name": agent_name, "model": image_model})
    return f"[IMAGE_PROMPT_READY]\nPrompt: {prompt_clean}"


@tool
def generate_video(prompt: str, duration: int = 5) -> str:
    """Generate a short video from a text prompt using AI video generation.

    Call this tool when you need to create a short video clip, animation, or motion content.
    The prompt should be in English and visually descriptive (describe scene, camera movement, lighting).
    Duration is in seconds (2-15). The prompt will be reviewed by the user before generation to control costs.
    Returns a confirmation that the prompt is ready for user approval.
    """
    global _progress_callback, _media_tool_results
    agent_name = getattr(_thread_local, 'agent_name', '')
    if not prompt or not prompt.strip():
        return "Error: Empty prompt for video generation"
    prompt_clean = prompt.strip()
    duration = max(2, min(15, int(duration)))
    prompt_hash = hash(prompt_clean.lower()[:200])
    existing = {hash(r.get("prompt", "")[:200].lower()) for r in _media_tool_results if r.get("type") == "video"}
    if prompt_hash in existing:
        print(f"[DEDUP] Skipping duplicate video prompt: {prompt_clean[:80]}...", flush=True)
        return f"[VIDEO_PROMPT_READY]\nPrompt: {prompt_clean}\nDuration: {duration}"
    if _progress_callback:
        _progress_callback(100, "✅ เขียน prompt วิดีโอเสร็จแล้ว — รอผู้ใช้อนุมัติ")
    video_model = _media_gen_manager.video_model if _media_gen_manager else ""
    _media_tool_results.append({"type": "video", "prompt": prompt_clean, "duration": duration, "agent_name": agent_name, "model": video_model})
    return f"[VIDEO_PROMPT_READY]\nPrompt: {prompt_clean}\nDuration: {duration}"


@tool
def text_to_speech(text: str, voice: str = "alloy") -> str:
    """Convert text to speech audio using AI TTS models.

    Call this tool when you need to generate narration, voiceover, or any spoken audio from text.
    The text should be in the language you want spoken.
    Voice options: alloy, echo, fable, onyx, nova, shimmer (availability depends on model).
    Returns a URL to the generated audio file that can be used by other agents.
    """
    global _progress_callback, _media_tool_results
    agent_name = getattr(_thread_local, 'agent_name', '')
    if not text or not text.strip():
        return "Error: Empty text for speech generation"
    text_clean = text.strip()
    if _progress_callback:
        _progress_callback(100, "✅ เขียน prompt เสียงพากย์เสร็จแล้ว — รอผู้ใช้อนุมัติ")
    tts_model = _media_gen_manager.tts_model if _media_gen_manager else ""
    _media_tool_results.append({"type": "tts", "text": text_clean, "voice": voice, "agent_name": agent_name, "model": tts_model})
    return f"[TTS_PROMPT_READY]\nText: {text_clean}\nVoice: {voice}"


@tool
def transcribe_audio(audio_url: str) -> str:
    """Transcribe an audio file to text using AI STT models.

    Call this tool when you need to convert audio (speech) to text — for subtitles,
    transcription, or audio content analysis.
    audio_url should be a URL to an audio file (mp3, wav, etc.).
    Returns the transcribed text.
    """
    global _progress_callback, _media_tool_results
    agent_name = getattr(_thread_local, 'agent_name', '')
    if not audio_url or not audio_url.strip():
        return "Error: Empty audio URL for transcription"
    audio_url_clean = audio_url.strip()
    if _progress_callback:
        _progress_callback(100, "✅ ส่งคำขอถอดเสียงเป็นข้อความ — รอผู้ใช้อนุมัติ")
    stt_model = _media_gen_manager.stt_model if _media_gen_manager else ""
    _media_tool_results.append({"type": "stt", "audio_url": audio_url_clean, "agent_name": agent_name, "model": stt_model})
    return f"[STT_PROMPT_READY]\nAudio URL: {audio_url_clean}"


@tool
def analyze_image(image_url: str, question: str = "Describe this image in detail.") -> str:
    """Analyze and describe an image using AI vision models.

    Call this tool when you need to understand, describe, or extract information from an image.
    image_url should be a URL to an image file.
    question specifies what you want to know about the image.
    Returns a text description/analysis of the image.
    """
    global _progress_callback, _media_tool_results
    agent_name = getattr(_thread_local, 'agent_name', '')
    if not image_url or not image_url.strip():
        return "Error: Empty image URL for analysis"
    image_url_clean = image_url.strip()
    question_clean = question.strip() if question else "Describe this image in detail."
    if _progress_callback:
        _progress_callback(100, "✅ ส่งคำขอวิเคราะห์รูปภาพ — รอผู้ใช้อนุมัติ")
    vision_model = _media_gen_manager.vision_model if _media_gen_manager else ""
    _media_tool_results.append({"type": "vision", "image_url": image_url_clean, "question": question_clean, "agent_name": agent_name, "model": vision_model})
    return f"[VISION_PROMPT_READY]\nImage URL: {image_url_clean}\nQuestion: {question_clean}"


# ============================================================
# 1. LLM Agnostic Architecture
# ============================================================
class FreeModelRotator:
    """DEPRECATED: Use OpenRouter routing models (openrouter/auto, openrouter/free) instead.
    Kept for backward compatibility — will be removed in future cleanup.
    """
    """Fetches models from OpenRouter and rotates through them on failure.

    When free_only=True (default): fetches only :free models.
    When free_only=False (paid tier): fetches all tool-capable large models.
    """

    def __init__(self, api_key: str, base_url: str, temperature: float = 0.7, free_only: bool = True):
        self.api_key = api_key
        self.base_url = base_url
        self.temperature = temperature
        self.free_only = free_only
        self._models: list[str] | None = None
        self._model_details: list[dict] | None = None

    _SMALL_KEYWORDS = ("mini", "nano", "xs", "tiny", "small")
    _NON_CHAT_KEYWORDS = ("content-safety", "guard", "moderation", "safety")
    _MIN_PARAMS_BILLION = 20.0

    def _parse_param_count(self, model_id: str) -> float | None:
        import re
        match = re.search(r"(\d+\.?\d*)b\b", model_id.lower())
        return float(match.group(1)) if match else None

    def _is_large_model(self, model_id: str) -> bool:
        lower = model_id.lower()
        if any(kw in lower for kw in self._SMALL_KEYWORDS):
            return False
        if any(kw in lower for kw in self._NON_CHAT_KEYWORDS):
            return False
        params = self._parse_param_count(model_id)
        if params is not None:
            return params >= self._MIN_PARAMS_BILLION
        return True

    def _fetch_models(self) -> list[str]:
        """Fetch models from OpenRouter API, filtered to large models that support tool use."""
        try:
            resp = requests.get(
                f"{self.base_url}/models",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=15,
            )
            if resp.status_code != 200:
                print(f"[FreeModelRotator] API returned {resp.status_code}")
                return []
            data = resp.json().get("data", [])
            if self.free_only:
                data = [m for m in data if ":free" in m.get("id", "")]
            tool_capable = [m for m in data if "tools" in m.get("supported_parameters", [])]
            large_models = [m for m in tool_capable if self._is_large_model(m["id"])]
            if self.free_only:
                print(f"[FreeModelRotator] {len(data)} free models, {len(tool_capable)} tool-capable, {len(large_models)} after size filter")
            else:
                large_models.sort(key=lambda m: self._parse_param_count(m["id"]) or 0, reverse=True)
                print(f"[FreeModelRotator] {len(data)} total models, {len(tool_capable)} tool-capable, {len(large_models)} after size filter")
            self._model_details = large_models
            return [m["id"] for m in large_models]
        except Exception as e:
            print(f"[FreeModelRotator] Fetch error: {_sanitize_error(e)}")
            return []

    def get_models(self) -> list[str]:
        """Return models list, fetching on first call."""
        if self._models is None:
            self._models = self._fetch_models()
        return self._models

    def get_model_details(self) -> list[dict]:
        """Return full model metadata list (for candidate table)."""
        if self._model_details is None:
            self.get_models()
        return self._model_details or []

    def pick_model(self) -> str:
        """Pick a random free model."""
        models = self.get_models()
        return random.choice(models) if models else ""

    def pick_smartest_model(self) -> str:
        """Pick the largest model by parameter count (for critical decisions like assess)."""
        models = self.get_models()
        if not models:
            return ""
        return max(models, key=lambda m: self._parse_param_count(m) or 0)

    def call(self, prompt: str, max_attempts: int = 4) -> str:
        """Try free models largest-first, then random. Raises RuntimeError after all attempts fail."""
        import time

        models = self.get_models()
        if not models:
            raise RuntimeError("No free models available")

        # Sort by parameter count descending — try smartest first
        sorted_models = sorted(models, key=lambda m: self._parse_param_count(m) or 0, reverse=True)

        tried: set[str] = set()
        backoff = 0.5
        for attempt in range(1, max_attempts + 1):
            available = [m for m in sorted_models if m not in tried]
            if not available:
                tried.clear()
                available = sorted_models
            model_id = available[0]  # largest available first
            tried.add(model_id)

            try:
                llm = LLM(
                    model=f"openrouter/{model_id}",
                    base_url=self.base_url,
                    api_key=self.api_key,
                    temperature=self.temperature,
                    max_retries=0,
                )
                result = llm.call(prompt)
                if attempt > 1:
                    print(f"[FreeModelRotator] Succeeded on attempt {attempt} with {model_id}")
                return result
            except Exception as e:
                print(f"[FreeModelRotator] Attempt {attempt}/{max_attempts} with {model_id}: {_sanitize_error(e)}")
                if attempt < max_attempts:
                    time.sleep(backoff)
                    backoff *= 2

        raise RuntimeError(f"All {max_attempts} attempts failed")

    def call_streaming(self, prompt: str, max_attempts: int = 4):
        """Streaming version of call() — yields text chunks as they arrive."""
        from openai import OpenAI

        models = self.get_models()
        if not models:
            raise RuntimeError("No free models available")

        sorted_models = sorted(models, key=lambda m: self._parse_param_count(m) or 0, reverse=True)
        tried: set[str] = set()

        for attempt in range(1, max_attempts + 1):
            available = [m for m in sorted_models if m not in tried]
            if not available:
                tried.clear()
                available = sorted_models
            model_id = available[0]
            tried.add(model_id)

            try:
                client = OpenAI(base_url=self.base_url, api_key=self.api_key, max_retries=0)
                stream = client.chat.completions.create(
                    model=model_id,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=self.temperature,
                    stream=True,
                )
                for chunk in stream:
                    if chunk.choices and chunk.choices[0].delta.content:
                        yield chunk.choices[0].delta.content
                return
            except Exception as e:
                print(f"[FreeModelRotator] Stream attempt {attempt}/{max_attempts} with {model_id}: {_sanitize_error(e)}")
                continue

        raise RuntimeError(f"All {max_attempts} streaming attempts failed")


class ModelCatalog:
    """Fetches and categorizes models from OpenRouter for user selection.

    Provides:
    - recommended: top models grouped by category (chat, reasoning, coding, vision, fast)
    - search: filter by keyword
    - all: full list with metadata
    """

    _CATEGORY_KEYWORDS = {
        "reasoning": ["o3", "o1", "thinking", "reasoning", "deepseek-r1", "qwq"],
        "coding": ["coder", "code", "starcoder", "deepseek-coder", "qwen2.5-coder"],
        "vision": ["vision", "llava", "pixtral", "gpt-4o", "claude-3", "gemini", "qwen2-vl", "qwen2.5-vl"],
        "fast": ["flash", "mini", "haiku", "8b", "7b", "3b", "1.5b", "nano"],
        "free": [":free"],
    }

    _POPULAR_PREFIXES = [
        "openai/gpt-4o", "openai/gpt-4.1", "anthropic/claude", "google/gemini",
        "deepseek/deepseek", "meta-llama/llama", "qwen/qwen",
        "mistral/mistral", "x-ai/grok", "nvidia/nemotron",
    ]

    def __init__(self, api_key: str, base_url: str):
        self.api_key = api_key
        self.base_url = base_url
        self._all_models: list[dict] | None = None

    def _fetch_all(self) -> list[dict]:
        if self._all_models is not None:
            return self._all_models
        try:
            resp = requests.get(
                f"{self.base_url}/models",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=15,
            )
            if resp.status_code == 200:
                self._all_models = resp.json().get("data", [])
                print(f"[ModelCatalog] Fetched {len(self._all_models)} models from OpenRouter")
            else:
                self._all_models = []
        except Exception as e:
            print(f"[ModelCatalog] Fetch error: {_sanitize_error(e)}")
            self._all_models = []
        return self._all_models

    def _categorize(self, model: dict) -> list[str]:
        mid = model.get("id", "").lower()
        cats = []
        for cat, keywords in self._CATEGORY_KEYWORDS.items():
            if any(kw in mid for kw in keywords):
                cats.append(cat)
        if not cats:
            cats.append("chat")
        return cats

    def _is_popular(self, model_id: str) -> bool:
        lower = model_id.lower()
        return any(lower.startswith(p) for p in self._POPULAR_PREFIXES)

    def _model_summary(self, m: dict) -> dict:
        pricing = m.get("pricing", {})
        prompt_price = pricing.get("prompt", "?")
        comp_price = pricing.get("completion", "?")
        # OpenRouter returns per-token prices; convert to per-1M-tokens for display
        try:
            prompt_price = round(float(prompt_price) * 1_000_000, 6)
        except (ValueError, TypeError):
            pass
        try:
            comp_price = round(float(comp_price) * 1_000_000, 6)
        except (ValueError, TypeError):
            pass
        return {
            "id": m.get("id", ""),
            "name": m.get("name", m.get("id", "")),
            "context_length": m.get("context_length", "?"),
            "prompt_price": prompt_price,
            "completion_price": comp_price,
            "categories": self._categorize(m),
            "is_free": ":free" in m.get("id", ""),
            "supported_parameters": m.get("supported_parameters", []),
        }

    def get_recommended(self, limit_per_cat: int = 0) -> dict[str, list[dict]]:
        """Return models grouped by category, sorted by popularity then price."""
        all_models = self._fetch_all()
        by_cat: dict[str, list[dict]] = {}
        for m in all_models:
            summary = self._model_summary(m)
            for cat in summary["categories"]:
                by_cat.setdefault(cat, []).append(summary)

        result = {}
        for cat, models in by_cat.items():
            models.sort(key=lambda x: (not self._is_popular(x["id"]), x.get("prompt_price", "999") if x.get("prompt_price") != "?" else "999"))
            result[cat] = models if limit_per_cat <= 0 else models[:limit_per_cat]
        return result

    def search(self, query: str, limit: int = 0) -> list[dict]:
        """Search models by keyword."""
        all_models = self._fetch_all()
        q = query.lower().strip()
        if not q:
            return []
        results = []
        for m in all_models:
            mid = m.get("id", "").lower()
            mname = m.get("name", "").lower()
            if q in mid or q in mname:
                results.append(self._model_summary(m))
        return results if limit <= 0 else results[:limit]

    def get_all(self, limit: int = 100) -> list[dict]:
        """Return all models (limited)."""
        all_models = self._fetch_all()
        return [self._model_summary(m) for m in all_models[:limit]]


class ModelDiscoveryService:
    """Discovers and categorizes all OpenRouter models by their capabilities.

    Fetches models from GET /models?output_modalities=all and groups them by:
    - output_modalities (text, image, video, audio, embeddings)
    - supported_parameters (web_search → search category)
    - input_modalities (image → vision, audio → audio_input/STT)

    No hardcoded keywords — all classification comes from API metadata.
    """

    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._all_models: list[dict] | None = None
        self._output_groups: dict[str, list[dict]] | None = None
        self._input_groups: dict[str, list[dict]] | None = None

    def _fetch_all_models(self) -> list[dict]:
        """Fetch all models from OpenRouter (free API call)."""
        if self._all_models is not None:
            return self._all_models
        try:
            resp = requests.get(
                f"{self.base_url}/models",
                headers={"Authorization": f"Bearer {self.api_key}"},
                params={"output_modalities": "all"},
                timeout=15,
            )
            if resp.status_code == 200:
                self._all_models = resp.json().get("data", [])
            else:
                print(f"[ModelDiscovery] API returned {resp.status_code}")
                self._all_models = []
        except Exception as e:
            print(f"[ModelDiscovery] Fetch error: {_sanitize_error(e)}")
            self._all_models = []
        return self._all_models

    def discover_all(self) -> dict[str, list[dict]]:
        """Group models by output modality + search capability.

        Returns dict with keys: text, image, video, audio, embeddings, search.
        Each value is a list of model dicts with id, name, context_length, pricing, etc.
        """
        if self._output_groups is not None:
            return self._output_groups

        all_models = self._fetch_all_models()
        groups: dict[str, list[dict]] = {
            "text": [],
            "image": [],
            "video": [],
            "audio": [],
            "embeddings": [],
            "search": [],
        }

        for m in all_models:
            mid = m.get("id", "")
            # Skip OpenRouter routing models — they are text-only routers, not real media models
            if mid.startswith("openrouter/"):
                continue

            arch = m.get("architecture", {})
            output_modalities = arch.get("output_modalities", [])
            params = m.get("supported_parameters", [])

            entry = {
                "id": mid,
                "name": m.get("name", mid),
                "context_length": m.get("context_length", 0),
                "pricing": m.get("pricing", {}),
                "description": m.get("description", "")[:100],
                "input_modalities": arch.get("input_modalities", []),
                "output_modalities": output_modalities,
                "supported_parameters": params,
            }

            # Search models: text output + web_search parameter
            if "web_search" in params and "text" in output_modalities:
                groups["search"].append(entry)
            elif "image" in output_modalities:
                groups["image"].append(entry)
            elif "video" in output_modalities:
                groups["video"].append(entry)
            elif "audio" in output_modalities:
                groups["audio"].append(entry)
            elif "embeddings" in output_modalities:
                groups["embeddings"].append(entry)
            elif "text" in output_modalities:
                groups["text"].append(entry)

        self._output_groups = groups
        return groups

    def discover_input_capabilities(self) -> dict[str, list[dict]]:
        """Group models by input modality for input-type capabilities (vision, STT).

        Returns dict with keys: vision (image input), audio_input (audio input/STT).
        """
        if self._input_groups is not None:
            return self._input_groups

        all_models = self._fetch_all_models()
        groups: dict[str, list[dict]] = {
            "vision": [],
            "audio_input": [],
        }

        for m in all_models:
            mid = m.get("id", "")
            if mid.startswith("openrouter/"):
                continue

            arch = m.get("architecture", {})
            input_modalities = arch.get("input_modalities", [])

            entry = {
                "id": mid,
                "name": m.get("name", mid),
                "context_length": m.get("context_length", 0),
                "pricing": m.get("pricing", {}),
                "description": m.get("description", "")[:100],
                "input_modalities": input_modalities,
                "output_modalities": arch.get("output_modalities", []),
                "supported_parameters": m.get("supported_parameters", []),
            }

            if "image" in input_modalities:
                groups["vision"].append(entry)
            if "audio" in input_modalities:
                groups["audio_input"].append(entry)

        self._input_groups = groups
        return groups

    def get_catalog_summary(self) -> str:
        """Build a text summary of all model categories for the Manager prompt.

        Includes output categories (image, video, audio/TTS, search, embeddings)
        and input categories (vision, STT) with model IDs.
        """
        output_groups = self.discover_all()
        input_groups = self.discover_input_capabilities()

        lines = []

        # Output capabilities
        if output_groups.get("image"):
            ids = [m["id"] for m in output_groups["image"]]
            lines.append("Image generation models: " + ", ".join(ids))
        if output_groups.get("video"):
            ids = [m["id"] for m in output_groups["video"]]
            lines.append("Video generation models: " + ", ".join(ids))
        if output_groups.get("audio"):
            ids = [m["id"] for m in output_groups["audio"]]
            lines.append("Text-to-Speech (TTS) models: " + ", ".join(ids))
        if output_groups.get("search"):
            ids = [m["id"] for m in output_groups["search"]]
            lines.append("Web search models: " + ", ".join(ids))
        if output_groups.get("embeddings"):
            ids = [m["id"] for m in output_groups["embeddings"]]
            lines.append("Embedding models: " + ", ".join(ids))

        # Input capabilities
        if input_groups.get("vision"):
            ids = [m["id"] for m in input_groups["vision"]]
            lines.append("Vision (image analysis) models: " + ", ".join(ids))
        if input_groups.get("audio_input"):
            ids = [m["id"] for m in input_groups["audio_input"]]
            lines.append("Speech-to-Text (STT) models: " + ", ".join(ids))

        return "\n".join(lines) if lines else "none"


class ModelSelector:
    """LLM-driven model assignment: analyzes live model metadata and assigns best model per agent."""

    def __init__(self, api_key: str, base_url: str, temperature: float = 0.7, rotator=None, default_model: str = ""):
        self.api_key = api_key
        self.base_url = base_url
        self.temperature = temperature
        self._rotator = rotator
        self._default_model = default_model
        self._candidates: list[dict] | None = None

    def _fetch_candidates(self) -> list[dict]:
        """Fetch tool-capable models from OpenRouter API directly."""
        if self._rotator:
            details = self._rotator.get_model_details()
            if details:
                return [
                    {
                        "id": m.get("id", ""),
                        "context_length": m.get("context_length", "?"),
                        "pricing": m.get("pricing", {"prompt": "?", "completion": "?"}),
                        "description": m.get("description", "")[:100],
                    }
                    for m in details
                ]
            # Fallback to model IDs only
            model_ids = self._rotator.get_models()
            return [{"id": mid, "context_length": "?", "pricing": {"prompt": "?", "completion": "?"}, "description": ""} for mid in model_ids]
        # No rotator — fetch directly from OpenRouter
        all_models = self._fetch_all_models()
        tool_capable = [m for m in all_models if "tools" in m.get("supported_parameters", [])]
        return [
            {
                "id": m.get("id", ""),
                "context_length": m.get("context_length", "?"),
                "pricing": m.get("pricing", {"prompt": "?", "completion": "?"}),
                "description": m.get("description", "")[:100],
            }
            for m in tool_capable
        ]

    def _get_candidates(self) -> list[dict]:
        if self._candidates is None:
            self._candidates = self._fetch_candidates()
        return self._candidates

    def _build_candidate_table(self, candidates: list[dict]) -> str:
        lines = []
        for c in candidates:
            pricing = c.get("pricing", {})
            prompt_price = pricing.get("prompt", "?")
            comp_price = pricing.get("completion", "?")
            lines.append(
                f"- {c['id']} | context={c.get('context_length', '?')} | "
                f"prompt_price={prompt_price} | completion_price={comp_price} | "
                f"desc={c.get('description', '')[:80]}"
            )
        return "\n".join(lines)

    def _pick_smartest(self) -> str:
        """Pick the default routing model, or first candidate if no default."""
        if self._default_model:
            return self._default_model
        if self._rotator:
            picked = self._rotator.pick_smartest_model()
            if picked:
                return picked
        candidates = self._get_candidates()
        return candidates[0]["id"] if candidates else ""

    def _fetch_all_models(self) -> list[dict]:
        """Fetch all models from OpenRouter /models endpoint (free API call, no cost)."""
        try:
            resp = requests.get(
                f"{self.base_url}/models",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=15,
            )
            if resp.status_code != 200:
                return []
            return resp.json().get("data", [])
        except Exception as e:
            print(f"[ModelSelector] Fetch all models error: {_sanitize_error(e)}")
            return []

    def _build_media_catalog(self) -> str:
        """Build a condensed catalog of image/video/search-capable models for the AI prompt."""
        all_models = self._fetch_all_models()
        if not all_models:
            return "none"

        video_keywords = ["sora", "wan", "kling", "veo", "runway", "pika", "luma"]
        search_keywords = ["sonar", "perplexity", "search", "online"]

        image_models = []
        video_models = []
        search_models = []

        for m in all_models:
            mid = m.get("id", "").lower()
            params = m.get("supported_parameters", [])
            # Skip OpenRouter routing models — they are text-only, not real media models
            if mid.startswith("openrouter/"):
                continue
            # Check output_modalities from architecture for image/video support
            arch = m.get("architecture", {})
            output_modalities = arch.get("output_modalities", [])

            # Mutually exclusive: image > video > search priority
            if "image" in output_modalities:
                image_models.append(m["id"])
            elif any(kw in mid for kw in video_keywords):
                video_models.append(m["id"])
            elif "web_search" in params or any(kw in mid for kw in search_keywords):
                search_models.append(m["id"])

        lines = []
        if image_models:
            lines.append("Image generation models: " + ", ".join(image_models))
        if video_models:
            lines.append("Video generation models: " + ", ".join(video_models))
        if search_models:
            lines.append("Web search models: " + ", ".join(search_models))

        return "\n".join(lines) if lines else "none"

    def assign_models(self, agent_specs: list[dict], manager_goal: str) -> dict:
        """Ask LLM (smartest model) to assign best model per agent. Falls back to smartest on any error."""
        candidates = self._get_candidates()
        if not candidates:
            return {"manager": "", "workers": {}}

        valid_ids = {c["id"] for c in candidates}
        table = self._build_candidate_table(candidates)

        agent_list = "\n".join(
            f"- {s.get('name', 'Agent')}: role={s.get('role', '')}, "
            f"capabilities={s.get('tools', [])}, "
            f"task={s.get('task_description', '')[:100]}"
            for s in agent_specs
        )

        prompt = (
            "You are a model assignment optimizer for an AI agent platform.\n"
            "Given a list of available LLM models and a team of agents, assign the best model to each.\n\n"
            "Rules:\n"
            "- Assign the SMARTER/larger model to the Manager (it coordinates and synthesizes)\n"
            "- Assign models suited to each worker's task based on their capabilities "
            "(e.g. coding models for write_code, creative models for creative_writing, "
            "large context models for long_context)\n"
            "- Only use model IDs from the list below\n"
            "- Consider context length and parameter count when choosing\n\n"
            f"Available models:\n{table}\n\n"
            f"Manager goal: {manager_goal}\n\n"
            f"Agents:\n{agent_list}\n\n"
            "Respond with EXACTLY this JSON (no other text):\n"
            '{"manager": "model_id", "workers": {"AgentName": "model_id", ...}}'
        )

        smartest = self._pick_smartest()
        if not smartest:
            return {"manager": "", "workers": {}}

        try:
            print(f"[ModelSelector] Using smartest model for analysis: {smartest}")
            llm = LLM(
                model=f"openrouter/{smartest}",
                base_url=self.base_url,
                api_key=self.api_key,
                temperature=0.3,
                max_retries=0,
            )
            response = llm.call(prompt).strip()
            import json as _json
            match = re.search(r'\{.*\}', response, re.DOTALL)
            if match:
                result = _json.loads(match.group())
                manager_model = result.get("manager", "")
                if manager_model not in valid_ids:
                    manager_model = smartest
                workers = {}
                for spec in agent_specs:
                    name = spec.get("name", "Agent")
                    assigned = result.get("workers", {}).get(name, "")
                    if assigned not in valid_ids:
                        assigned = smartest
                    workers[name] = assigned
                print(f"[ModelSelector] manager={manager_model}, workers={workers}")
                return {"manager": manager_model, "workers": workers}
        except Exception as e:
            print(f"[ModelSelector] LLM analysis failed: {e}")

        # Fallback: smartest for manager, smartest for all workers
        workers = {s.get("name", "Agent"): smartest for s in agent_specs}
        print(f"[ModelSelector] Fallback smartest: manager={smartest}, workers={workers}")
        return {"manager": smartest, "workers": workers}


class LLMManager:
    """จัดการ LLM แบบ Modular รองรับ Local LLM และ OpenRouter พร้อม auto-fallback

    Tier priority (auto-detected from API key):
    1. paid   — API key มีเครดิต → ใช้ openrouter/auto (OpenRouter เลือก model อัตโนมัติ)
    2. free   — API key เป็น free tier → ใช้ openrouter/free (OpenRouter เลือก free model อัตโนมัติ)
    3. local  — ไม่มี key หรือทั้งสองขั้นต้นล้มเหลว → ใช้ Ollama
    4. error  — ใช้ไม่ได้เลย
    """

    def __init__(self):
        self.provider = os.getenv("LLM_PROVIDER", "local").lower()
        self.model = os.getenv("LLM_MODEL", "qwen2.5:7b")
        self.base_url = os.getenv("LLM_BASE_URL", "http://localhost:11434")
        self.api_key = os.getenv("LLM_API_KEY", "ollama")
        self.temperature = float(os.getenv("LLM_TEMPERATURE", "0.7"))

        # Fallback config (local Ollama) — dev-only opt-in
        # PRD: OpenRouter is the single API. Local fallback is for dev only.
        self.local_fallback_enabled = os.getenv("LOCAL_LLM_FALLBACK", "true").lower() == "true"
        self.fallback_provider = os.getenv("LLM_FALLBACK_PROVIDER", "local").lower()
        self.fallback_model = os.getenv("LLM_FALLBACK_MODEL", "qwen2.5:7b")
        self.fallback_base_url = os.getenv("LLM_FALLBACK_BASE_URL", "http://localhost:11434")
        self.fallback_api_key = os.getenv("LLM_FALLBACK_API_KEY", "ollama")

        # Rate limit tracking
        self._fallback_until = 0.0
        self._fallback_cooldown = 60.0
        self._max_attempts = int(os.getenv("LLM_MAX_ATTEMPTS", "4"))

        # Auto-detect tier from API key
        self.tier = self._detect_tier()
        print(f"[LLMManager] Detected tier: {self.tier}")

        # Default routing model — OpenRouter selects the best model per prompt
        self._default_model = "openrouter/auto" if self.tier == "paid" else "openrouter/free" if self.tier == "free" else ""

        # User-selected model (session-level override)
        self._selected_model: str = ""

    def set_selected_model(self, model_id: str):
        """Set user-selected model to override default routing."""
        self._selected_model = model_id
        print(f"[LLMManager] User selected model: {model_id}")

    def _detect_tier(self) -> str:
        """Auto-detect LLM tier from API key: paid → free → local."""
        if self.provider != "openrouter":
            return "local"
        if not self.api_key or self.api_key == "ollama":
            return "local"
        # Check if key has credits via OpenRouter API
        try:
            resp = requests.get(
                f"{self.base_url}/credits",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=5,
            )
            if resp.status_code == 200:
                data = resp.json()
                credits = float(data.get("data", {}).get("total_credits", 0))
                if credits > 0:
                    print(f"[LLMManager] Paid tier detected: {credits} credits available")
                    return "paid"
            print(f"[LLMManager] Free tier (no credits). status={resp.status_code}")
            return "free"
        except Exception as e:
            print(f"[LLMManager] Credit check failed: {_sanitize_error(e)}, defaulting to free")
            return "free"

    def _is_in_cooldown(self) -> bool:
        import time
        return time.time() < self._fallback_until

    def _trigger_cooldown(self, reason: str = ""):
        import time
        self._fallback_until = time.time() + self._fallback_cooldown
        print(f"[LLMManager] Cooldown triggered ({reason or 'unknown'}). Falling back to {self.fallback_provider} for {self._fallback_cooldown}s")

    async def call_async(self, prompt: str) -> str:
        """Call LLM in a thread pool so the event loop stays free for websocket pings."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.call_with_fallback, prompt)

    async def call_with_image_async(self, prompt: str, image_data_url: str) -> str:
        """Call LLM with text + image (multimodal/vision) in a thread pool."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._call_with_image, prompt, image_data_url)

    def _call_with_image(self, prompt: str, image_data_url: str) -> str:
        """Call OpenRouter with multimodal content (text + image_url)."""
        from openai import OpenAI
        model_id = self._selected_model or self._default_model
        if not model_id:
            raise RuntimeError("No model available for vision call")
        client = OpenAI(base_url=self.base_url, api_key=self.api_key, max_retries=0, timeout=120)
        response = client.chat.completions.create(
            model=model_id,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_data_url}},
                ],
            }],
            temperature=self.temperature,
        )
        return response.choices[0].message.content or ""

    async def call_with_multimodal_async(self, prompt: str, content_blocks: list[dict], plugins: list = None) -> str:
        """Call LLM with text + multimodal content blocks (image, PDF, audio, video)."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._call_with_multimodal, prompt, content_blocks, plugins)

    def _call_with_multimodal(self, prompt: str, content_blocks: list[dict], plugins: list = None) -> str:
        """Call OpenRouter with multimodal content blocks."""
        from openai import OpenAI
        model_id = self._selected_model or self._default_model
        if not model_id:
            raise RuntimeError("No model available for multimodal call")
        client = OpenAI(base_url=self.base_url, api_key=self.api_key, max_retries=0, timeout=120)
        messages = [{"role": "user", "content": [{"type": "text", "text": prompt}] + content_blocks}]
        kwargs = {"model": model_id, "messages": messages, "temperature": self.temperature}
        if plugins:
            kwargs["extra_body"] = {"plugins": plugins}
        response = client.chat.completions.create(**kwargs)
        return response.choices[0].message.content or ""

    def call_with_multimodal_streaming(self, prompt: str, content_blocks: list[dict], plugins: list = None):
        """Streaming version of multimodal call — yields text chunks."""
        from openai import OpenAI
        model_id = self._selected_model or self._default_model
        if not model_id:
            raise RuntimeError("No model available for multimodal streaming")
        client = OpenAI(base_url=self.base_url, api_key=self.api_key, max_retries=0, timeout=120)
        messages = [{"role": "user", "content": [{"type": "text", "text": prompt}] + content_blocks}]
        kwargs = {"model": model_id, "messages": messages, "temperature": self.temperature, "stream": True}
        if plugins:
            kwargs["extra_body"] = {"plugins": plugins}
        stream = client.chat.completions.create(**kwargs)
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    def call_streaming(self, prompt: str):
        """Streaming version of call_with_fallback — yields text chunks."""
        if not self._is_in_cooldown():
            if self.tier in ("paid", "free"):
                try:
                    from openai import OpenAI
                    client = OpenAI(base_url=self.base_url, api_key=self.api_key, max_retries=0, timeout=120)
                    model_id = self._selected_model or self._default_model
                    stream = client.chat.completions.create(
                        model=model_id,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=self.temperature,
                        stream=True,
                        stream_options={"include_usage": True},
                    )
                    got_content = False
                    for chunk in stream:
                        if chunk.choices and chunk.choices[0].delta.content:
                            got_content = True
                            yield chunk.choices[0].delta.content
                    if got_content:
                        return
                    # Empty stream — treat as error so caller can retry
                    print(f"[LLMManager] Empty stream from {model_id}, treating as failure", flush=True)
                except Exception as e:
                    err_msg = _sanitize_error(e)
                    print(f"[LLMManager] Primary LLM streaming error: {err_msg}")
                    self._trigger_cooldown(err_msg)

        # Local fallback streaming
        if not self.local_fallback_enabled:
            raise RuntimeError("All OpenRouter tiers exhausted. Local fallback is disabled.")
        print(f"[LLMManager] Using local fallback streaming: {self.fallback_provider}/{self.fallback_model}")
        from openai import OpenAI
        client = OpenAI(base_url=self.fallback_base_url, api_key=self.fallback_api_key, max_retries=0)
        stream = client.chat.completions.create(
            model=self.fallback_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=self.temperature,
            stream=True,
        )
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    def _build_llm(self, provider: str, model: str, base_url: str, api_key: str) -> LLM:
        if provider == "openrouter":
            return LLM(
                model=model if model.startswith("openrouter/") else f"openrouter/{model}",
                base_url=base_url,
                api_key=api_key,
                temperature=self.temperature,
                max_retries=0,
            )
        if provider == "google":
            os.environ["GEMINI_API_KEY"] = api_key
            return LLM(
                model=f"gemini/{model}",
                temperature=self.temperature,
            )
        return LLM(
            model=f"ollama/{model}",
            base_url=base_url,
            api_key=api_key,
            temperature=self.temperature,
        )

    def get_llm(self) -> LLM:
        """สร้าง LLM instance ตาม tier ที่ตรวจพบ พร้อม auto-fallback"""
        if self._is_in_cooldown():
            print(f"[LLMManager] Cooldown active, using fallback: {self.fallback_provider}/{self.fallback_model}")
            return self._build_llm(
                self.fallback_provider,
                self.fallback_model,
                self.fallback_base_url,
                self.fallback_api_key,
            )
        if self._selected_model and self.tier in ("paid", "free"):
            print(f"[LLMManager] Using user-selected model: {self._selected_model}")
            return self._build_llm(self.provider, self._selected_model, self.base_url, self.api_key)
        if self._default_model and self.tier in ("paid", "free"):
            print(f"[LLMManager] Using routing model: {self._default_model}")
            return self._build_llm(self.provider, self._default_model, self.base_url, self.api_key)
        # local or fallback
        return self._build_llm(self.fallback_provider, self.fallback_model, self.fallback_base_url, self.fallback_api_key)

    def get_selected_model_name(self) -> str:
        """Return the model name that get_llm() would actually use."""
        if self._selected_model and self.tier in ("paid", "free"):
            return self._selected_model
        if self._default_model and self.tier in ("paid", "free"):
            return self._default_model
        return self.fallback_model or "local"

    def build_llm_for_model(self, model_id: str) -> LLM:
        """Build LLM for a specific model id (used by ModelSelector assignments)."""
        if not model_id:
            return self.get_llm()
        if self._is_in_cooldown():
            return self._build_llm(
                self.fallback_provider,
                self.fallback_model,
                self.fallback_base_url,
                self.fallback_api_key,
            )
        return self._build_llm(self.provider, model_id, self.base_url, self.api_key)

    def call_with_fallback(self, prompt: str) -> str:
        """Call LLM with automatic fallback: routing model → local → error."""
        if not self._is_in_cooldown():
            if self.tier in ("paid", "free"):
                try:
                    llm = self.get_llm()
                    return llm.call(prompt)
                except Exception as e:
                    err_msg = _sanitize_error(e)
                    print(f"[LLMManager] Primary LLM error: {err_msg}")
                    self._trigger_cooldown(err_msg)
                    if not self.local_fallback_enabled:
                        raise RuntimeError(self._format_user_error(err_msg))

        # Use local fallback (dev-only opt-in)
        if not self.local_fallback_enabled:
            raise RuntimeError("OpenRouter is in cooldown. Local fallback is disabled. Set LOCAL_LLM_FALLBACK=true to enable.")
        print(f"[LLMManager] Using local fallback: {self.fallback_provider}/{self.fallback_model}")
        llm = self._build_llm(
            self.fallback_provider,
            self.fallback_model,
            self.fallback_base_url,
            self.fallback_api_key,
        )
        try:
            return llm.call(prompt)
        except Exception as e:
            raise RuntimeError(f"All LLM tiers failed. Last error: {e}")

    def report_rate_limit(self):
        """Call this when a rate limit error is caught to trigger fallback."""
        self._trigger_cooldown("rate limit reported")

    def _format_user_error(self, err_msg: str) -> str:
        """Translate raw API error into user-friendly message with suggested action."""
        model_id = self._selected_model or self._default_model or "auto"
        if "502" in err_msg or "Bad Gateway" in err_msg:
            return (
                f"⚠️ โมเดล '{model_id}' ไม่สามารถใช้งานได้ (Error 502: Bad Gateway)\n"
                f"สาเหตุ: OpenRouter ส่งคำขอไปยัง provider แล้วได้รับ error กลับมา\n"
                f"แนะนำ: กรุณาเปลี่ยนโมเดลในปุ่ม Model ด้านบน แล้วลองใหม่"
            )
        if "404" in err_msg or "Not Found" in err_msg or "No endpoints" in err_msg:
            return (
                f"⚠️ โมเดล '{model_id}' ไม่รองรับการใช้งานนี้ (Error 404: Not Found)\n"
                f"สาเหตุ: โมเดลนี้อาจไม่รองรับ tool use หรือไม่มี provider ที่พร้อมให้บริการ\n"
                f"แนะนำ: กรุณาเปลี่ยนโมเดลในปุ่ม Model ด้านบน แล้วลองใหม่"
            )
        if "429" in err_msg or "rate limit" in err_msg.lower() or "too many requests" in err_msg.lower():
            return (
                f"⚠️ โมเดล '{model_id}' ถูกจำกัดการใช้งานชั่วคราว (Error 429: Rate Limit)\n"
                f"สาเหตุ: ใช้งานเกินโควต้าในช่วงเวลาสั้น ๆ\n"
                f"แนะนำ: กรุณารอ 1-2 นาทีแล้วลองใหม่ หรือเปลี่ยนโมเดลในปุ่ม Model ด้านบน"
            )
        if "401" in err_msg or "403" in err_msg or "Unauthorized" in err_msg or "Forbidden" in err_msg:
            return (
                f"⚠️ ไม่สามารถเข้าถึงโมเดล '{model_id}' ได้ (Error 401/403: Unauthorized)\n"
                f"สาเหตุ: API key ไม่ถูกต้องหรือไม่มีสิทธิ์ใช้โมเดลนี้\n"
                f"แนะนำ: ตรวจสอบ API key หรือเปลี่ยนโมเดลในปุ่ม Model ด้านบน"
            )
        if "500" in err_msg or "Internal Server Error" in err_msg:
            return (
                f"⚠️ เซิร์ฟเวอร์ OpenRouter มีปัญหา (Error 500: Internal Server Error)\n"
                f"สาเหตุ: ปัญหาฝั่งเซิร์ฟเวอร์ชั่วคราว\n"
                f"แนะนำ: กรุณารอสักครู่แล้วลองใหม่ หรือเปลี่ยนโมเดลในปุ่ม Model ด้านบน"
            )
        return (
            f"⚠️ โมเดล '{model_id}' เกิดข้อผิดพลาด: {err_msg}\n"
            f"แนะนำ: กรุณาเปลี่ยนโมเดลในปุ่ม Model ด้านบน แล้วลองใหม่"
        )


def _is_rate_limit_error(error: Exception) -> bool:
    """Check if an exception is a rate limit error from OpenRouter or similar."""
    msg = str(error).lower()
    keywords = ["rate limit", "rate_limit", "429", "too many requests", "quota exceeded"]
    return any(kw in msg for kw in keywords)


# ============================================================
# 1b. Media Generation Manager (Image & Video) — Tiered Fallback
# ============================================================
class MediaGenerationManager:
    """จัดการ media generation ผ่าน OpenRouter API เท่านั้น
    AI เป็นตัวเลือก model สำหรับ image, video, TTS, STT, และ vision analysis
    """

    PUBLIC_DIR = os.path.join(os.path.dirname(__file__), "public", "generated")
    BASE_URL_FOR_CLIENT = "/public/generated"

    def __init__(self, llm_manager: 'LLMManager'):
        self.tier = llm_manager.tier
        self.openrouter_key = llm_manager.api_key
        self.openrouter_base = llm_manager.base_url.rstrip("/")
        self.image_model = ""  # Set per run via set_models()
        self.video_model = ""  # Set per run via set_models()
        self.tts_model = ""  # Set per run via set_models()
        self.stt_model = ""  # Set per run via set_models()
        self.vision_model = ""  # Set per run via set_models()
        os.makedirs(self.PUBLIC_DIR, exist_ok=True)

    def set_models(self, image_model: str = "", video_model: str = "",
                   tts_model: str = "", stt_model: str = "", vision_model: str = ""):
        """Set AI-selected models for this run."""
        self.image_model = image_model
        self.video_model = video_model
        self.tts_model = tts_model
        self.stt_model = stt_model
        self.vision_model = vision_model

    def _save_binary(self, content: bytes, ext: str, prefix: str = "gen") -> str:
        filename = f"{prefix}_{uuid.uuid4().hex[:8]}.{ext}"
        filepath = os.path.join(self.PUBLIC_DIR, filename)
        with open(filepath, "wb") as f:
            f.write(content)
        return f"{self.BASE_URL_FOR_CLIENT}/{filename}"

    def generate_image(self, prompt: str, width: int = 1024, height: int = 1024) -> str:
        """Generate an image via OpenRouter. Returns a URL to the saved file, or an error message."""
        if not prompt or not prompt.strip():
            return "Error: Empty prompt for image generation"

        if not self.image_model:
            return "Error: No image model selected by AI. Cannot generate image."

        print(f"[MediaGen] Starting image generation with model={self.image_model}, prompt={prompt[:80]}...", flush=True)
        try:
            result = self._openrouter_image(prompt, width, height)
            print(f"[MediaGen] Image generation succeeded: {result}", flush=True)
            return result
        except Exception as e:
            print(f"[MediaGen] OpenRouter image failed: {_sanitize_error(e)}", flush=True)
            return f"Error: Image generation failed: {_sanitize_error(e)}"

    def generate_video(self, prompt: str, width: int = 1024, height: int = 1024, duration: int = 5) -> str:
        """Generate a video via OpenRouter. Returns a URL to the saved file, or an error message."""
        if not prompt or not prompt.strip():
            return "Error: Empty prompt for video generation"

        if not self.video_model:
            return "Error: No video model selected by AI. Cannot generate video."

        try:
            return self._openrouter_video(prompt, width, height, duration)
        except Exception as e:
            print(f"[MediaGen] OpenRouter video failed: {_sanitize_error(e)}")
            return f"Error: Video generation failed: {_sanitize_error(e)}"

    def _placeholder_image(self, prompt: str, width: int, height: int) -> str:
        """Generate a placeholder image locally with Pillow (no external API needed)."""
        try:
            from PIL import Image as PILImage, ImageDraw, ImageFont
            w, h = min(width, 1024), min(height, 1024)
            img = PILImage.new('RGB', (w, h), color=(45, 45, 55))
            draw = ImageDraw.Draw(img)
            text = f"Placeholder\n{prompt[:80]}\n— generation pending paid tier"
            try:
                font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 20)
            except Exception:
                font = ImageFont.load_default()
            lines = text.split('\n')
            total_h = len(lines) * 28
            y = (h - total_h) // 2
            for line in lines:
                bbox = draw.textbbox((0, 0), line, font=font)
                tw = bbox[2] - bbox[0]
                x = (w - tw) // 2
                draw.text((x, y), line, fill=(180, 180, 200), font=font)
                y += 28
            return self._save_binary(self._pil_to_bytes(img, 'JPEG'), 'jpg', 'placeholder_image')
        except Exception as e:
            print(f"[MediaGen] Placeholder image generation failed: {e}")
            return f"{self.BASE_URL_FOR_CLIENT}/placeholder_image.jpg"

    def _placeholder_video(self, prompt: str, width: int, height: int, duration: int) -> str:
        """Generate a placeholder image representing a video generation locally with Pillow."""
        try:
            from PIL import Image as PILImage, ImageDraw, ImageFont
            w, h = min(width, 1024), min(height, 1024)
            img = PILImage.new('RGB', (w, h), color=(35, 25, 45))
            draw = ImageDraw.Draw(img)
            text = f"Video Placeholder\n{prompt[:80]}\n({duration}s) — pending paid tier"
            try:
                font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 20)
            except Exception:
                font = ImageFont.load_default()
            lines = text.split('\n')
            total_h = len(lines) * 28
            y = (h - total_h) // 2
            for line in lines:
                bbox = draw.textbbox((0, 0), line, font=font)
                tw = bbox[2] - bbox[0]
                x = (w - tw) // 2
                draw.text((x, y), line, fill=(200, 180, 220), font=font)
                y += 28
            return self._save_binary(self._pil_to_bytes(img, 'JPEG'), 'jpg', 'placeholder_video')
        except Exception as e:
            print(f"[MediaGen] Placeholder video generation failed: {e}")
            return f"{self.BASE_URL_FOR_CLIENT}/placeholder_video.jpg"

    @staticmethod
    def _pil_to_bytes(img, fmt='JPEG'):
        buf = io.BytesIO()
        img.save(buf, format=fmt)
        return buf.getvalue()

    def _resolution_tier(self, width: int, height: int) -> str:
        max_dim = max(width, height)
        if max_dim >= 2048:
            return "4K"
        if max_dim >= 1024:
            return "1K"
        return "512"

    def _openrouter_image(self, prompt: str, width: int, height: int) -> str:
        payload = {
            "prompt": prompt,
        }
        if self.image_model:
            payload["model"] = self.image_model
        print(f"[MediaGen] POST {self.openrouter_base}/images model={self.image_model}", flush=True)
        resp = requests.post(
            f"{self.openrouter_base}/images",
            headers={
                "Authorization": f"Bearer {self.openrouter_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=120,
        )
        print(f"[MediaGen] API responded: {resp.status_code}", flush=True)
        if resp.status_code != 200:
            raise RuntimeError(f"OpenRouter image API returned {resp.status_code}: {resp.text[:200]}")
        data = resp.json()
        items = data.get("data", [])
        if not items:
            raise RuntimeError("OpenRouter image API returned empty data")
        item = items[0]
        print(f"[MediaGen] Response keys: {list(item.keys())}", flush=True)
        # API may return b64_json (base64-encoded image) or url (downloadable URL)
        if "b64_json" in item:
            import base64
            img_bytes = base64.b64decode(item["b64_json"])
            return self._save_binary(img_bytes, "png", "img")
        elif "url" in item and item["url"]:
            img_resp = requests.get(item["url"], timeout=60)
            if img_resp.status_code != 200:
                raise RuntimeError(f"Failed to download image: {img_resp.status_code}")
            return self._save_binary(img_resp.content, "png", "img")
        else:
            raise RuntimeError(f"OpenRouter image API returned no usable image data (keys: {list(item.keys())})")

    def _openrouter_video(self, prompt: str, width: int, height: int, duration: int) -> str:
        payload = {
            "prompt": prompt,
            "resolution": "720p",
            "duration": duration,
            "aspect_ratio": "16:9" if width > height else "9:16",
        }
        if self.video_model:
            payload["model"] = self.video_model
        resp = requests.post(
            f"{self.openrouter_base}/videos",
            headers={
                "Authorization": f"Bearer {self.openrouter_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=120,
        )
        if resp.status_code not in (200, 201, 202):
            raise RuntimeError(f"OpenRouter video API returned {resp.status_code}: {resp.text[:200]}")
        data = resp.json()
        job_id = data.get("id", "")
        polling_url = data.get("polling_url", f"{self.openrouter_base}/videos/{job_id}")
        if not job_id:
            raise RuntimeError("OpenRouter video API returned no job ID")

        for _ in range(60):
            time.sleep(5)
            poll = requests.get(
                polling_url,
                headers={"Authorization": f"Bearer {self.openrouter_key}"},
                timeout=30,
            )
            if poll.status_code != 200:
                continue
            poll_data = poll.json()
            status = poll_data.get("status", "")
            if status == "completed":
                unsigned_urls = poll_data.get("unsigned_urls", [])
                if not unsigned_urls:
                    raise RuntimeError("OpenRouter video completed but no unsigned_urls")
                content_url = unsigned_urls[0]
                vid_resp = requests.get(
                    content_url,
                    headers={"Authorization": f"Bearer {self.openrouter_key}"},
                    timeout=120,
                )
                if vid_resp.status_code != 200:
                    raise RuntimeError(f"Failed to download video: {vid_resp.status_code}")
                return self._save_binary(vid_resp.content, "mp4", "vid")
            if status in ("failed", "error"):
                raise RuntimeError(f"OpenRouter video generation failed: {poll_data.get('error', 'unknown')}")
        raise RuntimeError("OpenRouter video generation timed out after 5 minutes")


# ============================================================
# 5a. Capability Registry — capability-based tool/model assignment
# ============================================================
class CapabilityRegistry:
    """Maps capability names to their fulfillment strategy (tool adapter or model trait)."""

    CAPABILITIES = [
        {
            "name": "search_web",
            "description": "Search the web for current information using OpenRouter (AI-selected search model)",
            "type": "tool",
            "tool_name": "search_web",
        },
        {
            "name": "generate_image",
            "description": "Generate images from text prompts using AI image generation via OpenRouter",
            "type": "tool",
            "tool_name": "generate_image",
        },
        {
            "name": "generate_video",
            "description": "Generate short videos from text prompts using AI video generation via OpenRouter",
            "type": "tool",
            "tool_name": "generate_video",
        },
        {
            "name": "text_to_speech",
            "description": "Convert text to speech audio using AI TTS models via OpenRouter (for narration, voiceover)",
            "type": "tool",
            "tool_name": "text_to_speech",
        },
        {
            "name": "transcribe_audio",
            "description": "Transcribe audio files to text using AI STT models via OpenRouter (for subtitle generation, audio analysis)",
            "type": "tool",
            "tool_name": "transcribe_audio",
        },
        {
            "name": "analyze_image",
            "description": "Analyze and describe images using AI vision models via OpenRouter (for image understanding, OCR, visual analysis)",
            "type": "tool",
            "tool_name": "analyze_image",
        },
        {
            "name": "reasoning",
            "description": "Strong analytical and reasoning capability for coordination and planning",
            "type": "model_trait",
            "traits": {"strength": "reasoning"},
        },
        {
            "name": "creative_writing",
            "description": "Creative writing for content, scripts, and marketing copy",
            "type": "model_trait",
            "traits": {"strength": "creative"},
        },
        {
            "name": "write_code",
            "description": "Code generation and technical writing",
            "type": "model_trait",
            "traits": {"strength": "coding"},
        },
        {
            "name": "long_context",
            "description": "Handles long documents and large context windows (128k+ tokens)",
            "type": "model_trait",
            "traits": {"min_context": 128000},
        },
    ]

    def __init__(self):
        self._caps = {c["name"]: c for c in self.CAPABILITIES}

    def list_capabilities(self) -> list[dict]:
        return list(self._caps.values())

    def list_catalog(self) -> list[dict]:
        return [
            {"name": c["name"], "description": c["description"]}
            for c in self._caps.values()
        ]

    def resolve(self, capability: str) -> dict | None:
        cap = self._caps.get(capability)
        if not cap:
            return None
        if cap["type"] == "tool":
            return {"type": "tool", "tool_name": cap["tool_name"]}
        else:
            return {"type": "model_trait", "traits": cap.get("traits", {})}


class CapabilityResolver:
    """Resolves capabilities to concrete tools and model traits for agents."""

    def __init__(self, registry: CapabilityRegistry | None = None):
        self.registry = registry or CapabilityRegistry()

    def infer_capabilities(self, agent_specs: list[dict]) -> list[dict]:
        """Map each agent spec's tools to capabilities, add reasoning if no tools."""
        results = []
        for spec in agent_specs:
            tools = spec.get("tools", [])
            caps = list(tools)  # tool names ARE capability names
            if not caps:
                caps = ["reasoning"]
            results.append({
                "name": spec.get("name", "Agent"),
                "capabilities": caps,
            })
        return results

    def assign_to_agent(self, capabilities: list[str], agent_spec: dict) -> dict:
        """Resolve capabilities into concrete tools + model traits for an agent."""
        tools = []
        traits = {}
        for cap_name in capabilities:
            resolution = self.registry.resolve(cap_name)
            if resolution is None:
                continue
            if resolution["type"] == "tool":
                tools.append(resolution["tool_name"])
            elif resolution["type"] == "model_trait":
                traits.update(resolution.get("traits", {}))
        return {
            "name": agent_spec.get("name", "Agent"),
            "role": agent_spec.get("role", ""),
            "goal": agent_spec.get("goal", ""),
            "backstory": agent_spec.get("backstory", ""),
            "tools": tools,
            "traits": traits,
        }


# ============================================================
# 5. Tool Registry (minimal)
# ============================================================
class ToolRegistry:
    """Registry สำหรับลงทะเบียนและค้นหาเครื่องมือภายนอก"""

    def __init__(self):
        self._tools = {}
        self.register("search_web", search_web)
        self.register("generate_image", generate_image)
        self.register("generate_video", generate_video)
        self.register("text_to_speech", text_to_speech)
        self.register("transcribe_audio", transcribe_audio)
        self.register("analyze_image", analyze_image)
        self._cap_registry = CapabilityRegistry()

    def register(self, name: str, tool):
        self._tools[name] = tool

    def get(self, name: str):
        return self._tools.get(name)

    def list_tools(self) -> list[str]:
        return list(self._tools.keys())

    def list_tool_catalog(self) -> list[dict]:
        return self._cap_registry.list_catalog()


# ============================================================
# 4. Agent Registry System
# ============================================================
class AgentRegistry:
    """คลาสสำหรับเก็บข้อมูล Agent ทั้งหมด (ID, Name, Role, Persona, Status)"""

    def __init__(self, filepath: str = AGENT_REGISTRY_FILE):
        self.filepath = filepath
        self.agents: list[dict] = []
        self._load()

    def _load(self):
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                self.agents = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self.agents = []

    def _save(self):
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(self.agents, f, ensure_ascii=False, indent=2)

    def add_agent(self, spec: dict) -> dict:
        agent = {
            "id": str(uuid.uuid4())[:8],
            "name": spec.get("name", "Unnamed"),
            "role": spec.get("role", ""),
            "goal": spec.get("goal", ""),
            "persona": spec.get("backstory", ""),
            "tools": spec.get("tools", []),
            "depends_on": spec.get("depends_on", []),
            "model": spec.get("model", ""),
            "status": "Idle",
            "created_at": datetime.now().isoformat(),
            "last_used_at": None,
        }
        self.agents.append(agent)
        self._save()
        return agent

    def find_idle_agent(self, required_role: str, required_tools: list[str]) -> dict | None:
        required_role_lower = required_role.lower() if required_role else ""
        for agent in self.agents:
            if agent.get("status") != "Idle":
                continue
            # 1) Exact tools match has highest priority
            if required_tools and all(t in agent.get("tools", []) for t in required_tools):
                return agent
            # 2) Role keyword match
            if required_role_lower and required_role_lower in agent.get("role", "").lower():
                return agent
        return None

    def get_by_id(self, agent_id: str) -> dict | None:
        for agent in self.agents:
            if agent.get("id") == agent_id:
                return agent
        return None

    def update_status(self, agent_id: str, status: str) -> bool:
        for agent in self.agents:
            if agent.get("id") == agent_id:
                agent["status"] = status
                if status == "Busy":
                    agent["last_used_at"] = datetime.now().isoformat()
                self._save()
                return True
        return False

    def update_agent(self, agent_id: str, fields: dict) -> bool:
        for agent in self.agents:
            if agent.get("id") == agent_id:
                for key in ("name", "role", "goal", "persona", "tools", "model"):
                    if key in fields:
                        agent[key] = fields[key]
                self._save()
                return True
        return False

    def delete_agent(self, agent_id: str) -> bool:
        original_len = len(self.agents)
        self.agents = [a for a in self.agents if a.get("id") != agent_id]
        if len(self.agents) < original_len:
            self._save()
            return True
        return False

    def list_agents(self) -> list[dict]:
        return self.agents

    def to_spec(self, agent: dict) -> dict:
        """แปลงข้อมูล Agent ในทะเบียนให้เป็น spec ที่ AgentFactory ใช้ได้"""
        return {
            "id": agent.get("id"),
            "name": agent.get("name", "Unnamed"),
            "role": agent.get("role", ""),
            "goal": agent.get("goal", agent.get("role", "")),
            "backstory": agent.get("persona", ""),
            "tools": agent.get("tools", []),
            "model": agent.get("model", ""),
            "task_description": agent.get("last_task", ""),
            "depends_on": agent.get("depends_on", []),
        }

    def to_markdown_table(self) -> str:
        if not self.agents:
            return "_ยังไม่มี Agent ในทะเบียน_"
        lines = [
            "| ID | Name | Role | Status | Tools |",
            "|---|---|---|---|---|",
        ]
        for a in self.agents:
            status = "🟢 Idle" if a.get("status") == "Idle" else "🔴 Busy"
            tools = ", ".join(a.get("tools", [])) if a.get("tools") else "-"
            name = a.get("name", "")[:25]
            role = a.get("role", "")[:35]
            lines.append(f"| {a.get('id', '')} | {name} | {role} | {status} | {tools} |")
        return "\n".join(lines)


# ============================================================
# 4b. Task Store (JSON-backed persistence)
# ============================================================
class TaskStore:
    """เก็บประวัติ Task ลง JSON file เพื่อไม่ให้หายเมื่อ refresh"""

    def __init__(self, filepath: str = TASK_REGISTRY_FILE):
        self.filepath = filepath
        self.tasks: list[dict] = []
        self._load()

    def _load(self):
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                self.tasks = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self.tasks = []

    def _save(self):
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(self.tasks, f, ensure_ascii=False, indent=2)

    def add_task(self, task: dict) -> dict:
        self.tasks.append(task)
        self._save()
        return task

    def get_task(self, task_id: str) -> dict | None:
        for t in self.tasks:
            if t.get("id") == task_id:
                return t
        return None

    def update_task(self, task_id: str, **kwargs) -> dict | None:
        for t in self.tasks:
            if t.get("id") == task_id:
                t.update(kwargs)
                self._save()
                return t
        return None

    def list_tasks(self) -> list[dict]:
        return self.tasks

    def delete_task(self, task_id: str) -> bool:
        original_len = len(self.tasks)
        self.tasks = [t for t in self.tasks if t.get("id") != task_id]
        if len(self.tasks) < original_len:
            self._save()
            return True
        return False

    def clear_all(self):
        self.tasks = []
        self._save()


# ============================================================
# 4c. Chat Session Store (JSON-backed persistence)
# ============================================================
class ChatStore:
    """เก็บประวัติแชทหลาย session ลง JSON file"""

    def __init__(self, filepath: str = CHAT_SESSIONS_FILE):
        self.filepath = filepath
        self.sessions: list[dict] = []
        self._load()

    def _load(self):
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                self.sessions = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self.sessions = []

    def _save(self):
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(self.sessions, f, ensure_ascii=False, indent=2)

    def create_session(self, title: str = "New Chat") -> dict:
        session = {
            "id": str(uuid.uuid4())[:8],
            "title": title,
            "messages": [],
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }
        self.sessions.append(session)
        self._save()
        return session

    def get_session(self, session_id: str) -> dict | None:
        for s in self.sessions:
            if s.get("id") == session_id:
                return s
        return None

    def add_message(self, session_id: str, message: dict):
        session = self.get_session(session_id)
        if session:
            session["messages"].append(message)
            session["updated_at"] = datetime.now().isoformat()
            # Auto-title from first user message
            if session["title"] == "New Chat" and message.get("role") == "user":
                title = message.get("content", "")[:40]
                if len(message.get("content", "")) > 40:
                    title += "..."
                session["title"] = title
            self._save()

    def rename_session(self, session_id: str, title: str) -> dict | None:
        session = self.get_session(session_id)
        if session:
            session["title"] = title
            session["updated_at"] = datetime.now().isoformat()
            self._save()
            return session
        return None

    def delete_session(self, session_id: str) -> bool:
        original_len = len(self.sessions)
        self.sessions = [s for s in self.sessions if s.get("id") != session_id]
        if len(self.sessions) < original_len:
            self._save()
            return True
        return False

    def list_sessions(self) -> list[dict]:
        return sorted(self.sessions, key=lambda s: s.get("updated_at", ""), reverse=True)

    def save_canvas_state(self, session_id: str, canvas_state: dict):
        """Save canvas state (nodes + edges) for a session"""
        session = self.get_session(session_id)
        if session:
            session["canvas_state"] = canvas_state
            session["updated_at"] = datetime.now().isoformat()
            self._save()

    def get_canvas_state(self, session_id: str) -> dict | None:
        """Get canvas state for a session"""
        session = self.get_session(session_id)
        if session:
            return session.get("canvas_state")
        return None


# ============================================================
# 3. Dynamic Agent Instantiation
# ============================================================
class AgentFactory:
    """เสก Agent และ Task ใหม่ระหว่างรัน (Runtime)"""

    def __init__(self, llm_manager: LLMManager, tool_registry: ToolRegistry):
        self.llm_manager = llm_manager
        self.tool_registry = tool_registry
        self._cap_resolver = CapabilityResolver()

    def create_agent(self, spec: dict, model_id: str = "") -> Agent:
        resolved = self._cap_resolver.assign_to_agent(
            spec.get("tools", []), spec
        )
        tools = []
        for tool_name in resolved["tools"]:
            tool = self.tool_registry.get(tool_name)
            if tool:
                tools.append(tool)

        if model_id:
            print(f"[AgentFactory] Agent {spec.get('name', '')} assigned model: {model_id}")
            llm = self.llm_manager.build_llm_for_model(model_id)
        else:
            llm = self.llm_manager.get_llm()

        return Agent(
            role=spec["role"],
            goal=spec["goal"],
            backstory=spec['backstory'],
            llm=llm,
            tools=tools,
            allow_delegation=False,
            verbose=True,
            max_iter=20,
            max_retry_limit=3,
        )

    def create_manager_agent(self, user_input: str, agent_specs: list[dict], model_id: str = "") -> Agent:
        agent_names = ", ".join(s.get("name", "Agent") for s in agent_specs)
        agent_roles = "; ".join(f"{s.get('name', 'Agent')} ({s.get('role', '')})" for s in agent_specs)

        if model_id:
            print(f"[AgentFactory] Manager assigned model: {model_id}")
            llm = self.llm_manager.build_llm_for_model(model_id)
        else:
            llm = self.llm_manager.get_llm()

        return Agent(
            role="Project Manager",
            goal=(
                f"Coordinate the team to accomplish: {user_input}\n"
                f"Available team members: {agent_roles}\n"
                "Delegate tasks efficiently, run independent tasks in parallel, "
                "and synthesize results into a final deliverable."
            ),
            backstory=(
                "You are an experienced project manager who coordinates teams effectively. "
                "You know when tasks can run in parallel and when one must wait for another. "
                "You ensure quality by reviewing each agent's output before moving forward."
            ),
            llm=llm,
            tools=[],
            allow_delegation=True,
            verbose=True,
            max_iter=25,
            max_retry_limit=3,
        )

    def create_task(self, agent: Agent, spec: dict, user_input: str) -> Task:
        tool_names = spec.get("tools", [])
        tool_instructions = ""
        cap_registry = CapabilityRegistry()
        for cap_name in tool_names:
            resolution = cap_registry.resolve(cap_name)
            if resolution and resolution["type"] == "tool":
                if cap_name == "generate_image":
                    tool_instructions += (
                        "\n\nIMPORTANT: You MUST call the generate_image tool with a detailed English prompt "
                        "that describes the visual you want to create. "
                        "Do NOT just describe the image in text — actually CALL the tool. "
                        "The prompt should be in English and visually descriptive. "
                        "Call the tool once per image you need to create — do not repeat the same call. "
                        "The user will review your prompt before generation happens — this is by design to control API costs."
                    )
                elif cap_name == "generate_video":
                    tool_instructions += (
                        "\n\nIMPORTANT: You MUST call the generate_video tool with a detailed English prompt "
                        "that describes the scene, camera movement, lighting, and mood. "
                        "Do NOT just describe the video in text — actually CALL the tool. "
                        "The prompt should be in English and cinematically descriptive. "
                        "Use duration parameter (2-15 seconds) to set clip length. "
                        "Call the tool once per video you need to create — do not repeat the same call. "
                        "The user will review your prompt before generation happens — this is by design to control API costs."
                    )
                elif cap_name == "search_web":
                    tool_instructions += (
                        "\n\nUse the search_web tool when you need current information or facts."
                    )

        attachment_ctx = cl.user_session.get("attachment_context")
        attachment_text = ""
        input_files = None
        if attachment_ctx:
            if attachment_ctx.get("text_content"):
                attachment_text = f"\n\nAttached file content:\n{attachment_ctx['text_content'][:5000]}\n"
            if attachment_ctx.get("context_text"):
                attachment_text += f"\nAttachment context: {attachment_ctx['context_text']}"
            crewai_files = cl.user_session.get("attachment_crewai_files")
            if crewai_files:
                input_files = crewai_files

        task_kwargs = {
            "description": (
                f"Context: A user requested: {user_input}\n\n"
                f"You are: {spec.get('name', 'Agent')} — {spec.get('role', '')}\n"
                f"Your task: {spec.get('task_description', '')}\n\n"
                "You are a worker agent in a multi-agent system. "
                "Your output will be collected and synthesized by a manager agent — it will NOT be shown directly to the user. "
                "Write your output as a report to the manager, not as a message to the user. "
                "Do not use conversational language (e.g., greetings, 'here are your...', 'please review'). "
                "Produce your work as a structured deliverable. "
                "Use your assigned tools when needed. "
                "Do not explain how things work internally."
                f"{tool_instructions}"
                f"{attachment_text}"
            ),
            "agent": agent,
            "expected_output": (
                "A structured deliverable in the same language as the user's request. "
                "Report what you produced, what tools you used, and any relevant details. "
                "This is a report to the manager agent, not a message to the user."
            ),
        }
        if input_files:
            task_kwargs["input_files"] = input_files
        return Task(**task_kwargs)


# ============================================================
# 2. Central Secretary
# ============================================================
class CentralSecretary:
    """AI Assessor: ประเมินความต้องการ, ถาม requirement, วิเคราะห์และวางแผน multi-agent"""

    def __init__(self, llm_manager: LLMManager):
        self.llm_manager = llm_manager

    async def assess(self, user_input: str, conversation_history: list[dict] | None = None) -> dict:
        """ประเมินความต้องการ: CHAT (ตอบเลย) / INFO (ตอบเลย) / TASK_NEEDS_INFO (ถามเพิ่ม) / TASK_READY (วางแผน)"""
        history_text = ""
        if conversation_history:
            history_text = "\nConversation so far:\n"
            for msg in conversation_history:
                history_text += f"- {msg.get('role', 'user')}: {msg.get('content', '')[:100]}\n"

        prompt = (
            "You are an AI Assessor for an Agent Management Platform.\n"
            "Evaluate the user's message and decide what to do next.\n\n"
            "Respond with EXACTLY one of these JSON objects (no other text):\n"
            '- {"action": "chat", "message": "your reply"} — for greetings, small talk, general questions\n'
            '- {"action": "info", "message": "your reply"} — for questions about the system/agents/status\n'
            '- {"action": "ask", "questions": ["q1", "q2", ...]} — when the user wants work done but needs are unclear\n'
            '- {"action": "plan", "summary": "brief summary of understood requirements"} — when requirements are clear enough to plan\n\n'
            "Guidelines:\n"
            "- If the user is just chatting or asking who you are → chat\n"
            "- If the user is asking about available agents or system status → info\n"
            "- If the user wants something done but missing key details (scope, quantity, platform, timeline) → ask\n"
            "- If the user has provided enough detail to design a plan → plan\n"
            "- Use the same language as the user.\n\n"
            f"{history_text}"
            f"User message: {user_input}\n"
            "Response JSON:"
        )
        response = (await self.llm_manager.call_async(prompt)).strip()
        return self._parse_assessment(response)

    def _parse_assessment(self, text: str) -> dict:
        """Parse LLM assessment response, with fallback"""
        try:
            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                if "action" in result:
                    return result
        except (json.JSONDecodeError, AttributeError):
            pass
        return {"action": "chat", "message": "ขออภัย ไม่เข้าใจคำถาม ลองใหม่อีกครั้ง"}

    async def assess_and_plan(
        self,
        user_input: str,
        conversation_history: list[dict] | None = None,
        model_table: str | None = None,
        valid_model_ids: set[str] | None = None,
        media_catalog: str | None = None,
        stream_callback=None,
    ) -> dict:
        """Unified call: assess + analyze + model assignment in one LLM response.

        Returns same format as assess() for chat/info/ask paths.
        For plan path, includes 'agents' and 'model_assignment' keys.
        Falls back to assess() on parse error.
        """
        history_text = ""
        if conversation_history:
            history_text = "\nConversation so far:\n"
            for msg in conversation_history:
                history_text += f"- {msg.get('role', 'user')}: {msg.get('content', '')[:100]}\n"

        cap_registry = CapabilityRegistry()
        catalog = cap_registry.list_catalog()
        caps_text = "\n".join(
            f"- {c['name']}: {c['description']}" for c in catalog
        ) if catalog else "none"

        models_text = model_table or "none"

        prompt = (
            "You are the Central Secretary of an Agent Management Platform.\n"
            "Evaluate the user's message and respond with a single JSON object.\n\n"
            "First, decide what to do:\n"
            "- chat: greetings, small talk, general questions, self-introduction requests\n"
            "- info: questions about system/agents/status\n"
            "- ask: user wants work done but needs are unclear\n"
            "- plan: user wants specific work produced (content, images, videos, analysis, etc.)\n\n"

            "Examples:\n"
            '  "Hello" → {"action": "chat", "message": "Hi! How can I help?"}\n'
            '  "แนะนำตัวหน่อย" → {"action": "chat", "message": "สวัสดีครับ ผมคือ..."}\n'
            '  "What can you do?" → {"action": "info", "message": "I can create content plans..."}\n'
            '  "สร้าง content plan สำหรับร้านกาแฟ" → {"action": "plan", ...}\n\n'

            "IMPORTANT: Do NOT create a plan for greetings, self-introductions, or simple questions.\n"
            "Only create a plan when the user explicitly asks for work to be done.\n\n"

            "For chat/info/ask, respond with:\n"
            '  {"action": "chat", "message": "your reply"}\n'
            '  {"action": "info", "message": "your reply"}\n'
            '  {"action": "ask", "questions": ["q1", "q2", ...]}\n\n'

            "For plan, respond with a complete plan including agents AND model assignments:\n"
            "{\n"
            '  "action": "plan",\n'
            '  "summary": "brief summary",\n'
            '  "agents": [\n'
            "    {\n"
            '      "name": "Agent Name",\n'
            '      "role": "Agent Role",\n'
            '      "goal": "Agent Goal",\n'
            '      "backstory": "Agent Backstory",\n'
            '      "tools": ["capability_name"],\n'
            '      "task_description": "What this agent should do",\n'
            '      "depends_on": [],\n'
            '      "model": "model_id from the list"\n'
            "    }\n"
            "  ],\n"
            '  "manager_model": "model_id from the list or openrouter/auto",\n'
            '  "image_model": "model_id from specialized catalog (REQUIRED if plan uses generate_image)",\n'
            '  "video_model": "model_id from specialized catalog (REQUIRED if plan uses generate_video)",\n'
            '  "search_model": "model_id from specialized catalog (REQUIRED if plan uses search_web)",\n'
            '  "tts_model": "model_id from specialized catalog (REQUIRED if plan uses text_to_speech)",\n'
            '  "stt_model": "model_id from specialized catalog (REQUIRED if plan uses transcribe_audio)",\n'
            '  "vision_model": "model_id from specialized catalog (REQUIRED if plan uses analyze_image)"\n'
            "}\n\n"

            "Design Rules for plan:\n"
            "- Create as many agents as needed (1, 2, 3, or more)\n"
            "- Each agent should have a clear, distinct responsibility\n"
            "- Assign capabilities based on the descriptions below\n"
            "- Capabilities of type 'tool' (search_web, generate_image, generate_video, text_to_speech, transcribe_audio, analyze_image) give external abilities\n"
            "- Capabilities of type 'model_trait' (reasoning, creative_writing, write_code, long_context) guide model selection\n"
            "- Assign the SMARTER/larger model to the manager (it coordinates)\n"
            "- Assign models suited to each worker's task based on capabilities\n"
            "- Only use model IDs from the available models list\n"
            "- You can use 'openrouter/auto' as a model ID — OpenRouter will automatically select the best model for each request\n"
            "- You can use 'openrouter/free' for free-tier auto-routing\n"
            "- For image_model/video_model/search_model/tts_model/stt_model/vision_model: you MUST pick a specific model from the specialized catalog if the plan uses those tools — do NOT leave empty\n"
            "- If the plan does NOT need a particular specialized model, leave that field empty\n"
            "- Write all content in the SAME language as the user's request\n\n"

            "CRITICAL — task_description & depends_on rules:\n"
            "- By default, agents with NO depends_on run IN PARALLEL.\n"
            "- If agent B needs the output of agent A to do its job, set depends_on: [\"Agent A name\"]. Agent B will receive Agent A's output automatically before starting.\n"
            "- Agents WITHOUT depends_on CANNOT see other agents' output — their task_description MUST be self-contained.\n"
            "- Agents WITH depends_on CAN reference the upstream agent's output — e.g. 'Based on the caption from Creative Copywriter, generate an image that matches'.\n"
            "- Decide how many agents to create based on the user's request. You may create one agent per item or one agent that handles multiple items — use your judgment.\n"
            "- Each task_description MUST be specific — tell the agent EXACTLY what to produce, including how many items and what subject/theme.\n"
            "- BAD: 'Generate images based on descriptions provided by the manager' (vague, no depends_on)\n"
            "- GOOD (no depends_on): 'Write 1 engaging caption for a coffee shop post about latte art. Include hashtags and CTA.'\n"
            "- GOOD (with depends_on): 'Based on the caption from Creative Copywriter, create 1 image that visually matches the described scene. Call generate_image with a detailed English prompt.' + depends_on: [\"Creative Copywriter\"]\n"
            "- Include: what to create, how many, subject/theme, and which tool to call.\n\n"

            f"Available capabilities:\n{caps_text}\n\n"
            f"Available text models:\n{models_text}\n\n"
            f"Specialized AI models:\n{media_catalog or 'none'}\n\n"
            f"{history_text}"
            f"User message: {user_input}\n\n"
            "Output ONLY the JSON object, no explanation:"
        )
        print(f"[DEBUG-PROMPT] media_catalog: {media_catalog or 'none'}", flush=True)

        if stream_callback:
            # Streaming mode: collect chunks while sending them to frontend
            import queue, threading
            chunk_queue: queue.Queue = queue.Queue()
            full_response = []

            def _stream_in_thread():
                try:
                    for chunk in self.llm_manager.call_streaming(prompt):
                        full_response.append(chunk)
                        chunk_queue.put(chunk)
                except Exception as e:
                    chunk_queue.put(e)
                chunk_queue.put(None)  # sentinel

            thread = threading.Thread(target=_stream_in_thread, daemon=True)
            thread.start()

            loop = asyncio.get_event_loop()
            import time as _time
            deadline = _time.time() + 30  # 30s total timeout for streaming
            while True:
                if _time.time() > deadline:
                    print("[assess_and_plan] Streaming timeout (30s) — no response from model", flush=True)
                    break
                try:
                    item = await loop.run_in_executor(None, chunk_queue.get, 0.1)
                except Exception:
                    continue
                if item is None:
                    break
                if isinstance(item, Exception):
                    print(f"[assess_and_plan] Streaming error: {_sanitize_error(item)}")
                    break
                if item:
                    await stream_callback(item)

            thread.join(timeout=1)
            response = "".join(full_response).strip()
        else:
            response = (await self.llm_manager.call_async(prompt)).strip()

        print(f"[DEBUG-STREAM] Response length: {len(response)}, full response: {response[:3000]}", flush=True)
        if not response:
            selected = self.llm_manager._selected_model or self.llm_manager._default_model or "auto"
            return {
                "action": "chat",
                "message": f"❌ โมเดล '{selected}' ส่งคำตอบกลับมาว่างเปล่า อาจไม่รองรับคำสั่งที่ซับซ้อน ลองเปลี่ยนโมเดลแล้วส่งใหม่อีกครั้ง"
            }
        if os.getenv("DEBUG_MODE", "false").lower() == "true":
            print(f"[DEBUG-PLAN-RAW] LLM response (first 800 chars): {response[:800]}", flush=True)
        return self._parse_unified_response(response, valid_model_ids)

    def _parse_unified_response(
        self, text: str, valid_model_ids: set[str] | None = None
    ) -> dict:
        """Parse unified assess_and_plan response."""
        try:
            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                if "action" not in result:
                    selected = self.llm_manager._selected_model or self.llm_manager._default_model or "auto"
                    return {
                        "action": "chat",
                        "message": (
                            f"⚠️ โมเดล '{selected}' ส่งคำตอบกลับมาไม่ถูกต้อง (ไม่มี JSON action) "
                            f"ลองเปลี่ยนโมเดลแล้วส่งใหม่อีกครั้ง"
                        )
                    }

                if result["action"] == "plan":
                    agents = []
                    for item in result.get("agents", []):
                        if isinstance(item, dict) and "name" in item and "role" in item:
                            depends_on = item.get("depends_on", [])
                            if not isinstance(depends_on, list):
                                depends_on = []
                            agents.append({
                                "name": item.get("name", "").strip(),
                                "role": item.get("role", "").strip(),
                                "goal": item.get("goal", "").strip(),
                                "backstory": item.get("backstory", "").strip(),
                                "tools": item.get("tools", []) if isinstance(item.get("tools"), list) else [],
                                "task_description": item.get("task_description", "").strip(),
                                "depends_on": [d.strip() for d in depends_on if isinstance(d, str) and d.strip()],
                                "model": item.get("model", ""),
                            })
                    if not agents:
                        return {"action": "chat", "message": "ไม่สามารถวางแผนได้ กรุณาลองใหม่"}

                    manager_model = result.get("manager_model", "")
                    model_assignment = {"manager": manager_model, "workers": {}}
                    for a in agents:
                        model_assignment["workers"][a["name"]] = a.get("model", "")

                    if valid_model_ids:
                        if model_assignment["manager"] not in valid_model_ids:
                            model_assignment["manager"] = ""
                        for name, mid in model_assignment["workers"].items():
                            if mid not in valid_model_ids:
                                model_assignment["workers"][name] = ""

                    return {
                        "action": "plan",
                        "summary": result.get("summary", ""),
                        "agents": agents,
                        "model_assignment": model_assignment,
                        "image_model": result.get("image_model", ""),
                        "video_model": result.get("video_model", ""),
                        "search_model": result.get("search_model", ""),
                    }

                return result
        except (json.JSONDecodeError, AttributeError) as e:
            print(f"[DEBUG-PARSE-UNIFIED] Failed: {e}", flush=True)
            print(f"[DEBUG-PARSE-UNIFIED] Response (first 500 chars): {text[:500]}", flush=True)
        selected = self.llm_manager._selected_model or self.llm_manager._default_model or "auto"
        return {
            "action": "chat",
            "message": (
                f"⚠️ โมเดล '{selected}' ไม่สามารถสร้างแผนงานได้ (คำตอบไม่ใช่ JSON) "
                f"ลองเปลี่ยนโมเดลแล้วส่งใหม่อีกครั้ง"
            )
        }

    async def chat_response(self, user_input: str) -> str:
        """ตอบกลับทักทาย/คำถามทั่วไป"""
        llm = self.llm_manager.get_llm()
        prompt = (
            "You are the assistant of an Agent Management Platform.\n"
            "Respond to the user's message. Be concise and friendly.\n\n"
            "Respond in the same language as the user's message.\n\n"
            "Do not mention agents or the system unless asked.\n\n"
            f"User message: {user_input}\n\n"
            "Answer:"
        )
        return (await self.llm_manager.call_async(prompt)).strip()

    async def chat_response_with_image(self, user_input: str, image_data_url: str) -> str:
        """ตอบกลับพร้อมวิเคราะห์รูปภาพ (vision/multimodal)"""
        prompt = (
            "You are the assistant of an Agent Management Platform.\n"
            "The user has attached an image. Analyze and describe what you see in the image.\n"
            "Respond in the same language as the user's message.\n"
            "Be concise and friendly.\n\n"
            f"User message: {user_input}\n\n"
            "Answer:"
        )
        return (await self.llm_manager.call_with_image_async(prompt, image_data_url)).strip()

    async def chat_response_multimodal(
        self, user_input: str, content_blocks: list[dict], plugins: list = None
    ) -> str:
        """ตอบกลับพร้อมวิเคราะห์ไฟล์ multimodal (image, PDF, audio, video)"""
        prompt = (
            "You are the assistant of an Agent Management Platform.\n"
            "The user has attached a file. Analyze and respond based on the attached content.\n"
            "Respond in the same language as the user's message.\n"
            "Be concise and friendly.\n\n"
            f"User message: {user_input}\n\n"
            "Answer:"
        )
        return (await self.llm_manager.call_with_multimodal_async(prompt, content_blocks, plugins)).strip()

    async def assess_and_plan_multimodal(
        self,
        user_input: str,
        content_blocks: list[dict],
        plugins: list = None,
        conversation_history: list[dict] | None = None,
        model_table: str | None = None,
        valid_model_ids: set[str] | None = None,
        media_catalog: str | None = None,
        stream_callback=None,
    ) -> dict:
        """assess_and_plan with multimodal content blocks (image, PDF, audio, video)."""
        history_text = ""
        if conversation_history:
            history_text = "\nConversation so far:\n"
            for msg in conversation_history:
                history_text += f"- {msg.get('role', 'user')}: {msg.get('content', '')[:100]}\n"

        cap_registry = CapabilityRegistry()
        catalog = cap_registry.list_catalog()
        caps_text = "\n".join(
            f"- {c['name']}: {c['description']}" for c in catalog
        ) if catalog else "none"

        models_text = model_table or "none"

        prompt = (
            "You are the Central Secretary of an Agent Management Platform.\n"
            "Evaluate the user's message and respond with a single JSON object.\n\n"
            "First, decide what to do:\n"
            "- chat: greetings, small talk, general questions, self-introduction requests\n"
            "- info: questions about system/agents/status\n"
            "- ask: user wants work done but needs are unclear\n"
            "- plan: user wants specific work produced (content, images, videos, analysis, etc.)\n\n"
            "The user has attached a file. Analyze the attached content and use it in your assessment.\n\n"
            "For chat/info/ask, respond with:\n"
            '  {"action": "chat", "message": "your reply"}\n'
            '  {"action": "info", "message": "your reply"}\n'
            '  {"action": "ask", "questions": ["q1", "q2", ...]}\n\n'
            "For plan, respond with a complete plan including agents AND model assignments:\n"
            "{\n"
            '  "action": "plan",\n'
            '  "summary": "brief summary",\n'
            '  "agents": [\n'
            "    {\n"
            '      "name": "Agent Name",\n'
            '      "role": "Agent Role",\n'
            '      "goal": "Agent Goal",\n'
            '      "backstory": "Agent Backstory",\n'
            '      "tools": ["capability_name"],\n'
            '      "task_description": "What this agent should do",\n'
            '      "depends_on": [],\n'
            '      "model": "model_id from the list"\n'
            "    }\n"
            "  ],\n"
            '  "manager_model": "model_id from the list or openrouter/auto",\n'
            '  "image_model": "model_id from specialized catalog (REQUIRED if plan uses generate_image)",\n'
            '  "video_model": "model_id from specialized catalog (REQUIRED if plan uses generate_video)",\n'
            '  "search_model": "model_id from specialized catalog (REQUIRED if plan uses search_web)",\n'
            '  "tts_model": "model_id from specialized catalog (REQUIRED if plan uses text_to_speech)",\n'
            '  "stt_model": "model_id from specialized catalog (REQUIRED if plan uses transcribe_audio)",\n'
            '  "vision_model": "model_id from specialized catalog (REQUIRED if plan uses analyze_image)"\n'
            "}\n\n"
            "Design Rules for plan:\n"
            "- Create as many agents as needed (1, 2, 3, or more)\n"
            "- Each agent should have a clear, distinct responsibility\n"
            "- Assign capabilities based on the descriptions below\n"
            "- Only use model IDs from the available models list\n"
            "- You can use 'openrouter/auto' as a model ID\n"
            "- Write all content in the SAME language as the user's request\n\n"
            "CRITICAL — task_description & depends_on rules:\n"
            "- By default, agents with NO depends_on run IN PARALLEL.\n"
            "- If agent B needs the output of agent A, set depends_on: [\"Agent A name\"].\n"
            "- Agents WITHOUT depends_on CANNOT see other agents' output.\n"
            "- Each task_description MUST be specific.\n\n"
            f"Available capabilities:\n{caps_text}\n\n"
            f"Available text models:\n{models_text}\n\n"
            f"Specialized AI models:\n{media_catalog or 'none'}\n\n"
            f"{history_text}"
            f"User message: {user_input}\n\n"
            "Output ONLY the JSON object, no explanation:"
        )

        if stream_callback:
            import queue, threading
            chunk_queue: queue.Queue = queue.Queue()
            full_response = []

            def _stream_in_thread():
                try:
                    for chunk in self.llm_manager.call_with_multimodal_streaming(prompt, content_blocks, plugins):
                        full_response.append(chunk)
                        chunk_queue.put(chunk)
                except Exception as e:
                    chunk_queue.put(e)
                chunk_queue.put(None)

            thread = threading.Thread(target=_stream_in_thread, daemon=True)
            thread.start()

            loop = asyncio.get_event_loop()
            import time as _time
            deadline = _time.time() + 30
            while True:
                if _time.time() > deadline:
                    break
                try:
                    item = await loop.run_in_executor(None, chunk_queue.get, 0.1)
                except Exception:
                    continue
                if item is None:
                    break
                if isinstance(item, Exception):
                    print(f"[assess_and_plan_multimodal] Streaming error: {_sanitize_error(item)}")
                    break
                if item:
                    await stream_callback(item)

            thread.join(timeout=1)
            response = "".join(full_response).strip()
        else:
            response = (await self.llm_manager.call_with_multimodal_async(prompt, content_blocks, plugins)).strip()

        if not response:
            selected = self.llm_manager._selected_model or self.llm_manager._default_model or "auto"
            return {
                "action": "chat",
                "message": f"❌ โมเดล '{selected}' ส่งคำตอบกลับมาว่างเปล่า อาจไม่รองรับ multimodal input"
            }
        return self._parse_unified_response(response, valid_model_ids)

    async def info_response(self, user_input: str, agents: list[dict], tasks: list[dict], state: str) -> str:
        """ตอบคำถามข้อมูลระบบ"""
        llm = self.llm_manager.get_llm()
        prompt = (
            "You are the central secretary of an Agent Management Platform.\n"
            "Answer the user's question based on the system data below.\n\n"
            "Respond in the same language as the user's question.\n\n"
            f"System state: {state}\n"
            f"Agents (JSON): {json.dumps(agents, ensure_ascii=False, indent=2)}\n\n"
            f"Tasks (JSON): {json.dumps(tasks, ensure_ascii=False, indent=2)}\n\n"
            f"User question: {user_input}\n\n"
            "Answer:"
        )
        return (await self.llm_manager.call_async(prompt)).strip()

    async def analyze(self, user_input: str, available_tools: list[str], conversation_history: list[dict] | None = None) -> list[dict]:
        """วิเคราะห์และออกแบบ multi-agent plan — ไม่จำกัดจำนวน agent หรือ capabilities"""
        llm = self.llm_manager.get_llm()

        # Build capability descriptions from registry
        cap_registry = CapabilityRegistry()
        catalog = cap_registry.list_catalog()
        caps_text = "\n".join(
            f"- {c['name']}: {c['description']}" for c in catalog
        ) if catalog else "none"

        history_text = ""
        if conversation_history:
            history_text = "\nConversation context:\n"
            for msg in conversation_history[-10:]:
                history_text += f"- {msg.get('role', 'user')}: {msg.get('content', '')[:150]}\n"

        prompt = (
            "You are the Central Secretary of an Agent Management Platform.\n"
            "Analyze the user's request and design a multi-agent plan to accomplish it.\n\n"
            f"User request: {user_input}\n"
            f"{history_text}"
            f"Available capabilities: {caps_text}\n\n"
            "Design Rules:\n"
            "- Create as many agents as needed (1, 2, 3, or more — your decision)\n"
            "- Each agent should have a clear, distinct responsibility\n"
            "- Assign capabilities to agents based on the descriptions above — "
            "match each capability to the agent whose task requires it\n"
            "- Capabilities of type 'tool' (search_web, generate_image) give the agent external abilities\n"
            "- Capabilities of type 'model_trait' (reasoning, creative_writing, write_code, long_context) "
            "guide model selection but are not tools\n"
            "- A manager agent will coordinate the team and delegate tasks\n"
            "- Independent tasks may run in parallel; dependent tasks will wait\n"
            "- Write all content in the SAME language as the user's request\n\n"
            "Output format (JSON array, no other text):\n"
            "[\n"
            "  {\n"
            '    "name": "Agent Name",\n'
            '    "role": "Agent Role",\n'
            '    "goal": "Agent Goal",\n'
            '    "backstory": "Agent Backstory/Persona",\n'
            '    "tools": ["capability_name"],\n'
            '    "task_description": "What this agent should do"\n'
            "  }\n"
            "]\n\n"
            "Output ONLY the JSON array, no explanation:"
        )
        response = await self.llm_manager.call_async(prompt)
        return self._parse_agent_specs(response, user_input)

    def check_resources(
        self, agent_spec: dict, registry: AgentRegistry
    ) -> dict:
        """
        เช็ค Registry ว่ามี Agent ที่ว่างและตรงสายงานหรือไม่
        Returns: {"type": "existing", "agent": {...}} หรือ {"type": "create", "spec": {...}}
        """
        existing = registry.find_idle_agent(
            agent_spec.get("role", ""), agent_spec.get("tools", [])
        )
        if existing:
            return {"type": "existing", "agent": existing}
        return {"type": "create", "spec": agent_spec}

    def _parse_agent_specs(self, text: str, user_input: str) -> list[dict]:
        """Parse agent specs from JSON array or text format"""
        agents = []

        # Try JSON array first
        try:
            json_match = re.search(r'\[.*\]', text, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group())
                if isinstance(parsed, list):
                    for item in parsed:
                        if isinstance(item, dict) and "name" in item and "role" in item:
                            depends_on = item.get("depends_on", [])
                            if not isinstance(depends_on, list):
                                depends_on = []
                            agents.append({
                                "name": item.get("name", "").strip(),
                                "role": item.get("role", "").strip(),
                                "goal": item.get("goal", "").strip(),
                                "backstory": item.get("backstory", "").strip(),
                                "tools": item.get("tools", []) if isinstance(item.get("tools"), list) else [],
                                "task_description": item.get("task_description", user_input).strip(),
                                "depends_on": [d.strip() for d in depends_on if isinstance(d, str) and d.strip()],
                            })
                    if agents:
                        return agents
        except (json.JSONDecodeError, AttributeError):
            pass

        # Fallback: text format parsing
        blocks = re.split(r"\n(?=\d+\.\s*Agent Name:)", text.strip())
        for block in blocks:
            if not block.strip():
                continue

            name_match = re.search(r"Agent Name:\s*(.+)", block)
            role_match = re.search(r"Role:\s*(.+)", block)
            goal_match = re.search(r"Goal:\s*(.+)", block)
            backstory_match = re.search(r"Backstory:\s*(.+)", block)
            tools_match = re.search(r"Tools:\s*(.+)", block)
            task_match = re.search(r"Task Description:\s*(.+)", block)

            if name_match and role_match:
                tools_str = tools_match.group(1).strip() if tools_match else ""
                tools = [t.strip() for t in tools_str.split(",") if t.strip()]
                agents.append(
                    {
                        "name": name_match.group(1).strip(),
                        "role": role_match.group(1).strip(),
                        "goal": goal_match.group(1).strip() if goal_match else "",
                        "backstory": backstory_match.group(1).strip()
                        if backstory_match
                        else "",
                        "tools": tools,
                        "task_description": task_match.group(1).strip()
                        if task_match
                        else user_input,
                    }
                )

        if not agents:
            agents.append(
                {
                    "name": "Agent หลัก",
                    "role": "ผู้ช่วยทั่วไป",
                    "goal": "ตอบคำถามและช่วยเหลือ User",
                    "backstory": "คุณเป็นผู้ช่วยที่มีประสบการณ์",
                    "tools": [],
                    "task_description": user_input,
                }
            )
        return agents


async def _async_progress_callback(sync_callback, progress_data):
    """Bridge: run progress callback in async context for run_coroutine_threadsafe."""
    result = sync_callback(progress_data)
    if asyncio.iscoroutine(result):
        await result


# ============================================================
# Execution Orchestrator
# ============================================================
class ExecutionOrchestrator:
    """รวม Agent Factory เพื่อรัน Crew แบบ Dynamic โดยไม่สร้าง Chat Log รก"""

    def __init__(
        self,
        llm_manager: LLMManager,
        tool_registry: ToolRegistry,
        progress_callback=None,
        agent_progress_callback=None,
    ):
        self.llm_manager = llm_manager
        self.tool_registry = tool_registry
        self.agent_factory = AgentFactory(llm_manager, tool_registry)
        self._progress_callback = progress_callback
        self._agent_progress_callback = agent_progress_callback
        self._media_gen_manager = MediaGenerationManager(llm_manager)
        self._event_handlers: list[tuple] = []
        self._agent_specs: list[dict] = []
        self._main_loop: asyncio.AbstractEventLoop | None = None
        self._state_lock = __import__("threading").Lock()
        self._ctx: contextvars.Context | None = None
        self.model_selector: ModelSelector | None = None
        if llm_manager.tier in ("paid", "free"):
            self.model_selector = ModelSelector(
                llm_manager.api_key, llm_manager.base_url, llm_manager.temperature,
                rotator=None,
                default_model=llm_manager._default_model,
            )

    _TOOL_DESCRIPTIONS = {
        "search_web": "🔍 Searching the web...",
        "generate_image": "🎨 Preparing image generation...",
    }

    @staticmethod
    def _clean_agent_output(output: str) -> str:
        """Strip CrewAI internal markers and box-drawing noise from agent output."""
        if not output:
            return output
        # Remove box-drawing characters used by CrewAI verbose logs
        cleaned = re.sub(r'[\u2500-\u257F]', '', output)
        # Remove common internal markers/sections
        markers = [
            "Crew Execution Started",
            "Crew Execution Completed",
            "Task Started",
            "Task Completed",
            "Agent Final Answer",
            "Final Answer:",
            "Final Deliverable:",
            "Tracing is disabled.",
            "To enable tracing",
            "crewai traces enable",
        ]
        for marker in markers:
            cleaned = cleaned.replace(marker, "")
        # Trim leading/trailing whitespace and collapse multiple blank lines
        cleaned = re.sub(r'\n{3,}', '\n\n', cleaned.strip())
        return cleaned

    def _tool_description(self, tool_name: str, tool_args: dict | str) -> str:
        desc = self._TOOL_DESCRIPTIONS.get(tool_name, f"⚙️ Using {tool_name}...")
        if tool_name == "search_web" and isinstance(tool_args, dict):
            query = tool_args.get("query", "")
            if query:
                return f"🔍 Searching: {query[:60]}"
        elif tool_name == "generate_image" and isinstance(tool_args, dict):
            prompt = tool_args.get("prompt", "")
            if prompt:
                return f"🎨 Image prompt: {prompt[:60]}"
        return desc

    def _match_agent_index(self, agent_role: str | None) -> int:
        if not agent_role:
            return -1
        for i, spec in enumerate(self._agent_specs):
            if spec.get("role", "").lower() in agent_role.lower() or agent_role.lower() in spec.get("role", "").lower():
                return i
            if spec.get("name", "").lower() in agent_role.lower() or agent_role.lower() in spec.get("name", "").lower():
                return i
        return -1

    def _build_progress(self, updates: dict[int, dict], state: dict | None = None) -> list[dict]:
        result = []
        for i, spec in enumerate(self._agent_specs):
            entry = {
                "name": spec.get("name", "Agent"),
                "role": spec.get("role", ""),
                "status": "pending",
                "progress": 0,
                "model": spec.get("model", ""),
            }
            if i in updates:
                entry.update(updates[i])
            elif state and i in state.get("outputs", {}):
                entry["output"] = state["outputs"][i]
                if i in state.get("completed", set()):
                    entry["status"] = "complete"
                    entry["progress"] = 100
                elif i == state.get("running_idx", -1):
                    entry["status"] = "running"
            result.append(entry)
        return result

    def _register_event_listeners(self):
        state = {"completed": set(), "running_idx": -1, "outputs": {}}

        def _send_progress(updates: dict[int, dict]):
            """Send progress update — thread-safe with Chainlit context."""
            if not self._agent_progress_callback or not self._main_loop or not self._ctx:
                return
            progress = self._build_progress(updates, state)
            ctx = self._ctx
            loop = self._main_loop
            callback = self._agent_progress_callback

            def _schedule():
                """Run in main thread with correct context vars."""
                loop.create_task(
                    _async_progress_callback(callback, progress),
                    context=ctx,
                )

            loop.call_soon_threadsafe(_schedule)

        def on_agent_started(source, event: AgentExecutionStartedEvent):
            idx = self._match_agent_index(event.agent_role)
            if idx >= 0:
                with self._state_lock:
                    state["running_idx"] = idx
                    task_desc = ""
                    if idx < len(self._agent_specs):
                        task_desc = self._agent_specs[idx].get("task_description", "")
                    updates = {idx: {"status": "running", "progress": 30, "current_task": task_desc, "current_tool": "", "tool_description": ""}}
                    for j in state["completed"]:
                        upd = {"status": "complete", "progress": 100}
                        if j in state["outputs"]:
                            upd["output"] = state["outputs"][j]
                        updates[j] = upd
                _send_progress(updates)

        def on_tool_started(source, event: ToolUsageStartedEvent):
            idx = self._match_agent_index(event.agent_role)
            if idx >= 0:
                tool_desc = self._tool_description(event.tool_name, event.tool_args)
                with self._state_lock:
                    updates = {idx: {"status": "running", "progress": 50, "current_tool": event.tool_name, "tool_description": tool_desc}}
                    for j in state["completed"]:
                        upd = {"status": "complete", "progress": 100}
                        if j in state["outputs"]:
                            upd["output"] = state["outputs"][j]
                        updates[j] = upd
                _send_progress(updates)

        def on_tool_finished(source, event: ToolUsageFinishedEvent):
            idx = self._match_agent_index(event.agent_role)
            if idx >= 0:
                output_preview = str(event.output)[:1500] if event.output else ""
                with self._state_lock:
                    state["outputs"][idx] = output_preview
                    updates = {idx: {"status": "running", "progress": 70, "current_tool": "", "tool_description": "", "output": output_preview}}
                    for j in state["completed"]:
                        upd = {"status": "complete", "progress": 100}
                        if j in state["outputs"]:
                            upd["output"] = state["outputs"][j]
                        updates[j] = upd
                _send_progress(updates)

        def on_task_completed(source, event: TaskCompletedEvent):
            idx = self._match_agent_index(event.agent_role)
            if idx >= 0:
                with self._state_lock:
                    state["completed"].add(idx)
                    output_raw = ""
                    if hasattr(event, "output") and event.output:
                        output_raw = getattr(event.output, "raw", str(event.output))[:2000]
                    state["outputs"][idx] = output_raw
                    updates = {idx: {"status": "complete", "progress": 100, "current_task": "", "current_tool": "", "tool_description": "", "output": output_raw}}
                _send_progress(updates)

        def on_agent_completed(source, event: AgentExecutionCompletedEvent):
            idx = self._match_agent_index(event.agent_role)
            if idx >= 0 and idx not in state["completed"]:
                with self._state_lock:
                    state["completed"].add(idx)
                    upd = {"status": "complete", "progress": 100, "current_task": "", "current_tool": "", "tool_description": ""}
                    if idx in state["outputs"]:
                        upd["output"] = state["outputs"][idx]
                    updates = {idx: upd}
                _send_progress(updates)

        handlers = [
            (AgentExecutionStartedEvent, on_agent_started),
            (ToolUsageStartedEvent, on_tool_started),
            (ToolUsageFinishedEvent, on_tool_finished),
            (TaskCompletedEvent, on_task_completed),
            (AgentExecutionCompletedEvent, on_agent_completed),
        ]
        for event_type, handler in handlers:
            crewai_event_bus.on(event_type)(handler)
            self._event_handlers.append((event_type, handler))

    def _unregister_event_listeners(self):
        for event_type, handler in self._event_handlers:
            try:
                crewai_event_bus.off(event_type, handler)
            except Exception:
                pass
        self._event_handlers.clear()

    async def run_async(
        self,
        user_input: str,
        agent_specs: list[dict],
        pre_assigned_models: dict | None = None,
    ) -> dict:
        global _progress_callback, _media_gen_manager, _media_tool_results, _search_model
        _progress_callback = self._progress_callback
        _media_gen_manager = self._media_gen_manager
        _media_tool_results = []  # Reset for this run
        total = len(agent_specs)
        self._agent_specs = agent_specs

        # Set AI-selected media/search models for this run
        ai_image_model = cl.user_session.get("ai_image_model") or ""
        ai_video_model = cl.user_session.get("ai_video_model") or ""
        ai_search_model = cl.user_session.get("ai_search_model") or ""
        ai_tts_model = cl.user_session.get("ai_tts_model") or ""
        ai_stt_model = cl.user_session.get("ai_stt_model") or ""
        ai_vision_model = cl.user_session.get("ai_vision_model") or ""
        self._media_gen_manager.set_models(
            image_model=ai_image_model, video_model=ai_video_model,
            tts_model=ai_tts_model, stt_model=ai_stt_model, vision_model=ai_vision_model,
        )
        _search_model = ai_search_model

        # Use pre-assigned models from unified call, or fall back to LLM assignment
        if pre_assigned_models and pre_assigned_models.get("workers"):
            model_assignment = pre_assigned_models
            print(f"[ExecutionOrchestrator] Using pre-assigned models: {model_assignment}", flush=True)
        else:
            model_assignment = {"manager": "", "workers": {}}
            if self.model_selector:
                try:
                    loop = asyncio.get_event_loop()
                    model_assignment = await loop.run_in_executor(
                        None,
                        lambda: self.model_selector.assign_models(
                            agent_specs, manager_goal=user_input
                        )
                    )
                except Exception as e:
                    print(f"[ExecutionOrchestrator] ModelSelector error: {e}")

        self._main_loop = asyncio.get_event_loop()
        self._ctx = contextvars.copy_context()
        self._register_event_listeners()

        # Resolve actual model names: if model is "" (adaptive), find what get_llm() would pick
        # Also validate: routing models (openrouter/auto, openrouter/free) don't support tool use
        routing_models = {"openrouter/auto", "openrouter/free"}
        for i, spec in enumerate(agent_specs):
            agent_name = spec.get("name", "")
            worker_model = model_assignment["workers"].get(agent_name, "")
            agent_tools = spec.get("tools", [])
            if not worker_model:
                # Auto-routing — find what the routing/user-selected model actually is
                resolved = self.llm_manager.get_selected_model_name()
                model_assignment["workers"][agent_name] = resolved
                spec["model"] = resolved
                worker_model = resolved
            # Routing models don't support tool use — notify user, don't auto-swap
            if worker_model in routing_models and agent_tools:
                print(f"[ExecutionOrchestrator] {agent_name} has tools {agent_tools} but '{worker_model}' doesn't support tool use.", flush=True)
            spec["model"] = worker_model
        # Also resolve manager model
        if not model_assignment.get("manager"):
            model_assignment["manager"] = self.llm_manager.get_selected_model_name()

        print(f"[ExecutionOrchestrator] Resolved models: {model_assignment}", flush=True)

        try:
            agents = []
            tasks = []
            for i, spec in enumerate(agent_specs):
                worker_model = model_assignment["workers"].get(spec.get("name", ""), "")
                agent = self.agent_factory.create_agent(spec, model_id=worker_model)
                task = self.agent_factory.create_task(agent, spec, user_input)
                agents.append(agent)
                tasks.append(task)
                tool_names = [getattr(t, "name", str(t)) for t in agent.tools]
                _debug(f"[DEBUG] Agent: {agent.role}, tools: {tool_names}")

                if self._progress_callback:
                    pct = int((i / total) * 100)
                    self._progress_callback(pct, f"Agent {i+1}/{total}: {spec.get('name', '')} starting...")

            # Send initial progress: all pending with task descriptions
            if self._agent_progress_callback:
                initial = self._build_progress({})
                for i, s in enumerate(agent_specs):
                    initial[i]["current_task"] = s.get("task_description", "")
                callback = self._agent_progress_callback
                ctx = self._ctx
                main_loop = self._main_loop
                if main_loop and ctx:
                    main_loop.create_task(callback(initial), context=ctx)
                else:
                    asyncio.ensure_future(callback(initial))

            manager = self.agent_factory.create_manager_agent(
                user_input, agent_specs, model_id=model_assignment["manager"]
            )

            # Run all worker agents in parallel — each in its own thread
            loop = asyncio.get_event_loop()

            def run_single_agent_sync(agent, task, spec, idx):
                """Run one agent on its task as a standalone Crew (sync, for thread pool).
                Falls back to local LLM on rate limit errors."""
                _thread_local.agent_name = spec.get("name", f"Agent {idx+1}")
                single_crew = Crew(
                    agents=[agent],
                    tasks=[task],
                    process=Process.sequential,
                    verbose=True,
                )
                try:
                    single_result = single_crew.kickoff()
                except Exception as e:
                    err_msg = _sanitize_error(e)
                    _debug(f"[DEBUG-PARALLEL] Agent {spec.get('name', '')} error: {err_msg}", flush=True)
                    if ("429" in err_msg or "rate limit" in err_msg.lower()) and self.llm_manager.local_fallback_enabled:
                        # Trigger cooldown and retry with local fallback LLM (dev-only)
                        self.llm_manager.report_rate_limit()
                        fallback_llm = self.llm_manager._build_llm(
                            self.llm_manager.fallback_provider,
                            self.llm_manager.fallback_model,
                            self.llm_manager.fallback_base_url,
                            self.llm_manager.fallback_api_key,
                        )
                        agent.llm = fallback_llm
                        _debug(f"[DEBUG-PARALLEL] Retrying {spec.get('name', '')} with local LLM (dev fallback)", flush=True)
                        single_crew = Crew(
                            agents=[agent],
                            tasks=[task],
                            process=Process.sequential,
                            verbose=True,
                        )
                        single_result = single_crew.kickoff()
                    else:
                        raise
                raw = getattr(single_result, "raw", str(single_result))
                name = spec.get("name", f"Agent {idx+1}")
                role = spec.get("role", "")
                _debug(f"[DEBUG-PARALLEL] Agent {name} completed, output_len={len(str(raw))}", flush=True)
                return {"name": name, "role": role, "output": str(raw)}

            # === Wave-based dependency-aware execution ===
            # Build dependency graph: compute waves (topological order)
            agent_name_to_idx = {agent_specs[i].get("name", f"Agent {i+1}"): i for i in range(len(agents))}
            print(f"[DEBUG-WAVES] agent_specs deps: {[(s.get('name'), s.get('depends_on', [])) for s in agent_specs]}", flush=True)
            completed_outputs: dict[str, str] = {}  # name -> output
            agent_outputs = [None] * len(agents)

            # Compute waves: agents with no unresolved depends_on go in current wave
            remaining = set(range(len(agents)))
            waves: list[list[int]] = []
            max_iterations = len(agents) + 1  # prevent infinite loop on circular deps
            iteration = 0
            while remaining and iteration < max_iterations:
                iteration += 1
                wave = []
                for i in list(remaining):
                    deps = agent_specs[i].get("depends_on", [])
                    # Check if all dependencies are satisfied (completed or not in this run)
                    all_satisfied = all(
                        dep_name in completed_outputs or dep_name not in agent_name_to_idx
                        for dep_name in deps
                    )
                    if all_satisfied:
                        wave.append(i)
                if not wave:
                    # Circular dependency or unresolvable — force remaining into one wave
                    wave = list(remaining)
                    print(f"[WARN] Circular/unresolvable dependencies detected, forcing remaining agents into one wave", flush=True)
                waves.append(wave)
                # Remove waved agents from remaining and mark as completed for next wave's dependency check
                for i in wave:
                    remaining.discard(i)
                    name = agent_specs[i].get("name", f"Agent {i+1}")
                    completed_outputs[name] = "__pending__"  # placeholder so dependents can proceed

            print(f"[DEBUG-WAVES] Execution plan: {len(waves)} wave(s): {[[agent_specs[i].get('name', '') for i in w] for w in waves]}", flush=True)

            # Execute wave by wave
            for wave_idx, wave in enumerate(waves):
                print(f"[DEBUG-WAVES] Starting wave {wave_idx+1}/{len(waves)}: {[agent_specs[i].get('name', '') for i in wave]}", flush=True)

                # Send progress: mark agents in this wave as running, previous waves as complete
                if self._agent_progress_callback and self._main_loop and self._ctx:
                    progress = self._build_progress({})
                    for i, spec in enumerate(agent_specs):
                        if i in wave:
                            progress[i]["status"] = "running"
                            progress[i]["progress"] = 10
                        elif any(i in w for w in waves[:wave_idx]):
                            progress[i]["status"] = "complete"
                            progress[i]["progress"] = 100
                        else:
                            progress[i]["status"] = "pending"
                    _ctx = self._ctx
                    _loop = self._main_loop
                    _cb = self._agent_progress_callback
                    _loop.call_soon_threadsafe(lambda p=progress: _loop.create_task(_async_progress_callback(_cb, p), context=_ctx))

                # Inject upstream context into tasks for agents with depends_on
                for i in wave:
                    deps = agent_specs[i].get("depends_on", [])
                    if deps:
                        context_parts = []
                        for dep_name in deps:
                            dep_output = completed_outputs.get(dep_name, "")
                            if dep_output:
                                context_parts.append(f"--- Output from {dep_name} ---\n{dep_output}")
                        if context_parts:
                            # Rebuild task with upstream context
                            upstream_context = "\n\n".join(context_parts)
                            tasks[i] = self.agent_factory.create_task(
                                agents[i], agent_specs[i], user_input + f"\n\n[UPSTREAM CONTEXT]\n{upstream_context}"
                            )
                            _debug(f"[DEBUG-WAVES] Agent {agent_specs[i].get('name', '')} received context from: {deps}", flush=True)
                        else:
                            print(f"[WARN-WAVES] Agent {agent_specs[i].get('name', '')} depends on {deps} but no upstream context available", flush=True)

                # Run wave agents in parallel
                wave_results = await asyncio.gather(
                    *[
                        loop.run_in_executor(
                            None, run_single_agent_sync,
                            agents[i], tasks[i], agent_specs[i], i
                        )
                        for i in wave
                    ],
                    return_exceptions=True,
                )

                # Collect wave results and mark agents as completed
                for j, i in enumerate(wave):
                    res = wave_results[j]
                    name = agent_specs[i].get("name", f"Agent {i+1}")
                    remaining.discard(i)
                    if isinstance(res, Exception):
                        role = agent_specs[i].get("role", "")
                        _debug(f"[DEBUG-WAVES] Agent {name} failed: {_sanitize_error(res)}", flush=True)
                        agent_outputs[i] = {"name": name, "role": role, "output": f"Error: {res}"}
                        completed_outputs[name] = f"Error: {res}"
                    else:
                        agent_outputs[i] = res
                        completed_outputs[name] = res.get("output", "")

                # Send progress: mark agents in this wave as complete
                if self._agent_progress_callback and self._main_loop and self._ctx:
                    progress = self._build_progress({})
                    for i, spec in enumerate(agent_specs):
                        if i in wave:
                            progress[i]["status"] = "complete"
                            progress[i]["progress"] = 100
                            if agent_outputs[i]:
                                progress[i]["output"] = (agent_outputs[i].get("output", "") or "")[:2000]
                        elif any(i in w for w in waves[:wave_idx]):
                            progress[i]["status"] = "complete"
                            progress[i]["progress"] = 100
                        else:
                            progress[i]["status"] = "pending"
                    _ctx2 = self._ctx
                    _loop2 = self._main_loop
                    _cb2 = self._agent_progress_callback
                    _loop2.call_soon_threadsafe(lambda p=progress: _loop2.create_task(_async_progress_callback(_cb2, p), context=_ctx2))

            # Filter None (shouldn't happen but safe)
            agent_outputs = [o for o in agent_outputs if o is not None]

            # Manager synthesizes all outputs
            _debug(f"[DEBUG-PARALLEL] Manager synthesizing {len(agent_outputs)} outputs", flush=True)

            # Send progress: all agents complete, Manager synthesizing
            if self._agent_progress_callback and self._main_loop and self._ctx:
                progress = self._build_progress({})
                for i, spec in enumerate(agent_specs):
                    progress[i]["status"] = "complete"
                    progress[i]["progress"] = 100
                    if i < len(agent_outputs):
                        progress[i]["output"] = (agent_outputs[i].get("output", "") or "")[:2000]
                progress.append({
                    "name": "Manager",
                    "role": "Synthesizing all agent outputs",
                    "status": "running",
                    "progress": 50,
                    "current_task": "Synthesizing all agent outputs into final response",
                })
                ctx = self._ctx
                loop = self._main_loop
                callback = self._agent_progress_callback

                def _schedule_manager_progress():
                    loop.create_task(
                        _async_progress_callback(callback, progress),
                        context=ctx,
                    )
                loop.call_soon_threadsafe(_schedule_manager_progress)

            synthesis_prompt = (
                f"User request: {user_input}\n\n"
                f"You are the Project Manager. Your team has completed their tasks.\n"
                f"Below are the outputs from each team member:\n\n"
            )
            for ao in agent_outputs:
                # Strip internal CrewAI markers from outputs before sending to manager
                clean_output = self._clean_agent_output(ao['output'])
                synthesis_prompt += f"--- {ao['name']} ({ao['role']}) ---\n{clean_output}\n\n"
            synthesis_prompt += (
                "\nPlease synthesize all outputs into a clean, user-friendly final response. "
                "Write it as if you are directly answering the user. "
                "Use clear headings, bullet points, and natural language. "
                "Do NOT include internal team member names, raw output markers, or technical metadata. "
                "Do NOT include phrases like 'Final Answer:', 'Task Completed:', or 'Crew Completion:'. "
                "Return only the final deliverable the user asked for."
            )

            manager_raw = await loop.run_in_executor(
                None, self.llm_manager.call_with_fallback, synthesis_prompt
            )

            # Clean manager output and add it to agent_outputs so it appears in result card
            clean_manager_output = self._clean_agent_output(str(manager_raw))
            agent_outputs.append({
                "name": "Manager",
                "role": "Project Manager",
                "output": clean_manager_output,
            })

            return {
                "raw": clean_manager_output,
                "agent_outputs": agent_outputs,
            }
        finally:
            _progress_callback = None
            _media_gen_manager = None
            _search_model = ""
            self._unregister_event_listeners()


# ============================================================
# Dashboard Manager
# ============================================================
class StateMessenger:
    """ส่ง Platform State ให้ Custom Frontend ผ่าน JSON Messages"""

    def __init__(self, task_store: TaskStore | None = None, chat_store: ChatStore | None = None):
        self.task_store = task_store or TaskStore()
        self.chat_store = chat_store or ChatStore()
        self.current_session_id: str | None = None
        self.state = {
            "tasks": self.task_store.list_tasks(),
            "current_plan": None,
            "notifications": [],
            "system_status": "Ready",
            "available_tools": ToolRegistry().list_tool_catalog(),
            "credits": None,
        }

    @staticmethod
    def _fetch_credits() -> dict | None:
        """Fetch credit balance from OpenRouter /key endpoint."""
        try:
            llm_mgr = LLMManager()
            if llm_mgr.tier not in ("paid", "free"):
                return None
            resp = requests.get(
                f"{llm_mgr.base_url}/key",
                headers={"Authorization": f"Bearer {llm_mgr.api_key}"},
                timeout=5,
            )
            if resp.status_code == 200:
                data = resp.json().get("data", {})
                return {
                    "limit": data.get("limit"),
                    "limit_remaining": data.get("limit_remaining"),
                    "usage": data.get("usage", 0),
                    "usage_daily": data.get("usage_daily", 0),
                    "usage_monthly": data.get("usage_monthly", 0),
                    "is_free_tier": data.get("is_free_tier", True),
                }
        except Exception as e:
            print(f"[Credits] Failed to fetch: {_sanitize_error(e)}")
        return None

    @staticmethod
    def _get_resolved_model_name() -> str:
        """Get the actual model name that adaptive mode would pick."""
        try:
            return LLMManager().get_selected_model_name()
        except Exception:
            return "local"

    @staticmethod
    def _agents_for_ui(agents: list[dict]) -> list[dict]:
        return [
            {
                "id": a.get("id"),
                "name": a.get("name", "Unnamed"),
                "role": a.get("role", ""),
                "goal": a.get("goal", ""),
                "persona": a.get("persona", ""),
                "tools": a.get("tools", []),
                "model": a.get("model", ""),
                "status": a.get("status", "Idle"),
            }
            for a in agents
        ]

    async def _send(self):
        self.state["credits"] = self._fetch_credits()
        payload = {
            "type": "platform_state",
            "payload": self.state,
        }
        await cl.Message(content=json.dumps(payload, ensure_ascii=False)).send()

    async def init(self, registry: AgentRegistry):
        self.state["agents"] = self._agents_for_ui(registry.list_agents())
        self.state["tasks"] = self.task_store.list_tasks()
        await self._send()

    async def update_agents(self, registry: AgentRegistry):
        self.state["agents"] = self._agents_for_ui(registry.list_agents())
        await self._send()

    async def set_status(self, status: str):
        self.state["system_status"] = status
        await self._send()

    async def notify(self, message: str):
        notifications = self.state["notifications"]
        notifications.append(message)
        if len(notifications) > 5:
            notifications.pop(0)
        await self._send()

    async def reply(self, message: str):
        """Send a chat reply message to the frontend (separate from notifications)"""
        self.state["notifications"] = []
        await self._send()
        payload = chat_reply(ChatReplyText(message=message))
        await cl.Message(content=json.dumps(payload, ensure_ascii=False)).send()
        self.persist_message({"role": "assistant", "content": message, "messageType": "text"})

    async def reply_plan_validation_error(self, errors: list[str]):
        """Send a plan validation error — frontend resets plan card to pending"""
        self.state["notifications"] = []
        await self._send()
        message = "\n".join(errors)
        payload = chat_reply(ChatReplyPlanValidationError(message=message, errors=errors))
        await cl.Message(content=json.dumps(payload, ensure_ascii=False)).send()
        self.persist_message({"role": "assistant", "content": message, "messageType": "plan_validation_error", "validationErrors": errors})

    async def reply_thinking(self, chunk: str, thinking_id: str = "thinking"):
        """Send a streaming thinking chunk to the frontend."""
        payload = {
            "type": "chat_reply",
            "payload": {
                "messageType": "thinking",
                "chunk": chunk,
                "thinkingId": thinking_id,
            }
        }
        await cl.Message(content=json.dumps(payload, ensure_ascii=False)).send()

    async def reply_thinking_done(self, thinking_id: str = "thinking"):
        """Signal that thinking stream is complete."""
        payload = {
            "type": "chat_reply",
            "payload": {
                "messageType": "thinking_done",
                "thinkingId": thinking_id,
            }
        }
        await cl.Message(content=json.dumps(payload, ensure_ascii=False)).send()

    async def reply_plan(self, agents: list[dict], task_description: str, plan_type: str = "new", image_model: str = "", video_model: str = "", search_model: str = "", tts_model: str = "", stt_model: str = "", vision_model: str = "", has_image_tool: bool = False, has_video_tool: bool = False, has_search_tool: bool = False, has_tts_tool: bool = False, has_stt_tool: bool = False, has_vision_tool: bool = False):
        """Send a plan card as a chat message"""
        self.state["notifications"] = []
        await self._send()
        plan_agents = [
            PlanAgentItem(
                name=a.get("name", "Unnamed"),
                role=a.get("role", ""),
                goal=a.get("goal", ""),
                tools=a.get("tools", []),
                depends_on=a.get("depends_on", []),
                is_existing=a.get("is_existing", False),
                model=a.get("model", ""),
            )
            for a in agents
        ]
        payload = chat_reply(ChatReplyPlan(
            planAgents=plan_agents,
            planTaskDescription=task_description,
            planType=plan_type,
            imageModel=image_model,
            videoModel=video_model,
            searchModel=search_model,
            ttsModel=tts_model,
            sttModel=stt_model,
            visionModel=vision_model,
            hasImageTool=has_image_tool,
            hasVideoTool=has_video_tool,
            hasSearchTool=has_search_tool,
            hasTtsTool=has_tts_tool,
            hasSttTool=has_stt_tool,
            hasVisionTool=has_vision_tool,
        ))
        await cl.Message(content=json.dumps(payload, ensure_ascii=False)).send()
        self.persist_message({"role": "assistant", "messageType": "plan", "planAgents": payload["payload"]["planAgents"], "planTaskDescription": task_description, "planType": plan_type, "planStatus": "pending"})

    async def reply_progress(self, percent: int, label: str, progress_id: str = ""):
        """Send a progress card as a chat message"""
        payload = chat_reply(ChatReplyProgress(
            progressId=progress_id,
            progressPercent=percent,
            progressLabel=label,
        ))
        await cl.Message(content=json.dumps(payload, ensure_ascii=False)).send()
        # Progress: update or insert in session (don't duplicate)
        if self.current_session_id:
            session = self.chat_store.get_session(self.current_session_id)
            if session:
                msgs = session["messages"]
                existing = None
                for m in msgs:
                    if m.get("messageType") == "progress" and m.get("progressId") == progress_id:
                        existing = m
                        break
                prog_msg = {"role": "assistant", "messageType": "progress", "progressId": progress_id, "progressPercent": percent, "progressLabel": label}
                if existing:
                    existing.update(prog_msg)
                else:
                    msgs.append(prog_msg)
                session["updated_at"] = datetime.now().isoformat()
                self.chat_store._save()

    async def reply_agent_progress(self, task_id: str, agents_progress: list[dict]):
        """Send per-agent progress card — updates in-place by task_id"""
        overall = sum(a.get("progress", 0) for a in agents_progress) // max(len(agents_progress), 1)
        entries = [
            AgentProgressEntry(
                name=a.get("name", "Agent"),
                role=a.get("role", ""),
                status=a.get("status", "pending"),
                progress=a.get("progress", 0),
                output=a.get("output", ""),
                current_task=a.get("current_task", ""),
                current_tool=a.get("current_tool", ""),
                tool_description=a.get("tool_description", ""),
                model=a.get("model", ""),
            )
            for a in agents_progress
        ]
        payload = chat_reply(ChatReplyAgentProgress(
            taskId=task_id,
            overallProgress=overall,
            agents=entries,
        ))
        await cl.Message(content=json.dumps(payload, ensure_ascii=False)).send()
        # Update or insert in session
        if self.current_session_id:
            session = self.chat_store.get_session(self.current_session_id)
            if session:
                msgs = session["messages"]
                existing = None
                for m in msgs:
                    if m.get("messageType") == "agent_progress" and m.get("taskId") == task_id:
                        existing = m
                        break
                prog_msg = {"role": "assistant", "messageType": "agent_progress", "taskId": task_id, "overallProgress": overall, "agents": agents_progress}
                if existing:
                    existing.update(prog_msg)
                else:
                    msgs.append(prog_msg)
                session["updated_at"] = datetime.now().isoformat()
                self.chat_store._save()

    async def reply_result(self, summary: str, agents: list[dict] | None = None, is_error: bool = False):
        """Send a result card as a chat message, with per-agent collapsible outputs"""
        result_agents = [
            ResultAgentItem(
                name=a.get("name", ""),
                role=a.get("role", ""),
                output=a.get("output", ""),
            )
            for a in (agents or [])
        ]
        payload = chat_reply(ChatReplyResult(
            resultSummary=summary,
            resultError=is_error,
            resultAgents=result_agents,
        ))
        await cl.Message(content=json.dumps(payload, ensure_ascii=False)).send()
        self.persist_message({"role": "assistant", "messageType": "result", "resultSummary": summary, "resultError": is_error, "resultAgents": [a.model_dump() for a in result_agents]})

    async def reply_image_approval(self, prompt: str, approval_id: str, agent_name: str = "", media_type: str = "image", duration: int = 0, model: str = "", approval_status: str = "pending", image_error: str = ""):
        """Send a media approval card — user must approve before generation"""
        payload = chat_reply(ChatReplyImageApproval(
            imagePrompt=prompt,
            approvalId=approval_id,
            agentName=agent_name,
            mediaType=media_type,
            duration=duration,
            model=model,
            approvalStatus=approval_status,
            imageError=image_error,
        ))
        await cl.Message(content=json.dumps(payload, ensure_ascii=False)).send()
        self.persist_message({"role": "assistant", "messageType": "image_approval", "imagePrompt": prompt, "approvalId": approval_id, "agentName": agent_name, "mediaType": media_type, "duration": duration, "model": model, "approvalStatus": approval_status, "imageError": image_error})

    async def reply_image_result(self, image_url: str, prompt: str, approval_id: str, task_id: str | None = None, media_type: str = "image", agent_name: str = ""):
        """Send a generated media result (image or video)"""
        payload = chat_reply(ChatReplyImageResult(
            imageUrl=image_url,
            imagePrompt=prompt,
            approvalId=approval_id,
            taskId=task_id or "",
            mediaType=media_type,
            agentName=agent_name,
        ))
        await cl.Message(content=json.dumps(payload, ensure_ascii=False)).send()
        self.persist_message({"role": "assistant", "messageType": "image_result", "imageUrl": image_url, "imagePrompt": prompt, "approvalId": approval_id, "taskId": task_id, "mediaType": media_type})

    async def reply_audio_result(self, audio_url: str, prompt: str, voice: str = "", agent_name: str = "", model: str = "", task_id: str = ""):
        """Send a TTS audio result to the frontend."""
        payload = chat_reply(ChatReplyAudioResult(
            audioUrl=audio_url,
            audioPrompt=prompt,
            voice=voice,
            agentName=agent_name,
            model=model,
            taskId=task_id,
        ))
        await cl.Message(content=json.dumps(payload, ensure_ascii=False)).send()
        self.persist_message({"role": "assistant", "messageType": "audio_result", "audioUrl": audio_url, "audioPrompt": prompt, "voice": voice, "agentName": agent_name, "model": model})

    async def reply_transcription_result(self, transcription_text: str, audio_url: str = "", agent_name: str = "", model: str = "", task_id: str = ""):
        """Send a transcription (STT) result to the frontend."""
        payload = chat_reply(ChatReplyTranscriptionResult(
            transcriptionText=transcription_text,
            audioUrl=audio_url,
            agentName=agent_name,
            model=model,
            taskId=task_id,
        ))
        await cl.Message(content=json.dumps(payload, ensure_ascii=False)).send()
        self.persist_message({"role": "assistant", "messageType": "transcription_result", "transcriptionText": transcription_text, "audioUrl": audio_url, "agentName": agent_name, "model": model})

    async def reply_video_result(self, video_url: str, prompt: str, agent_name: str = "", model: str = "", task_id: str = ""):
        """Send a video generation result to the frontend."""
        payload = chat_reply(ChatReplyVideoResult(
            videoUrl=video_url,
            videoPrompt=prompt,
            agentName=agent_name,
            model=model,
            taskId=task_id,
        ))
        await cl.Message(content=json.dumps(payload, ensure_ascii=False)).send()
        self.persist_message({"role": "assistant", "messageType": "video_result", "videoUrl": video_url, "videoPrompt": prompt, "agentName": agent_name, "model": model})

    async def reply_file_result(self, file_url: str, file_name: str, file_mime: str = "", agent_name: str = "", task_id: str = ""):
        """Send a generic file result to the frontend."""
        payload = chat_reply(ChatReplyFileResult(
            fileUrl=file_url,
            fileName=file_name,
            fileMime=file_mime,
            agentName=agent_name,
            taskId=task_id,
        ))
        await cl.Message(content=json.dumps(payload, ensure_ascii=False)).send()
        self.persist_message({"role": "assistant", "messageType": "file_result", "fileUrl": file_url, "fileName": file_name, "fileMime": file_mime, "agentName": agent_name})

    async def reply_model_catalog(self, recommended: dict, search_results: list, selected_model: str = "", catalog_type: str = "text"):
        """Send model catalog to frontend for user selection"""
        # Resolve actual model name if adaptive (empty)
        resolved_model = selected_model
        if not selected_model:
            resolved_model = self._get_resolved_model_name()
        # Convert to ModelCatalogItem lists
        rec_items = {}
        for cat, models in recommended.items():
            rec_items[cat] = [
                ModelCatalogItem(
                    id=m.get("id", ""),
                    name=m.get("name", ""),
                    context_length=m.get("context_length", "?"),
                    prompt_price=m.get("prompt_price", "?"),
                    completion_price=m.get("completion_price", "?"),
                    categories=m.get("categories", []),
                    is_free=m.get("is_free", False),
                )
                for m in models
            ]
        search_items = [
            ModelCatalogItem(
                id=m.get("id", ""),
                name=m.get("name", ""),
                context_length=m.get("context_length", "?"),
                prompt_price=m.get("prompt_price", "?"),
                completion_price=m.get("completion_price", "?"),
                categories=m.get("categories", []),
                is_free=m.get("is_free", False),
            )
            for m in search_results
        ]
        payload = chat_reply(ChatReplyModelCatalog(
            recommended=rec_items,
            searchResults=search_items,
            selectedModel=selected_model,
            catalogType=catalog_type,
        ))
        # Add resolved model name for adaptive mode display
        payload["payload"]["resolvedModel"] = resolved_model
        await cl.Message(content=json.dumps(payload, ensure_ascii=False)).send()

    async def reply_chat_history(self, session_id: str):
        """Send full chat history for a session, including canvas state"""
        session = self.chat_store.get_session(session_id)
        messages = session["messages"] if session else []
        canvas_state = self.chat_store.get_canvas_state(session_id) if session else None
        payload = {
            "type": "chat_reply",
            "payload": {
                "messageType": "chat_history",
                "sessionId": session_id,
                "messages": messages,
                "canvasState": canvas_state,
            },
        }
        await cl.Message(content=json.dumps(payload, ensure_ascii=False)).send()

    async def reply_chat_sessions(self):
        """Send list of all chat sessions"""
        sessions = self.chat_store.list_sessions()
        session_list = [
            {"id": s["id"], "title": s["title"], "updated_at": s.get("updated_at", "")}
            for s in sessions
        ]
        payload = {
            "type": "chat_reply",
            "payload": {
                "messageType": "chat_sessions",
                "sessions": session_list,
                "currentSessionId": self.current_session_id,
            },
        }
        await cl.Message(content=json.dumps(payload, ensure_ascii=False)).send()

    def persist_message(self, message: dict):
        """Persist a message to the current chat session"""
        if self.current_session_id:
            self.chat_store.add_message(self.current_session_id, message)

    def update_plan_status(self, status: str):
        """Update the planStatus of the most recent plan message in the current session"""
        if not self.current_session_id:
            return
        session = self.chat_store.get_session(self.current_session_id)
        if not session:
            return
        msgs = session["messages"]
        for i in range(len(msgs) - 1, -1, -1):
            if msgs[i].get("messageType") == "plan":
                msgs[i]["planStatus"] = status
                self.chat_store._save()
                break

    async def clear_plan(self):
        self.state["current_plan"] = None
        await self._send()

    async def set_plan(self, agent: dict, task_description: str, plan_type: str = "new"):
        self.state["current_plan"] = {
            "agents": [agent],
            "task_description": task_description,
            "plan_type": plan_type,
        }
        await self._send()

    async def set_multi_agent_plan(self, agents: list[dict], task_description: str, plan_type: str = "new"):
        self.state["current_plan"] = {
            "agents": agents,
            "task_description": task_description,
            "plan_type": plan_type,
        }
        await self._send()

    async def add_task(self, task_id: str, title: str, agent_name: str) -> dict:
        task = {
            "id": task_id,
            "title": title,
            "agent": agent_name,
            "status": "running",
            "progress": 0,
            "result": "",
            "created_at": datetime.now().isoformat(),
        }
        self.task_store.add_task(task)
        self.state["tasks"] = self.task_store.list_tasks()
        await self._send()
        return task

    async def update_task(self, task_id: str, **kwargs):
        self.task_store.update_task(task_id, **kwargs)
        self.state["tasks"] = self.task_store.list_tasks()
        await self._send()

    async def update_task_image(self, task_id: str, image_url: str, image_prompt: str, media_type: str = "image"):
        """Append a generated image to its originating task's image list."""
        task = self.task_store.get_task(task_id)
        images = task.get("images", []) if task else []
        images.append({"url": image_url, "prompt": image_prompt, "media_type": media_type})
        self.task_store.update_task(task_id, image_url=image_url, image_prompt=image_prompt, images=images)
        self.state["tasks"] = self.task_store.list_tasks()
        await self._send()

    async def delete_task(self, task_id: str):
        self.task_store.delete_task(task_id)
        self.state["tasks"] = self.task_store.list_tasks()
        await self._send()


def get_messenger() -> StateMessenger:
    return cl.user_session.get("messenger")


async def execute_multi_agent_task(
    user_input: str,
    agent_specs: list[dict],
    registry: AgentRegistry,
):
    """รัน Task กับหลาย Agent พร้อมกันใน Crew เดียว"""
    cl.user_session.set("state", STATE_EXECUTING)
    messenger = get_messenger()
    task_id = str(uuid.uuid4())[:8]

    if messenger:
        agent_names = ", ".join(s.get("name", "Agent") for s in agent_specs)
        await messenger.add_task(task_id, user_input, agent_names)
        # Send initial per-agent progress: all pending
        initial_agents = [
            {
                "name": s.get("name", "Agent"),
                "role": s.get("role", ""),
                "status": "pending",
                "progress": 0,
                "model": s.get("model", ""),
            }
            for s in agent_specs
        ]
        await messenger.reply_agent_progress(task_id, initial_agents)

    # Mark all agents as Busy
    for spec in agent_specs:
        rid = spec.get("registry_id")
        if rid:
            registry.update_status(rid, "Busy")
    if messenger:
        await messenger.update_agents(registry)

    _exec_loop = asyncio.get_event_loop()
    _exec_ctx = contextvars.copy_context()

    def update_progress(percent: int, status: str):
        if messenger:
            def _schedule():
                _exec_loop.create_task(
                    messenger.update_task(task_id, progress=percent, result=status),
                    context=_exec_ctx,
                )
            _exec_loop.call_soon_threadsafe(_schedule)

    async def update_agent_progress(agents_progress: list[dict]):
        """Send per-agent progress update to frontend (async for thread-safe scheduling)."""
        if messenger:
            await messenger.reply_agent_progress(task_id, agents_progress)

    try:
        llm_manager = LLMManager()
        tool_registry = ToolRegistry()
        orchestrator = ExecutionOrchestrator(llm_manager, tool_registry, update_progress, update_agent_progress)
        pre_assigned = cl.user_session.get("pre_assigned_models")
        # Assign model to each spec so progress can display it
        for spec in agent_specs:
            name = spec.get("name", "")
            if pre_assigned and name and pre_assigned.get("workers", {}).get(name):
                spec["model"] = pre_assigned["workers"][name]
            if not spec.get("model"):
                spec["model"] = ""
        if messenger and not pre_assigned:
            await messenger.notify(f"⚙️ กำลังกำหนด model ให้ {len(agent_specs)} agents...")
        if messenger:
            await messenger.notify("🔥 Crew เริ่มทำงานแล้ว — รอผลลัพธ์...")
        result = await orchestrator.run_async(user_input, agent_specs, pre_assigned_models=pre_assigned)
        cl.user_session.set("pre_assigned_models", None)  # clear after use

        # result is now a dict with "raw" and "agent_outputs"
        raw_output = result.get("raw", str(result))
        agent_outputs = result.get("agent_outputs", [])

        if messenger:
            # Send final per-agent progress: all complete with outputs
            final_agents = []
            for i, spec in enumerate(agent_specs):
                out = agent_outputs[i] if i < len(agent_outputs) else {}
                final_agents.append({
                    "name": spec.get("name", "Agent"),
                    "role": spec.get("role", ""),
                    "status": "complete",
                    "progress": 100,
                    "output": (out.get("output", "") or "")[:2000],
                    "model": spec.get("model", ""),
                })
            await messenger.reply_agent_progress(task_id, final_agents)

            cl.run_sync(
                messenger.update_task(
                    task_id,
                    progress=100,
                    status="complete",
                    result=raw_output,
                    agent_outputs=agent_outputs,
                    agent_progress=final_agents,
                )
            )
            await messenger.reply_result(
                f"✅ งานเสร็จสมบูรณ์ ({len(agent_specs)} agents)",
                agent_outputs,
            )

            # Send approval cards for media prompts captured directly from tool calls
            # (not from agent final answer — CrewAI may not echo tool results back)
            # Sort: images first, then videos; each sorted by detected day number
            def _day_sort_key(item):
                prompt_lower = item.get("prompt", "").lower()
                for day_num in range(1, 10):
                    if f"day {day_num}" in prompt_lower or f"day{day_num}" in prompt_lower:
                        return day_num
                return 99  # unknown day → sort last
            sorted_results = sorted(_media_tool_results, key=lambda r: (0 if r.get("type") == "image" else 1, _day_sort_key(r)))

            # Check if plan includes a review/quality step
            has_reviewer = any(
                any(kw in (spec.get("role", "") + spec.get("name", "")).lower()
                    for kw in ["review", "quality", "checker", "approver", "editor"])
                for spec in agent_specs
            )

            # If reviewer exists, ask manager LLM to refine prompts before sending approvals
            if has_reviewer and sorted_results and llm_manager:
                print(f"[APPROVAL-FLOW] Plan has reviewer — refining {len(sorted_results)} prompts via manager LLM", flush=True)
                await messenger.notify("🔍 Reviewer กำลังตรวจสอบ prompt สำหรับสื่อ...")
                try:
                    prompts_text = "\n".join(
                        f"{i+1}. [{r.get('type','image')}] {r.get('prompt','')}"
                        for i, r in enumerate(sorted_results)
                    )
                    review_prompt = (
                        f"You are reviewing image/video generation prompts for quality.\n"
                        f"Original prompts from agents:\n{prompts_text}\n\n"
                        f"For each prompt, check: clarity, visual detail, English quality, alignment with the task.\n"
                        f"If a prompt is good, keep it as-is. If it needs improvement, rewrite it.\n"
                        f"Return ONLY the refined prompts, one per line, prefixed with the index number and type.\n"
                        f"Format: N. [type] refined prompt here"
                    )
                    refined = llm_manager.call_with_fallback(review_prompt)
                    # Parse refined prompts
                    for line in refined.strip().split("\n"):
                        line = line.strip()
                        # Match "N. [type] prompt" format
                        m = re.match(r'^(\d+)\.\s*\[?(\w+)\]?\s*(.+)', line)
                        if m:
                            idx = int(m.group(1)) - 1
                            if 0 <= idx < len(sorted_results):
                                sorted_results[idx]["prompt"] = m.group(3).strip()
                    print(f"[APPROVAL-FLOW] Prompts refined by reviewer", flush=True)
                except Exception as e:
                    print(f"[APPROVAL-FLOW] Review failed, using original prompts: {_sanitize_error(e)}", flush=True)
            else:
                print(f"[APPROVAL-FLOW] No reviewer in plan — prompts are final from agent", flush=True)

            async def _send_approval_card(media_result, idx):
                media_type = media_result.get("type", "image")
                media_prompt = media_result.get("prompt", "")
                media_duration = media_result.get("duration", 5)
                agent_name = media_result.get("agent_name", "")
                if not agent_name:
                    # Fallback: try to match by checking which agent spec has generate_image/generate_video tool
                    tool_name = "generate_image" if media_type == "image" else "generate_video"
                    for spec in agent_specs:
                        if tool_name in spec.get("tools", []):
                            agent_name = spec.get("name", "")
                            break
                _debug(f"[DEBUG-APPROVAL] Sending approval card: agent_name='{agent_name}', type={media_type}, prompt_len={len(media_prompt)}", flush=True)
                if not media_prompt:
                    return
                approval_id = f"{media_type}_{task_id}_{idx}"
                cl.user_session.set(f"pending_media_{approval_id}", {
                    "prompt": media_prompt,
                    "agent_name": agent_name,
                    "task_id": task_id,
                    "media_type": media_type,
                    "duration": media_duration,
                })
                await messenger.reply_image_approval(
                    media_prompt, approval_id, agent_name,
                    media_type=media_type, duration=media_duration,
                    model=media_result.get("model", "")
                )

            for idx, media_result in enumerate(sorted_results):
                await _send_approval_card(media_result, idx)

            # Fallback: if agent was supposed to call generate_video but didn't (local LLM
            # sometimes outputs tool call as text instead of calling it), parse output.
            # Only look for generate_video tool call patterns, NOT generic "prompt" keys
            # (which could match image prompts in JSON output).
            if not any(r.get("type") == "video" for r in _media_tool_results):
                for i, agent_out in enumerate(agent_outputs):
                    agent_spec = agent_specs[i] if i < len(agent_specs) else {}
                    if "generate_video" not in agent_spec.get("tools", []):
                        continue
                    output_text = agent_out.get("output", "")
                    vid_match = re.search(
                        r'"name"\s*:\s*"generate_video"\s*,\s*"arguments"\s*:\s*\{[^}]*"prompt"\s*:\s*"([^"]+)"',
                        output_text
                    )
                    if vid_match:
                        vid_prompt = vid_match.group(1)
                        _debug(f"[DEBUG-FALLBACK] Extracted video prompt from agent output: {vid_prompt[:80]}...", flush=True)
                        media_entry = {
                            "type": "video", "prompt": vid_prompt,
                            "duration": 5, "agent_name": agent_out.get("name", ""),
                        }
                        _media_tool_results.append(media_entry)
                        await _send_approval_card(media_entry, len(_media_tool_results) - 1)

            # Fallback: if agent was supposed to call generate_image but didn't,
            # parse English prompt from code block in agent output
            if not any(r.get("type") == "image" for r in _media_tool_results):
                for i, agent_out in enumerate(agent_outputs):
                    agent_spec = agent_specs[i] if i < len(agent_specs) else {}
                    if "generate_image" not in agent_spec.get("tools", []):
                        continue
                    output_text = agent_out.get("output", "")
                    # Try to find prompt in a code block (```...```)
                    img_match = re.search(r'```\s*\n([A-Za-z][^`]{20,})\n```', output_text)
                    if not img_match:
                        # Also try: "Prompt:" followed by text
                        img_match = re.search(r'Prompt[:\s]+([A-Za-z][^\n]{20,})', output_text)
                    if img_match:
                        img_prompt = img_match.group(1).strip()
                        image_model = cl.user_session.get("ai_image_model") or ""
                        _debug(f"[DEBUG-FALLBACK] Extracted image prompt from agent output: {img_prompt[:80]}...", flush=True)
                        media_entry = {
                            "type": "image", "prompt": img_prompt,
                            "agent_name": agent_out.get("name", ""),
                            "model": image_model,
                        }
                        _media_tool_results.append(media_entry)
                        await _send_approval_card(media_entry, len(_media_tool_results) - 1)
    except Exception as e:
        tb = traceback.format_exc()
        print(f"[CREW ERROR] {_sanitize_error(e)}")
        _debug(f"[TRACEBACK] {tb}", flush=True)
        if _is_rate_limit_error(e):
            llm_mgr = LLMManager()
            llm_mgr.report_rate_limit()
            if messenger:
                if llm_mgr.local_fallback_enabled:
                    await messenger.reply("⚠️ ติดลิมิตการใช้ AI ฝรั่ง กำลังสลับไปใช้ Local LLM ชั่วคราว (60 วินาที)")
                else:
                    await messenger.reply("⚠️ ติดลิมิตการใช้ OpenRouter — กรุณารอสักครู่แล้วลองใหม่ (Local fallback ปิดอยู่)")
        if messenger:
            cl.run_sync(
                messenger.update_task(
                    task_id,
                    progress=100,
                    status="error",
                    result=f"❌ เกิดข้อผิดพลาด: {str(e)}\n\n```\n{tb[:1000]}\n```",
                )
            )
            await messenger.reply_progress(100, "❌ งานล้มเหลว", progress_id=task_id)
            await messenger.reply_result(
                "❌ งานล้มเหลว",
                [{"name": "Error", "role": "", "output": f"{str(e)}\n\n{tb[:500]}"}],
                is_error=True,
            )
    finally:
        for spec in agent_specs:
            rid = spec.get("registry_id")
            if rid:
                registry.update_status(rid, "Idle")
        if messenger:
            await messenger.update_agents(registry)
        cl.user_session.set("state", STATE_IDLE)
        cl.user_session.set("current_agent_specs", None)
        cl.user_session.set("current_input", None)


async def execute_task_with_agent(
    user_input: str,
    agent_spec: dict,
    registry_id: str | None,
    registry: AgentRegistry,
):
    """รัน Task กับ Agent ที่ระบุ พร้อมอัปเดต Task Slot และ Registry Status"""
    cl.user_session.set("state", STATE_EXECUTING)
    messenger = get_messenger()
    task_id = str(uuid.uuid4())[:8]
    agent_name = agent_spec.get("name", "Agent")

    if messenger:
        await messenger.add_task(task_id, user_input, agent_name)

    if registry_id:
        registry.update_status(registry_id, "Busy")
        if messenger:
            await messenger.update_agents(registry)

    _exec_loop = asyncio.get_event_loop()
    _exec_ctx = contextvars.copy_context()

    def update_progress(percent: int, status: str):
        if messenger:
            def _schedule():
                _exec_loop.create_task(
                    messenger.update_task(task_id, progress=percent, result=status),
                    context=_exec_ctx,
                )
            _exec_loop.call_soon_threadsafe(_schedule)

    try:
        llm_manager = LLMManager()
        tool_registry = ToolRegistry()
        orchestrator = ExecutionOrchestrator(llm_manager, tool_registry, update_progress)
        result = await orchestrator.run_async(user_input, [agent_spec])

        if messenger:
            cl.run_sync(
                messenger.update_task(
                    task_id,
                    progress=100,
                    status="complete",
                    result=str(result),
                )
            )
            await messenger.notify(f"✅ งานของ {agent_name} เสร็จสมบูรณ์")
    except Exception as e:
        tb = traceback.format_exc()
        print(f"[CREW ERROR] {_sanitize_error(e)}")
        _debug(f"[TRACEBACK] {tb}", flush=True)
        if _is_rate_limit_error(e):
            llm_mgr = LLMManager()
            llm_mgr.report_rate_limit()
            if messenger:
                await messenger.notify("⚠️ ติดลิมิต AI ฝรั่ง สลับไป Local LLM ชั่วคราว (60 วินาที)")
        if messenger:
            cl.run_sync(
                messenger.update_task(
                    task_id,
                    progress=100,
                    status="error",
                    result=f"❌ เกิดข้อผิดพลาด: {str(e)}\n\n```\n{tb[:1000]}\n```",
                )
            )
            await messenger.notify(f"❌ งานของ {agent_name} ล้มเหลว")
    finally:
        if registry_id:
            registry.update_status(registry_id, "Idle")
            if messenger:
                await messenger.update_agents(registry)
        cl.user_session.set("state", STATE_IDLE)
        cl.user_session.set("current_agent_specs", None)
        cl.user_session.set("current_input", None)
        cl.user_session.set("current_registry_id", None)


# ============================================================
# Chat Lifecycle
# ============================================================
@cl.on_chat_start
async def on_chat_start():
    registry = AgentRegistry()
    cl.user_session.set("registry", registry)
    cl.user_session.set("state", STATE_IDLE)
    cl.user_session.set("current_agent_specs", None)
    cl.user_session.set("current_input", None)
    cl.user_session.set("current_registry_id", None)
    cl.user_session.set("conversation_history", [])

    chat_store = ChatStore()
    # Create default session if none exists
    sessions = chat_store.list_sessions()
    if not sessions:
        default = chat_store.create_session("New Chat")
        current_session_id = default["id"]
    else:
        current_session_id = sessions[0]["id"]

    messenger = StateMessenger(task_store=TaskStore(), chat_store=chat_store)
    messenger.current_session_id = current_session_id
    cl.user_session.set("messenger", messenger)
    await messenger.init(registry)
    await messenger.set_status("Ready")
    await messenger.reply_chat_sessions()
    await messenger.reply_chat_history(current_session_id)

    # Send model catalog with resolved model name so frontend shows proper names
    try:
        llm_mgr = LLMManager()
        if llm_mgr.tier in ("paid", "free"):
            catalog = ModelCatalog(llm_mgr.api_key, llm_mgr.base_url)
            loop = asyncio.get_event_loop()
            recommended = await loop.run_in_executor(None, catalog.get_recommended)
            selected = cl.user_session.get("selected_model") or ""
            await messenger.reply_model_catalog(recommended, [], selected)

            # Also fetch and send media catalogs (image + video + search)
            selector = ModelSelector(llm_mgr.api_key, llm_mgr.base_url)
            all_models = await loop.run_in_executor(None, selector._fetch_all_models)
            for media_type in ("image", "video", "search"):
                filtered = []
                for m in all_models:
                    arch = m.get("architecture", {})
                    output_modalities = arch.get("output_modalities", [])
                    mid = m.get("id", "").lower()
                    # Skip OpenRouter routing models — they are text-only, not real media models
                    if mid.startswith("openrouter/"):
                        continue
                    if media_type == "image" and "image" in output_modalities:
                        filtered.append(m)
                    elif media_type == "video" and "video" in output_modalities:
                        filtered.append(m)
                    elif media_type == "search":
                        params = m.get("supported_parameters", [])
                        search_keywords = ["sonar", "perplexity", "search", "online"]
                        if "web_search" in params or any(kw in mid for kw in search_keywords):
                            filtered.append(m)
                if not filtered:
                    continue
                entries = []
                for m in filtered:
                    mid = m.get("id", "")
                    name = m.get("name", mid)
                    pricing = m.get("pricing", {})
                    entries.append({
                        "id": mid,
                        "name": name,
                        "context_length": m.get("context_length", "?"),
                        "prompt_price": pricing.get("prompt", "?"),
                        "completion_price": pricing.get("completion", "?"),
                        "categories": [media_type],
                        "is_free": ":free" in mid,
                    })
                grouped = {media_type: entries}
                print(f"[CHAT-START] Sending media catalog for {media_type}: {len(entries)} models", flush=True)
                await messenger.reply_model_catalog(grouped, [], "", catalog_type="media")
    except Exception as e:
        print(f"[CHAT-START] Failed to send model catalog: {_sanitize_error(e)}", flush=True)


# ============================================================
# Attachment & URL Processing Pipeline
# ============================================================

URL_REGEX = r'https?://[^\s<>"{}|\\^`\[\]]+'

MAX_TEXT_LENGTH = 50000
MAX_URL_DOWNLOAD_SIZE = 50 * 1024 * 1024  # 50MB

AUDIO_FORMAT_MAP = {
    "audio/wav": "wav", "audio/x-wav": "wav",
    "audio/mpeg": "mp3", "audio/mp3": "mp3",
    "audio/flac": "flac",
    "audio/mp4": "m4a", "audio/x-m4a": "m4a",
    "audio/ogg": "ogg",
    "audio/webm": "webm",
    "audio/aac": "aac",
}

URL_EXT_MAP = {
    ".jpg": "image", ".jpeg": "image", ".png": "image", ".webp": "image", ".gif": "image",
    ".pdf": "pdf",
    ".mp3": "audio", ".wav": "audio", ".flac": "audio", ".ogg": "audio",
    ".m4a": "audio", ".aac": "audio",
    ".mp4": "video", ".mov": "video", ".webm": "video", ".mpeg": "video",
}


def classify_url(url: str) -> str:
    """Classify URL into type: youtube, image, pdf, audio, video, webpage."""
    if "youtube.com/watch" in url or "youtu.be/" in url:
        return "youtube"
    url_lower = url.lower().split("?")[0]
    for ext, ftype in URL_EXT_MAP.items():
        if url_lower.endswith(ext):
            return ftype
    return "webpage"


def _is_localhost_url(url: str) -> bool:
    """Check if URL points to localhost or internal IP (SSRF protection)."""
    from urllib.parse import urlparse
    parsed = urlparse(url)
    host = parsed.hostname or ""
    if host in ("localhost", "127.0.0.1", "0.0.0.0", "::1"):
        return True
    if host.startswith("10.") or host.startswith("192.168.") or host.startswith("172.16."):
        return True
    return False


def download_with_limit(url: str, timeout: int = 30) -> bytes:
    """Download URL content with size limit. Raises ValueError if exceeds MAX_URL_DOWNLOAD_SIZE."""
    response = requests.get(
        url, timeout=timeout, stream=True,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    response.raise_for_status()
    content = b""
    for chunk in response.iter_content(chunk_size=8192):
        content += chunk
        if len(content) > MAX_URL_DOWNLOAD_SIZE:
            raise ValueError(
                f"URL content exceeds {MAX_URL_DOWNLOAD_SIZE // 1024 // 1024}MB limit"
            )
    return content


def check_model_modality_support(model_id: str, required_modality: str) -> bool:
    """Check if model supports required modality (image, pdf, audio, video)."""
    discovery = ModelDiscoveryService(
        base_url=os.getenv("LLM_BASE_URL", "https://openrouter.ai/api/v1"),
        api_key=os.getenv("LLM_API_KEY", ""),
    )
    all_models = discovery._fetch_all_models()
    for m in all_models:
        if m.get("id") == model_id:
            arch = m.get("architecture", {})
            input_modalities = arch.get("input_modalities", [])
            modality_map = {
                "image": "image",
                "pdf": "file",
                "audio": "audio",
                "video": "video",
            }
            return modality_map.get(required_modality) in input_modalities
    return False


def llm_manager_tier_check() -> bool:
    """Check if LLM is configured for OpenRouter (paid/free tier)."""
    provider = os.getenv("LLM_PROVIDER", "local").lower()
    return provider == "openrouter"


def _resolve_file_path(file_url: str) -> str:
    """Convert attachment URL to local file path."""
    if file_url.startswith("http"):
        from urllib.parse import urlparse
        parsed = urlparse(file_url)
        return os.path.join(os.path.dirname(__file__), parsed.path.lstrip("/"))
    return os.path.join(os.path.dirname(__file__), file_url.lstrip("/"))


def _extract_text_content(file_path: str, file_mime: str) -> str:
    """Extract text from text-based files."""
    if file_mime == "application/pdf":
        try:
            import pdfplumber
            with pdfplumber.open(file_path) as pdf:
                text = "\n".join(page.extract_text() or "" for page in pdf.pages)
                return text[:MAX_TEXT_LENGTH] + ("[...truncated]" if len(text) > MAX_TEXT_LENGTH else "")
        except Exception as e:
            print(f"[ATTACHMENT] PDF text extraction failed: {_sanitize_error(e)}", flush=True)
            return ""

    if file_mime == "application/vnd.openxmlformats-officedocument.wordprocessingml.document" or file_path.endswith(".docx"):
        try:
            from docx import Document
            doc = Document(file_path)
            text = "\n".join(p.text for p in doc.paragraphs)
            return text[:MAX_TEXT_LENGTH] + ("[...truncated]" if len(text) > MAX_TEXT_LENGTH else "")
        except Exception as e:
            print(f"[ATTACHMENT] DOCX extraction failed: {_sanitize_error(e)}", flush=True)
            return ""

    if file_mime == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" or file_path.endswith(".xlsx"):
        try:
            from openpyxl import load_workbook
            wb = load_workbook(file_path, read_only=True)
            text_parts = []
            for ws in wb.worksheets:
                for row in ws.iter_rows(values_only=True):
                    text_parts.append("\t".join(str(c) if c is not None else "" for c in row))
            wb.close()
            text = "\n".join(text_parts)
            return text[:MAX_TEXT_LENGTH] + ("[...truncated]" if len(text) > MAX_TEXT_LENGTH else "")
        except Exception as e:
            print(f"[ATTACHMENT] XLSX extraction failed: {_sanitize_error(e)}", flush=True)
            return ""

    # Default: read as text
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
        return text[:MAX_TEXT_LENGTH] + ("[...truncated]" if len(text) > MAX_TEXT_LENGTH else "")
    except Exception as e:
        print(f"[ATTACHMENT] Text read failed: {_sanitize_error(e)}", flush=True)
        return ""


async def process_attachment(file_url: str, file_name: str, file_mime: str) -> dict:
    """Process an uploaded file and return AI-consumable context.

    Returns:
        {
            "type": "multimodal" | "text" | "metadata",
            "content_blocks": list[dict],
            "plugins": list[dict] | None,
            "crewai_files": dict | None,
            "text_content": str,
            "context_text": str,
            "required_modality": str | None,
            "file_name": str,
            "file_mime": str,
        }
    """
    file_path = _resolve_file_path(file_url)

    if not os.path.exists(file_path):
        print(f"[ATTACHMENT] File not found: {file_path}", flush=True)
        return {
            "type": "metadata",
            "content_blocks": [],
            "plugins": None,
            "crewai_files": None,
            "text_content": "",
            "context_text": f"[Attachment: {file_name} — file not found]",
            "required_modality": None,
            "file_name": file_name,
            "file_mime": file_mime,
        }

    # --- Image ---
    if file_mime.startswith("image/") and not file_mime == "image/svg+xml":
        try:
            with open(file_path, "rb") as f:
                file_bytes = f.read()
            b64 = base64.b64encode(file_bytes).decode("utf-8")
            data_url = f"data:{file_mime};base64,{b64}"
            crewai_files = {}
            try:
                from crewai_files import ImageFile
                crewai_files = {"image": ImageFile(source=file_path)}
            except ImportError:
                pass
            return {
                "type": "multimodal",
                "content_blocks": [{"type": "image_url", "image_url": {"url": data_url}}],
                "plugins": None,
                "crewai_files": crewai_files or None,
                "text_content": "",
                "context_text": f"[Image: {file_name}]",
                "required_modality": "image",
                "file_name": file_name,
                "file_mime": file_mime,
            }
        except Exception as e:
            print(f"[ATTACHMENT] Image processing failed: {_sanitize_error(e)}", flush=True)

    # --- PDF ---
    if file_mime == "application/pdf":
        try:
            with open(file_path, "rb") as f:
                file_bytes = f.read()
            b64 = base64.b64encode(file_bytes).decode("utf-8")
            crewai_files = {}
            try:
                from crewai_files import PDFFile
                crewai_files = {"pdf": PDFFile(source=file_path)}
            except ImportError:
                pass
            return {
                "type": "multimodal",
                "content_blocks": [{"type": "file", "file": {"filename": file_name, "file_data": f"data:application/pdf;base64,{b64}"}}],
                "plugins": [{"id": "file-parser", "pdf": {"engine": "cloudflare-ai"}}],
                "crewai_files": crewai_files or None,
                "text_content": "",
                "context_text": f"[PDF: {file_name}]",
                "required_modality": "pdf",
                "file_name": file_name,
                "file_mime": file_mime,
            }
        except Exception as e:
            print(f"[ATTACHMENT] PDF processing failed: {_sanitize_error(e)}, falling back to text", flush=True)
            text = _extract_text_content(file_path, file_mime)
            if text:
                return {
                    "type": "text",
                    "content_blocks": [],
                    "plugins": None,
                    "crewai_files": None,
                    "text_content": text,
                    "context_text": f"[PDF text: {file_name}]",
                    "required_modality": None,
                    "file_name": file_name,
                    "file_mime": file_mime,
                }

    # --- Audio ---
    if file_mime.startswith("audio/"):
        try:
            with open(file_path, "rb") as f:
                file_bytes = f.read()
            b64 = base64.b64encode(file_bytes).decode("utf-8")
            fmt = AUDIO_FORMAT_MAP.get(file_mime, "mp3")
            crewai_files = {}
            try:
                from crewai_files import AudioFile
                crewai_files = {"audio": AudioFile(source=file_path)}
            except ImportError:
                pass
            return {
                "type": "multimodal",
                "content_blocks": [{"type": "input_audio", "input_audio": {"data": b64, "format": fmt}}],
                "plugins": None,
                "crewai_files": crewai_files or None,
                "text_content": "",
                "context_text": f"[Audio: {file_name}]",
                "required_modality": "audio",
                "file_name": file_name,
                "file_mime": file_mime,
            }
        except Exception as e:
            print(f"[ATTACHMENT] Audio processing failed: {_sanitize_error(e)}", flush=True)

    # --- Video ---
    if file_mime.startswith("video/"):
        try:
            file_size = os.path.getsize(file_path)
            if file_size < 20 * 1024 * 1024:
                with open(file_path, "rb") as f:
                    file_bytes = f.read()
                b64 = base64.b64encode(file_bytes).decode("utf-8")
                crewai_files = {}
                try:
                    from crewai_files import VideoFile
                    crewai_files = {"video": VideoFile(source=file_path)}
                except ImportError:
                    pass
                return {
                    "type": "multimodal",
                    "content_blocks": [{"type": "video_url", "video_url": {"url": f"data:{file_mime};base64,{b64}"}}],
                    "plugins": None,
                    "crewai_files": crewai_files or None,
                    "text_content": "",
                    "context_text": f"[Video: {file_name}]",
                    "required_modality": "video",
                    "file_name": file_name,
                    "file_mime": file_mime,
                }
            else:
                print(f"[ATTACHMENT] Video too large ({file_size} bytes), metadata only", flush=True)
        except Exception as e:
            print(f"[ATTACHMENT] Video processing failed: {_sanitize_error(e)}", flush=True)

    # --- Text-extractable files ---
    text_extractable = (
        file_mime.startswith("text/") or
        file_mime in ("application/json", "application/xml", "application/csv") or
        file_mime == "image/svg+xml" or
        file_name.endswith((".txt", ".csv", ".json", ".xml", ".svg", ".md")) or
        file_name.endswith(".docx") or
        file_name.endswith(".xlsx") or
        file_mime == "application/pdf"  # fallback if multimodal failed
    )
    if text_extractable:
        text = _extract_text_content(file_path, file_mime)
        if text:
            return {
                "type": "text",
                "content_blocks": [],
                "plugins": None,
                "crewai_files": None,
                "text_content": text,
                "context_text": f"[Text file: {file_name}]",
                "required_modality": None,
                "file_name": file_name,
                "file_mime": file_mime,
            }

    # --- Metadata fallback ---
    return {
        "type": "metadata",
        "content_blocks": [],
        "plugins": None,
        "crewai_files": None,
        "text_content": "",
        "context_text": f"[Attachment: {file_name} ({file_mime})]",
        "required_modality": None,
        "file_name": file_name,
        "file_mime": file_mime,
    }


async def process_url(url: str) -> dict:
    """Process a URL and return AI-consumable context (same format as process_attachment)."""
    url_type = classify_url(url)

    if _is_localhost_url(url) and not url.startswith("http://localhost:8000"):
        return {
            "type": "metadata",
            "content_blocks": [],
            "plugins": None,
            "crewai_files": None,
            "text_content": "",
            "context_text": f"[URL rejected for security: {url}]",
            "required_modality": None,
            "file_name": url,
            "file_mime": "",
        }

    if url_type == "youtube":
        crewai_files = {}
        try:
            from crewai_files import VideoFile
            crewai_files = {"video": VideoFile(source=url)}
        except ImportError:
            pass
        return {
            "type": "multimodal",
            "content_blocks": [{"type": "video_url", "video_url": {"url": url}}],
            "plugins": None,
            "crewai_files": crewai_files or None,
            "text_content": "",
            "context_text": f"[YouTube video: {url}]",
            "required_modality": "video",
            "file_name": url,
            "file_mime": "",
        }

    if url_type == "image":
        crewai_files = {}
        try:
            from crewai_files import ImageFile
            crewai_files = {"image": ImageFile(source=url)}
        except ImportError:
            pass
        return {
            "type": "multimodal",
            "content_blocks": [{"type": "image_url", "image_url": {"url": url}}],
            "plugins": None,
            "crewai_files": crewai_files or None,
            "text_content": "",
            "context_text": f"[Image URL: {url}]",
            "required_modality": "image",
            "file_name": url,
            "file_mime": "",
        }

    if url_type == "pdf":
        crewai_files = {}
        try:
            from crewai_files import PDFFile
            crewai_files = {"pdf": PDFFile(source=url)}
        except ImportError:
            pass
        return {
            "type": "multimodal",
            "content_blocks": [{"type": "file", "file": {"filename": "document.pdf", "file_data": url}}],
            "plugins": [{"id": "file-parser", "pdf": {"engine": "cloudflare-ai"}}],
            "crewai_files": crewai_files or None,
            "text_content": "",
            "context_text": f"[PDF URL: {url}]",
            "required_modality": "pdf",
            "file_name": url,
            "file_mime": "",
        }

    if url_type == "audio":
        try:
            audio_bytes = download_with_limit(url, timeout=30)
            b64 = base64.b64encode(audio_bytes).decode("utf-8")
            content_type = ""
            url_lower = url.lower().split("?")[0]
            for ext, fmt in [(".mp3", "mp3"), (".wav", "wav"), (".flac", "flac"),
                             (".ogg", "ogg"), (".m4a", "m4a"), (".aac", "aac")]:
                if url_lower.endswith(ext):
                    fmt_key = f"audio/{fmt}"
                    fmt = AUDIO_FORMAT_MAP.get(fmt_key, fmt)
                    break
            crewai_files = {}
            try:
                from crewai_files import AudioFile
                crewai_files = {"audio": AudioFile(source=url)}
            except ImportError:
                pass
            return {
                "type": "multimodal",
                "content_blocks": [{"type": "input_audio", "input_audio": {"data": b64, "format": fmt}}],
                "plugins": None,
                "crewai_files": crewai_files or None,
                "text_content": "",
                "context_text": f"[Audio URL: {url}]",
                "required_modality": "audio",
                "file_name": url,
                "file_mime": "",
            }
        except Exception as e:
            print(f"[ATTACHMENT] Audio URL download failed: {_sanitize_error(e)}", flush=True)
            return {
                "type": "metadata",
                "content_blocks": [],
                "plugins": None,
                "crewai_files": None,
                "text_content": "",
                "context_text": f"[Audio URL failed: {url} — {_sanitize_error(e)}]",
                "required_modality": None,
                "file_name": url,
                "file_mime": "",
            }

    if url_type == "video":
        try:
            video_bytes = download_with_limit(url, timeout=60)
            if len(video_bytes) < 20 * 1024 * 1024:
                b64 = base64.b64encode(video_bytes).decode("utf-8")
                crewai_files = {}
                try:
                    from crewai_files import VideoFile
                    crewai_files = {"video": VideoFile(source=url)}
                except ImportError:
                    pass
                return {
                    "type": "multimodal",
                    "content_blocks": [{"type": "video_url", "video_url": {"url": f"data:video/mp4;base64,{b64}"}}],
                    "plugins": None,
                    "crewai_files": crewai_files or None,
                    "text_content": "",
                    "context_text": f"[Video URL: {url}]",
                    "required_modality": "video",
                    "file_name": url,
                    "file_mime": "",
                }
            else:
                return {
                    "type": "metadata",
                    "content_blocks": [],
                    "plugins": None,
                    "crewai_files": None,
                    "text_content": "",
                    "context_text": f"[Video URL too large: {url}]",
                    "required_modality": None,
                    "file_name": url,
                    "file_mime": "",
                }
        except Exception as e:
            print(f"[ATTACHMENT] Video URL download failed: {_sanitize_error(e)}", flush=True)
            return {
                "type": "metadata",
                "content_blocks": [],
                "plugins": None,
                "crewai_files": None,
                "text_content": "",
                "context_text": f"[Video URL failed: {url} — {_sanitize_error(e)}]",
                "required_modality": None,
                "file_name": url,
                "file_mime": "",
            }

    # --- Webpage ---
    if url_type == "webpage":
        try:
            response = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
            response.raise_for_status()
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(response.text, "html.parser")
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()
            text = soup.get_text(separator="\n", strip=True)
            text = text[:MAX_TEXT_LENGTH] + ("[...truncated]" if len(text) > MAX_TEXT_LENGTH else "")
            return {
                "type": "text",
                "content_blocks": [],
                "plugins": None,
                "crewai_files": None,
                "text_content": text,
                "context_text": f"[Webpage content from {url}]",
                "required_modality": None,
                "file_name": url,
                "file_mime": "",
            }
        except Exception as e:
            print(f"[ATTACHMENT] Webpage scrape failed: {_sanitize_error(e)}", flush=True)
            return {
                "type": "metadata",
                "content_blocks": [],
                "plugins": None,
                "crewai_files": None,
                "text_content": "",
                "context_text": f"[Webpage URL failed: {url} — {_sanitize_error(e)}]",
                "required_modality": None,
                "file_name": url,
                "file_mime": "",
            }

    return {
        "type": "metadata",
        "content_blocks": [],
        "plugins": None,
        "crewai_files": None,
        "text_content": "",
        "context_text": f"[Unknown URL type: {url}]",
        "required_modality": None,
        "file_name": url,
        "file_mime": "",
    }


# ============================================================
# Message Router
# ============================================================
def _parse_json_command(text: str) -> dict | None:
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict) and parsed.get("type") == "action":
            return {
                "name": parsed.get("name"),
                "payload": parsed.get("payload", {}),
            }
    except (json.JSONDecodeError, ValueError):
        return None
    return None


@cl.on_message
async def on_message(message: cl.Message):
    state = cl.user_session.get("state") or STATE_IDLE
    user_input = message.content
    registry = cl.user_session.get("registry") or AgentRegistry()
    messenger = get_messenger()

    # Parse mode prefix: __mode:chat__ or __mode:plan__
    input_mode = "plan"
    mode_match = re.match(r'^__mode:(chat|plan)__\n', user_input)
    if mode_match:
        input_mode = mode_match.group(1)
        user_input = user_input[mode_match.end():]

    # Extract attachment data from message
    attachment = None
    attachment_match = re.search(r'\[ATTACHMENT\|([^\|]+)\|([^\|]+)\|([^\]]+)\]', user_input)
    if attachment_match:
        file_url, file_name, file_mime = attachment_match.groups()
        attachment = {"file_url": file_url, "file_name": file_name, "file_mime": file_mime}
        # Remove attachment marker from user_input before processing
        user_input = re.sub(r'\n\n\[ATTACHMENT\|[^\]]+\]', '', user_input).strip()
        # Store attachment URL in session for later use
        cl.user_session.set("last_attachment_url", file_url)
        cl.user_session.set("last_attachment_name", file_name)
        cl.user_session.set("last_attachment_mime", file_mime)
        print(f"[ATTACHMENT] {file_name} → {file_url}", flush=True)

    # Handle JSON action commands from custom frontend
    command = _parse_json_command(user_input)
    if command:
        action_name = command.get("name")
        payload = command.get("payload") or {}
        if action_name == "accept_plan":
            await on_action_accept(cl.Action(name="accept_plan", payload=payload))
        elif action_name == "reject_plan":
            await on_action_reject(cl.Action(name="reject_plan", payload=payload))
        elif action_name == "cancel_plan":
            await on_action_cancel(cl.Action(name="cancel_plan", payload=payload))
        elif action_name == "confirm_create_agent":
            await on_action_create_agent(cl.Action(name="confirm_create_agent", payload=payload))
        elif action_name == "add_agent_form":
            await on_action_add_agent_form(cl.Action(name="add_agent_form", payload=payload))
        elif action_name == "edit_agent_form":
            await on_action_edit_agent_form(cl.Action(name="edit_agent_form", payload=payload))
        elif action_name == "delete_agent":
            await on_action_delete_agent(cl.Action(name="delete_agent", payload=payload))
        elif action_name == "assign_task_form":
            await on_action_assign_task_form(cl.Action(name="assign_task_form", payload=payload))
        elif action_name == "delete_task":
            task_id = payload.get("task_id", "")
            if messenger and task_id:
                await messenger.delete_task(task_id)
        elif action_name == "approve_image":
            approval_id = payload.get("approval_id", "")
            print(f"[APPROVE] approval_id={approval_id}", flush=True)
            pending = cl.user_session.get(f"pending_media_{approval_id}")
            if pending and messenger:
                prompt = pending["prompt"]
                task_id = pending.get("task_id")
                media_type = pending.get("media_type", "image")
                duration = pending.get("duration", 5)
                print(f"[APPROVE] Generating {media_type}, model={cl.user_session.get('ai_image_model')}, prompt={prompt[:60]}...", flush=True)
                try:
                    llm_mgr = LLMManager()
                    gen_mgr = MediaGenerationManager(llm_mgr)
                    gen_mgr.set_models(
                        image_model=cl.user_session.get("ai_image_model") or "",
                        video_model=cl.user_session.get("ai_video_model") or "",
                    )
                    if media_type == "video":
                        result = await asyncio.to_thread(gen_mgr.generate_video, prompt, duration=duration)
                    else:
                        result = await asyncio.to_thread(gen_mgr.generate_image, prompt)
                    _debug(f"[DEBUG-APPROVE] Result: {result[:100]}", flush=True)
                    if result.startswith("Error:"):
                        # Keep pending_media for retry, send error card
                        error_msg = result.replace("Error: ", "").strip()
                        await messenger.reply_image_approval(
                            prompt, approval_id, pending.get("agent_name", ""),
                            media_type=media_type, duration=duration,
                            model=pending.get("model", ""),
                            approval_status="error",
                            image_error=error_msg,
                        )
                    else:
                        print(f"[APPROVE] Image generated successfully: {result[:80]}", flush=True)
                        await messenger.reply_image_result(result, prompt, approval_id, task_id=task_id, media_type=media_type, agent_name=pending.get('agent_name', ''))
                        print(f"[APPROVE] reply_image_result sent", flush=True)
                        if task_id:
                            await messenger.update_task_image(task_id, result, prompt, media_type=media_type)
                        # Keep pending_media for regenerate after success
                except Exception as e:
                    _debug(f"[DEBUG-APPROVE] Error: {_sanitize_error(e)}", flush=True)
                    # Keep pending_media for retry
                    await messenger.reply(f"⚠️ เกิดข้อผิดพลาดในการสร้างสื่อ: {_sanitize_error(e)}")
            elif messenger:
                _debug(f"[DEBUG-APPROVE] No pending media found for {approval_id}", flush=True)
                await messenger.reply(f"⚠️ ไม่พบคำขอสร้างสื่อ (ID: {approval_id}) อาจหมดอายุแล้ว กรุณาลองใหม่")
        elif action_name == "retry_image":
            approval_id = payload.get("approval_id", "")
            _debug(f"[DEBUG-RETRY] approval_id={approval_id}", flush=True)
            pending = cl.user_session.get(f"pending_media_{approval_id}")
            if pending and messenger:
                prompt = pending["prompt"]
                task_id = pending.get("task_id")
                media_type = pending.get("media_type", "image")
                duration = pending.get("duration", 5)
                _debug(f"[DEBUG-RETRY] Retrying {media_type} for prompt: {prompt[:80]}...", flush=True)
                try:
                    llm_mgr = LLMManager()
                    gen_mgr = MediaGenerationManager(llm_mgr)
                    gen_mgr.set_models(
                        image_model=cl.user_session.get("ai_image_model") or "",
                        video_model=cl.user_session.get("ai_video_model") or "",
                    )
                    if media_type == "video":
                        result = await asyncio.to_thread(gen_mgr.generate_video, prompt, duration=duration)
                    else:
                        result = await asyncio.to_thread(gen_mgr.generate_image, prompt)
                    _debug(f"[DEBUG-RETRY] Result: {result[:100]}", flush=True)
                    if result.startswith("Error:"):
                        await messenger.reply(f"⚠️ {result}")
                    else:
                        await messenger.reply_image_result(result, prompt, approval_id, task_id=task_id, media_type=media_type, agent_name=pending.get('agent_name', ''))
                        if task_id:
                            await messenger.update_task_image(task_id, result, prompt, media_type=media_type)
                        # Keep pending_media for regenerate after success
                except Exception as e:
                    _debug(f"[DEBUG-RETRY] Error: {_sanitize_error(e)}", flush=True)
                    await messenger.reply(f"⚠️ เกิดข้อผิดพลาดในการสร้างสื่อ: {_sanitize_error(e)}")
            elif messenger:
                await messenger.reply(f"⚠️ ไม่พบคำขอสร้างสื่อ (ID: {approval_id}) อาจหมดอายุแล้ว")
        elif action_name == "edit_image_prompt":
            approval_id = payload.get("approval_id", "")
            new_prompt = payload.get("new_prompt", "").strip()
            if new_prompt and messenger:
                pending = cl.user_session.get(f"pending_media_{approval_id}") or {}
                pending["prompt"] = new_prompt
                cl.user_session.set(f"pending_media_{approval_id}", pending)
                media_type = pending.get("media_type", "image")
                duration = pending.get("duration", 0)
                await messenger.reply_image_approval(
                    new_prompt, approval_id, pending.get("agent_name", ""),
                    media_type=media_type, duration=duration
                )
            elif messenger:
                await messenger.reply(f"⚠️ prompt ว่าง กรุณาใส่ prompt แล้วลองใหม่")
        elif action_name == "reject_image":
            approval_id = payload.get("approval_id", "")
            if messenger:
                await messenger.reply(f"❌ ยกเลิกการสร้างสื่อ (ID: {approval_id})")
                cl.user_session.set(f"pending_media_{approval_id}", None)
        elif action_name == "new_chat":
            session = messenger.chat_store.create_session("New Chat")
            messenger.current_session_id = session["id"]
            await messenger.reply_chat_sessions()
            await messenger.reply_chat_history(session["id"])
        elif action_name == "switch_chat":
            session_id = payload.get("session_id", "")
            session = messenger.chat_store.get_session(session_id)
            if session:
                messenger.current_session_id = session_id
                await messenger.reply_chat_sessions()
                await messenger.reply_chat_history(session_id)
        elif action_name == "rename_chat":
            session_id = payload.get("session_id", "")
            title = payload.get("title", "Untitled")
            messenger.chat_store.rename_session(session_id, title)
            await messenger.reply_chat_sessions()
        elif action_name == "delete_chat":
            session_id = payload.get("session_id", "")
            messenger.chat_store.delete_session(session_id)
            # Switch to another session or create new
            remaining = messenger.chat_store.list_sessions()
            if remaining:
                messenger.current_session_id = remaining[0]["id"]
            else:
                new_s = messenger.chat_store.create_session("New Chat")
                messenger.current_session_id = new_s["id"]
            await messenger.reply_chat_sessions()
            await messenger.reply_chat_history(messenger.current_session_id)
        elif action_name == "save_canvas":
            session_id = payload.get("session_id", "")
            canvas_state = payload.get("canvas_state", {})
            if session_id and canvas_state:
                messenger.chat_store.save_canvas_state(session_id, canvas_state)
        elif action_name == "fetch_model_catalog":
            llm_mgr = LLMManager()
            if llm_mgr.tier in ("paid", "free"):
                catalog = ModelCatalog(llm_mgr.api_key, llm_mgr.base_url)
                loop = asyncio.get_event_loop()
                recommended = await loop.run_in_executor(None, catalog.get_recommended)
                selected = cl.user_session.get("selected_model") or ""
                if messenger:
                    await messenger.reply_model_catalog(recommended, [], selected)
            else:
                if messenger:
                    await messenger.reply("⚠️ Model catalog ใช้ได้เฉพาะ OpenRouter tier (paid/free)")
        elif action_name == "fetch_media_catalog":
            media_type = payload.get("media_type", "image")
            llm_mgr = LLMManager()
            if llm_mgr.tier in ("paid", "free"):
                discovery = ModelDiscoveryService(base_url=llm_mgr.base_url, api_key=llm_mgr.api_key)
                loop = asyncio.get_event_loop()
                # Map media_type to discovery category
                discovery_map = {
                    "image": "output:image",
                    "video": "output:video",
                    "search": "output:search",
                    "tts": "output:audio",
                    "stt": "input:audio_input",
                    "vision": "input:vision",
                }
                target = discovery_map.get(media_type, f"output:{media_type}")
                filtered = []
                if target.startswith("output:"):
                    cat = target.split(":")[1]
                    all_groups = await loop.run_in_executor(None, discovery.discover_all)
                    filtered = all_groups.get(cat, [])
                elif target.startswith("input:"):
                    cat = target.split(":")[1]
                    all_groups = await loop.run_in_executor(None, discovery.discover_input_capabilities)
                    filtered = all_groups.get(cat, [])
                # Build catalog entries in the same format as ModelCatalog
                entries = []
                for m in filtered:
                    mid = m["id"]
                    pricing = m.get("pricing", {})
                    entries.append({
                        "id": mid,
                        "name": m.get("name", mid),
                        "context_length": m.get("context_length", "?"),
                        "prompt_price": pricing.get("prompt", "?"),
                        "completion_price": pricing.get("completion", "?"),
                        "categories": [media_type],
                        "is_free": ":free" in mid,
                        "input_modalities": m.get("input_modalities", []),
                        "output_modalities": m.get("output_modalities", []),
                    })
                # Group by category (media_type) so ModelPicker can render correctly
                grouped = {media_type: entries}
                if messenger:
                    await messenger.reply_model_catalog(grouped, [], "", catalog_type="media")
            else:
                if messenger:
                    await messenger.reply("⚠️ Media catalog ใช้ได้เฉพาะ OpenRouter tier (paid/free)")
        elif action_name == "search_models":
            query = payload.get("query", "")
            llm_mgr = LLMManager()
            if llm_mgr.tier in ("paid", "free") and query:
                catalog = ModelCatalog(llm_mgr.api_key, llm_mgr.base_url)
                loop = asyncio.get_event_loop()
                results = await loop.run_in_executor(None, catalog.search, query)
                recommended = await loop.run_in_executor(None, catalog.get_recommended)
                selected = cl.user_session.get("selected_model") or ""
                if messenger:
                    await messenger.reply_model_catalog(recommended, results, selected)
        elif action_name == "set_selected_model":
            model_id = payload.get("model_id", "")
            cl.user_session.set("selected_model", model_id)
            # No chat reply — UI shows selection in the model button
        elif action_name == "change_agent_model":
            agent_name = payload.get("agent_name", "")
            model_id = payload.get("model_id", "")
            # Update pre_assigned_models in session
            pre_assigned = cl.user_session.get("pre_assigned_models") or {"manager": "", "workers": {}}
            if agent_name and model_id:
                if agent_name in pre_assigned.get("workers", {}):
                    pre_assigned["workers"][agent_name] = model_id
                elif pre_assigned.get("manager") == agent_name or agent_name.lower() == "manager":
                    pre_assigned["manager"] = model_id
                else:
                    pre_assigned.setdefault("workers", {})[agent_name] = model_id
                cl.user_session.set("pre_assigned_models", pre_assigned)
                _debug(f"[DEBUG-MODEL-CHANGE] {agent_name} → {model_id}", flush=True)
        elif action_name == "change_media_model":
            media_type = payload.get("media_type", "")
            model_id = payload.get("model_id", "")
            if media_type and model_id is not None:
                session_key = f"ai_{media_type.replace('Model', '_model')}"
                cl.user_session.set(session_key, model_id)
                print(f"[DEBUG-MEDIA-CHANGE] {media_type} → {model_id}", flush=True)
        elif action_name == "stop_generation":
            cl.user_session.set("cancel_generation", True)
            print(f"[STOP] User requested to stop generation", flush=True)
            if messenger:
                await messenger.reply("⏹️ หยุดการทำงานแล้ว")
        elif action_name == "upload_file":
            file_data = payload.get("file_data", "")
            file_name = payload.get("file_name", "upload")
            file_mime = payload.get("file_mime", "application/octet-stream")
            if file_data and file_name:
                import base64
                attach_dir = os.path.join(os.path.dirname(__file__), "public", "attachments")
                os.makedirs(attach_dir, exist_ok=True)
                # Sanitize filename
                safe_name = re.sub(r'[^a-zA-Z0-9._-]', '_', file_name)
                unique_name = f"{uuid.uuid4().hex[:8]}_{safe_name}"
                filepath = os.path.join(attach_dir, unique_name)
                try:
                    file_bytes = base64.b64decode(file_data.split(",")[-1] if "," in file_data else file_data)
                    with open(filepath, "wb") as f:
                        f.write(file_bytes)
                    file_url = f"/public/attachments/{unique_name}"
                    if messenger:
                        payload_resp = chat_reply(ChatReplyFileResult(
                            fileUrl=file_url,
                            fileName=file_name,
                            fileMime=file_mime,
                        ))
                        await cl.Message(content=json.dumps(payload_resp, ensure_ascii=False)).send()
                    print(f"[UPLOAD] Saved {file_name} → {file_url}", flush=True)
                except Exception as e:
                    if messenger:
                        await messenger.reply(f"❌ Upload failed: {_sanitize_error(e)}")
        return

    # Persist user message to chat session
    if messenger:
        messenger.persist_message({"role": "user", "content": user_input, "messageType": "text"})

    # Process attachment via unified pipeline
    attachment_ctx = None
    last_attach_url = cl.user_session.get("last_attachment_url") or ""
    last_attach_name = cl.user_session.get("last_attachment_name") or ""
    last_attach_mime = cl.user_session.get("last_attachment_mime") or ""
    if last_attach_url:
        attachment_ctx = await process_attachment(last_attach_url, last_attach_name, last_attach_mime)
        print(f"[ATTACHMENT] Processed {last_attach_name} → type={attachment_ctx['type']}", flush=True)

    # Detect and process URLs in user message
    urls_in_message = re.findall(URL_REGEX, user_input)
    url_contexts = []
    for found_url in urls_in_message:
        if last_attach_url and found_url == last_attach_url:
            continue
        url_ctx = await process_url(found_url)
        url_contexts.append(url_ctx)
        print(f"[URL] Processed {found_url} → type={url_ctx['type']}", flush=True)

    # Merge attachment + URL contexts
    all_contexts = []
    if attachment_ctx:
        all_contexts.append(attachment_ctx)
    all_contexts.extend(url_contexts)

    # Build unified context for AI
    multimodal_blocks = []
    multimodal_plugins = None
    text_context_parts = []
    crewai_files = {}
    context_texts = []
    required_modalities = []

    for ctx in all_contexts:
        if ctx["type"] == "multimodal":
            multimodal_blocks.extend(ctx["content_blocks"])
            if ctx.get("plugins"):
                multimodal_plugins = ctx["plugins"]
        elif ctx["type"] == "text":
            text_context_parts.append(ctx["text_content"])
        if ctx.get("crewai_files"):
            crewai_files.update(ctx["crewai_files"])
        context_texts.append(ctx["context_text"])
        if ctx.get("required_modality"):
            required_modalities.append(ctx["required_modality"])

    # Model compatibility check
    selected_model = cl.user_session.get("selected_model") or ""
    if selected_model and required_modalities and llm_manager_tier_check():
        for modality in required_modalities:
            if not check_model_modality_support(selected_model, modality):
                if messenger:
                    await messenger.reply(
                        f"⚠️ Model '{selected_model}' อาจไม่รองรับ {modality} input. "
                        f"แนะนำให้เปลี่ยน model เป็นที่รองรับ multimodal (เช่น Google Gemini)"
                    )
                break

    # Build user_input_for_ai
    context_summary = " ".join(context_texts)
    if text_context_parts:
        user_input_for_ai = f"{user_input}\n\n[Attached content:\n" + "\n---\n".join(text_context_parts) + "\n]"
    elif context_summary:
        user_input_for_ai = f"{user_input}\n\n{context_summary}"
    else:
        user_input_for_ai = user_input

    # Store for CrewAI worker agents
    cl.user_session.set("attachment_context", {
        "type": "multimodal" if multimodal_blocks else "text" if text_context_parts else "metadata",
        "content_blocks": multimodal_blocks,
        "plugins": multimodal_plugins,
        "text_content": "\n---\n".join(text_context_parts),
        "context_text": context_summary,
        "crewai_files": crewai_files or None,
    } if all_contexts else None)
    cl.user_session.set("attachment_crewai_files", crewai_files or None)

    # Gather conversation history for context
    conversation_history = cl.user_session.get("conversation_history") or []

    # Chat mode: bypass assess_and_plan, answer directly with LLM
    if input_mode == "chat" and state == STATE_IDLE:
        if messenger:
            await messenger.notify("💬 กำลังตอบ...")
        try:
            llm_manager = LLMManager()
            selected_model = cl.user_session.get("selected_model") or ""
            if selected_model and llm_manager.tier in ("paid", "free"):
                llm_manager.set_selected_model(selected_model)
            secretary = CentralSecretary(llm_manager)
            if multimodal_blocks:
                response = await secretary.chat_response_multimodal(
                    user_input, multimodal_blocks, multimodal_plugins
                )
            elif text_context_parts:
                response = await secretary.chat_response(user_input_for_ai)
            else:
                response = await secretary.chat_response(user_input_for_ai)
            if messenger:
                await messenger.reply(response)
            conversation_history.append({"role": "user", "content": user_input, "attachment_context_text": context_summary})
            conversation_history.append({"role": "assistant", "content": response})
            cl.user_session.set("conversation_history", conversation_history)
        except Exception as e:
            if messenger:
                await messenger.reply(f"⚠️ เกิดข้อผิดพลาด: {_sanitize_error(e)}")
        finally:
            cl.user_session.set("last_attachment_url", None)
            cl.user_session.set("last_attachment_name", None)
            cl.user_session.set("last_attachment_mime", None)
            cl.user_session.set("attachment_context", None)
            cl.user_session.set("attachment_crewai_files", None)
        return

    if state == STATE_IDLE:
        cl.user_session.set("state", STATE_ASSESSING)
        if messenger:
            selected_model = cl.user_session.get("selected_model") or ""
            if selected_model:
                await messenger.notify(f"🧠 กำลังประเมินและวางแผน... (Model: {selected_model})")
                print(f"[PLAN] User selected model: {selected_model}", flush=True)
            else:
                # Adaptive — show which model the system will actually use
                llm_mgr_tmp = LLMManager()
                resolved = llm_mgr_tmp.get_selected_model_name()
                await messenger.notify(f"🧠 กำลังประเมินและวางแผน... (Adaptive → {resolved})")
                print(f"[PLAN] Adaptive mode → resolved to {resolved}", flush=True)

        try:
            llm_manager = LLMManager()
            selected_model = cl.user_session.get("selected_model") or ""
            if selected_model and llm_manager.tier in ("paid", "free"):
                llm_manager.set_selected_model(selected_model)
            tool_registry = ToolRegistry()
            secretary = CentralSecretary(llm_manager)

            # Build model table for unified call
            model_table = "none"
            valid_model_ids = set()
            if llm_manager.tier in ("paid", "free"):
                model_selector = ModelSelector(
                    base_url=llm_manager.base_url,
                    api_key=llm_manager.api_key,
                    rotator=None,
                    default_model=llm_manager._default_model,
                )
                loop = asyncio.get_event_loop()
                candidates = await loop.run_in_executor(None, model_selector._get_candidates)
                valid_model_ids = {c["id"] for c in candidates}
                model_table = model_selector._build_candidate_table(candidates)
                discovery = ModelDiscoveryService(base_url=llm_manager.base_url, api_key=llm_manager.api_key)
                media_catalog = await loop.run_in_executor(None, discovery.get_catalog_summary)
            else:
                media_catalog = "none"

            thinking_id = f"thinking-{int(time.time())}"
            async def _stream_cb(chunk: str):
                if messenger:
                    await messenger.reply_thinking(chunk, thinking_id)

            result = await secretary.assess_and_plan(
                user_input_for_ai, conversation_history,
                model_table=model_table,
                valid_model_ids=valid_model_ids,
                media_catalog=media_catalog,
                stream_callback=_stream_cb,
            ) if not multimodal_blocks else await secretary.assess_and_plan_multimodal(
                user_input, multimodal_blocks, multimodal_plugins,
                conversation_history=conversation_history,
                model_table=model_table,
                valid_model_ids=valid_model_ids,
                media_catalog=media_catalog,
                stream_callback=_stream_cb,
            )
            if messenger:
                await messenger.reply_thinking_done(thinking_id)
            if os.getenv("DEBUG_MODE", "false").lower() == "true":
                print(f"[DEBUG-UNIFIED] user_input='{user_input[:50]}' action={result.get('action')}", flush=True)
                if result.get("action") == "plan":
                    print(f"[DEBUG-PLAN] raw agents JSON: {json.dumps(result.get('agents', []), ensure_ascii=False)[:500]}", flush=True)

            action = result.get("action", "chat")

            if action == "chat":
                cl.user_session.set("state", STATE_IDLE)
                response = result.get("message") or await secretary.chat_response(user_input)
                if messenger:
                    await messenger.reply(response)
                conversation_history.append({"role": "user", "content": user_input})
                conversation_history.append({"role": "assistant", "content": response})
                cl.user_session.set("conversation_history", conversation_history)
                return

            if action == "info":
                cl.user_session.set("state", STATE_IDLE)
                agents = registry.list_agents()
                tasks = messenger.state.get("tasks", []) if messenger else []
                if messenger:
                    await messenger.notify("ℹ️ กำลังดึงข้อมูลระบบ...")
                response = await secretary.info_response(user_input, agents, tasks, STATE_IDLE)
                if messenger:
                    await messenger.reply(response)
                conversation_history.append({"role": "user", "content": user_input})
                conversation_history.append({"role": "assistant", "content": response})
                cl.user_session.set("conversation_history", conversation_history)
                return

            if action == "ask":
                cl.user_session.set("state", STATE_GATHERING_REQUIREMENTS)
                cl.user_session.set("current_input", user_input)
                questions = result.get("questions", [])
                questions_text = "\n".join(f"• {q}" for q in questions)
                if messenger:
                    await messenger.reply(f"ก่อนที่จะเริ่มทำงาน ผมต้องการข้อมูลเพิ่มเติม:\n\n{questions_text}")
                conversation_history.append({"role": "user", "content": user_input})
                conversation_history.append({"role": "assistant", "content": f"Questions: {questions_text}"})
                cl.user_session.set("conversation_history", conversation_history)
                return

            if action == "plan":
                # Unified call already produced agent specs + model assignments
                cl.user_session.set("state", STATE_PLANNING)
                cl.user_session.set("current_input", user_input)
                conversation_history.append({"role": "user", "content": user_input})
                cl.user_session.set("conversation_history", conversation_history)

                agent_specs = result.get("agents", [])
                model_assignment = result.get("model_assignment", {"manager": "", "workers": {}})
                _debug(f"[DEBUG-PLAN] agent_specs count={len(agent_specs)}, models={model_assignment}", flush=True)
                if agent_specs:
                    for s in agent_specs:
                        _debug(f"[DEBUG-PLAN] agent: {s.get('name', '?')} role={s.get('role', '?')} tools={s.get('tools', [])} model={s.get('model', '?')} depends_on={s.get('depends_on', [])}", flush=True)
                if not agent_specs:
                    raise ValueError("AI ไม่สามารถวิเคราะห์แผนงานได้")

                # Store model_assignment for run_async to skip assign_models
                cl.user_session.set("pre_assigned_models", model_assignment)
                cl.user_session.set("ai_image_model", result.get("image_model", ""))
                cl.user_session.set("ai_video_model", result.get("video_model", ""))
                cl.user_session.set("ai_search_model", result.get("search_model", ""))
                cl.user_session.set("ai_tts_model", result.get("tts_model", ""))
                cl.user_session.set("ai_stt_model", result.get("stt_model", ""))
                cl.user_session.set("ai_vision_model", result.get("vision_model", ""))
                print(f"[DEBUG-MODELS] image_model={result.get('image_model', '')} video_model={result.get('video_model', '')} search_model={result.get('search_model', '')} tts_model={result.get('tts_model', '')} stt_model={result.get('stt_model', '')} vision_model={result.get('vision_model', '')}", flush=True)

                # Check Registry for existing agents that match each spec
                resolved_specs = []
                agents_for_plan = []
                has_existing = False
                for spec in agent_specs:
                    resource = secretary.check_resources(spec, registry)
                    if resource["type"] == "existing":
                        existing_agent = resource["agent"]
                        merged = registry.to_spec(existing_agent)
                        merged["task_description"] = spec.get("task_description", user_input)
                        merged["depends_on"] = spec.get("depends_on", [])
                        merged["registry_id"] = existing_agent.get("id")
                        resolved_specs.append(merged)
                        agents_for_plan.append({
                            "id": existing_agent.get("id"),
                            "name": existing_agent.get("name", "Unnamed"),
                            "role": existing_agent.get("role", ""),
                            "goal": existing_agent.get("goal", ""),
                            "persona": existing_agent.get("persona", ""),
                            "tools": existing_agent.get("tools", []),
                            "status": existing_agent.get("status", "Idle"),
                            "is_existing": True,
                            "model": model_assignment.get("workers", {}).get(existing_agent.get("name", ""), model_assignment.get("manager", "")),
                        })
                        has_existing = True
                    else:
                        resolved_specs.append(spec)
                        agents_for_plan.append({
                            "id": None,
                            "name": spec.get("name", "Unnamed"),
                            "role": spec.get("role", ""),
                            "goal": spec.get("goal", ""),
                            "persona": spec.get("backstory", ""),
                            "tools": spec.get("tools", []),
                            "depends_on": spec.get("depends_on", []),
                            "status": "Idle",
                            "is_existing": False,
                            "model": model_assignment.get("workers", {}).get(spec.get("name", ""), model_assignment.get("manager", "")),
                        })

                cl.user_session.set("current_agent_specs", resolved_specs)
                cl.user_session.set("state", STATE_AWAITING_APPROVAL)

                print(f"[DEBUG-PLAN] Sending plan to frontend: {len(agents_for_plan)} agents, plan_type={'existing' if has_existing else 'new'}", flush=True)

                if messenger:
                    await messenger.update_agents(registry)
                    plan_type = "existing" if has_existing else "new"
                    await messenger.set_multi_agent_plan(
                        agents_for_plan,
                        user_input,
                        plan_type=plan_type,
                    )
                    await messenger.reply_plan(agents_for_plan, user_input, plan_type=plan_type,
                        image_model=result.get('image_model', ''),
                        video_model=result.get('video_model', ''),
                        search_model=result.get('search_model', ''),
                        tts_model=result.get('tts_model', ''),
                        stt_model=result.get('stt_model', ''),
                        vision_model=result.get('vision_model', ''),
                        has_image_tool=result.get('image_model', '') != '' or result.get('has_image_tool', False),
                        has_video_tool=result.get('video_model', '') != '' or result.get('has_video_tool', False),
                        has_search_tool=result.get('search_model', '') != '' or result.get('has_search_tool', False),
                        has_tts_tool=result.get('tts_model', '') != '' or result.get('has_tts_tool', False),
                        has_stt_tool=result.get('stt_model', '') != '' or result.get('has_stt_tool', False),
                        has_vision_tool=result.get('vision_model', '') != '' or result.get('has_vision_tool', False))
                    print("[DEBUG-PLAN] reply_plan sent", flush=True)

        except Exception as e:
            cl.user_session.set("state", STATE_IDLE)
            if _is_rate_limit_error(e):
                llm_mgr = LLMManager()
                llm_mgr.report_rate_limit()
                if messenger:
                    await messenger.reply("⚠️ ติดลิมิต AI ฝรั่ง สลับไป Local LLM ชั่วคราว (60 วินาที) กรุณาลองใหม่")
            elif messenger:
                await messenger.reply(f"❌ เกิดข้อผิดพลาด: {str(e)}")

    elif state == STATE_GATHERING_REQUIREMENTS:
        # User is answering clarifying questions — re-assess with new info
        cl.user_session.set("state", STATE_ASSESSING)
        conversation_history.append({"role": "user", "content": user_input})
        cl.user_session.set("conversation_history", conversation_history)

        try:
            llm_manager = LLMManager()
            selected_model = cl.user_session.get("selected_model") or ""
            if selected_model and llm_manager.tier in ("paid", "free"):
                llm_manager.set_selected_model(selected_model)
            tool_registry = ToolRegistry()
            secretary = CentralSecretary(llm_manager)

            # Build model table for unified call
            model_table = "none"
            valid_model_ids = set()
            if llm_manager.tier in ("paid", "free"):
                model_selector = ModelSelector(
                    base_url=llm_manager.base_url,
                    api_key=llm_manager.api_key,
                    rotator=None,
                    default_model=llm_manager._default_model,
                )
                loop = asyncio.get_event_loop()
                candidates = await loop.run_in_executor(None, model_selector._get_candidates)
                valid_model_ids = {c["id"] for c in candidates}
                model_table = model_selector._build_candidate_table(candidates)
                discovery = ModelDiscoveryService(base_url=llm_manager.base_url, api_key=llm_manager.api_key)
                media_catalog = await loop.run_in_executor(None, discovery.get_catalog_summary)
            else:
                media_catalog = "none"

            thinking_id = f"thinking-reassess-{int(time.time())}"
            async def _stream_cb_reassess(chunk: str):
                if messenger:
                    await messenger.reply_thinking(chunk, thinking_id)

            result = await secretary.assess_and_plan(
                user_input, conversation_history,
                model_table=model_table,
                valid_model_ids=valid_model_ids,
                media_catalog=media_catalog,
                stream_callback=_stream_cb_reassess,
            )
            if messenger:
                await messenger.reply_thinking_done(thinking_id)
            print(f"[DEBUG-REASSESS] action={result.get('action')}", flush=True)

            action = result.get("action", "chat")

            if action == "ask":
                # Still need more info
                cl.user_session.set("state", STATE_GATHERING_REQUIREMENTS)
                questions = result.get("questions", [])
                questions_text = "\n".join(f"• {q}" for q in questions)
                if messenger:
                    await messenger.reply(f"ขอบคุณครับ ยังต้องการข้อมูลเพิ่มอีกนิด:\n\n{questions_text}")
                conversation_history.append({"role": "assistant", "content": f"Questions: {questions_text}"})
                cl.user_session.set("conversation_history", conversation_history)
                return

            if action == "plan":
                # Now we have enough info — unified call already produced agent specs
                cl.user_session.set("state", STATE_PLANNING)
                original_input = cl.user_session.get("current_input") or user_input
                combined_input = original_input + " " + user_input

                agent_specs = result.get("agents", [])
                model_assignment = result.get("model_assignment", {"manager": "", "workers": {}})
                if not agent_specs:
                    raise ValueError("AI ไม่สามารถวิเคราะห์แผนงานได้")

                cl.user_session.set("pre_assigned_models", model_assignment)
                cl.user_session.set("ai_image_model", result.get("image_model", ""))
                cl.user_session.set("ai_video_model", result.get("video_model", ""))
                cl.user_session.set("ai_search_model", result.get("search_model", ""))
                cl.user_session.set("ai_tts_model", result.get("tts_model", ""))
                cl.user_session.set("ai_stt_model", result.get("stt_model", ""))
                cl.user_session.set("ai_vision_model", result.get("vision_model", ""))

                # Check Registry for existing agents
                resolved_specs = []
                agents_for_plan = []
                has_existing = False
                for spec in agent_specs:
                    resource = secretary.check_resources(spec, registry)
                    if resource["type"] == "existing":
                        existing_agent = resource["agent"]
                        merged = registry.to_spec(existing_agent)
                        merged["task_description"] = spec.get("task_description", combined_input)
                        merged["depends_on"] = spec.get("depends_on", [])
                        merged["registry_id"] = existing_agent.get("id")
                        resolved_specs.append(merged)
                        agents_for_plan.append({
                            "id": existing_agent.get("id"),
                            "name": existing_agent.get("name", "Unnamed"),
                            "role": existing_agent.get("role", ""),
                            "goal": existing_agent.get("goal", ""),
                            "persona": existing_agent.get("persona", ""),
                            "tools": existing_agent.get("tools", []),
                            "status": existing_agent.get("status", "Idle"),
                            "is_existing": True,
                            "model": model_assignment.get("workers", {}).get(existing_agent.get("name", ""), model_assignment.get("manager", "")),
                        })
                        has_existing = True
                    else:
                        resolved_specs.append(spec)
                        agents_for_plan.append({
                            "id": None,
                            "name": spec.get("name", "Unnamed"),
                            "role": spec.get("role", ""),
                            "goal": spec.get("goal", ""),
                            "persona": spec.get("backstory", ""),
                            "tools": spec.get("tools", []),
                            "depends_on": spec.get("depends_on", []),
                            "status": "Idle",
                            "is_existing": False,
                            "model": model_assignment.get("workers", {}).get(spec.get("name", ""), model_assignment.get("manager", "")),
                        })

                cl.user_session.set("current_input", combined_input)
                cl.user_session.set("current_agent_specs", resolved_specs)
                cl.user_session.set("state", STATE_AWAITING_APPROVAL)

                if messenger:
                    await messenger.update_agents(registry)
                    plan_type = "existing" if has_existing else "new"
                    await messenger.set_multi_agent_plan(
                        agents_for_plan,
                        combined_input,
                        plan_type=plan_type,
                    )
                    await messenger.reply_plan(agents_for_plan, combined_input, plan_type=plan_type,
                        image_model=result.get('image_model', ''),
                        video_model=result.get('video_model', ''),
                        search_model=result.get('search_model', ''),
                        tts_model=result.get('tts_model', ''),
                        stt_model=result.get('stt_model', ''),
                        vision_model=result.get('vision_model', ''),
                        has_image_tool=result.get('image_model', '') != '' or result.get('has_image_tool', False),
                        has_video_tool=result.get('video_model', '') != '' or result.get('has_video_tool', False),
                        has_search_tool=result.get('search_model', '') != '' or result.get('has_search_tool', False),
                        has_tts_tool=result.get('tts_model', '') != '' or result.get('has_tts_tool', False),
                        has_stt_tool=result.get('stt_model', '') != '' or result.get('has_stt_tool', False),
                        has_vision_tool=result.get('vision_model', '') != '' or result.get('has_vision_tool', False))
                return

            # Fallback: treat as chat
            cl.user_session.set("state", STATE_IDLE)
            response = result.get("message") or await secretary.chat_response(user_input)
            if messenger:
                await messenger.reply(response)
            conversation_history.append({"role": "assistant", "content": response})
            cl.user_session.set("conversation_history", conversation_history)

        except Exception as e:
            cl.user_session.set("state", STATE_IDLE)
            if _is_rate_limit_error(e):
                llm_mgr = LLMManager()
                llm_mgr.report_rate_limit()
                if messenger:
                    await messenger.notify("⚠️ ติดลิมิต AI ฝรั่ง สลับไป Local LLM ชั่วคราว (60 วินาที) กรุณาลองใหม่")
            elif messenger:
                await messenger.notify(f"❌ เกิดข้อผิดพลาด: {str(e)}")

    elif state in (STATE_CREATING_AGENT, STATE_AWAITING_APPROVAL, STATE_EXECUTING, STATE_PLANNING, STATE_ASSESSING):
        if messenger:
            await messenger.notify(f"⏳ รอสถานะปัจจุบัน: {state}")


# ============================================================
# Pre-execution Model Validation
# ============================================================
ROUTING_MODELS = {"openrouter/auto", "openrouter/free"}


def validate_plan_models(agent_specs: list[dict]) -> list[str]:
    """Validate that no agent uses a routing model for execution.
    Returns a list of error messages. Empty list = all valid.
    """
    errors = []
    for spec in agent_specs:
        name = spec.get("name", "Agent")
        model = spec.get("model", "")
        tools = spec.get("tools", [])
        if model in ROUTING_MODELS:
            if tools:
                errors.append(
                    f"❌ {name} ใช้ '{model}' ซึ่งเป็น routing model ที่ไม่รองรับ tool use "
                    f"(tools: {', '.join(tools)}) กรุณาเลือกโมเดลเฉพาะทาง"
                )
            else:
                errors.append(
                    f"❌ {name} ใช้ '{model}' ซึ่งเป็น routing model ที่ไม่เสถียร "
                    f"กรุณาเลือกโมเดลเฉพาะทาง"
                )
    return errors


# ============================================================
# Action Handlers
# ============================================================
@cl.action_callback("confirm_create_agent")
async def on_action_create_agent(action: cl.Action):
    state = cl.user_session.get("state")
    messenger = get_messenger()
    if state != STATE_CREATING_AGENT:
        if messenger:
            await messenger.notify(f"⚠️ ไม่สามารถดำเนินการได้ สถานะปัจจุบัน: {state}")
        return

    agent_specs = cl.user_session.get("current_agent_specs")
    user_input = cl.user_session.get("current_input")
    registry = cl.user_session.get("registry") or AgentRegistry()

    primary_spec = agent_specs[0] if agent_specs else None
    if not primary_spec:
        if messenger:
            await messenger.notify("❌ ไม่พบข้อมูล Agent ที่ต้องสร้าง")
        cl.user_session.set("state", STATE_IDLE)
        return

    new_agent = registry.add_agent(primary_spec)
    merged_spec = registry.to_spec(new_agent)
    merged_spec["task_description"] = primary_spec.get("task_description", user_input)
    merged_spec["registry_id"] = new_agent.get("id")

    cl.user_session.set("current_agent_specs", [merged_spec])
    cl.user_session.set("current_registry_id", new_agent.get("id"))
    cl.user_session.set("state", STATE_AWAITING_APPROVAL)

    if messenger:
        await messenger.update_agents(registry)
        await messenger.set_plan(
            messenger._agents_for_ui([new_agent])[0],
            merged_spec.get("task_description", user_input),
            plan_type="new",
        )
        await messenger.notify(f"✅ สร้าง Agent {new_agent['name']} และบันทึกลงทะเบียนแล้ว")


@cl.action_callback("accept_plan")
async def on_action_accept(action: cl.Action):
    state = cl.user_session.get("state")
    messenger = get_messenger()
    if state not in (STATE_AWAITING_APPROVAL, STATE_CREATING_AGENT):
        if messenger:
            await messenger.notify(f"⚠️ ไม่สามารถดำเนินการได้ สถานะปัจจุบัน: {state}")
        return

    user_input = cl.user_session.get("current_input")
    agent_specs = cl.user_session.get("current_agent_specs")
    registry = cl.user_session.get("registry") or AgentRegistry()

    if not agent_specs:
        if messenger:
            await messenger.notify("❌ ไม่พบข้อมูล Agent สำหรับประมวลผล")
        cl.user_session.set("state", STATE_IDLE)
        return

    # Resolve models from pre_assigned_models into specs for validation
    pre_assigned = cl.user_session.get("pre_assigned_models")
    for spec in agent_specs:
        name = spec.get("name", "")
        if pre_assigned and name and pre_assigned.get("workers", {}).get(name):
            spec["model"] = pre_assigned["workers"][name]

    # Pre-execution validation: reject routing models
    validation_errors = validate_plan_models(agent_specs)
    if validation_errors:
        if messenger:
            await messenger.reply_plan_validation_error(validation_errors)
        cl.user_session.set("state", STATE_AWAITING_APPROVAL)
        return

    # Register all new agents in the plan
    registered_specs = []
    for spec in agent_specs:
        if spec.get("registry_id"):
            # Already registered
            registered_specs.append(spec)
        else:
            new_agent = registry.add_agent(spec)
            merged = registry.to_spec(new_agent)
            merged["task_description"] = spec.get("task_description", user_input)
            merged["depends_on"] = spec.get("depends_on", [])
            merged["registry_id"] = new_agent.get("id")
            registered_specs.append(merged)

    cl.user_session.set("current_agent_specs", registered_specs)
    if messenger:
        messenger.update_plan_status("approved")
        await messenger.update_agents(registry)
        await messenger.clear_plan()
        await messenger.notify("🚀 กำลังเตรียม agents และเริ่มประมวลผล...")

    await execute_multi_agent_task(user_input, registered_specs, registry)

    cl.user_session.set("attachment_context", None)
    cl.user_session.set("attachment_crewai_files", None)
    cl.user_session.set("last_attachment_url", None)
    cl.user_session.set("last_attachment_name", None)
    cl.user_session.set("last_attachment_mime", None)


@cl.action_callback("reject_plan")
async def on_action_reject(action: cl.Action):
    state = cl.user_session.get("state")
    messenger = get_messenger()
    if state not in (STATE_AWAITING_APPROVAL, STATE_CREATING_AGENT):
        if messenger:
            await messenger.notify(f"⚠️ ไม่สามารถดำเนินการได้ สถานะปัจจุบัน: {state}")
        return

    cl.user_session.set("state", STATE_IDLE)
    cl.user_session.set("current_agent_specs", None)
    cl.user_session.set("current_input", None)
    cl.user_session.set("current_registry_id", None)
    if messenger:
        messenger.update_plan_status("rejected")
        await messenger.clear_plan()
        await messenger.reply("🔄 แผนงานถูกปฏิเสธ กรุณาพิมพ์คำสั่งใหม่หรืออธิบายเพิ่มเติม")


@cl.action_callback("cancel_plan")
async def on_action_cancel(action: cl.Action):
    state = cl.user_session.get("state")
    messenger = get_messenger()
    if state not in (STATE_AWAITING_APPROVAL, STATE_CREATING_AGENT):
        if messenger:
            await messenger.notify(f"⚠️ ไม่สามารถดำเนินการได้ สถานะปัจจุบัน: {state}")
        return

    cl.user_session.set("state", STATE_IDLE)
    cl.user_session.set("current_agent_specs", None)
    cl.user_session.set("current_input", None)
    cl.user_session.set("current_registry_id", None)
    if messenger:
        await messenger.clear_plan()
        await messenger.notify("❌ แผนงานถูกยกเลิกแล้ว")


@cl.action_callback("add_agent_form")
async def on_action_add_agent_form(action: cl.Action):
    registry = cl.user_session.get("registry") or AgentRegistry()
    messenger = get_messenger()
    payload = action.payload or {}

    spec = {
        "name": payload.get("name", "Unnamed"),
        "role": payload.get("role", ""),
        "goal": payload.get("goal", ""),
        "backstory": payload.get("persona", ""),
        "persona": payload.get("persona", ""),
        "tools": [t.strip() for t in payload.get("tools", "").split(",") if t.strip()],
        "model": payload.get("model", ""),
    }

    try:
        new_agent = registry.add_agent(spec)
        if messenger:
            await messenger.update_agents(registry)
            await messenger.notify(f"✅ สร้าง Agent {new_agent['name']} สำเร็จ")
    except Exception as e:
        if messenger:
            await messenger.notify(f"❌ สร้าง Agent ไม่สำเร็จ: {str(e)}")


@cl.action_callback("edit_agent_form")
async def on_action_edit_agent_form(action: cl.Action):
    registry = cl.user_session.get("registry") or AgentRegistry()
    messenger = get_messenger()
    payload = action.payload or {}
    agent_id = payload.get("agent_id")

    if not agent_id:
        if messenger:
            await messenger.notify("❌ ไม่พบ Agent ID")
        return

    agent = registry.get_by_id(agent_id)
    if not agent:
        if messenger:
            await messenger.notify("❌ ไม่พบ Agent ที่ต้องการแก้ไข")
        return

    spec = {
        "name": payload.get("name", agent.get("name")),
        "role": payload.get("role", agent.get("role")),
        "goal": payload.get("goal", agent.get("goal")),
        "persona": payload.get("persona", agent.get("persona")),
        "tools": [t.strip() for t in payload.get("tools", "").split(",") if t.strip()],
        "model": payload.get("model", agent.get("model", "")),
    }

    try:
        registry.update_agent(agent_id, spec)
        if messenger:
            await messenger.update_agents(registry)
            await messenger.notify(f"✅ แก้ไข Agent {agent_id} สำเร็จ")
    except Exception as e:
        if messenger:
            await messenger.notify(f"❌ แก้ไข Agent ไม่สำเร็จ: {str(e)}")


@cl.action_callback("delete_agent")
async def on_action_delete_agent(action: cl.Action):
    registry = cl.user_session.get("registry") or AgentRegistry()
    messenger = get_messenger()
    agent_id = action.payload.get("agent_id")
    agent = registry.get_by_id(agent_id)
    if not agent:
        if messenger:
            await messenger.notify("❌ ไม่พบ Agent ที่ต้องการลบ")
        return

    registry.delete_agent(agent_id)
    if messenger:
        await messenger.update_agents(registry)


@cl.action_callback("assign_task_form")
async def on_action_assign_task_form(action: cl.Action):
    registry = cl.user_session.get("registry") or AgentRegistry()
    messenger = get_messenger()
    payload = action.payload or {}
    agent_id = payload.get("agent_id")
    task_description = payload.get("task", "").strip()

    agent = registry.get_by_id(agent_id)
    if not agent:
        if messenger:
            await messenger.notify("❌ ไม่พบ Agent ที่ต้องการมอบหมายงาน")
        return

    if agent.get("status") != "Idle":
        if messenger:
            await messenger.notify(f"⚠️ Agent {agent.get('name')} กำลัง Busy")
        return

    if not task_description:
        if messenger:
            await messenger.notify("❌ กรุณาระบุรายละเอียดงาน")
        return

    agent_spec = registry.to_spec(agent)
    agent_spec["task_description"] = task_description
    agent_spec["registry_id"] = agent_id

    if messenger:
        await messenger.notify(f"🚀 มอบหมายงานให้ {agent.get('name')}")

    await execute_task_with_agent(task_description, agent_spec, agent_id, registry)


# ============================================================
# HTTP Upload endpoint + static file serving for attachments
# ============================================================

# Import Chainlit app reference
from chainlit import server as _cl_server

_ATTACH_DIR = os.path.join(os.path.dirname(__file__), "public", "attachments")
os.makedirs(_ATTACH_DIR, exist_ok=True)


@_cl_server.app.post("/api/upload")
async def _http_upload_file(request: Request):
    """Receive a file upload via HTTP and return a public URL.

    Accepts multipart/form-data with a `file` field, or JSON with
    base64 `file_data`, `file_name` and `file_mime`.
    """
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
        _cl_server.app.mount(_mount_point, StaticFiles(directory=_public_dir), name="public")

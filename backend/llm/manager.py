"""LLMManager — modular LLM management with auto-fallback."""

import asyncio
import os
import re
import time
import requests
from crewai import LLM
from backend.utils import _sanitize_error
from backend.ai_usage_hub import log_ai_usage
from backend.llm.rotator import FreeModelRotator

class LLMManager:
    """จัดการ LLM แบบ Modular รองรับ Local LLM และ OpenRouter พร้อม auto-fallback

    Tier priority (auto-detected from API key):
    1. paid   — API key มีเครดิต → ใช้ openrouter/free (OpenRouter เลือก free model อัตโนมัติ)
    2. free   — API key เป็น free tier → ใช้ openrouter/free (OpenRouter เลือก free model อัตโนมัติ)
    3. local  — ไม่มี key หรือทั้งสองขั้นต้นล้มเหลว → ใช้ Ollama
    4. error  — ใช้ไม่ได้เลย
    """

    _multimodal_cache: dict[str, bool] = {}

    def __init__(self):
        self.provider = os.getenv("LLM_PROVIDER", "local").lower()
        self.model = os.getenv("LLM_MODEL", "qwen2.5:7b")
        self.base_url = os.getenv("LLM_BASE_URL", "http://localhost:11434")
        self.api_key = os.getenv("LLM_API_KEY", "ollama")
        self.temperature = float(os.getenv("LLM_TEMPERATURE", "0.7"))

        # Fallback config (local Ollama) — dev-only opt-in
        self.local_fallback_enabled = os.getenv("LOCAL_LLM_FALLBACK", "true").lower() == "true"
        self.fallback_provider = os.getenv("LLM_FALLBACK_PROVIDER", "local").lower()
        self.fallback_model = os.getenv("LLM_FALLBACK_MODEL", "qwen2.5:7b")
        self.fallback_base_url = os.getenv("LLM_FALLBACK_BASE_URL", "http://localhost:11434")
        self.fallback_api_key = os.getenv("LLM_FALLBACK_API_KEY", "ollama")

        # Rate limit tracking
        self._fallback_until = 0.0
        self._fallback_cooldown = 60.0
        self._max_attempts = int(os.getenv("LLM_MAX_ATTEMPTS", "4"))

        # Default routing model — free by default, no credit check
        self._default_model = "openrouter/free" if self._is_openrouter() else ""

        # User-selected model (session-level override)
        self._selected_model: str = ""

        # Free model rotator (used only when model is openrouter/free)
        self._rotator: FreeModelRotator | None = None

    @classmethod
    def populate_multimodal_cache(cls, catalog: list[dict]):
        """Populate multimodal cache from OpenRouter model catalog.

        Called once at startup (on_chat_start) to avoid per-LLM API calls.
        """
        for m in catalog:
            mid = m.get("id", "")
            if not mid:
                continue
            modalities = m.get("architecture", {}).get("input_modalities", [])
            cls._multimodal_cache[mid] = "image" in modalities

    @classmethod
    def _check_multimodal(cls, model_id: str) -> bool | None:
        """Check if a model supports multimodal input from cache.

        Returns True/False if cached, None if not in cache.
        """
        return cls._multimodal_cache.get(model_id)

    def _get_rotator(self) -> FreeModelRotator:
        """Get or create the FreeModelRotator instance."""
        if self._rotator is None:
            self._rotator = FreeModelRotator(
                api_key=self.api_key,
                base_url=self.base_url,
                temperature=self.temperature,
            )
        return self._rotator

    def _is_free_routing(self) -> bool:
        """Check if current model is openrouter/free (the only case where rotator applies)."""
        model_id = self._selected_model or self._default_model
        return model_id == "openrouter/free"

    def _is_openrouter(self) -> bool:
        """Check if OpenRouter API is configured."""
        return self.provider == "openrouter" and self.api_key and self.api_key != "ollama"

    def set_selected_model(self, model_id: str):
        """Set user-selected model to override default routing."""
        self._selected_model = model_id
        print(f"[LLMManager] User selected model: {model_id}")

    def _is_in_cooldown(self) -> bool:
        import time
        return time.time() < self._fallback_until

    def _trigger_cooldown(self, reason: str = ""):
        import time
        self._fallback_until = time.time() + self._fallback_cooldown
        print(f"[LLMManager] Cooldown triggered ({reason or 'unknown'}). Falling back to {self.fallback_provider} for {self._fallback_cooldown}s")

    async def call_async(self, prompt: str, caller: str = "call_with_fallback") -> str:
        """Call LLM in a thread pool so the event loop stays free for websocket pings."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: self.call_with_fallback(prompt, caller=caller))

    async def call_with_image_async(self, prompt: str, image_data_url: str, caller: str = "call_with_image") -> str:
        """Call LLM with text + image (multimodal/vision) in a thread pool."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._call_with_image, prompt, image_data_url, caller)

    def _call_with_image(self, prompt: str, image_data_url: str, caller: str = "call_with_image") -> str:
        """Call OpenRouter with multimodal content (text + image_url).
        Tries the current model first; if empty response, falls back to rotator's vision models.
        """
        from openai import OpenAI
        model_id = self._selected_model or self._default_model
        if not model_id:
            raise RuntimeError("No model available for vision call")
        client = OpenAI(base_url=self.base_url, api_key=self.api_key, max_retries=0, timeout=120)
        started_at = time.time()
        try:
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
            usage = response.usage.model_dump() if response.usage and hasattr(response.usage, "model_dump") else (response.usage or {})
            log_ai_usage({
                "provider": "openrouter",
                "model": model_id,
                "operation": "chat.completions",
                "source": caller,
                "status": "success",
                "prompt_tokens": usage.get("prompt_tokens"),
                "completion_tokens": usage.get("completion_tokens"),
                "cost_usd": usage.get("cost"),
                "duration_ms": int((time.time() - started_at) * 1000),
                "raw_usage": usage,
                "request_id": getattr(response, "id", None),
                "metadata": {"analysis_type": "chat"},
            })
            content = response.choices[0].message.content or ""
            if content.strip():
                return content
            print(f"[LLMManager] Vision call returned empty with {model_id} — trying rotator", flush=True)
        except Exception as e:
            err_msg = _sanitize_error(e)
            log_ai_usage({
                "provider": "openrouter",
                "model": model_id,
                "operation": "chat.completions",
                "source": caller,
                "status": "error",
                "error_message": err_msg,
                "duration_ms": int((time.time() - started_at) * 1000),
                "metadata": {"analysis_type": "chat"},
            })
            print(f"[LLMManager] Vision call failed with {model_id}: {err_msg} — trying rotator", flush=True)
        # Fallback to rotator's vision-capable free models
        if self._is_free_routing():
            return self._get_rotator().call_with_image(prompt, image_data_url, caller=caller)
        raise RuntimeError(f"Vision call failed with {model_id} and no rotator fallback available")

    async def call_with_multimodal_async(self, prompt: str, content_blocks: list[dict], plugins: list = None, caller: str = "call_with_multimodal") -> str:
        """Call LLM with text + multimodal content blocks (image, PDF, audio, video)."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._call_with_multimodal, prompt, content_blocks, plugins, caller)

    def _call_with_multimodal(self, prompt: str, content_blocks: list[dict], plugins: list = None, caller: str = "call_with_multimodal") -> str:
        """Call OpenRouter with multimodal content blocks.
        Tries the current model first; if empty response, falls back to rotator's vision models.
        """
        from openai import OpenAI
        model_id = self._selected_model or self._default_model
        if not model_id:
            raise RuntimeError("No model available for multimodal call")
        client = OpenAI(base_url=self.base_url, api_key=self.api_key, max_retries=0, timeout=120)
        messages = [{"role": "user", "content": [{"type": "text", "text": prompt}] + content_blocks}]
        kwargs = {"model": model_id, "messages": messages, "temperature": self.temperature}
        if plugins:
            kwargs["extra_body"] = {"plugins": plugins}
        started_at = time.time()
        try:
            response = client.chat.completions.create(**kwargs)
            usage = response.usage.model_dump() if response.usage and hasattr(response.usage, "model_dump") else (response.usage or {})
            log_ai_usage({
                "provider": "openrouter",
                "model": model_id,
                "operation": "chat.completions",
                "source": caller,
                "status": "success",
                "prompt_tokens": usage.get("prompt_tokens"),
                "completion_tokens": usage.get("completion_tokens"),
                "cost_usd": usage.get("cost"),
                "duration_ms": int((time.time() - started_at) * 1000),
                "raw_usage": usage,
                "request_id": getattr(response, "id", None),
                "metadata": {"analysis_type": "chat"},
            })
            content = response.choices[0].message.content or ""
            if content.strip():
                return content
            print(f"[LLMManager] Multimodal call returned empty with {model_id} — trying rotator", flush=True)
        except Exception as e:
            err_msg = _sanitize_error(e)
            log_ai_usage({
                "provider": "openrouter",
                "model": model_id,
                "operation": "chat.completions",
                "source": caller,
                "status": "error",
                "error_message": err_msg,
                "duration_ms": int((time.time() - started_at) * 1000),
                "metadata": {"analysis_type": "chat"},
            })
            print(f"[LLMManager] Multimodal call failed with {model_id}: {err_msg} — trying rotator", flush=True)
        # Fallback to rotator's vision-capable free models
        if self._is_free_routing():
            return self._get_rotator().call_with_multimodal(prompt, content_blocks, plugins, caller=caller)
        raise RuntimeError(f"Multimodal call failed with {model_id} and no rotator fallback available")

    def call_with_multimodal_streaming(self, prompt: str, content_blocks: list[dict], plugins: list = None, caller: str = "call_with_multimodal_streaming"):
        """Streaming version of multimodal call — yields text chunks.
        Tries the current model first; if it fails, falls back to rotator's vision models.
        """
        from openai import OpenAI
        model_id = self._selected_model or self._default_model
        if not model_id:
            raise RuntimeError("No model available for multimodal streaming")
        client = OpenAI(base_url=self.base_url, api_key=self.api_key, max_retries=0, timeout=120)
        messages = [{"role": "user", "content": [{"type": "text", "text": prompt}] + content_blocks}]
        kwargs = {"model": model_id, "messages": messages, "temperature": self.temperature, "stream": True, "stream_options": {"include_usage": True}}
        if plugins:
            kwargs["extra_body"] = {"plugins": plugins}
        started_at = time.time()
        try:
            stream = client.chat.completions.create(**kwargs)
            usage_data = None
            has_content = False
            _stream_id = None
            for chunk in stream:
                if chunk.usage:
                    usage_data = chunk.usage
                if hasattr(chunk, "id") and chunk.id:
                    _stream_id = chunk.id
                if chunk.choices and chunk.choices[0].delta.content:
                    has_content = True
                    yield chunk.choices[0].delta.content
            if usage_data:
                usage = usage_data.model_dump() if hasattr(usage_data, "model_dump") else (usage_data or {})
                log_ai_usage({
                    "provider": "openrouter",
                    "model": model_id,
                    "operation": "chat.completions",
                    "source": caller,
                    "status": "success",
                    "prompt_tokens": usage.get("prompt_tokens"),
                    "completion_tokens": usage.get("completion_tokens"),
                    "cost_usd": usage.get("cost"),
                    "duration_ms": int((time.time() - started_at) * 1000),
                    "raw_usage": usage,
                    "request_id": _stream_id if "_stream_id" in locals() else None,
                    "metadata": {"analysis_type": "chat"},
                })
            else:
                log_ai_usage({
                    "provider": "openrouter",
                    "model": model_id,
                    "operation": "chat.completions",
                    "source": caller,
                    "status": "success",
                    "duration_ms": int((time.time() - started_at) * 1000),
                    "request_id": _stream_id if "_stream_id" in locals() else None,
                    "metadata": {"analysis_type": "chat", "note": "stream omitted usage"},
                })
            if has_content:
                return
            print(f"[LLMManager] Multimodal stream returned empty with {model_id} — trying rotator", flush=True)
        except Exception as e:
            err_msg = _sanitize_error(e)
            log_ai_usage({
                "provider": "openrouter",
                "model": model_id,
                "operation": "chat.completions",
                "source": caller,
                "status": "error",
                "error_message": err_msg,
                "duration_ms": int((time.time() - started_at) * 1000),
                "metadata": {"analysis_type": "chat"},
            })
            print(f"[LLMManager] Multimodal stream failed with {model_id}: {err_msg} — trying rotator", flush=True)
        # Fallback to rotator's vision-capable free models (non-streaming)
        if self._is_free_routing():
            result = self._get_rotator().call_with_multimodal(prompt, content_blocks, plugins, caller=caller)
            if result:
                yield result
            return
        raise RuntimeError(f"Multimodal streaming failed with {model_id} and no rotator fallback available")

    def call_streaming(self, prompt: str, caller: str = "call_streaming"):
        """Streaming version of call_with_fallback — yields text chunks."""
        if not self._is_in_cooldown():
            if self._is_openrouter():
                model_id = self._selected_model or self._default_model
                is_free = ":free" in model_id or model_id == "openrouter/free"
                if not is_free:
                    print(f"[LLMManager] WARNING: call_streaming using PAID model: {model_id!r}", flush=True)
                # Try the selected/default model first
                started_at = time.time()
                try:
                    from openai import OpenAI
                    client = OpenAI(base_url=self.base_url, api_key=self.api_key, max_retries=0, timeout=120)
                    stream = client.chat.completions.create(
                        model=model_id,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=self.temperature,
                        stream=True,
                        stream_options={"include_usage": True},
                    )
                    got_content = False
                    usage_data = None
                    _stream_id = None
                    for chunk in stream:
                        if chunk.usage:
                            usage_data = chunk.usage
                        if hasattr(chunk, "id") and chunk.id:
                            _stream_id = chunk.id
                        if chunk.choices and chunk.choices[0].delta.content:
                            got_content = True
                            yield chunk.choices[0].delta.content
                    if usage_data:
                        usage = usage_data.model_dump() if hasattr(usage_data, "model_dump") else (usage_data or {})
                        log_ai_usage({
                            "provider": "openrouter",
                            "model": model_id,
                            "operation": "chat.completions",
                            "source": caller,
                            "status": "success",
                            "prompt_tokens": usage.get("prompt_tokens"),
                            "completion_tokens": usage.get("completion_tokens"),
                            "cost_usd": usage.get("cost"),
                            "duration_ms": int((time.time() - started_at) * 1000),
                            "raw_usage": usage,
                            "request_id": _stream_id if "_stream_id" in locals() else None,
                            "metadata": {"analysis_type": "chat"},
                        })
                    else:
                        # Stream omitted usage (some models/providers do this).
                        # Still log the call so it shows on the dashboard —
                        # token/cost fields will be absent, which the Hub accepts.
                        log_ai_usage({
                            "provider": "openrouter",
                            "model": model_id,
                            "operation": "chat.completions",
                            "source": caller,
                            "status": "success",
                            "duration_ms": int((time.time() - started_at) * 1000),
                            "request_id": _stream_id if "_stream_id" in locals() else None,
                            "metadata": {"analysis_type": "chat", "note": "stream omitted usage"},
                        })
                    if got_content:
                        return
                    # Empty stream — return error, don't retry with rotator (saves credits)
                    print(f"[LLMManager] Empty stream from {model_id}", flush=True)
                    raise RuntimeError(f"Model '{model_id}' returned empty response")
                except Exception as e:
                    err_msg = _sanitize_error(e)
                    log_ai_usage({
                        "provider": "openrouter",
                        "model": model_id,
                        "operation": "chat.completions",
                        "source": caller,
                        "status": "error",
                        "error_message": err_msg,
                        "duration_ms": int((time.time() - started_at) * 1000),
                        "metadata": {"analysis_type": "chat"},
                    })
                    print(f"[LLMManager] Primary LLM streaming error: {err_msg}")
                    # Only try free model rotator if using openrouter/free
                    if self._is_free_routing():
                        print(f"[LLMManager] openrouter/free stream failed — trying free model rotator", flush=True)
                        try:
                            yield from self._get_rotator().call_streaming(prompt, caller=caller)
                            return
                        except Exception as rotator_err:
                            print(f"[LLMManager] Free model rotator stream also failed: {_sanitize_error(rotator_err)}", flush=True)
                    self._trigger_cooldown(err_msg)

        # Local fallback streaming
        if not self.local_fallback_enabled:
            raise RuntimeError("All OpenRouter tiers exhausted. Local fallback is disabled.")
        print(f"[LLMManager] Using local fallback streaming: {self.fallback_provider}/{self.fallback_model}")
        from openai import OpenAI
        client = OpenAI(base_url=self.fallback_base_url, api_key=self.fallback_api_key, max_retries=0)
        started_at = time.time()
        try:
            stream = client.chat.completions.create(
                model=self.fallback_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.temperature,
                stream=True,
            )
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
            log_ai_usage({
                "provider": "other",  # local fallback — spec normalizes unknown to "other"
                "model": self.fallback_model,
                "operation": "chat.completions",
                "source": caller,
                "status": "success",
                "cost_usd": 0,  # local fallback (Ollama) is free
                "duration_ms": int((time.time() - started_at) * 1000),
                "metadata": {"analysis_type": "chat"},
            })
        except Exception as e:
            log_ai_usage({
                "provider": "other",  # local fallback — spec normalizes unknown to "other"
                "model": self.fallback_model,
                "operation": "chat.completions",
                "source": caller,
                "status": "error",
                "error_message": _sanitize_error(e),
                "duration_ms": int((time.time() - started_at) * 1000),
                "metadata": {"analysis_type": "chat"},
            })
            raise

    def _build_llm(self, provider: str, model: str, base_url: str, api_key: str) -> LLM:
        # Check if there are attachment plugins (e.g. PDF file-parser) to pass to OpenRouter
        additional_params = {}
        try:
            import chainlit as cl
            plugins = cl.user_session.get("attachment_plugins")
            if plugins and provider == "openrouter":
                # litellm passes extra_body to the underlying HTTP request
                # 'plugins' is OpenRouter-specific, not part of OpenAI API spec
                additional_params["extra_body"] = {"plugins": plugins}
        except Exception:
            pass

        # OpenRouter server tools (web_search, web_fetch) were previously injected
        # here via extra_body["tools"], but LiteLLM treats extra_body.tools as the
        # complete tools array — this silently overwrote all CrewAI tools
        # (generate_document, generate_image, etc.) so agents only saw web_search
        # and web_fetch. Removed to let CrewAI tools pass through correctly.
        # Web access is available via the `search_web` and `browse_web` CrewAI tools.
        if provider == "openrouter":
            # litellm uses "openrouter/<model_id>" format and strips the first "openrouter/" prefix
            # before sending <model_id> to OpenRouter's API.
            # Routing models (openrouter/free) → openrouter/openrouter/free → litellm sends "openrouter/free"
            # Regular models (meta-llama/...) → openrouter/meta-llama/... → litellm sends "meta-llama/..."
            full_model = f"openrouter/{model}"
            is_free = ":free" in model or model == "openrouter/free"
            if not is_free:
                print(f"[LLMManager] WARNING: _build_llm using PAID model: {model!r} (full={full_model!r})", flush=True)
            print(f"[LLMManager] _build_llm: provider={provider}, model={model!r}, full_model={full_model!r}", flush=True)
            # Don't send max_tokens — let OpenRouter use the model's default output limit.
            # Previously sent max_completion_tokens (e.g., 128K) which caused 402 credit errors
            # when user credits couldn't cover that many output tokens.
            # Empty stream responses were caused by openrouter/free routing to non-working models,
            # NOT by missing max_tokens — that's handled by rotator fallback.
            llm = LLM(
                model=full_model,
                base_url=base_url,
                api_key=api_key,
                temperature=self.temperature,
                max_retries=0,
                stream=True,
                additional_params=additional_params,
            )
            # Override supports_multimodal using OpenRouter catalog cache
            # CrewAI's OpenAICompatibleCompletion uses a hardcoded prefix list that
            # doesn't match models like 'openai/gpt-5.6-luna' (starts with 'openai/')
            cached = self._check_multimodal(model)
            if cached is not None:
                llm.supports_multimodal = lambda: cached
            return llm
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
        if self._selected_model and self._is_openrouter():
            print(f"[LLMManager] Using user-selected model: {self._selected_model}")
            return self._build_llm(self.provider, self._selected_model, self.base_url, self.api_key)
        if self._default_model and self._is_openrouter():
            print(f"[LLMManager] Using routing model: {self._default_model}")
            return self._build_llm(self.provider, self._default_model, self.base_url, self.api_key)
        # local or fallback
        return self._build_llm(self.fallback_provider, self.fallback_model, self.fallback_base_url, self.fallback_api_key)

    def get_selected_model_name(self) -> str:
        """Return the model name that get_llm() would actually use."""
        if self._selected_model and self._is_openrouter():
            return self._selected_model
        if self._default_model and self._is_openrouter():
            return self._default_model
        return self.fallback_model or "local"

    def build_llm_for_model(self, model_id: str) -> LLM:
        """Build LLM for a specific model id (used by ModelSelector assignments)."""
        if not model_id:
            return self.get_llm()
        if self._is_in_cooldown():
            # Only apply cooldown to openrouter/free (the routing model) —
            # free models share rate limits so backing off makes sense.
            # For specific user-selected models (e.g., paid models), don't switch
            # to fallback without user consent — the manager should respect user's choice.
            # If the model fails, error handling in the caller will catch it.
            if model_id == "openrouter/free":
                ranking = self._get_rotator().get_ranking()
                if ranking:
                    best = ranking[0]
                    print(f"[LLMManager] openrouter/free in cooldown — using rotator best: {best}", flush=True)
                    return self._get_rotator().build_crewai_llm(best)
                # No rotator models available — fall through to fallback
                return self._build_llm(
                    self.fallback_provider,
                    self.fallback_model,
                    self.fallback_base_url,
                    self.fallback_api_key,
                )
            # Non-free model: ignore cooldown, respect user's selection
            print(f"[LLMManager] Cooldown active but using user-selected model: {model_id}", flush=True)
        is_free = ":free" in model_id or model_id == "openrouter/free"
        if not is_free:
            print(f"[LLMManager] WARNING: build_llm_for_model using PAID model: {model_id!r}", flush=True)
        return self._build_llm(self.provider, model_id, self.base_url, self.api_key)

    def call_with_fallback(self, prompt: str, caller: str = "call_with_fallback") -> str:
        """Call LLM with automatic fallback: routing model → free rotator → local → error."""
        if not self._is_in_cooldown():
            if self._is_openrouter():
                started_at = time.time()
                try:
                    model_id = self._selected_model or self._default_model
                    from openai import OpenAI
                    client = OpenAI(base_url=self.base_url, api_key=self.api_key, max_retries=0, timeout=120)
                    response = client.chat.completions.create(
                        model=model_id,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=self.temperature,
                    )
                    usage = response.usage.model_dump() if response.usage and hasattr(response.usage, "model_dump") else (response.usage or {})
                    log_ai_usage({
                        "provider": "openrouter",
                        "model": model_id,
                        "operation": "chat.completions",
                        "source": caller,
                        "status": "success",
                        "prompt_tokens": usage.get("prompt_tokens"),
                        "completion_tokens": usage.get("completion_tokens"),
                        "cost_usd": usage.get("cost"),
                        "duration_ms": int((time.time() - started_at) * 1000),
                        "raw_usage": usage,
                        "request_id": getattr(response, "id", None),
                        "metadata": {"analysis_type": "chat"},
                    })
                    return response.choices[0].message.content or ""
                except Exception as e:
                    err_msg = _sanitize_error(e)
                    model_id = self._selected_model or self._default_model
                    log_ai_usage({
                        "provider": "openrouter",
                        "model": model_id,
                        "operation": "chat.completions",
                        "source": caller,
                        "status": "error",
                        "error_message": err_msg,
                        "duration_ms": int((time.time() - started_at) * 1000),
                        "metadata": {"analysis_type": "chat"},
                    })
                    print(f"[LLMManager] Primary LLM error: {err_msg}")
                    # Only try free model rotator if using openrouter/free
                    if self._is_free_routing():
                        print(f"[LLMManager] openrouter/free failed — trying free model rotator", flush=True)
                        try:
                            return self._get_rotator().call(prompt, caller=caller)
                        except Exception as rotator_err:
                            print(f"[LLMManager] Free model rotator also failed: {_sanitize_error(rotator_err)}", flush=True)
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
        started_at = time.time()
        try:
            result = llm.call(prompt)
            log_ai_usage({
                "provider": "other",  # local fallback — spec normalizes unknown to "other"
                "model": self.fallback_model,
                "operation": "chat.completions",
                "source": caller,
                "status": "success",
                "cost_usd": 0,  # local fallback (Ollama) is free
                "duration_ms": int((time.time() - started_at) * 1000),
                "metadata": {"analysis_type": "chat"},
            })
            return result
        except Exception as e:
            log_ai_usage({
                "provider": "other",  # local fallback — spec normalizes unknown to "other"
                "model": self.fallback_model,
                "operation": "chat.completions",
                "source": caller,
                "status": "error",
                "error_message": _sanitize_error(e),
                "duration_ms": int((time.time() - started_at) * 1000),
                "metadata": {"analysis_type": "chat"},
            })
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
    # Include 402 (insufficient credits) so credit exhaustion triggers fallback path
    keywords = ["rate limit", "rate_limit", "429", "too many requests", "quota exceeded", "402", "more credits"]
    return any(kw in msg for kw in keywords)

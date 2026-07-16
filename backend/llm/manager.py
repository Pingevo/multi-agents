"""LLMManager — modular LLM management with auto-fallback."""

import asyncio
import os
import re
import requests
from crewai import LLM
from backend.utils import _sanitize_error
from backend.credit_logger import log_llm_call

class LLMManager:
    """จัดการ LLM แบบ Modular รองรับ Local LLM และ OpenRouter พร้อม auto-fallback

    Tier priority (auto-detected from API key):
    1. paid   — API key มีเครดิต → ใช้ openrouter/free (OpenRouter เลือก free model อัตโนมัติ)
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
        log_llm_call(model_id, response.usage, caller="call_with_image", prompt_preview=prompt)
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
        log_llm_call(model_id, response.usage, caller="call_with_multimodal", prompt_preview=prompt)
        return response.choices[0].message.content or ""

    def call_with_multimodal_streaming(self, prompt: str, content_blocks: list[dict], plugins: list = None):
        """Streaming version of multimodal call — yields text chunks."""
        from openai import OpenAI
        model_id = self._selected_model or self._default_model
        if not model_id:
            raise RuntimeError("No model available for multimodal streaming")
        client = OpenAI(base_url=self.base_url, api_key=self.api_key, max_retries=0, timeout=120)
        messages = [{"role": "user", "content": [{"type": "text", "text": prompt}] + content_blocks}]
        kwargs = {"model": model_id, "messages": messages, "temperature": self.temperature, "stream": True, "stream_options": {"include_usage": True}}
        if plugins:
            kwargs["extra_body"] = {"plugins": plugins}
        stream = client.chat.completions.create(**kwargs)
        usage_data = None
        for chunk in stream:
            if chunk.usage:
                usage_data = chunk.usage
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
        if usage_data:
            log_llm_call(model_id, usage_data, caller="call_with_multimodal_streaming", prompt_preview=prompt)

    def call_streaming(self, prompt: str):
        """Streaming version of call_with_fallback — yields text chunks."""
        if not self._is_in_cooldown():
            if self._is_openrouter():
                model_id = self._selected_model or self._default_model
                is_free = ":free" in model_id or model_id == "openrouter/free"
                if not is_free:
                    print(f"[LLMManager] WARNING: call_streaming using PAID model: {model_id!r}", flush=True)
                # Try the selected/default model first
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
                    for chunk in stream:
                        if chunk.usage:
                            usage_data = chunk.usage
                        if chunk.choices and chunk.choices[0].delta.content:
                            got_content = True
                            yield chunk.choices[0].delta.content
                    if usage_data:
                        log_llm_call(model_id, usage_data, caller="call_streaming", prompt_preview=prompt)
                    if got_content:
                        return
                    # Empty stream — return error, don't retry with rotator (saves credits)
                    print(f"[LLMManager] Empty stream from {model_id}", flush=True)
                    raise RuntimeError(f"Model '{model_id}' returned empty response")
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
            return LLM(
                model=full_model,
                base_url=base_url,
                api_key=api_key,
                temperature=self.temperature,
                max_retries=0,
                stream=True,
                additional_params=additional_params,
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
            return self._build_llm(
                self.fallback_provider,
                self.fallback_model,
                self.fallback_base_url,
                self.fallback_api_key,
            )
        is_free = ":free" in model_id or model_id == "openrouter/free"
        if not is_free:
            print(f"[LLMManager] WARNING: build_llm_for_model using PAID model: {model_id!r}", flush=True)
        return self._build_llm(self.provider, model_id, self.base_url, self.api_key)

    def call_with_fallback(self, prompt: str) -> str:
        """Call LLM with automatic fallback: routing model → local → error."""
        if not self._is_in_cooldown():
            if self._is_openrouter():
                try:
                    model_id = self._selected_model or self._default_model
                    from openai import OpenAI
                    client = OpenAI(base_url=self.base_url, api_key=self.api_key, max_retries=0, timeout=120)
                    response = client.chat.completions.create(
                        model=model_id,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=self.temperature,
                    )
                    log_llm_call(model_id, response.usage, caller="call_with_fallback", prompt_preview=prompt)
                    return response.choices[0].message.content or ""
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

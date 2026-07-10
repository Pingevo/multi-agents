"""MediaGenerationManager — image/video/TTS/STT/vision via OpenRouter."""

import os
import time
import uuid
import requests
from backend.utils import _sanitize_error

class MediaGenerationManager:
    """จัดการ media generation ผ่าน OpenRouter API เท่านั้น
    AI เป็นตัวเลือก model สำหรับ image, video, TTS, STT, และ vision analysis
    """

    PUBLIC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "public", "generated")
    BASE_URL_FOR_CLIENT = "/public/generated"

    def __init__(self, llm_manager: 'LLMManager'):
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

        is_free = ":free" in self.image_model or self.image_model == "openrouter/free"
        if not is_free:
            print(f"[MediaGen] WARNING: using PAID image model: {self.image_model!r}", flush=True)
        else:
            print(f"[MediaGen] Using FREE image model: {self.image_model!r}", flush=True)
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



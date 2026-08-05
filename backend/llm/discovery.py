"""ModelDiscoveryService — discovers models by capabilities from OpenRouter API."""

import requests
from backend.utils import _sanitize_error

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

    def get_supported_parameters(self, model_id: str) -> list[str]:
        """Return supported_parameters for a specific model from the catalog.

        Returns empty list if model not found. Unlike discover_all(), this does
        NOT skip openrouter/ routing models — callers needing raw capability
        data (e.g. SearchAdapter checking tool vs web_search_options support)
        must see every model.
        """
        all_models = self._fetch_all_models()
        for m in all_models:
            if m.get("id") == model_id:
                return m.get("supported_parameters", [])
        return []

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

            # Search models: text output + web_search parameter.
            # OpenRouter exposes search via two parameter names:
            #   - `web_search` (legacy/routing models)
            #   - `web_search_options` (Perplexity native, see ADR-0004)
            # Checking only `web_search` misses all Perplexity models, leaving
            # the Secretary prompt with no "Web search models:" line — so the
            # LLM cannot fill `search_model` and plan approval blocks.
            if ("web_search" in params or "web_search_options" in params) and "text" in output_modalities:
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

    def fetch_video_models(self) -> list[dict]:
        """Fetch video generation models from OpenRouter's dedicated endpoint.

        Video models (Veo, Kling, Sora, Seedance, etc.) are NOT listed in the
        regular /models endpoint with output_modalities=["video"] — they require
        a separate GET /videos/models call. Each model returns pricing_skus
        (price per second) instead of per-token pricing.
        """
        try:
            resp = requests.get(
                f"{self.base_url}/videos/models",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=15,
            )
            if resp.status_code == 200:
                return resp.json().get("data", [])
            print(f"[ModelDiscovery] Video models endpoint returned {resp.status_code}")
            return []
        except Exception as e:
            print(f"[ModelDiscovery] Video models fetch error: {_sanitize_error(e)}")
            return []

    def fetch_image_models(self) -> list[dict]:
        """Fetch image generation models from OpenRouter's dedicated endpoint.

        Image models (GPT Image, FLUX, Recraft, etc.) are listed in a separate
        GET /images/models endpoint with pricing_skus for image generation,
        not per-token text pricing.
        """
        try:
            resp = requests.get(
                f"{self.base_url}/images/models",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=15,
            )
            if resp.status_code == 200:
                return resp.json().get("data", [])
            print(f"[ModelDiscovery] Image models endpoint returned {resp.status_code}")
            return []
        except Exception as e:
            print(f"[ModelDiscovery] Image models fetch error: {_sanitize_error(e)}")
            return []


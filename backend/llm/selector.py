"""ModelSelector — LLM-driven model assignment for agents."""

import re
import requests
from crewai import LLM
from backend.utils import _sanitize_error

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
        """Fetch tool-capable models from rotator (if available) or OpenRouter API."""
        if self._rotator:
            details = self._rotator.get_model_details()
            if details and isinstance(details, list) and len(details) > 0:
                return [
                    {
                        "id": m.get("id", "") if isinstance(m, dict) else str(m),
                        "context_length": m.get("context_length", "?") if isinstance(m, dict) else "?",
                        "pricing": m.get("pricing", {"prompt": "?", "completion": "?"}) if isinstance(m, dict) else {"prompt": "?", "completion": "?"},
                        "description": (m.get("description", "")[:100] if isinstance(m, dict) else ""),
                    }
                    for m in details
                ]
            # Fallback to model IDs only
            model_ids = self._rotator.get_models()
            return [{"id": mid, "context_length": "?", "pricing": {"prompt": "?", "completion": "?"}, "description": ""} for mid in model_ids]
        # No rotator — fetch directly from OpenRouter API
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
            import app as _app
            _LLM = getattr(_app, "LLM", LLM)
            llm = _LLM(
                model=f"openrouter/{smartest}",
                base_url=self.base_url,
                api_key=self.api_key,
                temperature=0.3,
                max_retries=0,
            )
            # Set caller context for CrewAI event bus logging
            try:
                from backend.core.orchestrator import set_llm_call_context, clear_llm_call_context
                set_llm_call_context("model_selector")
            except ImportError:
                pass
            response = llm.call(prompt).strip()
            try:
                clear_llm_call_context()
            except Exception:
                pass
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


"""CapabilityRegistry and CapabilityResolver — capability-to-tool mapping."""

class CapabilityRegistry:
    """Maps capability names to their fulfillment strategy (tool adapter or model trait)."""

    CAPABILITIES = [
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
            "name": "generate_document",
            "description": "Generate downloadable document files (markdown, text, HTML) — reports, plans, scripts, articles",
            "type": "tool",
            "tool_name": "generate_document",
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



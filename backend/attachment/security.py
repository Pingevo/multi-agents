"""Security: model modality checks and SSRF protection."""

import os


def check_model_modality_support(model_id: str, required_modality: str) -> bool:
    """Check if model supports required modality (image, pdf, audio, video)."""
    import app
    ModelDiscoveryService = app.ModelDiscoveryService
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

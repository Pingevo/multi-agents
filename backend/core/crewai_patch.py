"""Monkey-patch CrewAI to recognize openrouter/ models as multimodal."""
import crewai.llm
from crewai.llms.providers.openai.completion import OpenAICompletion
from crewai.llms.base_llm import BaseLLM

def _is_openrouter_multimodal(model: str) -> bool:
    if model.lower().startswith("openrouter/"):
        return True
    return False

# Patch LLM (legacy path)
_original_llm_mm = crewai.llm.LLM.supports_multimodal
def _patched_llm_mm(self) -> bool:
    if _is_openrouter_multimodal(self.model):
        return True
    return _original_llm_mm(self)
crewai.llm.LLM.supports_multimodal = _patched_llm_mm

# Patch OpenAICompletion (native provider path used by openrouter)
_original_oai_mm = OpenAICompletion.supports_multimodal
def _patched_oai_mm(self) -> bool:
    if _is_openrouter_multimodal(self.model):
        return True
    return _original_oai_mm(self)
OpenAICompletion.supports_multimodal = _patched_oai_mm

# Patch BaseLLM (fallback for any other provider)
_original_base_mm = BaseLLM.supports_multimodal
def _patched_base_mm(self) -> bool:
    if hasattr(self, 'model') and _is_openrouter_multimodal(self.model):
        return True
    return _original_base_mm(self)
BaseLLM.supports_multimodal = _patched_base_mm

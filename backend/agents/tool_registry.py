"""ToolRegistry — maps tool names to CrewAI tool functions."""

from backend.tools.media import generate_image, generate_video
from backend.tools.audio import text_to_speech, transcribe_audio, analyze_image
from backend.tools.document import generate_document
from backend.tools.browser import browse_web
from backend.tools.search import search_web
from backend.tools.web import scrape_web
from backend.agents.capability import CapabilityRegistry

class ToolRegistry:
    """Registry สำหรับลงทะเบียนและค้นหาเครื่องมือภายนอก"""

    def __init__(self):
        self._tools = {}
        self.register("generate_image", generate_image)
        self.register("generate_video", generate_video)
        self.register("text_to_speech", text_to_speech)
        self.register("transcribe_audio", transcribe_audio)
        self.register("analyze_image", analyze_image)
        self.register("generate_document", generate_document)
        self.register("browse_web", browse_web)
        self.register("search_web", search_web)
        self.register("scrape_web", scrape_web)
        self._cap_registry = CapabilityRegistry()

    def register(self, name: str, tool):
        self._tools[name] = tool

    def get(self, name: str):
        return self._tools.get(name)

    def list_tools(self) -> list[str]:
        return list(self._tools.keys())

    def list_tool_catalog(self) -> list[dict]:
        return self._cap_registry.list_catalog()



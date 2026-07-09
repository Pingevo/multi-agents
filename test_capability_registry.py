"""Tests for CapabilityRegistry and CapabilityResolver — capability-based tool/model assignment."""

import unittest
from unittest.mock import patch, MagicMock
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class TestCapabilityRegistryList(unittest.TestCase):
    """Seam: list_capabilities() returns all registered capabilities with metadata."""

    def test_returns_non_empty_list(self):
        from app import CapabilityRegistry
        reg = CapabilityRegistry()
        caps = reg.list_capabilities()
        self.assertGreater(len(caps), 0)

    def test_each_capability_has_required_fields(self):
        from app import CapabilityRegistry
        reg = CapabilityRegistry()
        caps = reg.list_capabilities()
        for cap in caps:
            self.assertIn("name", cap)
            self.assertIn("description", cap)
            self.assertIn("type", cap)  # "tool" or "model_trait"


class TestCapabilityRegistryResolve(unittest.TestCase):
    """Seam: resolve(capability_name) returns how to fulfill a capability."""

    def test_resolve_tool_capability_returns_tool_adapter(self):
        from app import CapabilityRegistry
        reg = CapabilityRegistry()
        resolution = reg.resolve("search_web")
        self.assertEqual(resolution["type"], "tool")
        self.assertIn("tool_name", resolution)

    def test_resolve_model_trait_returns_traits(self):
        from app import CapabilityRegistry
        reg = CapabilityRegistry()
        resolution = reg.resolve("reasoning")
        self.assertEqual(resolution["type"], "model_trait")
        self.assertIn("traits", resolution)

    def test_resolve_unknown_capability_returns_none(self):
        from app import CapabilityRegistry
        reg = CapabilityRegistry()
        resolution = reg.resolve("nonexistent_capability")
        self.assertIsNone(resolution)

    def test_resolve_generate_image_returns_tool(self):
        from app import CapabilityRegistry
        reg = CapabilityRegistry()
        resolution = reg.resolve("generate_image")
        self.assertEqual(resolution["type"], "tool")
        self.assertEqual(resolution["tool_name"], "generate_image")


class TestCapabilityRegistryCatalog(unittest.TestCase):
    """Seam: list_catalog() returns name+description for LLM prompt."""

    def test_catalog_has_name_and_description(self):
        from app import CapabilityRegistry
        reg = CapabilityRegistry()
        catalog = reg.list_catalog()
        self.assertGreater(len(catalog), 0)
        for entry in catalog:
            self.assertIn("name", entry)
            self.assertIn("description", entry)


class TestCapabilityResolverInfer(unittest.TestCase):
    """Seam: infer_capabilities(goal, agent_specs) maps capabilities to agents."""

    def test_returns_capabilities_per_agent(self):
        from app import CapabilityResolver
        resolver = CapabilityResolver()
        agent_specs = [
            {"name": "Researcher", "role": "Research", "tools": ["search_web"]},
            {"name": "Artist", "role": "Artwork", "tools": ["generate_image"]},
        ]
        result = resolver.infer_capabilities(agent_specs)
        self.assertEqual(len(result), 2)
        self.assertIn("search_web", result[0]["capabilities"])
        self.assertIn("generate_image", result[1]["capabilities"])

    def test_agent_without_tools_gets_reasoning_trait(self):
        from app import CapabilityResolver
        resolver = CapabilityResolver()
        agent_specs = [
            {"name": "Manager", "role": "Coordinator", "tools": []},
        ]
        result = resolver.infer_capabilities(agent_specs)
        self.assertIn("reasoning", result[0]["capabilities"])


class TestCapabilityResolverAssign(unittest.TestCase):
    """Seam: assign_to_agent(capabilities, agent_spec) returns ResolvedAgent with model + tools."""

    def test_assign_tool_capability_binds_tool(self):
        from app import CapabilityResolver, CapabilityRegistry
        reg = CapabilityRegistry()
        resolver = CapabilityResolver(reg)
        resolved = resolver.assign_to_agent(
            ["search_web"],
            {"name": "Researcher", "role": "Research", "goal": "Find info", "backstory": "Researcher"}
        )
        self.assertIn("tools", resolved)
        self.assertEqual(resolved["tools"], ["search_web"])

    def test_assign_model_trait_does_not_bind_tool(self):
        from app import CapabilityResolver, CapabilityRegistry
        reg = CapabilityRegistry()
        resolver = CapabilityResolver(reg)
        resolved = resolver.assign_to_agent(
            ["reasoning"],
            {"name": "Manager", "role": "Coordinator", "goal": "Manage", "backstory": "Manager"}
        )
        self.assertEqual(resolved["tools"], [])

    def test_assign_multiple_capabilities(self):
        from app import CapabilityResolver, CapabilityRegistry
        reg = CapabilityRegistry()
        resolver = CapabilityResolver(reg)
        resolved = resolver.assign_to_agent(
            ["search_web", "generate_image"],
            {"name": "Content Creator", "role": "Creator", "goal": "Create", "backstory": "Creator"}
        )
        self.assertIn("search_web", resolved["tools"])
        self.assertIn("generate_image", resolved["tools"])


class TestCapabilityRegistryNewCapabilities(unittest.TestCase):
    """Tests for new capabilities: TTS, STT, Vision, Embeddings."""

    def test_text_to_speech_capability_exists(self):
        from app import CapabilityRegistry
        reg = CapabilityRegistry()
        resolution = reg.resolve("text_to_speech")
        self.assertIsNotNone(resolution)
        self.assertEqual(resolution["type"], "tool")
        self.assertEqual(resolution["tool_name"], "text_to_speech")

    def test_transcribe_audio_capability_exists(self):
        from app import CapabilityRegistry
        reg = CapabilityRegistry()
        resolution = reg.resolve("transcribe_audio")
        self.assertIsNotNone(resolution)
        self.assertEqual(resolution["type"], "tool")
        self.assertEqual(resolution["tool_name"], "transcribe_audio")

    def test_analyze_image_capability_exists(self):
        from app import CapabilityRegistry
        reg = CapabilityRegistry()
        resolution = reg.resolve("analyze_image")
        self.assertIsNotNone(resolution)
        self.assertEqual(resolution["type"], "tool")
        self.assertEqual(resolution["tool_name"], "analyze_image")

    def test_new_capabilities_in_catalog(self):
        from app import CapabilityRegistry
        reg = CapabilityRegistry()
        catalog = reg.list_catalog()
        names = [c["name"] for c in catalog]
        self.assertIn("text_to_speech", names)
        self.assertIn("transcribe_audio", names)
        self.assertIn("analyze_image", names)

    def test_assign_text_to_speech_binds_tool(self):
        from app import CapabilityResolver, CapabilityRegistry
        reg = CapabilityRegistry()
        resolver = CapabilityResolver(reg)
        resolved = resolver.assign_to_agent(
            ["text_to_speech"],
            {"name": "Voice Actor", "role": "TTS", "goal": "Narrate", "backstory": "Voice actor"}
        )
        self.assertIn("text_to_speech", resolved["tools"])

    def test_assign_analyze_image_binds_tool(self):
        from app import CapabilityResolver, CapabilityRegistry
        reg = CapabilityRegistry()
        resolver = CapabilityResolver(reg)
        resolved = resolver.assign_to_agent(
            ["analyze_image"],
            {"name": "Image Analyst", "role": "Vision", "goal": "Analyze images", "backstory": "Analyst"}
        )
        self.assertIn("analyze_image", resolved["tools"])

    def test_assign_multiple_new_capabilities(self):
        """Agent can have both TTS and image generation (e.g. for video narration)."""
        from app import CapabilityResolver, CapabilityRegistry
        reg = CapabilityRegistry()
        resolver = CapabilityResolver(reg)
        resolved = resolver.assign_to_agent(
            ["text_to_speech", "generate_image"],
            {"name": "Content Creator", "role": "Creator", "goal": "Create", "backstory": "Creator"}
        )
        self.assertIn("text_to_speech", resolved["tools"])
        self.assertIn("generate_image", resolved["tools"])


if __name__ == "__main__":
    unittest.main()

"""Test: Secretary prompt instructs agents to read full pages after search.

Bug (Task C / search parity): Market leaders (Claude, ChatGPT, Gemini) read
the actual page content before synthesizing answers. Our `search_web` returns
only the search-engine summary with source URLs — agents never call
`browse_web` or `scrape_web` to read the full page, so synthesized answers
are shallower than the market.

Fix: Secretary prompt must instruct any agent with `search_web` in its tools
to call `browse_web` (or `scrape_web` as fallback) on the source URLs returned
by search BEFORE writing the final answer.

Seam: `backend.core.secretary._build_search_behavior_section` — same pattern
as `_build_plan_schema_section` and `_build_design_rules_section` (extracted
prompt section, testable without LLM calls).
"""


class TestSecretaryPromptReadFullPages:
    """Verify Secretary prompt tells agents to read full pages after search."""

    def test_search_behavior_section_exists(self):
        """The extracted prompt section must exist (RED until implemented)."""
        from backend.core.secretary import _build_search_behavior_section
        section = _build_search_behavior_section()
        assert isinstance(section, str)
        assert len(section) > 0

    def test_section_mentions_browse_web(self):
        """Must tell agents to use browse_web to read full pages."""
        from backend.core.secretary import _build_search_behavior_section
        section = _build_search_behavior_section()
        assert "browse_web" in section, (
            f"Section should instruct agents to call browse_web. Got: {section}"
        )

    def test_section_requires_browse_web_in_tools_array(self):
        """Must tell Secretary to ADD browse_web to the agent's tools array.

        Bug: prompt said "agent with search_web MUST call browse_web" but
        never told the Secretary to put browse_web in the tools array —
        so the agent never received browse_web and could not call it.
        The word "call" means "use", not "declare in tools". Must explicitly
        say "add ... to tools" or "must also have ... in tools array".
        """
        from backend.core.secretary import _build_search_behavior_section
        section = _build_search_behavior_section().lower()
        # Must explicitly say browse_web goes IN the tools array.
        # "call browse_web" = use it (not declare it)
        # "add browse_web to tools" / "must also have browse_web in tools" = declare it
        has_tools_array_instruction = (
            ("add" in section and "browse_web" in section and "tools" in section)
            or ("must also have" in section and "browse_web" in section)
            or ("tools array" in section and "browse_web" in section)
        )
        assert has_tools_array_instruction, (
            f"Section should instruct Secretary to ADD browse_web to the agent's "
            f"tools array (not just 'call' it). Got: {section}"
        )

    def test_section_mentions_scrape_web_as_fallback(self):
        """Must offer scrape_web as a fallback when browse_web fails."""
        from backend.core.secretary import _build_search_behavior_section
        section = _build_search_behavior_section()
        assert "scrape_web" in section, (
            f"Section should mention scrape_web as fallback. Got: {section}"
        )

    def test_section_links_search_web_to_reading(self):
        """Must tie search_web results to the read-full-page instruction."""
        from backend.core.secretary import _build_search_behavior_section
        section = _build_search_behavior_section()
        assert "search_web" in section, (
            f"Section should reference search_web. Got: {section}"
        )

    def test_section_says_before_synthesize_or_final_answer(self):
        """Must specify WHEN to read: before writing the final answer."""
        from backend.core.secretary import _build_search_behavior_section
        section = _build_search_behavior_section().lower()
        assert "before" in section and (
            "synthes" in section or "final answer" in section or "final output" in section
        ), (
            f"Section should say to read full pages BEFORE synthesizing. Got: {section}"
        )

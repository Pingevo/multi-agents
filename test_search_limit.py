"""Test: search_web respects per-agent max_search_calls limit.

When an agent spec includes max_search_calls > 0, the search_web tool
should refuse further calls after the limit is reached, returning a
message that tells the agent to synthesize from existing data.

Business rule:
- max_search_calls = 0 → unlimited (default, backward compatible)
- max_search_calls = N → after N successful calls, return limit message

The limit is enforced via _thread_local (per-agent, parallel-safe),
set by the orchestrator before each agent run.
"""

import threading
from backend.globals import _thread_local
from backend.tools.search import _check_search_call_limit


class TestSearchCallLimit:
    """Verify the per-agent search call limit enforced in search_web."""

    def test_unlimited_when_max_search_calls_zero(self):
        """When max_search_calls=0 (default), no limit is enforced."""
        _thread_local.max_search_calls = 0
        _thread_local.search_call_count = 0
        result = _check_search_call_limit()
        assert result is None  # No refusal, search allowed

    def test_limit_reached_returns_refusal_message(self):
        """When count >= max_search_calls, returns refusal message."""
        _thread_local.max_search_calls = 3
        _thread_local.search_call_count = 3
        result = _check_search_call_limit()
        assert result is not None
        assert "ค้นหาครบ" in result
        assert "max_search_calls=3" in result

    def test_limit_not_reached_allows_search(self):
        """When count < max_search_calls, search is allowed (returns None)."""
        _thread_local.max_search_calls = 3
        _thread_local.search_call_count = 2
        result = _check_search_call_limit()
        assert result is None  # No refusal

    def test_count_increments_per_call(self):
        """Each allowed call increments search_call_count."""
        _thread_local.max_search_calls = 5
        _thread_local.search_call_count = 0
        for i in range(3):
            result = _check_search_call_limit()
            assert result is None  # All allowed
        assert _thread_local.search_call_count == 3

    def test_thread_local_is_per_thread(self):
        """Each thread has its own search_call_count (parallel-safe)."""
        results = {}

        def worker(name, results):
            _thread_local.search_call_count = 0
            _thread_local.max_search_calls = 2
            for _ in range(2):
                _check_search_call_limit()
            results[name] = _thread_local.search_call_count

        t1 = threading.Thread(target=worker, args=("t1", results))
        t2 = threading.Thread(target=worker, args=("t2", results))
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        # Both threads should have count=2 (independent)
        assert results["t1"] == 2
        assert results["t2"] == 2

    def test_refusal_message_instructs_agent_to_synthesize(self):
        """The refusal message tells the agent to use existing data."""
        _thread_local.max_search_calls = 1
        _thread_local.search_call_count = 1
        result = _check_search_call_limit()
        assert result is not None
        assert "สรุปผล" in result  # "synthesize" instruction

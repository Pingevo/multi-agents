"""Pytest configuration: fix asyncio event loop for tests that use run_in_executor + threading."""

import asyncio
import pytest


@pytest.fixture(autouse=True)
def _fix_event_loop():
    """Ensure each test gets a fresh event loop with a running executor.

    Without this, asyncio.get_event_loop() in tests may reuse a closed/stale
    loop from a previous test, causing hangs when run_in_executor is used
    with threading.Thread inside async code.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield
    loop.close()

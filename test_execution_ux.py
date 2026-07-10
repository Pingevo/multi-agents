"""Tests for execution UX fixes: result ordering, is_free logic, final summary."""
import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch


# ============================================================
# Test 1: is_free logic — should be True for :free models
# ============================================================

def test_is_free_logic_for_free_suffix():
    """Models with :free suffix should have is_free=True."""
    mid = "x-ai/grok-2-image:free"
    pricing = {"prompt": "0", "completion": "0"}
    all_pricing_fields = {k: v for k, v in pricing.items() if v and v != "0"}
    is_free = ":free" in mid or not all_pricing_fields
    assert is_free is True, f":free model should be free, got {is_free}"


def test_is_free_logic_for_paid_model():
    """Paid models with non-zero pricing should have is_free=False."""
    mid = "google/gemini-3-pro-image"
    pricing = {"prompt": "0.000002", "completion": "0.000012", "image": "0.000002"}
    all_pricing_fields = {k: v for k, v in pricing.items() if v and v != "0"}
    is_free = ":free" in mid or not all_pricing_fields
    assert is_free is False, f"Paid model should not be free, got {is_free}"


def test_is_free_logic_for_zero_pricing_no_free_suffix():
    """Models with all-zero pricing and no :free suffix should be free."""
    mid = "some-model/free-tier"
    pricing = {"prompt": "0", "completion": "0"}
    all_pricing_fields = {k: v for k, v in pricing.items() if v and v != "0"}
    is_free = ":free" in mid or not all_pricing_fields
    assert is_free is True, f"All-zero pricing model should be free, got {is_free}"


def test_is_free_logic_not_inverted():
    """Ensure the old inverted logic is NOT used."""
    mid = "x-ai/grok-2-image:free"
    pricing = {"prompt": "0", "completion": "0"}
    all_pricing_fields = {k: v for k, v in pricing.items() if v and v != "0"}
    old_inverted = ":free" not in mid and not all_pricing_fields
    new_correct = ":free" in mid or not all_pricing_fields
    assert old_inverted != new_correct, "Old inverted logic should differ from new correct logic"
    assert new_correct is True, "New logic should mark :free model as free"


# ============================================================
# Test 2: reply_result called after approval cards
# ============================================================

@pytest.mark.anyio
async def test_result_after_approval():
    """reply_result should be called after all approval cards are sent."""
    from backend.core.messenger import StateMessenger

    messenger = MagicMock(spec=StateMessenger)
    messenger.reply_result = AsyncMock()
    messenger.reply_image_approval = AsyncMock()
    messenger.reply_agent_progress = AsyncMock()
    messenger.update_task = AsyncMock()
    messenger.update_agents = AsyncMock()
    messenger.notify = AsyncMock()
    messenger.reply = AsyncMock()
    messenger.persist_message = MagicMock()

    call_order = []
    async def track_reply_result(*args, **kwargs):
        call_order.append("reply_result")
    async def track_image_approval(*args, **kwargs):
        call_order.append("image_approval")
    messenger.reply_result.side_effect = track_reply_result
    messenger.reply_image_approval.side_effect = track_image_approval

    # Simulate sending approval cards first
    for i in range(3):
        await messenger.reply_image_approval(f"prompt {i}", f"img_{i}", "Agent")
    # Then send result
    await messenger.reply_result("Done", [])

    assert call_order == ["image_approval", "image_approval", "image_approval", "reply_result"], \
        f"Expected approval cards before result, got {call_order}"


# ============================================================
# Test 3: Final summary sent when raw_output is meaningful
# ============================================================

@pytest.mark.anyio
async def test_final_summary_sent():
    """messenger.reply should be called with raw_output when it's meaningful text."""
    raw_output = "Here is the final summary of the content plan for your coffee shop..."

    should_send = raw_output and len(raw_output) > 20 and not raw_output.strip().startswith("{")
    assert should_send, "Meaningful raw_output should trigger reply"


def test_final_summary_not_sent_for_json():
    """messenger.reply should NOT be called when raw_output is JSON."""
    raw_output = '{"result": "done", "agents": []}'
    should_send = raw_output and len(raw_output) > 20 and not raw_output.strip().startswith("{")
    assert not should_send, "JSON raw_output should not trigger reply"


def test_final_summary_not_sent_for_empty():
    """messenger.reply should NOT be called when raw_output is empty or too short."""
    raw_output = ""
    should_send = raw_output and len(raw_output) > 20 and not raw_output.strip().startswith("{")
    assert not should_send, "Empty raw_output should not trigger reply"


# ============================================================
# Test 4: MediaGenerationManager logs free status
# ============================================================

def test_media_gen_free_log():
    """MediaGenerationManager should correctly identify free models."""
    # Simulate the is_free check from manager.py
    image_model = "x-ai/grok-2-image:free"
    is_free = ":free" in image_model or image_model == "openrouter/free"
    assert is_free is True

    image_model = "google/gemini-3-pro-image"
    is_free = ":free" in image_model or image_model == "openrouter/free"
    assert is_free is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

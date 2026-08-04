"""Test: auto-approve policy on media retry after user rejection.

When a user rejects media with feedback, the agent re-runs with the feedback
and produces a new prompt. The retry attempt should auto-approve (skip the
approval card) because the user already gave instructions by rejecting.

Business rule:
- First attempt (retry_count=0): respect user's auto_approve setting
- Retry attempts (retry_count>0): always auto-approve
"""

import pytest
from backend.core.media_awaiter import should_auto_approve_on_retry


class TestShouldAutoApproveOnRetry:
    """Verify the auto-approve policy for media retry attempts."""

    def test_first_attempt_respects_user_disabled(self):
        """When user has auto_approve=False and retry_count=0, should NOT auto-approve."""
        assert should_auto_approve_on_retry(user_auto_approve=False, retry_count=0) is False

    def test_first_attempt_respects_user_enabled(self):
        """When user has auto_approve=True and retry_count=0, should auto-approve."""
        assert should_auto_approve_on_retry(user_auto_approve=True, retry_count=0) is True

    def test_retry_always_auto_approves_even_if_user_disabled(self):
        """On retry (retry_count=1), should auto-approve even if user setting is False."""
        assert should_auto_approve_on_retry(user_auto_approve=False, retry_count=1) is True

    def test_second_retry_also_auto_approves(self):
        """On second retry (retry_count=2), should still auto-approve."""
        assert should_auto_approve_on_retry(user_auto_approve=False, retry_count=2) is True

    def test_retry_with_user_enabled_still_true(self):
        """When user has auto_approve=True, retry should also be True (no regression)."""
        assert should_auto_approve_on_retry(user_auto_approve=True, retry_count=1) is True

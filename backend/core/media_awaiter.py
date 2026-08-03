"""MediaAwaiter — Deep Module for media approval workflow.

Encapsulates all complexity of:
- Creating asyncio.Future objects for media approval requests
- Sending approval cards to the frontend via messenger
- Waiting for user approval/rejection via socket events
- Auto-approving when the setting is enabled
- Calling MediaGenerationManager for actual generation
- Returning structured results to the orchestrator

No hardcoded timeouts — relies on the API's own limits and the user's Cancel button.
"""

from __future__ import annotations

import asyncio
import hashlib
import time
from typing import Any, Optional

import chainlit as cl


class MediaAwaiter:
    """Manages media approval futures and resolution.

    Class-level state:
        _futures: approval_id -> asyncio.Future
            Stores pending futures keyed by approval_id.
            The future resolves to a dict:
                {"status": "approved", "urls": [...]}   — media generated
                {"status": "rejected", "feedback": "..."} — user rejected
                {"status": "error", "error": "..."}       — generation failed
    """

    _futures: dict[str, asyncio.Future] = {}

    # ------------------------------------------------------------------
    # Public class methods — called by socket handlers (chat.py)
    # ------------------------------------------------------------------

    @classmethod
    def resolve_approval(cls, approval_id: str, result: dict) -> bool:
        """Resolve a pending approval future.

        Called by approve_image / reject_image socket handlers.
        Returns True if a future was resolved, False if none existed.
        """
        future = cls._futures.get(approval_id)
        if future and not future.done():
            future.set_result(result)
            return True
        return False

    @classmethod
    def cancel_approval(cls, approval_id: str) -> bool:
        """Cancel a pending approval future (e.g. user cancelled generation)."""
        future = cls._futures.get(approval_id)
        if future and not future.done():
            future.cancel()
            return True
        return False

    @classmethod
    def clear(cls, approval_id: str) -> None:
        """Clean up a resolved or cancelled future."""
        cls._futures.pop(approval_id, None)

    @classmethod
    def has_pending(cls) -> bool:
        """Check if any media approval futures are still pending."""
        return any(not f.done() for f in cls._futures.values())

    # ------------------------------------------------------------------
    # Core interface — called by the orchestrator
    # ------------------------------------------------------------------

    @classmethod
    async def resolve_media_dependencies(
        cls,
        agent_name: str,
        media_tool_results: list[dict],
        auto_approve: bool,
        session_id: str,
        messenger: Any = None,
        media_gen_manager: Any = None,
    ) -> dict:
        """Resolve all media requests produced by a single agent.

        Args:
            agent_name: Name of the agent that produced the media requests.
            media_tool_results: List of media request dicts (from _media_tool_results)
                                filtered to this agent's requests.
            auto_approve: If True, skip user approval and generate immediately.
            session_id: Current chat session ID for persistence.
            messenger: StateMessenger instance for sending UI updates.
            media_gen_manager: MediaGenerationManager for actual generation.

        Returns:
            {"status": "approved", "urls": [...], "media_results": [...]}
                — All media generated successfully, agent can complete.
            {"status": "rejected", "feedback": "..."}
                — User rejected with feedback, agent should re-run with feedback.
            {"status": "error", "error": "..."}
                — Generation failed, agent output used as-is.
            {"status": "no_media"}
                — No media requests for this agent, nothing to do.
        """
        # Filter to this agent's media requests
        agent_media = [r for r in media_tool_results if r.get("agent_name") == agent_name]
        if not agent_media:
            return {"status": "no_media"}

        # Check for cancellation
        if cl.user_session.get("cancel_generation"):
            return {"status": "error", "error": "Cancelled by user"}

        if auto_approve:
            return await cls._auto_approve_media(
                agent_media, session_id, messenger, media_gen_manager
            )
        else:
            return await cls._await_user_approval(
                agent_name, agent_media, session_id, messenger, media_gen_manager
            )

    # ------------------------------------------------------------------
    # Private implementation — hidden behind the interface
    # ------------------------------------------------------------------

    @classmethod
    async def _auto_approve_media(
        cls,
        agent_media: list[dict],
        session_id: str,
        messenger: Any,
        media_gen_manager: Any,
    ) -> dict:
        """Auto-approve: generate all media immediately without user review."""
        urls = []
        media_results = []

        for media_req in agent_media:
            approval_id = cls._make_approval_id(media_req)
            media_type = media_req.get("type", "image")
            prompt = media_req.get("prompt", "")

            if messenger:
                await messenger.update_approval_status(approval_id, "approved")

            try:
                url = await cls._generate_media(
                    media_req, media_gen_manager, messenger, approval_id
                )
                if url:
                    urls.append(url)
                    media_results.append({**media_req, "url": url, "approval_id": approval_id})
                else:
                    media_results.append({**media_req, "url": None, "approval_id": approval_id, "error": "Generation returned no URL"})
            except Exception as e:
                print(f"[MEDIA-AWAITER] Auto-approve generation error: {e}", flush=True)
                media_results.append({**media_req, "url": None, "approval_id": approval_id, "error": str(e)})
                if messenger:
                    await messenger.update_approval_status(approval_id, "error", str(e))

        if urls:
            return {"status": "approved", "urls": urls, "media_results": media_results}
        else:
            return {"status": "error", "error": "All media generation failed", "media_results": media_results}

    @classmethod
    async def _await_user_approval(
        cls,
        agent_name: str,
        agent_media: list[dict],
        session_id: str,
        messenger: Any,
        media_gen_manager: Any,
    ) -> dict:
        """Manual approval: send approval cards and wait for user decision.

        Creates an asyncio.Future per media request, sends approval cards,
        and awaits all futures. No hardcoded timeout — waits indefinitely
        until the user approves, rejects, or cancels.
        """
        futures: dict[str, asyncio.Future] = {}
        approval_ids: list[str] = []

        for media_req in agent_media:
            approval_id = cls._make_approval_id(media_req)
            approval_ids.append(approval_id)

            loop = asyncio.get_event_loop()
            future = loop.create_future()
            cls._futures[approval_id] = future
            futures[approval_id] = future

            # Store pending media in user session for socket handler lookup
            cl.user_session.set(f"pending_media_{approval_id}", media_req)

            # Send approval card to frontend
            if messenger:
                media_type = media_req.get("type", "image")
                prompt = media_req.get("prompt", "")
                duration = media_req.get("duration", 0)
                model = media_req.get("model", "")
                await messenger.reply_image_approval(
                    prompt, approval_id, agent_name,
                    media_type=media_type, duration=duration
                )

        # Wait for all futures to resolve (no timeout — user decides)
        try:
            results = await asyncio.gather(
                *[futures[aid] for aid in approval_ids],
                return_exceptions=True
            )
        except asyncio.CancelledError:
            # Clean up on cancellation
            for aid in approval_ids:
                cls.clear(aid)
            return {"status": "error", "error": "Cancelled by user"}

        # Process results
        urls = []
        all_media_results = []
        rejection_feedback = None

        for aid, result in zip(approval_ids, results):
            cls.clear(aid)

            if isinstance(result, asyncio.CancelledError):
                all_media_results.append({"approval_id": aid, "error": "Cancelled"})
                continue

            if isinstance(result, Exception):
                all_media_results.append({"approval_id": aid, "error": str(result)})
                continue

            status = result.get("status", "error")

            if status == "approved":
                url = result.get("url")
                if url:
                    urls.append(url)
                all_media_results.append({**result, "approval_id": aid})

            elif status == "rejected":
                feedback = result.get("feedback", "")
                if feedback:
                    rejection_feedback = feedback
                all_media_results.append({**result, "approval_id": aid})

            else:
                all_media_results.append({**result, "approval_id": aid})

        # If any rejection with feedback, return rejected status
        if rejection_feedback:
            return {"status": "rejected", "feedback": rejection_feedback, "media_results": all_media_results}

        if urls:
            return {"status": "approved", "urls": urls, "media_results": all_media_results}

        # All rejected without feedback or errored
        has_rejection = any(r.get("status") == "rejected" for r in all_media_results)
        if has_rejection:
            return {"status": "rejected", "feedback": "", "media_results": all_media_results}

        return {"status": "error", "error": "All media requests failed", "media_results": all_media_results}

    @classmethod
    async def _generate_media(
        cls,
        media_req: dict,
        media_gen_manager: Any,
        messenger: Any,
        approval_id: str,
    ) -> Optional[str]:
        """Call MediaGenerationManager to generate actual media.

        Returns the generated media URL, or None on failure.
        """
        if not media_gen_manager:
            print(f"[MEDIA-AWAITER] No media_gen_manager available", flush=True)
            return None

        media_type = media_req.get("type", "image")
        prompt = media_req.get("prompt", "")
        model = media_req.get("model", "")
        duration = media_req.get("duration", 0)

        # MediaGenerationManager only has synchronous methods — wrap with asyncio.to_thread
        # to avoid blocking the event loop during media generation.
        try:
            if media_type == "image":
                result = await asyncio.to_thread(media_gen_manager.generate_image, prompt)
            elif media_type == "video":
                result = await asyncio.to_thread(media_gen_manager.generate_video, prompt, duration=duration)
            elif media_type == "tts":
                # TTS uses text + voice, not prompt + model — voice defaults to "alloy"
                text = media_req.get("text", prompt)
                voice = media_req.get("voice", "alloy")
                result = await asyncio.to_thread(media_gen_manager.generate_tts, text, voice)
            elif media_type == "stt":
                audio_url = media_req.get("audio_url", prompt)
                result = await asyncio.to_thread(media_gen_manager.generate_stt, audio_url)
            elif media_type == "vision":
                image_url = media_req.get("image_url", "")
                question = media_req.get("question", prompt)
                result = await asyncio.to_thread(media_gen_manager.generate_vision, image_url, question)
            else:
                print(f"[MEDIA-AWAITER] Unknown media type: {media_type}", flush=True)
                return None

            if isinstance(result, dict):
                url = result.get("url") or result.get("image_url") or result.get("output_url")
                if url and messenger:
                    await messenger.reply_image_result(
                        url, prompt, approval_id,
                        agent_name=media_req.get("agent_name", ""),
                        media_type=media_type,
                    )
                return url
            elif isinstance(result, str):
                if messenger:
                    await messenger.reply_image_result(
                        result, prompt, approval_id,
                        agent_name=media_req.get("agent_name", ""),
                        media_type=media_type,
                    )
                return result
            else:
                print(f"[MEDIA-AWAITER] Unexpected result type: {type(result)}", flush=True)
                return None

        except Exception as e:
            print(f"[MEDIA-AWAITER] Generation error for {approval_id}: {e}", flush=True)
            if messenger:
                await messenger.update_approval_status(approval_id, "error", str(e))
            raise

    @staticmethod
    def _make_approval_id(media_req: dict) -> str:
        """Generate a deterministic approval ID from media request content."""
        prompt = media_req.get("prompt", "")
        agent_name = media_req.get("agent_name", "")
        media_type = media_req.get("type", "image")
        content = f"{media_type}_{agent_name}_{prompt[:200]}"
        return hashlib.md5(content.encode()).hexdigest()[:16]

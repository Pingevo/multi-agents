"""Regression tests for URL migration in reply_chat_history.

Tests that _migrate_msg_urls converts absolute URLs to relative paths
so that images and attachments survive server restarts with different ports.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("OPENROUTER_API_KEY", "test-key-fake")

from backend.core.messenger import StateMessenger


class TestUrlMigration(unittest.TestCase):
    """_migrate_msg_urls must convert absolute URLs to relative paths."""

    def test_attachment_url_converted(self):
        msg = {
            "role": "user",
            "messageType": "text",
            "attachmentUrl": "http://127.0.0.1:64446/public/attachments/a355f89d_ZMI_HA716.webp",
        }
        result = StateMessenger._migrate_msg_urls(msg)
        self.assertEqual(result["attachmentUrl"], "/public/attachments/a355f89d_ZMI_HA716.webp")

    def test_localhost_url_converted(self):
        msg = {
            "role": "assistant",
            "messageType": "image_result",
            "imageUrl": "http://localhost:8000/public/generated/img_0299baee.png",
        }
        result = StateMessenger._migrate_msg_urls(msg)
        self.assertEqual(result["imageUrl"], "/public/generated/img_0299baee.png")

    def test_already_relative_unchanged(self):
        msg = {
            "role": "user",
            "attachmentUrl": "/public/attachments/test.webp",
        }
        result = StateMessenger._migrate_msg_urls(msg)
        self.assertEqual(result["attachmentUrl"], "/public/attachments/test.webp")

    def test_attachments_list_converted(self):
        msg = {
            "role": "user",
            "attachments": [
                {"url": "http://127.0.0.1:50994/public/attachments/abc.png", "name": "test.png", "mime": "image/png"},
                {"url": "http://localhost:8000/public/attachments/def.jpg", "name": "test.jpg", "mime": "image/jpeg"},
            ],
        }
        result = StateMessenger._migrate_msg_urls(msg)
        self.assertEqual(result["attachments"][0]["url"], "/public/attachments/abc.png")
        self.assertEqual(result["attachments"][1]["url"], "/public/attachments/def.jpg")

    def test_non_public_url_unchanged(self):
        msg = {
            "role": "assistant",
            "imageUrl": "https://cdn.example.com/some-other-url.png",
        }
        result = StateMessenger._migrate_msg_urls(msg)
        self.assertEqual(result["imageUrl"], "https://cdn.example.com/some-other-url.png")

    def test_no_url_fields_unchanged(self):
        msg = {
            "role": "assistant",
            "messageType": "text",
            "content": "Hello world",
        }
        result = StateMessenger._migrate_msg_urls(msg)
        self.assertEqual(result["content"], "Hello world")
        self.assertNotIn("imageUrl", result)

    def test_does_not_mutate_original(self):
        original = {
            "role": "user",
            "attachmentUrl": "http://127.0.0.1:64446/public/attachments/test.webp",
        }
        result = StateMessenger._migrate_msg_urls(original)
        self.assertEqual(original["attachmentUrl"], "http://127.0.0.1:64446/public/attachments/test.webp")
        self.assertEqual(result["attachmentUrl"], "/public/attachments/test.webp")

    def test_video_url_converted(self):
        msg = {
            "role": "assistant",
            "messageType": "video_result",
            "videoUrl": "http://127.0.0.1:8000/public/generated/vid_abc.mp4",
        }
        result = StateMessenger._migrate_msg_urls(msg)
        self.assertEqual(result["videoUrl"], "/public/generated/vid_abc.mp4")


if __name__ == "__main__":
    unittest.main()

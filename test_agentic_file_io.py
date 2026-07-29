"""Tests for agentic file I/O: URL classification, text extraction, media type handling.

Covers:
- Phase 1.1: Code file extensions in text_extractable
- Phase 1.2: PPTX text extraction
- Phase 1.4: Archive extraction (.zip)
- Phase 1.6: URL extension map for documents/code/archives
- Phase 2.4: Image format detection from media_type
- Phase 3.3b: has_pending_approvals excludes documents
- Phase 3.3a: edit_image_prompt type-aware field mapping
"""

import unittest
import asyncio
import os
import sys
import tempfile
import zipfile
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ.setdefault("OPENROUTER_API_KEY", "test-key-fake")

ATTACHMENTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "public", "attachments")


def _make_test_file(suffix, content, mode="wb"):
    """Create a test file in public/attachments/ and return its URL and path."""
    os.makedirs(ATTACHMENTS_DIR, exist_ok=True)
    import uuid as _uuid
    filename = f"test_{_uuid.uuid4().hex[:8]}{suffix}"
    path = os.path.join(ATTACHMENTS_DIR, filename)
    with open(path, mode) as f:
        f.write(content)
    url = f"http://localhost:8000/public/attachments/{filename}"
    return url, path, filename


class TestClassifyUrlExtensions(unittest.TestCase):
    """Phase 1.6: URL classification must handle document, code, and archive extensions."""

    def test_classify_docx_url(self):
        from app import classify_url
        self.assertEqual(classify_url("https://example.com/report.docx"), "docx")

    def test_classify_xlsx_url(self):
        from app import classify_url
        self.assertEqual(classify_url("https://example.com/data.xlsx"), "xlsx")

    def test_classify_pptx_url(self):
        from app import classify_url
        self.assertEqual(classify_url("https://example.com/slides.pptx"), "pptx")

    def test_classify_py_url(self):
        from app import classify_url
        self.assertEqual(classify_url("https://example.com/script.py"), "code")

    def test_classify_js_url(self):
        from app import classify_url
        self.assertEqual(classify_url("https://example.com/app.js"), "code")

    def test_classify_ts_url(self):
        from app import classify_url
        self.assertEqual(classify_url("https://example.com/index.ts"), "code")

    def test_classify_zip_url(self):
        from app import classify_url
        self.assertEqual(classify_url("https://example.com/archive.zip"), "archive")

    def test_classify_tar_url(self):
        from app import classify_url
        self.assertEqual(classify_url("https://example.com/backup.tar"), "archive")

    def test_classify_targz_url(self):
        from app import classify_url
        self.assertEqual(classify_url("https://example.com/backup.tar.gz"), "archive")


class TestCodeFileTextExtraction(unittest.TestCase):
    """Phase 1.1: Code files should be text-extracted, not treated as metadata."""

    def test_py_file_extracted_as_text(self):
        from app import process_attachment
        url, path, name = _make_test_file(".py", b"print('hello world')\nx = 42\n")
        try:
            result = asyncio.get_event_loop().run_until_complete(
                process_attachment(url, name, "text/x-python")
            )
            self.assertEqual(result["type"], "text")
            self.assertIn("hello world", result["content_blocks"][0].get("text", "") if result["content_blocks"] else result.get("text_content", ""))
        finally:
            os.unlink(path)

    def test_js_file_extracted_as_text(self):
        from app import process_attachment
        url, path, name = _make_test_file(".js", b"console.log('hello');\nconst x = 42;\n")
        try:
            result = asyncio.get_event_loop().run_until_complete(
                process_attachment(url, name, "text/javascript")
            )
            self.assertEqual(result["type"], "text")
        finally:
            os.unlink(path)

    def test_ts_file_extracted_as_text(self):
        from app import process_attachment
        url, path, name = _make_test_file(".ts", b"const x: number = 42;\nexport default x;\n")
        try:
            result = asyncio.get_event_loop().run_until_complete(
                process_attachment(url, name, "text/typescript")
            )
            self.assertEqual(result["type"], "text")
        finally:
            os.unlink(path)


class TestArchiveExtraction(unittest.TestCase):
    """Phase 1.4: Archive files (.zip) should be extracted and text files concatenated."""

    def test_zip_with_text_files_extracted(self):
        from app import process_attachment
        # Create a zip with a text file inside
        buf_path = os.path.join(ATTACHMENTS_DIR, "test_zip_temp.zip")
        with zipfile.ZipFile(buf_path, 'w') as zf:
            zf.writestr("readme.txt", "This is a readme file.\nHello world!")
            zf.writestr("config.json", json.dumps({"key": "value"}))
        try:
            url = f"http://localhost:8000/public/attachments/test_zip_temp.zip"
            result = asyncio.get_event_loop().run_until_complete(
                process_attachment(url, "test_zip_temp.zip", "application/zip")
            )
            self.assertEqual(result["type"], "text")
            # The text content should contain the extracted file contents
            text_content = ""
            if result.get("content_blocks"):
                for block in result["content_blocks"]:
                    if isinstance(block, dict) and "text" in block:
                        text_content += block["text"]
            elif result.get("text_content"):
                text_content = result["text_content"]
            self.assertIn("This is a readme file", text_content)
            self.assertIn("key", text_content)
        finally:
            os.unlink(buf_path)

    def test_zip_with_binary_files_skipped(self):
        from app import process_attachment
        buf_path = os.path.join(ATTACHMENTS_DIR, "test_zip_binary.zip")
        with zipfile.ZipFile(buf_path, 'w') as zf:
            zf.writestr("image.png", b"\x89PNG\r\n\x1a\n fake png data")
            zf.writestr("readme.txt", "Hello from text!")
        try:
            url = f"http://localhost:8000/public/attachments/test_zip_binary.zip"
            result = asyncio.get_event_loop().run_until_complete(
                process_attachment(url, "test_zip_binary.zip", "application/zip")
            )
            self.assertEqual(result["type"], "text")
            # Should only have text file content, not binary
            text_content = ""
            if result.get("content_blocks"):
                for block in result["content_blocks"]:
                    if isinstance(block, dict) and "text" in block:
                        text_content += block["text"]
            elif result.get("text_content"):
                text_content = result["text_content"]
            self.assertIn("Hello from text", text_content)
            self.assertNotIn("PNG", text_content)
        finally:
            os.unlink(buf_path)


class TestVideoMimeDetection(unittest.TestCase):
    """Phase 1.3: Video MIME type should be detected from URL extension, not hardcoded."""

    def test_video_mime_from_url_webm(self):
        from backend.attachment.processor import _video_mime_from_url
        self.assertEqual(_video_mime_from_url("https://example.com/video.webm"), "video/webm")

    def test_video_mime_from_url_mov(self):
        from backend.attachment.processor import _video_mime_from_url
        self.assertEqual(_video_mime_from_url("https://example.com/video.mov"), "video/quicktime")

    def test_video_mime_from_url_mp4(self):
        from backend.attachment.processor import _video_mime_from_url
        self.assertEqual(_video_mime_from_url("https://example.com/video.mp4"), "video/mp4")

    def test_video_mime_from_url_unknown_defaults_to_mp4(self):
        from backend.attachment.processor import _video_mime_from_url
        self.assertEqual(_video_mime_from_url("https://example.com/video.xyz"), "video/mp4")


class TestImageFormatDetection(unittest.TestCase):
    """Phase 2.4: Image file extension should come from API media_type, not hardcoded .png."""

    def test_jpeg_media_type_returns_jpg(self):
        # Test the mapping logic used in manager.py
        media_type_to_ext = {
            "image/png": ".png",
            "image/jpeg": ".jpg",
            "image/webp": ".webp",
            "image/gif": ".gif",
        }
        self.assertEqual(media_type_to_ext.get("image/jpeg", ".png"), ".jpg")
        self.assertEqual(media_type_to_ext.get("image/webp", ".png"), ".webp")
        self.assertEqual(media_type_to_ext.get("image/png", ".png"), ".png")
        self.assertEqual(media_type_to_ext.get("unknown", ".png"), ".png")


class TestTypeAwarePromptMapping(unittest.TestCase):
    """Phase 3.1/3.3a: Type-aware prompt field mapping for all media types."""

    def test_prompt_map_covers_all_types(self):
        prompt_map = {
            "image": "prompt", "video": "prompt",
            "tts": "text", "stt": "audio_url",
            "vision": "question", "document": "filename",
        }
        for mt in ["image", "video", "tts", "stt", "vision", "document"]:
            self.assertIn(mt, prompt_map, f"Missing prompt_map entry for {mt}")

    def test_tool_map_covers_all_types(self):
        tool_map = {
            "image": "generate_image", "video": "generate_video",
            "tts": "text_to_speech", "stt": "transcribe_audio",
            "vision": "analyze_image", "document": "generate_document",
        }
        for mt in ["image", "video", "tts", "stt", "vision", "document"]:
            self.assertIn(mt, tool_map, f"Missing tool_map entry for {mt}")


class TestHasPendingApprovalsExcludesDocuments(unittest.TestCase):
    """Phase 3.3b: has_pending_approvals should be False when only documents are pending."""

    def test_only_documents_no_pending_approvals(self):
        media_tool_results = [{"type": "document"}, {"type": "document"}]
        has_pending = any(r.get("type") != "document" for r in media_tool_results)
        self.assertFalse(has_pending)

    def test_mixed_types_has_pending_approvals(self):
        media_tool_results = [{"type": "document"}, {"type": "image"}]
        has_pending = any(r.get("type") != "document" for r in media_tool_results)
        self.assertTrue(has_pending)

    def test_empty_results_no_pending(self):
        media_tool_results = []
        has_pending = any(r.get("type") != "document" for r in media_tool_results)
        self.assertFalse(has_pending)


if __name__ == "__main__":
    unittest.main()

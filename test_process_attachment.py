"""Tests for attachment processing pipeline: process_attachment, process_url, classify_url."""

import unittest
import asyncio
import os
import sys
import tempfile
import base64
import pytest
from unittest.mock import patch, MagicMock

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


class TestClassifyUrl(unittest.TestCase):
    """classify_url must correctly identify URL types by domain and extension."""

    def test_classify_youtube_url(self):
        from app import classify_url
        self.assertEqual(classify_url("https://www.youtube.com/watch?v=abc123"), "youtube")

    def test_classify_youtu_be_short_url(self):
        from app import classify_url
        self.assertEqual(classify_url("https://youtu.be/abc123"), "youtube")

    def test_classify_image_url_jpg(self):
        from app import classify_url
        self.assertEqual(classify_url("https://example.com/photo.jpg"), "image")

    def test_classify_image_url_png(self):
        from app import classify_url
        self.assertEqual(classify_url("https://example.com/photo.png"), "image")

    def test_classify_pdf_url(self):
        from app import classify_url
        self.assertEqual(classify_url("https://example.com/doc.pdf"), "pdf")

    def test_classify_audio_url_mp3(self):
        from app import classify_url
        self.assertEqual(classify_url("https://example.com/audio.mp3"), "audio")

    def test_classify_video_url_mp4(self):
        from app import classify_url
        self.assertEqual(classify_url("https://example.com/video.mp4"), "video")

    def test_classify_webpage_url_default(self):
        from app import classify_url
        self.assertEqual(classify_url("https://example.com/article"), "webpage")

    def test_classify_strips_query_params(self):
        from app import classify_url
        self.assertEqual(classify_url("https://example.com/photo.jpg?w=100&h=200"), "image")


class TestProcessAttachmentImage(unittest.TestCase):
    """process_attachment must handle image files correctly."""

    def test_image_png_returns_multimodal_with_image_url_block(self):
        from app import process_attachment
        url, path, name = _make_test_file(".png", b"\x89PNG\r\n\x1a\n fake png data")
        try:
            result = asyncio.get_event_loop().run_until_complete(
                process_attachment(url, name, "image/png")
            )
            self.assertEqual(result["type"], "multimodal")
            self.assertTrue(len(result["content_blocks"]) > 0)
            block = result["content_blocks"][0]
            self.assertEqual(block["type"], "image_url")
            self.assertIn("base64", block["image_url"]["url"])
        finally:
            os.unlink(path)

    def test_image_returns_required_modality(self):
        from app import process_attachment
        url, path, name = _make_test_file(".png", b"\x89PNG\r\n\x1a\n fake png data")
        try:
            result = asyncio.get_event_loop().run_until_complete(
                process_attachment(url, name, "image/png")
            )
            self.assertEqual(result.get("required_modality"), "image")
        finally:
            os.unlink(path)

    def test_image_returns_crewai_imagefile(self):
        from app import process_attachment
        url, path, name = _make_test_file(".png", b"\x89PNG\r\n\x1a\n fake png data")
        try:
            result = asyncio.get_event_loop().run_until_complete(
                process_attachment(url, name, "image/png")
            )
            self.assertIsNotNone(result.get("crewai_files"))
            self.assertIn("image", result["crewai_files"])
        finally:
            os.unlink(path)

    def test_image_returns_context_text(self):
        from app import process_attachment
        url, path, name = _make_test_file(".png", b"\x89PNG\r\n\x1a\n fake png data")
        try:
            result = asyncio.get_event_loop().run_until_complete(
                process_attachment(url, name, "image/png")
            )
            self.assertIn("context_text", result)
            self.assertTrue(len(result["context_text"]) > 0)
        finally:
            os.unlink(path)


class TestProcessAttachmentText(unittest.TestCase):
    """process_attachment must extract text from text files."""

    def test_text_plain_returns_text_type_with_content(self):
        from app import process_attachment
        url, path, name = _make_test_file(".txt", "Hello, this is a test file.\nLine 2.", mode="w")
        try:
            result = asyncio.get_event_loop().run_until_complete(
                process_attachment(url, name, "text/plain")
            )
            self.assertEqual(result["type"], "text")
            self.assertIn("Hello, this is a test file", result["text_content"])
        finally:
            os.unlink(path)

    def test_json_returns_text_type_with_content(self):
        from app import process_attachment
        url, path, name = _make_test_file(".json", '{"key": "value", "num": 42}', mode="w")
        try:
            result = asyncio.get_event_loop().run_until_complete(
                process_attachment(url, name, "application/json")
            )
            self.assertEqual(result["type"], "text")
            self.assertIn('"key"', result["text_content"])
        finally:
            os.unlink(path)

    def test_large_text_truncated_at_50k_chars(self):
        from app import process_attachment
        url, path, name = _make_test_file(".txt", "A" * 60000, mode="w")
        try:
            result = asyncio.get_event_loop().run_until_complete(
                process_attachment(url, name, "text/plain")
            )
            self.assertEqual(result["type"], "text")
            self.assertLessEqual(len(result["text_content"]), 51000)
            self.assertIn("[...truncated]", result["text_content"])
        finally:
            os.unlink(path)


class TestProcessAttachmentMetadata(unittest.TestCase):
    """process_attachment must return metadata for unknown types."""

    def test_unknown_mime_returns_metadata_type(self):
        from app import process_attachment
        url, path, name = _make_test_file(".bin", b"\x00\x01\x02\x03")
        try:
            result = asyncio.get_event_loop().run_until_complete(
                process_attachment(url, name, "application/octet-stream")
            )
            self.assertEqual(result["type"], "metadata")
            self.assertIn("context_text", result)
        finally:
            os.unlink(path)

    def test_file_not_found_returns_metadata_with_error(self):
        from app import process_attachment
        result = asyncio.get_event_loop().run_until_complete(
            process_attachment(
                "http://localhost:8000/public/attachments/nonexistent.png",
                "nonexistent.png",
                "image/png",
            )
        )
        self.assertEqual(result["type"], "metadata")
        self.assertIn("context_text", result)


class TestProcessUrlImage(unittest.TestCase):
    """process_url must handle image URLs without downloading."""

    @patch("app.requests")
    def test_image_url_returns_image_url_block_with_direct_url(self, mock_requests):
        from app import process_url
        result = asyncio.get_event_loop().run_until_complete(
            process_url("https://example.com/photo.jpg")
        )
        self.assertEqual(result["type"], "multimodal")
        block = result["content_blocks"][0]
        self.assertEqual(block["type"], "image_url")
        self.assertEqual(block["image_url"]["url"], "https://example.com/photo.jpg")
        mock_requests.get.assert_not_called()


class TestProcessUrlYouTube(unittest.TestCase):
    """process_url must handle YouTube URLs without downloading."""

    @pytest.mark.network
    def test_youtube_url_returns_video_url_block_with_direct_url(self):
        from app import process_url
        result = asyncio.get_event_loop().run_until_complete(
            process_url("https://www.youtube.com/watch?v=abc123")
        )
        self.assertEqual(result["type"], "multimodal")
        block = result["content_blocks"][0]
        self.assertEqual(block["type"], "video_url")
        self.assertEqual(block["video_url"]["url"], "https://www.youtube.com/watch?v=abc123")


class TestProcessUrlWebpage(unittest.TestCase):
    """process_url must scrape webpage content."""

    @pytest.mark.network
    def test_webpage_url_returns_text_type_with_scraped_content(self):
        from app import process_url
        mock_response = MagicMock()
        mock_response.text = "<html><body><script>evil()</script><p>Hello world</p></body></html>"
        mock_response.status_code = 200
        with patch("app.requests.get", return_value=mock_response):
            result = asyncio.get_event_loop().run_until_complete(
                process_url("https://example.com/article")
            )
        self.assertEqual(result["type"], "text")
        self.assertIn("Hello world", result["text_content"])
        self.assertNotIn("evil()", result["text_content"])


class TestDownloadWithLimit(unittest.TestCase):
    """download_with_limit must enforce size limits."""

    def test_url_exceeds_download_limit_raises_error(self):
        from app import download_with_limit
        mock_response = MagicMock()
        mock_response.iter_content.return_value = [b"x" * 8192] * 10000
        with patch("app.requests.get", return_value=mock_response):
            with self.assertRaises(ValueError):
                download_with_limit("https://example.com/big.mp4", timeout=10)


class TestCheckModelModalitySupport(unittest.TestCase):
    """check_model_modality_support must check model capabilities."""

    @pytest.mark.network
    def test_model_supports_image_returns_true(self):
        from app import check_model_modality_support
        mock_model = {"id": "google/gemini-2.0-flash", "architecture": {"input_modalities": ["text", "image"]}}
        with patch("app.ModelDiscoveryService") as MockDiscovery:
            instance = MockDiscovery.return_value
            instance._fetch_all_models.return_value = [mock_model]
            self.assertTrue(check_model_modality_support("google/gemini-2.0-flash", "image"))

    def test_model_does_not_support_video_returns_false(self):
        from app import check_model_modality_support
        mock_model = {"id": "openai/gpt-4o", "architecture": {"input_modalities": ["text", "image"]}}
        with patch("app.ModelDiscoveryService") as MockDiscovery:
            instance = MockDiscovery.return_value
            instance._fetch_all_models.return_value = [mock_model]
            self.assertFalse(check_model_modality_support("openai/gpt-4o", "video"))

    def test_unknown_model_returns_false(self):
        from app import check_model_modality_support
        with patch("app.ModelDiscoveryService") as MockDiscovery:
            instance = MockDiscovery.return_value
            instance._fetch_all_models.return_value = []
            self.assertFalse(check_model_modality_support("unknown/model", "image"))


class TestProcessAttachmentPdf(unittest.TestCase):
    """process_attachment must handle PDF files."""

    def test_pdf_returns_multimodal_with_file_block_and_plugins(self):
        from app import process_attachment
        url, path, name = _make_test_file(".pdf", b"%PDF-1.4\nfake pdf content\n%%EOF")
        try:
            result = asyncio.get_event_loop().run_until_complete(
                process_attachment(url, name, "application/pdf")
            )
            self.assertEqual(result["type"], "multimodal")
            block = result["content_blocks"][0]
            self.assertEqual(block["type"], "file")
            self.assertIn("file_data", block["file"])
            self.assertIsNotNone(result.get("plugins"))
        finally:
            os.unlink(path)

    def test_pdf_returns_required_modality_pdf(self):
        from app import process_attachment
        url, path, name = _make_test_file(".pdf", b"%PDF-1.4\nfake pdf content\n%%EOF")
        try:
            result = asyncio.get_event_loop().run_until_complete(
                process_attachment(url, name, "application/pdf")
            )
            self.assertEqual(result.get("required_modality"), "pdf")
        finally:
            os.unlink(path)


class TestProcessAttachmentAudio(unittest.TestCase):
    """process_attachment must handle audio files."""

    def test_audio_mp3_returns_multimodal_with_input_audio_block(self):
        from app import process_attachment
        url, path, name = _make_test_file(".mp3", b"ID3\x03\x00fake mp3 data")
        try:
            result = asyncio.get_event_loop().run_until_complete(
                process_attachment(url, name, "audio/mpeg")
            )
            self.assertEqual(result["type"], "multimodal")
            block = result["content_blocks"][0]
            self.assertEqual(block["type"], "input_audio")
            self.assertIn("data", block["input_audio"])
            self.assertEqual(block["input_audio"]["format"], "mp3")
        finally:
            os.unlink(path)

    def test_audio_wav_returns_correct_format_wav(self):
        from app import process_attachment
        url, path, name = _make_test_file(".wav", b"RIFF\x00\x00\x00\x00WAVEfmt fake")
        try:
            result = asyncio.get_event_loop().run_until_complete(
                process_attachment(url, name, "audio/wav")
            )
            self.assertEqual(result["type"], "multimodal")
            block = result["content_blocks"][0]
            self.assertEqual(block["input_audio"]["format"], "wav")
        finally:
            os.unlink(path)

    def test_audio_returns_required_modality_audio(self):
        from app import process_attachment
        url, path, name = _make_test_file(".mp3", b"ID3\x03\x00fake mp3 data")
        try:
            result = asyncio.get_event_loop().run_until_complete(
                process_attachment(url, name, "audio/mpeg")
            )
            self.assertEqual(result.get("required_modality"), "audio")
        finally:
            os.unlink(path)


class TestProcessAttachmentVideo(unittest.TestCase):
    """process_attachment must handle video files."""

    def test_video_mp4_small_returns_multimodal_with_video_url_base64(self):
        from app import process_attachment
        url, path, name = _make_test_file(".mp4", b"\x00\x00\x00\x18ftypmp42 fake video")
        try:
            result = asyncio.get_event_loop().run_until_complete(
                process_attachment(url, name, "video/mp4")
            )
            self.assertEqual(result["type"], "multimodal")
            block = result["content_blocks"][0]
            self.assertEqual(block["type"], "video_url")
            self.assertIn("base64", block["video_url"]["url"])
        finally:
            os.unlink(path)

    def test_video_returns_required_modality_video(self):
        from app import process_attachment
        url, path, name = _make_test_file(".mp4", b"\x00\x00\x00\x18ftypmp42 fake video")
        try:
            result = asyncio.get_event_loop().run_until_complete(
                process_attachment(url, name, "video/mp4")
            )
            self.assertEqual(result.get("required_modality"), "video")
        finally:
            os.unlink(path)


class TestProcessAttachmentDocXlsxSvg(unittest.TestCase):
    """process_attachment must handle DOCX, XLSX, CSV, SVG files."""

    def test_csv_returns_text_type_with_content(self):
        from app import process_attachment
        url, path, name = _make_test_file(".csv", "name,age\nAlice,30\nBob,25", mode="w")
        try:
            result = asyncio.get_event_loop().run_until_complete(
                process_attachment(url, name, "text/csv")
            )
            self.assertEqual(result["type"], "text")
            self.assertIn("Alice", result["text_content"])
            self.assertIn("Bob", result["text_content"])
        finally:
            os.unlink(path)

    def test_svg_returns_text_type_with_xml_content(self):
        from app import process_attachment
        svg_content = '<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg"><circle r="50"/></svg>'
        url, path, name = _make_test_file(".svg", svg_content, mode="w")
        try:
            result = asyncio.get_event_loop().run_until_complete(
                process_attachment(url, name, "image/svg+xml")
            )
            self.assertEqual(result["type"], "text")
            self.assertIn("svg", result["text_content"])
        finally:
            os.unlink(path)

    def test_docx_returns_text_type_with_extracted_paragraphs(self):
        from app import process_attachment
        try:
            from docx import Document
        except ImportError:
            self.skipTest("python-docx not installed")
        url, path, name = _make_test_file(".docx", b"", mode="wb")
        try:
            doc = Document()
            doc.add_paragraph("Hello from DOCX")
            doc.add_paragraph("Second paragraph")
            doc.save(path)
            result = asyncio.get_event_loop().run_until_complete(
                process_attachment(url, name, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
            )
            self.assertEqual(result["type"], "text")
            self.assertIn("Hello from DOCX", result["text_content"])
        finally:
            os.unlink(path)

    def test_xlsx_returns_text_type_with_extracted_rows(self):
        from app import process_attachment
        try:
            from openpyxl import Workbook
        except ImportError:
            self.skipTest("openpyxl not installed")
        url, path, name = _make_test_file(".xlsx", b"", mode="wb")
        try:
            wb = Workbook()
            ws = wb.active
            ws.append(["Name", "Score"])
            ws.append(["Alice", 95])
            wb.save(path)
            result = asyncio.get_event_loop().run_until_complete(
                process_attachment(url, name, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            )
            self.assertEqual(result["type"], "text")
            self.assertIn("Alice", result["text_content"])
            self.assertIn("95", result["text_content"])
        finally:
            os.unlink(path)


class TestProcessUrlPdf(unittest.TestCase):
    """process_url must handle PDF URLs."""

    def test_pdf_url_returns_file_block_with_direct_url_and_plugins(self):
        from app import process_url
        result = asyncio.get_event_loop().run_until_complete(
            process_url("https://example.com/doc.pdf")
        )
        self.assertEqual(result["type"], "multimodal")
        block = result["content_blocks"][0]
        self.assertEqual(block["type"], "file")
        self.assertIsNotNone(result.get("plugins"))


class TestProcessUrlAudio(unittest.TestCase):
    """process_url must handle audio URLs."""

    def test_audio_url_downloads_and_returns_input_audio_block(self):
        from app import process_url
        mock_response = MagicMock()
        mock_response.iter_content.return_value = [b"fake mp3 audio data"]
        mock_response.raise_for_status = MagicMock()
        with patch("app.requests.get", return_value=mock_response):
            result = asyncio.get_event_loop().run_until_complete(
                process_url("https://example.com/audio.mp3")
            )
        self.assertEqual(result["type"], "multimodal")
        block = result["content_blocks"][0]
        self.assertEqual(block["type"], "input_audio")


class TestProcessUrlVideo(unittest.TestCase):
    """process_url must handle video URLs."""

    def test_video_url_small_downloads_and_returns_base64(self):
        from app import process_url
        mock_response = MagicMock()
        mock_response.iter_content.return_value = [b"\x00\x00\x00\x18ftypmp42 fake video"]
        mock_response.raise_for_status = MagicMock()
        with patch("app.requests.get", return_value=mock_response):
            result = asyncio.get_event_loop().run_until_complete(
                process_url("https://example.com/video.mp4")
            )
        self.assertEqual(result["type"], "multimodal")
        block = result["content_blocks"][0]
        self.assertEqual(block["type"], "video_url")

    def test_video_url_large_returns_metadata(self):
        from app import process_url
        mock_response = MagicMock()
        mock_response.iter_content.return_value = [b"x" * (21 * 1024 * 1024)]
        mock_response.raise_for_status = MagicMock()
        with patch("app.requests.get", return_value=mock_response):
            with patch("app.MAX_URL_DOWNLOAD_SIZE", 100 * 1024 * 1024):
                result = asyncio.get_event_loop().run_until_complete(
                    process_url("https://example.com/bigvideo.mp4")
                )
        self.assertEqual(result["type"], "metadata")


class TestProcessUrlErrorHandling(unittest.TestCase):
    """process_url must handle errors gracefully."""

    def test_url_download_404_returns_metadata_with_error(self):
        from app import process_url
        mock_response = MagicMock()
        import requests as _requests
        mock_response.raise_for_status.side_effect = _requests.HTTPError("404 Not Found")
        with patch("app.requests.get", return_value=mock_response):
            result = asyncio.get_event_loop().run_until_complete(
                process_url("https://example.com/audio.mp3")
            )
        self.assertEqual(result["type"], "metadata")
        self.assertIn("failed", result["context_text"].lower())

    def test_localhost_url_rejected_for_ssrf_protection(self):
        from app import process_url
        result = asyncio.get_event_loop().run_until_complete(
            process_url("http://192.168.1.1/secret")
        )
        self.assertEqual(result["type"], "metadata")
        self.assertIn("rejected", result["context_text"].lower())

    @pytest.mark.network
    def test_webpage_url_strips_script_and_style_tags(self):
        from app import process_url
        mock_response = MagicMock()
        mock_response.text = "<html><head><style>body{color:red}</style></head><body><script>alert(1)</script><p>Safe content</p></body></html>"
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        with patch("app.requests.get", return_value=mock_response):
            result = asyncio.get_event_loop().run_until_complete(
                process_url("https://example.com/article")
            )
        self.assertEqual(result["type"], "text")
        self.assertIn("Safe content", result["text_content"])
        self.assertNotIn("alert", result["text_content"])
        self.assertNotIn("color:red", result["text_content"])


class TestIntegration(unittest.TestCase):
    """Integration tests for attachment + URL processing in on_message context."""

    def test_url_in_message_detected_and_processed(self):
        from app import classify_url, URL_REGEX
        import re
        msg = "Check this out https://example.com/photo.jpg and also https://youtu.be/abc"
        urls = re.findall(URL_REGEX, msg)
        self.assertEqual(len(urls), 2)
        self.assertEqual(classify_url(urls[0]), "image")
        self.assertEqual(classify_url(urls[1]), "youtube")

    def test_attachment_and_url_in_same_message_both_processed(self):
        from app import process_attachment, process_url
        url, path, name = _make_test_file(".png", b"\x89PNG\r\n\x1a\n fake png data")
        try:
            attach_result = asyncio.get_event_loop().run_until_complete(
                process_attachment(url, name, "image/png")
            )
            url_result = asyncio.get_event_loop().run_until_complete(
                process_url("https://example.com/doc.pdf")
            )
            self.assertEqual(attach_result["type"], "multimodal")
            self.assertEqual(url_result["type"], "multimodal")
            self.assertNotEqual(attach_result["content_blocks"][0]["type"],
                               url_result["content_blocks"][0]["type"])
        finally:
            os.unlink(path)

    def test_follow_up_message_does_not_include_base64_in_history(self):
        from app import process_attachment
        url, path, name = _make_test_file(".png", b"\x89PNG\r\n\x1a\n fake png data")
        try:
            result = asyncio.get_event_loop().run_until_complete(
                process_attachment(url, name, "image/png")
            )
            context_text = result["context_text"]
            self.assertIn("[Image:", context_text)
            self.assertNotIn("base64", context_text)
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()

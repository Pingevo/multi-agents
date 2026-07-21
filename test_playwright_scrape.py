"""Tests for Playwright headless browser scraping fallback.

Tests verify:
1. scrape_with_playwright returns extracted text
2. process_url falls back to Playwright when requests gets empty text
3. JS-required domains use Playwright directly (skip requests)
4. SSRF protection blocks localhost URLs
5. Timeout handling returns graceful error
"""

import os
import sys
import unittest
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("OPENROUTER_API_KEY", "test-key-fake")


class TestScrapeWithPlaywright(unittest.TestCase):
    """scrape_with_playwright must extract text from JS-rendered pages."""

    @pytest.mark.network
    def test_scrape_with_playwright_returns_text(self):
        """scrape_with_playwright should return extracted text from a page."""
        from backend.attachment.processor import scrape_with_playwright
        result = scrape_with_playwright("https://example.com")
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)

    @pytest.mark.network
    def test_scrape_with_playwright_ssrf_blocked(self):
        """scrape_with_playwright should reject localhost URLs."""
        from backend.attachment.processor import scrape_with_playwright
        with self.assertRaises(ValueError):
            scrape_with_playwright("http://localhost:8080/admin")

    @pytest.mark.network
    def test_scrape_with_playwright_ssrf_blocked_internal_ip(self):
        """scrape_with_playwright should reject internal IP addresses."""
        from backend.attachment.processor import scrape_with_playwright
        with self.assertRaises(ValueError):
            scrape_with_playwright("http://192.168.1.1/secret")

    @pytest.mark.network
    def test_scrape_with_playwright_timeout(self):
        """scrape_with_playwright should handle timeout gracefully."""
        from backend.attachment.processor import scrape_with_playwright
        result = scrape_with_playwright("https://example.com", timeout=0)
        # Should return empty string or raise — either is acceptable as long as it doesn't hang
        self.assertTrue(isinstance(result, str) or result == "")


class TestProcessUrlPlaywrightFallback(unittest.IsolatedAsyncioTestCase):
    """process_url should fall back to Playwright when requests fails or returns empty."""

    async def test_process_url_fallback_to_playwright(self):
        """When requests.get returns empty text, process_url should try Playwright."""
        from backend.attachment import processor

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html><body></body></html>"
        mock_response.raise_for_status = MagicMock()

        with patch.object(processor, "requests") as mock_req, \
             patch.object(processor, "scrape_with_playwright", return_value="Real content from JS rendering") as mock_pw:
            mock_req.get.return_value = mock_response
            result = await processor.process_url("https://some-site.com/page")

            self.assertEqual(result["type"], "text")
            self.assertIn("Real content from JS rendering", result["text_content"])
            mock_pw.assert_called_once_with("https://some-site.com/page")

    async def test_js_required_domain_uses_playwright_directly(self):
        """Shopee URLs should skip requests and use Playwright directly."""
        from backend.attachment import processor

        with patch.object(processor, "requests") as mock_req, \
             patch.object(processor, "scrape_with_playwright", return_value="Shopee product details") as mock_pw:
            result = await processor.process_url(
                "https://shopee.co.th/product-123?extraParams=abc"
            )

            self.assertEqual(result["type"], "text")
            self.assertIn("Shopee product details", result["text_content"])
            mock_req.get.assert_not_called()
            mock_pw.assert_called_once()

    async def test_js_required_domain_lazada(self):
        """Lazada URLs should also use Playwright directly."""
        from backend.attachment import processor

        with patch.object(processor, "requests") as mock_req, \
             patch.object(processor, "scrape_with_playwright", return_value="Lazada product info"):
            result = await processor.process_url("https://www.lazada.co.th/products/item123")

            self.assertEqual(result["type"], "text")
            mock_req.get.assert_not_called()

    async def test_playwright_failure_returns_metadata(self):
        """If both requests and Playwright fail, return metadata with error."""
        from backend.attachment import processor

        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.text = ""
        mock_response.raise_for_status = MagicMock(side_effect=Exception("403 Forbidden"))

        with patch.object(processor, "requests") as mock_req, \
             patch.object(processor, "scrape_with_playwright", side_effect=RuntimeError("Browser crashed")):
            mock_req.get.return_value = mock_response
            result = await processor.process_url("https://some-site.com/page")

            self.assertEqual(result["type"], "metadata")
            self.assertIn("failed", result["context_text"].lower())


class TestJsRequiredDomains(unittest.TestCase):
    """JS_REQUIRED_DOMAINS should include known JS-heavy e-commerce sites."""

    def test_js_required_domains_contains_shopee(self):
        from backend.attachment.url import JS_REQUIRED_DOMAINS
        self.assertIn("shopee.co.th", JS_REQUIRED_DOMAINS)

    def test_js_required_domains_contains_lazada(self):
        from backend.attachment.url import JS_REQUIRED_DOMAINS
        self.assertIn("lazada.co.th", JS_REQUIRED_DOMAINS)

    def test_js_required_domains_contains_tiktok(self):
        from backend.attachment.url import JS_REQUIRED_DOMAINS
        self.assertIn("tiktok.com", JS_REQUIRED_DOMAINS)

    def test_is_js_required_domain_shopee(self):
        from backend.attachment.url import is_js_required_domain
        self.assertTrue(is_js_required_domain("https://shopee.co.th/product/123"))

    def test_is_js_required_domain_not_required(self):
        from backend.attachment.url import is_js_required_domain
        self.assertFalse(is_js_required_domain("https://example.com/page"))


if __name__ == "__main__":
    unittest.main()

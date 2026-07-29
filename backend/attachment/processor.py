"""Attachment processing: file upload + URL processing pipeline."""

import base64
import io
import os
import re
import requests
from backend.utils import _sanitize_error
from backend.attachment.security import check_model_modality_support, llm_manager_tier_check
from backend.attachment.url import classify_url, download_with_limit, MAX_TEXT_LENGTH, AUDIO_FORMAT_MAP, _is_localhost_url, is_js_required_domain
from backend.globals import DATA_DIR

_VIDEO_MIME_MAP = {
    ".mp4": "video/mp4", ".mov": "video/quicktime",
    ".webm": "video/webm", ".mpeg": "video/mpeg", ".mpg": "video/mpeg",
}

def _video_mime_from_url(url: str) -> str:
    url_lower = url.lower().split("?")[0]
    for ext, mime in _VIDEO_MIME_MAP.items():
        if url_lower.endswith(ext):
            return mime
    return "video/mp4"

def _resolve_file_path(file_url: str, user_id: str | None = None) -> str:
    """Convert attachment URL to local file path.

    Handles both new /api/media/ URLs (per-user isolation) and legacy /public/ URLs.
    """
    _PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    # Per-user isolation: /api/media/ URLs resolve to data/users/{uid}/ directory
    if file_url.startswith("/api/media/") or (file_url.startswith("http") and "/api/media/" in file_url):
        if user_id:
            from urllib.parse import urlparse
            if file_url.startswith("http"):
                parsed = urlparse(file_url)
                path = parsed.path.lstrip("/")
            else:
                path = file_url.lstrip("/")
            # path is like "api/media/attachments/filename" or "api/media/generated/filename"
            # strip "api/media/" prefix and join with data/users/{uid}/
            relative = path.replace("api/media/", "", 1)
            return os.path.join(DATA_DIR, "users", user_id, relative)
        # Fallback: no user_id — shouldn't happen for new URLs, but resolve via project root
        if file_url.startswith("http"):
            from urllib.parse import urlparse
            parsed = urlparse(file_url)
            return os.path.join(_PROJECT_ROOT, parsed.path.lstrip("/"))
        return os.path.join(_PROJECT_ROOT, file_url.lstrip("/"))
    # Legacy /public/ URLs — resolve from project root (backward compat)
    if file_url.startswith("http"):
        from urllib.parse import urlparse
        parsed = urlparse(file_url)
        return os.path.join(_PROJECT_ROOT, parsed.path.lstrip("/"))
    return os.path.join(_PROJECT_ROOT, file_url.lstrip("/"))


def _extract_text_content(file_path: str, file_mime: str) -> str:
    """Extract text from text-based files."""
    if file_mime == "application/pdf":
        try:
            import pdfplumber
            with pdfplumber.open(file_path) as pdf:
                text = "\n".join(page.extract_text() or "" for page in pdf.pages)
                return text[:MAX_TEXT_LENGTH] + ("[...truncated]" if len(text) > MAX_TEXT_LENGTH else "")
        except Exception as e:
            print(f"[ATTACHMENT] PDF text extraction failed: {_sanitize_error(e)}", flush=True)
            return ""

    if file_mime == "application/vnd.openxmlformats-officedocument.wordprocessingml.document" or file_path.endswith(".docx"):
        try:
            from docx import Document
            doc = Document(file_path)
            text = "\n".join(p.text for p in doc.paragraphs)
            return text[:MAX_TEXT_LENGTH] + ("[...truncated]" if len(text) > MAX_TEXT_LENGTH else "")
        except Exception as e:
            print(f"[ATTACHMENT] DOCX extraction failed: {_sanitize_error(e)}", flush=True)
            return ""

    if file_mime == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" or file_path.endswith(".xlsx"):
        try:
            from openpyxl import load_workbook
            wb = load_workbook(file_path, read_only=True)
            text_parts = []
            for ws in wb.worksheets:
                for row in ws.iter_rows(values_only=True):
                    text_parts.append("\t".join(str(c) if c is not None else "" for c in row))
            wb.close()
            text = "\n".join(text_parts)
            return text[:MAX_TEXT_LENGTH] + ("[...truncated]" if len(text) > MAX_TEXT_LENGTH else "")
        except Exception as e:
            print(f"[ATTACHMENT] XLSX extraction failed: {_sanitize_error(e)}", flush=True)
            return ""

    # PPTX extraction — python-pptx reads slides and speaker notes
    if file_mime == "application/vnd.openxmlformats-officedocument.presentationml.presentation" or file_path.endswith(".pptx"):
        try:
            from pptx import Presentation
            prs = Presentation(file_path)
            text_parts = []
            for slide_num, slide in enumerate(prs.slides, 1):
                text_parts.append(f"--- Slide {slide_num} ---")
                for shape in slide.shapes:
                    if shape.has_text_frame:
                        for para in shape.text_frame.paragraphs:
                            text = para.text.strip()
                            if text:
                                text_parts.append(text)
                if slide.has_notes_slide:
                    notes = slide.notes_slide.notes_text_frame.text.strip()
                    if notes:
                        text_parts.append(f"[Notes: {notes}]")
            text = "\n".join(text_parts)
            return text[:MAX_TEXT_LENGTH] + ("[...truncated]" if len(text) > MAX_TEXT_LENGTH else "")
        except Exception as e:
            print(f"[ATTACHMENT] PPTX extraction failed: {_sanitize_error(e)}", flush=True)
            return ""

    # Archive extraction — .zip/.tar/.gz: extract and concatenate text file contents
    # Security: only extract text files (skip binaries), limit total output size
    if file_path.endswith((".zip", ".tar", ".tar.gz", ".tgz")):
        try:
            import tempfile, tarfile, zipfile
            text_parts = []
            total_size = 0
            if file_path.endswith(".zip"):
                with zipfile.ZipFile(file_path, 'r') as zf:
                    for info in zf.infolist():
                        if info.is_dir() or info.file_size > 1024 * 1024:
                            continue
                        # Only extract text-like files to avoid binary noise
                        if not info.filename.lower().endswith((
                            ".txt", ".csv", ".json", ".xml", ".md", ".py", ".js",
                            ".ts", ".html", ".css", ".yaml", ".yml", ".sh", ".sql",
                            ".ini", ".cfg", ".svg", ".log",
                        )):
                            continue
                        try:
                            data = zf.read(info)
                            decoded = data.decode("utf-8", errors="replace")
                            text_parts.append(f"--- {info.filename} ---\n{decoded}")
                            total_size += len(decoded)
                            if total_size > MAX_TEXT_LENGTH:
                                break
                        except Exception:
                            continue
            else:  # .tar / .tar.gz
                with tarfile.open(file_path, 'r:*') as tf:
                    for member in tf.getmembers():
                        if not member.isfile() or member.size > 1024 * 1024:
                            continue
                        if not member.name.lower().endswith((
                            ".txt", ".csv", ".json", ".xml", ".md", ".py", ".js",
                            ".ts", ".html", ".css", ".yaml", ".yml", ".sh", ".sql",
                            ".ini", ".cfg", ".svg", ".log",
                        )):
                            continue
                        try:
                            f = tf.extractfile(member)
                            if f:
                                decoded = f.read().decode("utf-8", errors="replace")
                                text_parts.append(f"--- {member.name} ---\n{decoded}")
                                total_size += len(decoded)
                                if total_size > MAX_TEXT_LENGTH:
                                    break
                        except Exception:
                            continue
            text = "\n\n".join(text_parts)
            if text:
                return text[:MAX_TEXT_LENGTH] + ("[...truncated]" if len(text) > MAX_TEXT_LENGTH else "")
            return ""
        except Exception as e:
            print(f"[ATTACHMENT] Archive extraction failed: {_sanitize_error(e)}", flush=True)
            return ""

    # Default: read as text
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
        return text[:MAX_TEXT_LENGTH] + ("[...truncated]" if len(text) > MAX_TEXT_LENGTH else "")
    except Exception as e:
        print(f"[ATTACHMENT] Text read failed: {_sanitize_error(e)}", flush=True)
        return ""


async def scrape_with_playwright(url: str, timeout: int = 30) -> str:
    """Scrape a URL using headless Chromium (Playwright async API).

    Used as fallback for JS-heavy sites that block requests.get().
    Returns extracted text (max MAX_TEXT_LENGTH chars).
    Raises ValueError for SSRF-blocked URLs.
    """
    if _is_localhost_url(url):
        raise ValueError(f"SSRF blocked: {url}")

    from playwright.async_api import async_playwright
    try:
        from playwright_stealth import stealth_async
    except ImportError:
        stealth_async = None

    async with async_playwright() as p:
        browser = None
        for channel in ["chrome", None]:
            try:
                launch_kwargs = {"headless": True}
                if channel:
                    launch_kwargs["channel"] = channel
                browser = await p.chromium.launch(**launch_kwargs)
                break
            except Exception:
                continue
        if browser is None:
            raise RuntimeError("Could not launch any browser (Chrome or Chromium)")
        try:
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080},
                locale="en-US",
            )
            page = await context.new_page()
            if stealth_async:
                await stealth_async(page)
            await page.goto(url, wait_until="domcontentloaded", timeout=timeout * 1000)
            try:
                await page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                pass
            await page.evaluate("""() => {
                document.querySelectorAll('script, style, nav, footer, header, noscript').forEach(el => el.remove());
            }""")
            text = await page.inner_text("body")
            text = text[:MAX_TEXT_LENGTH] + ("[...truncated]" if len(text) > MAX_TEXT_LENGTH else "")
            return text
        finally:
            await browser.close()


async def process_attachment(file_url: str, file_name: str, file_mime: str, user_id: str | None = None) -> dict:
    """Process an uploaded file and return AI-consumable context.

    Returns:
        {
            "type": "multimodal" | "text" | "metadata",
            "content_blocks": list[dict],
            "plugins": list[dict] | None,
            "crewai_files": dict | None,
            "text_content": str,
            "context_text": str,
            "required_modality": str | None,
            "file_name": str,
            "file_mime": str,
        }
    """
    file_path = _resolve_file_path(file_url, user_id=user_id)

    if not os.path.exists(file_path):
        print(f"[ATTACHMENT] File not found: {file_path}", flush=True)
        return {
            "type": "metadata",
            "content_blocks": [],
            "plugins": None,
            "crewai_files": None,
            "text_content": "",
            "context_text": f"[Attachment: {file_name} — file not found]",
            "required_modality": None,
            "file_name": file_name,
            "file_mime": file_mime,
        }

    # --- Image ---
    if file_mime.startswith("image/") and not file_mime == "image/svg+xml":
        try:
            with open(file_path, "rb") as f:
                file_bytes = f.read()
            b64 = base64.b64encode(file_bytes).decode("utf-8")
            data_url = f"data:{file_mime};base64,{b64}"
            crewai_files = {}
            try:
                from crewai_files import ImageFile
                crewai_files = {"image": ImageFile(source=file_path)}
            except ImportError:
                pass
            return {
                "type": "multimodal",
                "content_blocks": [{"type": "image_url", "image_url": {"url": data_url}}],
                "plugins": None,
                "crewai_files": crewai_files or None,
                "text_content": "",
                "context_text": f"[Image: {file_name}]",
                "required_modality": "image",
                "file_name": file_name,
                "file_mime": file_mime,
            }
        except Exception as e:
            print(f"[ATTACHMENT] Image processing failed: {_sanitize_error(e)}", flush=True)

    # --- PDF ---
    if file_mime == "application/pdf":
        try:
            with open(file_path, "rb") as f:
                file_bytes = f.read()
            b64 = base64.b64encode(file_bytes).decode("utf-8")
            data_url = f"data:application/pdf;base64,{b64}"

            # Extract text as fallback/ supplement
            extracted_text = _extract_text_content(file_path, file_mime)

            # Build text_content: extracted text + OpenRouter data URL
            # OpenRouter accepts data:application/pdf;base64,... in message content
            # with plugins: [{id: "file-parser", pdf: {engine: "mistral-ocr"}}] in request body
            text_parts = []
            if extracted_text:
                text_parts.append(f"[PDF text content: {file_name}]\n{extracted_text}")
            text_parts.append(f"[PDF file for multimodal processing: {data_url}]")
            combined_text = "\n\n".join(text_parts)

            return {
                "type": "multimodal",
                "content_blocks": [{"type": "file", "file": {"filename": file_name, "file_data": data_url}}],
                "plugins": [{"id": "file-parser", "pdf": {"engine": "mistral-ocr"}}],
                "crewai_files": None,  # Don't use CrewAI input_files — bypass to OpenRouter format
                "text_content": combined_text,
                "context_text": f"[PDF: {file_name}]",
                "required_modality": "pdf",
                "file_name": file_name,
                "file_mime": file_mime,
            }
        except Exception as e:
            print(f"[ATTACHMENT] PDF processing failed: {_sanitize_error(e)}, falling back to text", flush=True)
            text = _extract_text_content(file_path, file_mime)
            if text:
                return {
                    "type": "text",
                    "content_blocks": [],
                    "plugins": None,
                    "crewai_files": None,
                    "text_content": text,
                    "context_text": f"[PDF text: {file_name}]",
                    "required_modality": None,
                    "file_name": file_name,
                    "file_mime": file_mime,
                }

    # --- Audio ---
    if file_mime.startswith("audio/"):
        try:
            with open(file_path, "rb") as f:
                file_bytes = f.read()
            b64 = base64.b64encode(file_bytes).decode("utf-8")
            fmt = AUDIO_FORMAT_MAP.get(file_mime, "mp3")
            data_url = f"data:{file_mime};base64,{b64}"
            return {
                "type": "multimodal",
                "content_blocks": [{"type": "input_audio", "input_audio": {"data": b64, "format": fmt}}],
                "plugins": None,
                "crewai_files": None,
                "text_content": f"[Audio for multimodal processing: {data_url}]",
                "context_text": f"[Audio: {file_name}]",
                "required_modality": "audio",
                "file_name": file_name,
                "file_mime": file_mime,
            }
        except Exception as e:
            print(f"[ATTACHMENT] Audio processing failed: {_sanitize_error(e)}", flush=True)

    # --- Video ---
    if file_mime.startswith("video/"):
        try:
            file_size = os.path.getsize(file_path)
            if file_size < 50 * 1024 * 1024:
                with open(file_path, "rb") as f:
                    file_bytes = f.read()
                b64 = base64.b64encode(file_bytes).decode("utf-8")
                data_url = f"data:{file_mime};base64,{b64}"
                return {
                    "type": "multimodal",
                    "content_blocks": [{"type": "video_url", "video_url": {"url": data_url}}],
                    "plugins": None,
                    "crewai_files": None,
                    "text_content": f"[Video for multimodal processing: {data_url}]",
                    "context_text": f"[Video: {file_name}]",
                    "required_modality": "video",
                    "file_name": file_name,
                    "file_mime": file_mime,
                }
            else:
                print(f"[ATTACHMENT] Video too large ({file_size} bytes), metadata only", flush=True)
        except Exception as e:
            print(f"[ATTACHMENT] Video processing failed: {_sanitize_error(e)}", flush=True)

    # --- Text-extractable files ---
    text_extractable = (
        file_mime.startswith("text/") or
        file_mime in ("application/json", "application/xml", "application/csv") or
        file_mime == "image/svg+xml" or
        file_name.endswith((".txt", ".csv", ".json", ".xml", ".svg", ".md",
                            ".py", ".js", ".ts", ".html", ".htm", ".css",
                            ".yaml", ".yml", ".toml", ".sh", ".sql",
                            ".ini", ".cfg", ".bat")) or
        file_name.endswith(".docx") or
        file_name.endswith(".xlsx") or
        file_name.endswith(".pptx") or
        file_name.endswith((".zip", ".tar", ".tar.gz", ".tgz")) or
        file_mime == "application/pdf"  # fallback if multimodal failed
    )
    if text_extractable:
        text = _extract_text_content(file_path, file_mime)
        if text:
            return {
                "type": "text",
                "content_blocks": [],
                "plugins": None,
                "crewai_files": None,
                "text_content": text,
                "context_text": f"[Text file: {file_name}]",
                "required_modality": None,
                "file_name": file_name,
                "file_mime": file_mime,
            }

    # --- Metadata fallback ---
    return {
        "type": "metadata",
        "content_blocks": [],
        "plugins": None,
        "crewai_files": None,
        "text_content": "",
        "context_text": f"[Attachment: {file_name} ({file_mime})]",
        "required_modality": None,
        "file_name": file_name,
        "file_mime": file_mime,
    }


async def process_url(url: str) -> dict:
    """Process a URL and return AI-consumable context (same format as process_attachment)."""
    url_type = classify_url(url)

    if _is_localhost_url(url) and not url.startswith("http://localhost:8000"):
        return {
            "type": "metadata",
            "content_blocks": [],
            "plugins": None,
            "crewai_files": None,
            "text_content": "",
            "context_text": f"[URL rejected for security: {url}]",
            "required_modality": None,
            "file_name": url,
            "file_mime": "",
        }

    if url_type == "youtube":
        # Use Playwright to extract page content (title, description, comments)
        # instead of sending as video_url which most LLMs don't support
        try:
            text = await scrape_with_playwright(url)
            if text and len(text) > 50:
                return {
                    "type": "text",
                    "content_blocks": [],
                    "plugins": None,
                    "crewai_files": None,
                    "text_content": text,
                    "context_text": f"[YouTube page content from {url}]",
                    "required_modality": None,
                    "file_name": url,
                    "file_mime": "",
                }
        except Exception as e:
            print(f"[ATTACHMENT] YouTube Playwright scrape failed: {_sanitize_error(e)}", flush=True)
        # Fallback: return as metadata
        return {
            "type": "metadata",
            "content_blocks": [],
            "plugins": None,
            "crewai_files": None,
            "text_content": "",
            "context_text": f"[YouTube video URL: {url} — could not extract page content]",
            "required_modality": None,
            "file_name": url,
            "file_mime": "",
        }

    if url_type == "image":
        crewai_files = {}
        try:
            from crewai_files import ImageFile
            crewai_files = {"image": ImageFile(source=url)}
        except ImportError:
            pass
        return {
            "type": "multimodal",
            "content_blocks": [{"type": "image_url", "image_url": {"url": url}}],
            "plugins": None,
            "crewai_files": crewai_files or None,
            "text_content": "",
            "context_text": f"[Image URL: {url}]",
            "required_modality": "image",
            "file_name": url,
            "file_mime": "",
        }

    if url_type == "pdf":
        crewai_files = {}
        try:
            from crewai_files import PDFFile
            crewai_files = {"pdf": PDFFile(source=url)}
        except ImportError:
            pass
        return {
            "type": "multimodal",
            "content_blocks": [{"type": "file", "file": {"filename": "document.pdf", "file_data": url}}],
            "plugins": [{"id": "file-parser", "pdf": {"engine": "cloudflare-ai"}}],
            "crewai_files": crewai_files or None,
            "text_content": "",
            "context_text": f"[PDF URL: {url}]",
            "required_modality": "pdf",
            "file_name": url,
            "file_mime": "",
        }

    if url_type == "audio":
        try:
            audio_bytes = download_with_limit(url, timeout=30)
            b64 = base64.b64encode(audio_bytes).decode("utf-8")
            content_type = ""
            url_lower = url.lower().split("?")[0]
            for ext, fmt in [(".mp3", "mp3"), (".wav", "wav"), (".flac", "flac"),
                             (".ogg", "ogg"), (".m4a", "m4a"), (".aac", "aac")]:
                if url_lower.endswith(ext):
                    fmt_key = f"audio/{fmt}"
                    fmt = AUDIO_FORMAT_MAP.get(fmt_key, fmt)
                    break
            crewai_files = {}
            try:
                from crewai_files import AudioFile
                crewai_files = {"audio": AudioFile(source=url)}
            except ImportError:
                pass
            return {
                "type": "multimodal",
                "content_blocks": [{"type": "input_audio", "input_audio": {"data": b64, "format": fmt}}],
                "plugins": None,
                "crewai_files": crewai_files or None,
                "text_content": "",
                "context_text": f"[Audio URL: {url}]",
                "required_modality": "audio",
                "file_name": url,
                "file_mime": "",
            }
        except Exception as e:
            print(f"[ATTACHMENT] Audio URL download failed: {_sanitize_error(e)}", flush=True)
            return {
                "type": "metadata",
                "content_blocks": [],
                "plugins": None,
                "crewai_files": None,
                "text_content": "",
                "context_text": f"[Audio URL failed: {url} — {_sanitize_error(e)}]",
                "required_modality": None,
                "file_name": url,
                "file_mime": "",
            }

    if url_type == "video":
        try:
            video_bytes = download_with_limit(url, timeout=60)
            if len(video_bytes) < 50 * 1024 * 1024:
                b64 = base64.b64encode(video_bytes).decode("utf-8")
                crewai_files = {}
                try:
                    from crewai_files import VideoFile
                    crewai_files = {"video": VideoFile(source=url)}
                except ImportError:
                    pass
                return {
                    "type": "multimodal",
                    "content_blocks": [{"type": "video_url", "video_url": {"url": f"data:{_video_mime_from_url(url)};base64,{b64}"}}],
                    "plugins": None,
                    "crewai_files": crewai_files or None,
                    "text_content": "",
                    "context_text": f"[Video URL: {url}]",
                    "required_modality": "video",
                    "file_name": url,
                    "file_mime": "",
                }
            else:
                return {
                    "type": "metadata",
                    "content_blocks": [],
                    "plugins": None,
                    "crewai_files": None,
                    "text_content": "",
                    "context_text": f"[Video URL too large: {url}]",
                    "required_modality": None,
                    "file_name": url,
                    "file_mime": "",
                }
        except Exception as e:
            print(f"[ATTACHMENT] Video URL download failed: {_sanitize_error(e)}", flush=True)
            return {
                "type": "metadata",
                "content_blocks": [],
                "plugins": None,
                "crewai_files": None,
                "text_content": "",
                "context_text": f"[Video URL failed: {url} — {_sanitize_error(e)}]",
                "required_modality": None,
                "file_name": url,
                "file_mime": "",
            }

    # --- Document/Code/Archive URLs ---
    if url_type in ("docx", "xlsx", "pptx", "code", "archive"):
        try:
            content_bytes = download_with_limit(url)
            import tempfile
            url_lower = url.lower().split("?")[0]
            ext = os.path.splitext(url_lower)[1] or ".txt"
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                tmp.write(content_bytes)
                tmp_path = tmp.name
            try:
                text = _extract_text_content(tmp_path, "application/octet-stream")
                if not text:
                    text = _extract_text_content(tmp_path, "")
            finally:
                os.unlink(tmp_path)
            if text:
                return {
                    "type": "text",
                    "content_blocks": [],
                    "plugins": None,
                    "crewai_files": None,
                    "text_content": text,
                    "context_text": f"[{url_type.title()} from {url}]",
                    "required_modality": None,
                    "file_name": url,
                    "file_mime": "",
                }
        except Exception as e:
            print(f"[ATTACHMENT] {url_type} URL download failed: {_sanitize_error(e)}", flush=True)
            # Fall through to webpage scraping as fallback

    # --- Webpage ---
    if url_type == "webpage":
        text = ""
        scrape_error = None

        # Step 1: Try requests.get + BeautifulSoup (skip for JS-required domains)
        if not is_js_required_domain(url):
            try:
                response = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
                response.raise_for_status()
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(response.text, "html.parser")
                for tag in soup(["script", "style", "nav", "footer", "header"]):
                    tag.decompose()
                text = soup.get_text(separator="\n", strip=True)
                text = text[:MAX_TEXT_LENGTH] + ("[...truncated]" if len(text) > MAX_TEXT_LENGTH else "")
            except Exception as e:
                scrape_error = _sanitize_error(e)
                print(f"[ATTACHMENT] Webpage requests scrape failed: {scrape_error}", flush=True)

        # Step 2: Fallback to Playwright if text is too short or JS-required domain
        if len(text) < 500:
            try:
                print(f"[ATTACHMENT] Trying Playwright for {url}", flush=True)
                text = await scrape_with_playwright(url)
                print(f"[ATTACHMENT] Playwright scrape success: {len(text)} chars", flush=True)
            except Exception as e:
                pw_error = _sanitize_error(e)
                print(f"[ATTACHMENT] Playwright scrape failed: {pw_error}", flush=True)
                if not text:
                    scrape_error = pw_error

        # Step 3: Return result
        if text and len(text) > 0:
            return {
                "type": "text",
                "content_blocks": [],
                "plugins": None,
                "crewai_files": None,
                "text_content": text,
                "context_text": f"[Webpage content from {url}]",
                "required_modality": None,
                "file_name": url,
                "file_mime": "",
            }
        else:
            error_msg = scrape_error or "No text content extracted"
            return {
                "type": "metadata",
                "content_blocks": [],
                "plugins": None,
                "crewai_files": None,
                "text_content": "",
                "context_text": f"[Webpage URL failed: {url} — {error_msg}]",
                "required_modality": None,
                "file_name": url,
                "file_mime": "",
            }

    return {
        "type": "metadata",
        "content_blocks": [],
        "plugins": None,
        "crewai_files": None,
        "text_content": "",
        "context_text": f"[Unknown URL type: {url}]",
        "required_modality": None,
        "file_name": url,
        "file_mime": "",
    }




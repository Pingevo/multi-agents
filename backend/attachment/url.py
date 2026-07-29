"""URL classification, download, and SSRF utilities."""

import requests
from urlextract import URLExtract

URL_REGEX = r'https?://[^\s<>"{}|\\^`]+'

_extractor = URLExtract()


def find_urls_in_text(text: str) -> list[str]:
    """Extract URLs from text using urlextract — handles typos and missing protocols."""
    from urllib.parse import urlparse
    urls = _extractor.find_urls(text)
    normalized = []
    for url in urls:
        parsed = urlparse(url)
        if parsed.scheme in ('http', 'https'):
            normalized.append(url)
        elif parsed.scheme and parsed.netloc:
            # Has a scheme but not http/https (e.g. ttps, htps, ftp) — replace with https
            normalized.append('https://' + parsed.netloc + parsed.path + ('?' + parsed.query if parsed.query else '') + ('#' + parsed.fragment if parsed.fragment else ''))
        elif parsed.netloc:
            # No scheme — prepend https://
            normalized.append('https://' + url)
        else:
            normalized.append('https://' + url)
    return normalized

MAX_TEXT_LENGTH = 50000
MAX_URL_DOWNLOAD_SIZE = 50 * 1024 * 1024  # 50MB

AUDIO_FORMAT_MAP = {
    "audio/wav": "wav", "audio/x-wav": "wav",
    "audio/mpeg": "mp3", "audio/mp3": "mp3",
    "audio/flac": "flac",
    "audio/mp4": "m4a", "audio/x-m4a": "m4a",
    "audio/ogg": "ogg",
    "audio/webm": "webm",
    "audio/aac": "aac",
}

URL_EXT_MAP = {
    ".jpg": "image", ".jpeg": "image", ".png": "image", ".webp": "image", ".gif": "image",
    ".pdf": "pdf",
    ".mp3": "audio", ".wav": "audio", ".flac": "audio", ".ogg": "audio",
    ".m4a": "audio", ".aac": "audio",
    ".mp4": "video", ".mov": "video", ".webm": "video", ".mpeg": "video",
    ".docx": "docx", ".xlsx": "xlsx", ".pptx": "pptx",
    ".py": "code", ".js": "code", ".ts": "code", ".html": "code", ".htm": "code",
    ".css": "code", ".yaml": "code", ".yml": "code", ".toml": "code",
    ".sh": "code", ".sql": "code", ".ini": "code", ".cfg": "code",
    ".json": "code", ".csv": "code", ".md": "code", ".txt": "code",
    ".zip": "archive", ".tar": "archive", ".gz": "archive", ".7z": "archive",
}

def classify_url(url: str) -> str:
    """Classify URL into type: youtube, image, pdf, audio, video, webpage."""
    if "youtube.com/watch" in url or "youtu.be/" in url:
        return "youtube"
    url_lower = url.lower().split("?")[0]
    for ext, ftype in URL_EXT_MAP.items():
        if url_lower.endswith(ext):
            return ftype
    return "webpage"


JS_REQUIRED_DOMAINS = [
    "shopee.co.th",
    "shopee.com",
    "lazada.co.th",
    "lazada.com",
    "tiktok.com",
    "amazon.com",
    "amazon.co.th",
]


def is_js_required_domain(url: str) -> bool:
    """Check if URL domain is known to require JavaScript rendering."""
    from urllib.parse import urlparse
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    for domain in JS_REQUIRED_DOMAINS:
        if host == domain or host.endswith("." + domain):
            return True
    return False


def _is_localhost_url(url: str) -> bool:
    """Check if URL points to localhost or internal IP (SSRF protection)."""
    from urllib.parse import urlparse
    parsed = urlparse(url)
    host = parsed.hostname or ""
    if host in ("localhost", "127.0.0.1", "0.0.0.0", "::1"):
        return True
    if host.startswith("10.") or host.startswith("192.168.") or host.startswith("172.16."):
        return True
    return False


def download_with_limit(url: str, timeout: int = 30) -> bytes:
    """Download URL content with size limit. Raises ValueError if exceeds MAX_URL_DOWNLOAD_SIZE."""
    response = requests.get(
        url, timeout=timeout, stream=True,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    response.raise_for_status()
    content = b""
    for chunk in response.iter_content(chunk_size=8192):
        content += chunk
        if len(content) > MAX_URL_DOWNLOAD_SIZE:
            raise ValueError(
                f"URL content exceeds {MAX_URL_DOWNLOAD_SIZE // 1024 // 1024}MB limit"
            )
    return content




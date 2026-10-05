"""
Deep Webpage Scanner for Universal Media Extraction.
Curls and scans arbitrary websites, embedded iframes, and modern JavaScript players
to uncover hidden HLS (.m3u8), DASH (.mpd), and direct video streams.
"""
import html
import re
import urllib.parse
from typing import Any, Dict, List, Optional
try:
    from curl_cffi import requests as curl_requests
    HAS_CURL_CFFI = True
except ImportError:
    import requests as curl_requests  # type: ignore
    HAS_CURL_CFFI = False


DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# Common stream patterns
M3U8_PATTERN = re.compile(
    r'(https?:\\?/\\?/[^\s"\'<>]+\.m3u8(?:[^\s"\'<>]*))', re.IGNORECASE
)
MPD_PATTERN = re.compile(
    r'(https?:\\?/\\?/[^\s"\'<>]+\.mpd(?:[^\s"\'<>]*))', re.IGNORECASE
)
DIRECT_VIDEO_PATTERN = re.compile(
    r'(https?:\\?/\\?/[^\s"\'<>]+\.(?:mp4|webm|mkv|mov)(?:[^\s"\'<>]*))', re.IGNORECASE
)

# Player configuration regexes
JS_PLAYER_SRC = re.compile(
    r'(?:file|source|src|url|videoUrl)\s*:\s*["\'](https?:\\?/\\?/[^"\']+)["\']', re.IGNORECASE
)
HLS_LOAD_SRC = re.compile(
    r'(?:hls\.loadSource|player\.src)\s*\(\s*["\'](https?:\\?/\\?/[^"\']+)["\']', re.IGNORECASE
)
IFRAME_PATTERN = re.compile(
    r'<iframe[^>]+src=["\']([^"\']+)["\']', re.IGNORECASE
)


def _sanitize_url(url: str) -> str:
    """Unescape JSON-escaped slashes and HTML entities."""
    clean = url.replace(r'\/', '/').replace(r'\u0026', '&')
    clean = html.unescape(clean)
    return clean.strip()


def _extract_page_metadata(html_text: str, base_url: str) -> Dict[str, str]:
    """Extract page title and thumbnail from HTML metadata."""
    title = ""
    thumb = ""

    # OpenGraph title
    og_title = re.search(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']', html_text, re.I)
    if not og_title:
        og_title = re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:title["\']', html_text, re.I)

    if og_title:
        title = html.unescape(og_title.group(1))
    else:
        title_match = re.search(r'<title[^>]*>(.*?)</title>', html_text, re.I | re.S)
        if title_match:
            title = html.unescape(re.sub(r'\s+', ' ', title_match.group(1)).strip())

    # OpenGraph image / thumbnail
    og_image = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', html_text, re.I)
    if not og_image:
        og_image = re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']', html_text, re.I)
    if og_image:
        thumb = urllib.parse.urljoin(base_url, html.unescape(og_image.group(1)))

    return {"title": title, "thumbnail": thumb}


def fetch_page_content(url: str, referer: Optional[str] = None) -> Optional[str]:
    """Fetch webpage HTML using curl_cffi with Chrome impersonation."""
    headers = {
        "User-Agent": DEFAULT_USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    }
    if referer:
        headers["Referer"] = referer

    try:
        if HAS_CURL_CFFI:
            resp = curl_requests.get(url, headers=headers, impersonate="chrome", timeout=10)
        else:
            resp = curl_requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            return resp.text
    except Exception:
        pass
    return None


def scan_page_for_streams(page_url: str, depth: int = 1) -> Optional[Dict[str, Any]]:
    """
    Deep-scans a webpage URL for playable video streams.
    Returns metadata dict if video stream found, else None.
    """
    html_text = fetch_page_content(page_url)
    if not html_text:
        return None

    meta = _extract_page_metadata(html_text, page_url)
    page_title = meta.get("title") or "웹 영상"
    thumbnail = meta.get("thumbnail") or ""

    found_streams: List[Dict[str, Any]] = []

    def _add_stream(raw_url: str, stream_type: str):
        clean = _sanitize_url(raw_url)
        # Avoid duplicate URLs
        if any(s["url"] == clean for s in found_streams):
            return
        found_streams.append({
            "url": clean,
            "type": stream_type,
            "referer": page_url,
        })

    # 1. Direct M3U8 links
    for match in M3U8_PATTERN.finditer(html_text):
        _add_stream(match.group(1), "HLS (m3u8)")

    # 2. Direct MPD links
    for match in MPD_PATTERN.finditer(html_text):
        _add_stream(match.group(1), "DASH (mpd)")

    # 3. Player scripts
    for match in HLS_LOAD_SRC.finditer(html_text):
        _add_stream(match.group(1), "HLS (m3u8)")

    for match in JS_PLAYER_SRC.finditer(html_text):
        cand = match.group(1)
        if ".m3u8" in cand.lower():
            _add_stream(cand, "HLS (m3u8)")
        elif ".mpd" in cand.lower():
            _add_stream(cand, "DASH (mpd)")
        elif any(ext in cand.lower() for ext in [".mp4", ".webm", ".mkv"]):
            _add_stream(cand, "Direct Video")

    # 4. Direct video files
    for match in DIRECT_VIDEO_PATTERN.finditer(html_text):
        cand = match.group(1)
        # Filter out minor asset files
        if not any(ign in cand.lower() for ign in ["sprite", "preview", "poster", "thumb"]):
            _add_stream(cand, "Direct Video")

    # 5. Scan embedded iframes (if depth > 0 and no direct stream found or to enrich)
    if depth > 0 and not found_streams:
        for ifm in IFRAME_PATTERN.finditer(html_text):
            iframe_src = ifm.group(1).strip()
            if not iframe_src or iframe_src.startswith("javascript:"):
                continue
            abs_iframe_url = urllib.parse.urljoin(page_url, html.unescape(iframe_src))
            # Avoid scanning same host tracking iframes
            if any(ign in abs_iframe_url.lower() for ign in ["google", "doubleclick", "ads", "facebook", "twitter"]):
                continue

            sub_html = fetch_page_content(abs_iframe_url, referer=page_url)
            if sub_html:
                for match in M3U8_PATTERN.finditer(sub_html):
                    _add_stream(match.group(1), "HLS (m3u8)")
                for match in MPD_PATTERN.finditer(sub_html):
                    _add_stream(match.group(1), "DASH (mpd)")
                for match in HLS_LOAD_SRC.finditer(sub_html):
                    _add_stream(match.group(1), "HLS (m3u8)")
                for match in JS_PLAYER_SRC.finditer(sub_html):
                    cand = match.group(1)
                    if ".m3u8" in cand.lower():
                        _add_stream(cand, "HLS (m3u8)")
                    elif ".mpd" in cand.lower():
                        _add_stream(cand, "DASH (mpd)")
                    elif any(ext in cand.lower() for ext in [".mp4", ".webm"]):
                        _add_stream(cand, "Direct Video")
                if found_streams:
                    break

    if not found_streams:
        return None

    # Pick the best stream: prioritize m3u8 > mpd > direct mp4
    priority_order = {"HLS (m3u8)": 1, "DASH (mpd)": 2, "Direct Video": 3}
    found_streams.sort(key=lambda s: priority_order.get(s["type"], 99))
    best = found_streams[0]

    domain = urllib.parse.urlparse(page_url).netloc

    return {
        "url": best["url"],
        "page_url": page_url,
        "title": f"[{best['type']}] {page_title}" if page_title else f"웹 영상 ({domain})",
        "channel": domain,
        "thumbnail_url": thumbnail,
        "stream_type": best["type"],
        "headers": {
            "Referer": page_url,
            "Origin": f"{urllib.parse.urlparse(page_url).scheme}://{domain}",
            "User-Agent": DEFAULT_USER_AGENT,
        },
        "all_streams": found_streams,
    }

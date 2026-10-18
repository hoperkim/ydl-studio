"""
Deep Webpage Scanner for Universal Media & Audio Extraction.
Scans arbitrary websites, embedded iframes, JSON-LD, OpenGraph tags, Base64 payloads,
and Dean Edwards packed JavaScript players (eval(function(p,a,c,k,e,d))) to uncover
hidden HLS (.m3u8), DASH (.mpd), direct video (.mp4/.webm), and audio (.mp3/.m4a/.flac) streams.
"""
import base64
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
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

# Common stream patterns
M3U8_PATTERN = re.compile(
    r'(https?:\\?/\\?/[^\s"\'<>\\]+\.m3u8(?:[^\s"\'<>\\]*))', re.IGNORECASE
)
MPD_PATTERN = re.compile(
    r'(https?:\\?/\\?/[^\s"\'<>\\]+\.mpd(?:[^\s"\'<>\\]*))', re.IGNORECASE
)
DIRECT_VIDEO_PATTERN = re.compile(
    r'(https?:\\?/\\?/[^\s"\'<>\\]+\.(?:mp4|webm|mkv|mov|m4v)(?:\?[^\s"\'<>\\]*)?)', re.IGNORECASE
)
DIRECT_AUDIO_PATTERN = re.compile(
    r'(https?:\\?/\\?/[^\s"\'<>\\]+\.(?:mp3|m4a|flac|wav|ogg|opus|aac)(?:\?[^\s"\'<>\\]*)?)', re.IGNORECASE
)

# Relative or full stream URLs in player configs
JS_PLAYER_SRC = re.compile(
    r'(?:file|source|src|url|videoUrl|streamUrl|audioUrl|hls|mp4|m3u8|contentUrl)\s*["\']?\s*[:=]\s*["\']([^"\']+\.(?:m3u8|mpd|mp4|webm|mp3|m4a|flac)[^"\']*)["\']',
    re.IGNORECASE
)
HLS_LOAD_SRC = re.compile(
    r'(?:hls\.loadSource|player\.src|jwplayer\([^)]*\)\.setup)\s*\(\s*["\'](https?:\\?/\\?/[^"\']+)["\']',
    re.IGNORECASE
)
HTML_MEDIA_TAG_SRC = re.compile(
    r'<(?:video|audio|source)[^>]+src=["\']([^"\']+)["\']',
    re.IGNORECASE
)
META_MEDIA_PATTERN = re.compile(
    r'<meta[^>]+(?:property|name)=["\'](?:og:video|og:video:url|og:video:secure_url|og:audio|twitter:player:stream)["\'][^>]+content=["\']([^"\']+)["\']',
    re.IGNORECASE
)
ATOB_PATTERN = re.compile(
    r'atob\(\s*["\']([A-Za-z0-9+/=]{20,})["\']\s*\)',
    re.IGNORECASE
)
IFRAME_PATTERN = re.compile(
    r'<iframe[^>]+src=["\']([^"\']+)["\']', re.IGNORECASE
)

PACKED_JS_PATTERN = re.compile(
    r"eval\(function\(p,a,c,k,e,[dr]\)\{.*?\}\('(.*?)',(\d+),(\d+),'(.*?)'\.split\('\|'\)",
    re.DOTALL
)


def _unpack_js(p: str, a: int, c: int, k: List[str]) -> str:
    """Unpack Dean Edwards p,a,c,k,e,d obfuscated JavaScript."""
    def _base_encode(num: int, radix: int) -> str:
        chars = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
        if num < radix:
            return chars[num] if num < len(chars) else ""
        return _base_encode(num // radix, radix) + (chars[num % radix] if (num % radix) < len(chars) else "")

    try:
        symtab = {}
        for i in range(c - 1, -1, -1):
            key = _base_encode(i, a)
            symtab[key] = k[i] if i < len(k) and k[i] else key
        return re.sub(r'\b\w+\b', lambda m: symtab.get(m.group(0), m.group(0)), p)
    except Exception:
        return ""


def _expand_obfuscated_content(html_text: str) -> str:
    """Unpack packed JS blocks and decode atob() Base64 strings to expose hidden stream URLs."""
    extra_chunks: List[str] = []

    for match in PACKED_JS_PATTERN.finditer(html_text):
        try:
            p_str = match.group(1)
            a_int = int(match.group(2))
            c_int = int(match.group(3))
            k_list = match.group(4).split("|")
            unpacked = _unpack_js(p_str, a_int, c_int, k_list)
            if unpacked:
                extra_chunks.append(unpacked)
        except Exception:
            pass

    for match in ATOB_PATTERN.finditer(html_text):
        try:
            decoded = base64.b64decode(match.group(1)).decode("utf-8", errors="ignore")
            if "http" in decoded or ".m3u8" in decoded or ".mp4" in decoded:
                extra_chunks.append(decoded)
        except Exception:
            pass

    if extra_chunks:
        return html_text + "\n" + "\n".join(extra_chunks)
    return html_text


def _sanitize_url(url: str, base_url: str = "") -> str:
    """Unescape JSON-escaped slashes, HTML entities, and resolve relative URLs."""
    clean = url.replace(r'\/', '/').replace(r'\u0026', '&').replace(r'\u003d', '=')
    clean = html.unescape(clean).strip().strip('"\'')
    if base_url and not clean.lower().startswith(("http://", "https://")):
        clean = urllib.parse.urljoin(base_url, clean)
    return clean


def _extract_page_metadata(html_text: str, base_url: str) -> Dict[str, str]:
    """Extract page title and thumbnail from HTML metadata."""
    title = ""
    thumb = ""

    og_title = re.search(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']', html_text, re.I)
    if not og_title:
        og_title = re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:title["\']', html_text, re.I)

    if og_title:
        title = html.unescape(og_title.group(1)).strip()
    else:
        title_match = re.search(r'<title[^>]*>(.*?)</title>', html_text, re.I | re.S)
        if title_match:
            title = html.unescape(re.sub(r'\s+', ' ', title_match.group(1)).strip())

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


def _extract_streams_from_html(raw_html: str, base_url: str, found_streams: List[Dict[str, Any]]) -> None:
    """Scan HTML and unpacked JS for video and audio streams."""
    expanded = _expand_obfuscated_content(raw_html)

    def _add_stream(raw_url: str, stream_type: str):
        clean = _sanitize_url(raw_url, base_url)
        if not clean.lower().startswith(("http://", "https://")):
            return
        lower_c = clean.lower()
        # Ignore obvious non-content preview/tracker assets
        if any(ign in lower_c for ign in ["sprite", "preview.mp4", "poster", "thumb", "doubleclick", "google-analytics", "adservice"]):
            return
        if any(s["url"] == clean for s in found_streams):
            return
        found_streams.append({
            "url": clean,
            "type": stream_type,
            "referer": base_url,
        })

    # 1. Direct M3U8 links
    for match in M3U8_PATTERN.finditer(expanded):
        _add_stream(match.group(1), "HLS (m3u8)")

    # 2. Direct MPD links
    for match in MPD_PATTERN.finditer(expanded):
        _add_stream(match.group(1), "DASH (mpd)")

    # 3. Player & HTML media tags
    for match in HLS_LOAD_SRC.finditer(expanded):
        _add_stream(match.group(1), "HLS (m3u8)")

    for match in META_MEDIA_PATTERN.finditer(expanded):
        cand = match.group(1)
        if ".m3u8" in cand.lower():
            _add_stream(cand, "HLS (m3u8)")
        elif any(ext in cand.lower() for ext in [".mp3", ".m4a", ".flac", ".wav", ".ogg"]):
            _add_stream(cand, "Direct Audio")
        else:
            _add_stream(cand, "Direct Video")

    for match in HTML_MEDIA_TAG_SRC.finditer(expanded):
        cand = match.group(1)
        if cand.startswith("blob:") or cand.startswith("data:"):
            continue
        lower_cand = cand.lower()
        if ".m3u8" in lower_cand:
            _add_stream(cand, "HLS (m3u8)")
        elif ".mpd" in lower_cand:
            _add_stream(cand, "DASH (mpd)")
        elif any(ext in lower_cand for ext in [".mp3", ".m4a", ".flac", ".wav", ".ogg", ".opus"]):
            _add_stream(cand, "Direct Audio")
        else:
            _add_stream(cand, "Direct Video")

    for match in JS_PLAYER_SRC.finditer(expanded):
        cand = match.group(1)
        lower_cand = cand.lower()
        if ".m3u8" in lower_cand:
            _add_stream(cand, "HLS (m3u8)")
        elif ".mpd" in lower_cand:
            _add_stream(cand, "DASH (mpd)")
        elif any(ext in lower_cand for ext in [".mp3", ".m4a", ".flac", ".wav", ".ogg", ".opus"]):
            _add_stream(cand, "Direct Audio")
        elif any(ext in lower_cand for ext in [".mp4", ".webm", ".mkv", ".mov"]):
            _add_stream(cand, "Direct Video")

    # 4. Direct video files
    for match in DIRECT_VIDEO_PATTERN.finditer(expanded):
        _add_stream(match.group(1), "Direct Video")

    # 5. Direct audio files
    for match in DIRECT_AUDIO_PATTERN.finditer(expanded):
        _add_stream(match.group(1), "Direct Audio")


def scan_page_for_streams(page_url: str, depth: int = 1) -> Optional[Dict[str, Any]]:
    """
    Deep-scans a webpage URL for playable video or audio streams.
    Returns metadata dict if stream found, else None.
    """
    html_text = fetch_page_content(page_url)
    if not html_text:
        return None

    meta = _extract_page_metadata(html_text, page_url)
    page_title = meta.get("title") or "웹 미디어"
    thumbnail = meta.get("thumbnail") or ""

    found_streams: List[Dict[str, Any]] = []
    _extract_streams_from_html(html_text, page_url, found_streams)

    # Scan embedded iframes if no stream found on outer page
    if depth > 0 and not found_streams:
        for ifm in IFRAME_PATTERN.finditer(html_text):
            iframe_src = ifm.group(1).strip()
            if not iframe_src or iframe_src.startswith(("javascript:", "about:", "data:")):
                continue
            abs_iframe_url = urllib.parse.urljoin(page_url, html.unescape(iframe_src))
            if any(ign in abs_iframe_url.lower() for ign in ["google", "doubleclick", "ads", "facebook.com/plugins", "disqus"]):
                continue

            sub_html = fetch_page_content(abs_iframe_url, referer=page_url)
            if sub_html:
                _extract_streams_from_html(sub_html, abs_iframe_url, found_streams)
                if found_streams:
                    break

    if not found_streams:
        return None

    # Priority order: HLS (m3u8) > DASH (mpd) > Direct Video > Direct Audio
    priority_order = {"HLS (m3u8)": 1, "DASH (mpd)": 2, "Direct Video": 3, "Direct Audio": 4}
    found_streams.sort(key=lambda s: priority_order.get(s["type"], 99))
    best = found_streams[0]

    domain = urllib.parse.urlparse(page_url).netloc
    ref_url = best.get("referer") or page_url

    return {
        "url": best["url"],
        "page_url": page_url,
        "title": page_title if page_title else f"웹 미디어 ({domain})",
        "channel": domain,
        "thumbnail_url": thumbnail,
        "stream_type": best["type"],
        "is_audio_only": best["type"] == "Direct Audio",
        "headers": {
            "Referer": ref_url,
            "Origin": f"{urllib.parse.urlparse(ref_url).scheme}://{urllib.parse.urlparse(ref_url).netloc}",
            "User-Agent": DEFAULT_USER_AGENT,
        },
        "all_streams": found_streams,
    }

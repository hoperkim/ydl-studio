"""
Clipboard monitoring, multi-URL extraction, URL sanitization, and smart media intent detection.
Supports 50+ global/Korean video & music platforms, direct stream manifests (.m3u8/.mpd),
and arbitrary streaming URLs.
"""
import re
import urllib.parse
from typing import List, Optional

# Recognized domains for automatic background clipboard detection
AUTO_CLIPBOARD_URL_REGEX = re.compile(
    r'(https?://(?:[a-zA-Z0-9_\-]+\.)?(?:'
    r'youtube\.com|youtu\.be|music\.youtube\.com|'
    r'soundcloud\.com|bandcamp\.com|mixcloud\.com|audiomack\.com|'
    r'tiktok\.com|douyin\.com|xiaohongshu\.com|xhslink\.com|'
    r'instagram\.com|threads\.net|facebook\.com|fb\.watch|'
    r'twitter\.com|x\.com|reddit\.com|redd\.it|pinterest\.com|pin\.it|'
    r'twitch\.tv|kick\.com|chzzk\.naver\.com|naver\.com|tv\.naver\.com|'
    r'sooplive\.co\.kr|afreecatv\.com|bilibili\.com|b23\.tv|'
    r'vimeo\.com|dailymotion\.com|dai\.ly|streamable\.com|imgur\.com|'
    r'upload18\.org|upload18\.com|upload18\.cc'
    r')/[^\s"\'<>]+)',
    re.IGNORECASE
)

# Direct stream / media file URL regex for auto clipboard detection
DIRECT_STREAM_REGEX = re.compile(
    r'(https?://[^\s"\'<>]+\.(?:m3u8|mpd|mp4|webm|mkv|mov|mp3|m4a|flac|wav|ogg|opus)(?:\?[^\s"\'<>]*)?)',
    re.IGNORECASE
)

# Any HTTP/HTTPS URL regex (used when user explicitly pastes or clicks Add)
GENERIC_HTTP_URL_REGEX = re.compile(
    r'(https?://[^\s"\'<>]+)',
    re.IGNORECASE
)

AUDIO_DOMAINS = (
    "music.youtube.com",
    "soundcloud.com",
    "bandcamp.com",
    "mixcloud.com",
    "audiomack.com",
    "podcasts.apple.com",
    "music.apple.com",
    "open.spotify.com",
    "melon.com",
    "genie.co.kr",
    "bugs.co.kr",
    "flo-music.com",
    "vibe.naver.com",
)

AUDIO_EXTENSIONS = (".mp3", ".m4a", ".flac", ".wav", ".ogg", ".opus", ".aac")


def clean_media_url(url: str) -> str:
    """
    Clean tracking query parameters and unwanted YouTube Mix/Radio playlist parameters
    that slow down or break extraction.
    """
    if not url:
        return ""
    clean = url.strip().rstrip('),.;!"\'>]')
    lower = clean.lower()

    # TikTok: strip tracking params like is_from_webapp, sender_device
    if "tiktok.com" in lower and ("/video/" in lower or "/photo/" in lower):
        clean = clean.split("?")[0]
        return clean

    # YouTube / YouTube Music: if watching a single video (v=...), strip Mix/Radio list=RD...
    # or general playlist parameters unless it's explicitly a /playlist?list= URL
    if ("youtube.com/watch" in lower or "youtu.be/" in lower) and "list=" in lower:
        try:
            parsed = urllib.parse.urlparse(clean)
            qs = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
            # When watching a specific video, user almost always intends that video,
            # especially for auto-generated YouTube Mixes (list=RD...)
            if "v" in qs or "youtu.be" in parsed.netloc.lower():
                qs.pop("list", None)
                qs.pop("index", None)
                qs.pop("start_radio", None)
                qs.pop("rv", None)
                new_query = urllib.parse.urlencode(qs, doseq=True)
                clean = urllib.parse.urlunparse(parsed._replace(query=new_query))
        except Exception:
            pass

    return clean


def detect_media_intent(url: str) -> str:
    """
    Detect whether a URL is inherently intended for 'audio' or 'video'.
    Returns 'audio' for music platforms and audio file links, otherwise 'video'.
    """
    if not url:
        return "video"
    lower = url.lower().split("?")[0]
    try:
        host = urllib.parse.urlparse(url.lower()).netloc
    except Exception:
        host = lower

    if any(domain in host for domain in AUDIO_DOMAINS):
        return "audio"
    if any(lower.endswith(ext) for ext in AUDIO_EXTENSIONS):
        return "audio"
    return "video"


def extract_media_url(text: str, allow_generic_http: bool = False) -> Optional[str]:
    """
    Extract and sanitize a valid media URL from text.
    If allow_generic_http is False (used by background clipboard monitor), matches known media sites & stream links.
    If allow_generic_http is True (used when user explicitly submits/pastes), matches any http(s) URL.
    """
    if not text:
        return None
    stripped = text.strip()

    match = AUTO_CLIPBOARD_URL_REGEX.search(stripped)
    if match:
        return clean_media_url(match.group(1))

    match_stream = DIRECT_STREAM_REGEX.search(stripped)
    if match_stream:
        return clean_media_url(match_stream.group(1))

    if allow_generic_http:
        match_any = GENERIC_HTTP_URL_REGEX.search(stripped)
        if match_any:
            return clean_media_url(match_any.group(1))

    return None


def extract_all_urls(text: str) -> List[str]:
    """
    Extract all HTTP/HTTPS URLs from a pasted text block (supports multi-line or space-separated URLs).
    """
    if not text:
        return []
    urls: List[str] = []
    for match in GENERIC_HTTP_URL_REGEX.finditer(text.strip()):
        cleaned = clean_media_url(match.group(1))
        if cleaned and cleaned not in urls:
            urls.append(cleaned)
    return urls


def is_valid_url(text: str) -> bool:
    """Check if the given string contains a valid media URL."""
    return extract_media_url(text, allow_generic_http=True) is not None

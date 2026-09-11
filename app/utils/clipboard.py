"""
Clipboard monitoring utility for detecting YouTube and media URLs.
"""
import re
from typing import Optional

MEDIA_URL_REGEX = re.compile(
    r'(https?://(?:[a-zA-Z0-9_\-]+\.)?(?:youtube\.com|youtu\.be|bilibili\.com|twitch\.tv|vimeo\.com|tiktok\.com|twitter\.com|x\.com|instagram\.com)/[^\s]+)',
    re.IGNORECASE
)


def clean_media_url(url: str) -> str:
    """Clean tracking and device query parameters that cause scraping errors (e.g. TikTok, Instagram)."""
    if not url:
        return ""
    clean = url.strip().rstrip('),.;"\'>')
    # For TikTok video links, remove query parameters like is_from_webapp or sender_device
    if "tiktok.com" in clean.lower() and "/video/" in clean:
        clean = clean.split("?")[0]
    return clean


def extract_media_url(text: str) -> Optional[str]:
    """Extract and sanitize a valid media URL from text, or return None."""
    if not text:
        return None
    match = MEDIA_URL_REGEX.search(text.strip())
    if match:
        raw_url = match.group(1)
        return clean_media_url(raw_url)
    return None


def is_valid_url(text: str) -> bool:
    """Check if the given string is a valid media URL."""
    return extract_media_url(text) is not None

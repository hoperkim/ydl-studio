"""
Clipboard monitoring utility for detecting YouTube and media URLs.
"""
import re
from typing import Optional

MEDIA_URL_REGEX = re.compile(
    r'(https?://(?:www\.|m\.)?(?:youtube\.com|youtu\.be|bilibili\.com|twitch\.tv|vimeo\.com|tiktok\.com|twitter\.com|x\.com)/[^\s]+)',
    re.IGNORECASE
)


def extract_media_url(text: str) -> Optional[str]:
    """Extract a valid media URL from text, or return None."""
    if not text:
        return None
    match = MEDIA_URL_REGEX.search(text.strip())
    if match:
        url = match.group(1).rstrip('),.;"\'>')
        return url
    return None


def is_valid_url(text: str) -> bool:
    """Check if the given string is a valid media URL."""
    return extract_media_url(text) is not None

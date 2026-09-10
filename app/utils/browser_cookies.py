"""
Browser cookie integration utility for yt-dlp.
Allows bypassing YouTube bot detection and age restrictions using browser login sessions.
"""
import os
import sys
from typing import List, Optional, Tuple

SUPPORTED_BROWSERS = [
    ("사용 안 함 (None)", None),
    ("Chrome (크롬)", "chrome"),
    ("Edge (엣지)", "edge"),
    ("Brave (브레이브)", "brave"),
    ("Firefox (파이어폭스)", "firefox"),
    ("Opera (오페라)", "opera"),
    ("Vivaldi (비발디)", "vivaldi"),
]


def get_browser_options() -> List[str]:
    """Return display labels for supported browsers."""
    return [label for label, _ in SUPPORTED_BROWSERS]


def get_browser_code_by_label(label: str) -> Optional[str]:
    """Map display label to yt-dlp browser identifier."""
    for display_label, code in SUPPORTED_BROWSERS:
        if display_label == label or (code and code in label.lower()):
            return code
    return None


def get_label_by_code(code: Optional[str]) -> str:
    """Map yt-dlp browser code to display label."""
    if not code:
        return SUPPORTED_BROWSERS[0][0]
    for display_label, b_code in SUPPORTED_BROWSERS:
        if b_code == code:
            return display_label
    return SUPPORTED_BROWSERS[0][0]

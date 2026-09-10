"""
Video metadata extraction module using yt-dlp.
"""
import io
import urllib.request
from typing import Any, Dict, List, Optional, Tuple
from PIL import Image
import yt_dlp


def format_duration(seconds: Optional[int]) -> str:
    """Format duration in seconds into HH:MM:SS or MM:SS."""
    if not seconds:
        return "00:00"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def extract_video_info(url: str, browser_cookie: Optional[str] = None) -> Dict[str, Any]:
    """
    Extract metadata for a video or playlist without downloading media files.
    Returns a dictionary containing title, channel, duration, thumbnail_url, formats, etc.
    """
    ydl_opts: Dict[str, Any] = {
        'skip_download': True,
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
    }

    if browser_cookie:
        ydl_opts['cookiesfrombrowser'] = (browser_cookie,)

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as e:
        err_str = str(e).lower()
        if browser_cookie and ("cookie" in err_str or "permission" in err_str):
            # Fallback: Retry without browser cookies if locked by browser process
            ydl_opts.pop('cookiesfrombrowser', None)
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
        else:
            raise e

    if not info:
        raise ValueError("영상 정보를 가져올 수 없습니다.")

    # Check if it's a playlist
    is_playlist = 'entries' in info and info['entries'] is not None
    if is_playlist:
        entries = list(info['entries'])
        first_entry = entries[0] if entries else {}
        title = info.get('title') or "재생목록"
        uploader = info.get('uploader') or first_entry.get('uploader') or "알 수 없음"
        thumbnail = info.get('thumbnail') or first_entry.get('thumbnail') or ""
        count = len(entries)
        return {
            'url': url,
            'is_playlist': True,
            'playlist_count': count,
            'title': f"[재생목록] {title} ({count}개 영상)",
            'channel': uploader,
            'duration_str': f"{count}개 항목",
            'thumbnail_url': thumbnail,
            'available_presets': get_available_presets([]),
        }

    title = info.get('title', '제목 없음')
    uploader = info.get('uploader') or info.get('channel') or '알 수 없는 채널'
    duration = info.get('duration')
    thumbnail = info.get('thumbnail') or ""
    formats = info.get('formats') or []

    # Find max available resolution
    heights = set()
    for f in formats:
        h = f.get('height')
        if h and isinstance(h, int):
            heights.add(h)

    presets = get_available_presets(sorted(list(heights), reverse=True))

    return {
        'url': url,
        'is_playlist': False,
        'title': title,
        'channel': uploader,
        'duration': duration,
        'duration_str': format_duration(duration),
        'thumbnail_url': thumbnail,
        'available_presets': presets,
        'raw_info': {
            'id': info.get('id'),
            'view_count': info.get('view_count'),
        }
    }


def get_available_presets(heights: List[int]) -> List[str]:
    """Generate user-friendly preset options based on available video heights."""
    presets = ["최고 화질 (Best Auto)"]

    if any(h >= 2160 for h in heights):
        presets.append("4K (2160p MP4)")
    if any(h >= 1440 for h in heights):
        presets.append("2K (1440p MP4)")
    if any(h >= 1080 for h in heights):
        presets.append("1080p FHD MP4")
    if any(h >= 720 for h in heights):
        presets.append("720p HD MP4")
    if any(h >= 480 for h in heights):
        presets.append("480p MP4")

    # Audio presets
    presets.extend([
        "오디오 MP3 (최고음질 320k)",
        "오디오 MP3 (표준 192k)",
        "오디오 M4A (무손실 원본)"
    ])
    return presets


def fetch_thumbnail_image(url: str, size: Tuple[int, int] = (160, 90)) -> Optional[Image.Image]:
    """Download and resize thumbnail image as PIL Image."""
    if not url:
        return None
    try:
        req = urllib.request.Request(
            url,
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = resp.read()
            img = Image.open(io.BytesIO(data))
            img = img.convert('RGB')
            img = img.resize(size, Image.Resampling.LANCZOS)
            return img
    except Exception:
        return None

"""
Smart Video & Audio Metadata Extraction Module (v2.0 Universal).
Combines yt-dlp, Music/DRM Track Search Bridge (Spotify/Melon/Bugs/Apple Music -> Audio),
DeepWebScanner, M3U8 Master Parser, and Automatic Browser Session Escalation.
"""
import html
import io
import re
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple
from PIL import Image
import yt_dlp

from app.core.deep_scanner import fetch_page_content, scan_page_for_streams
from app.utils.clipboard import clean_media_url, detect_media_intent

try:
    from curl_cffi import requests as curl_requests
except ImportError:
    import requests as curl_requests  # type: ignore


MUSIC_BRIDGE_DOMAINS = (
    "open.spotify.com",
    "melon.com",
    "genie.co.kr",
    "bugs.co.kr",
    "music.apple.com",
    "vibe.naver.com",
    "flo-music.com",
)


def format_duration(seconds: Optional[int]) -> str:
    """Format duration in seconds into HH:MM:SS or MM:SS."""
    if not seconds:
        return "00:00"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def parse_m3u8_info(url: str, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Parse M3U8 master playlist for resolutions and live status."""
    req_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0.0.0"
    }
    if headers:
        req_headers.update(headers)

    heights = set()
    is_live = False
    try:
        resp = curl_requests.get(url, headers=req_headers, timeout=5)
        if resp.status_code == 200:
            text = resp.text
            if "#EXT-X-ENDLIST" not in text and ("#EXTINF" in text or "#EXT-X-TARGETDURATION" in text):
                is_live = True

            res_matches = re.findall(r'RESOLUTION=\d+x(\d+)', text, re.I)
            for h_str in res_matches:
                try:
                    heights.add(int(h_str))
                except ValueError:
                    pass
    except Exception:
        pass

    return {
        "heights": sorted(list(heights), reverse=True),
        "is_live": is_live
    }


def _try_resolve_music_bridge(url: str) -> Optional[Tuple[str, str, str]]:
    """
    If URL is from a DRM music chart/streaming service (Spotify, Melon, Genie, Bugs, Apple Music),
    extract track title & artist from OpenGraph metadata and return (ytsearch_query, display_title, thumb_url).
    """
    lower = url.lower()
    if not any(d in lower for d in MUSIC_BRIDGE_DOMAINS):
        return None

    html_text = fetch_page_content(url)
    if not html_text:
        return None

    og_title = re.search(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']', html_text, re.I)
    og_desc = re.search(r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)["\']', html_text, re.I)
    og_img = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', html_text, re.I)

    title = html.unescape(og_title.group(1)).strip() if og_title else ""
    desc = html.unescape(og_desc.group(1)).strip() if og_desc else ""
    thumb = html.unescape(og_img.group(1)).strip() if og_img else ""

    if not title:
        t_m = re.search(r'<title[^>]*>(.*?)</title>', html_text, re.I | re.S)
        if t_m:
            title = html.unescape(re.sub(r'\s+', ' ', t_m.group(1)).strip())

    # Clean common suffixes
    for suffix in [" - Spotify", " | Spotify", " - 멜론", " - 지니", " - 벅스", " on Apple Music"]:
        title = title.replace(suffix, "").strip()

    if not title:
        return None

    query_str = title
    if desc and len(desc) < 80 and "listen to" not in desc.lower():
        artist_part = desc.split("·")[0].split("-")[0].strip()
        if artist_part and artist_part.lower() not in title.lower():
            query_str = f"{artist_part} - {title}"

    return (f"ytsearch1:{query_str} official audio", query_str, thumb)


def get_available_presets(heights: List[int], prefer_audio: bool = False) -> List[str]:
    """Generate user-friendly preset options based on available video heights and media intent."""
    video_presets = ["최고 화질 (Best Auto)"]

    if any(h >= 2160 for h in heights):
        video_presets.append("4K (2160p MP4)")
    if any(h >= 1440 for h in heights):
        video_presets.append("2K (1440p MP4)")
    if any(h >= 1080 for h in heights) or not heights:
        video_presets.append("1080p FHD MP4")
    if any(h >= 720 for h in heights) or not heights:
        video_presets.append("720p HD MP4")
    if any(h >= 480 for h in heights):
        video_presets.append("480p MP4")

    audio_presets = [
        "오디오 MP3 (최고음질 320k)",
        "오디오 FLAC (무손실 음원)",
        "오디오 M4A (원본 AAC)",
        "오디오 MP3 (표준 192k)",
    ]

    if prefer_audio:
        return audio_presets + video_presets
    return video_presets + audio_presets


def select_preset_for_mode(available_presets: List[str], intent_mode: str, media_intent: str) -> str:
    """
    Choose the optimal preset based on user's top-bar intent_mode and URL's detected media_intent.
    intent_mode options:
      - 'auto': Smart Auto (Music/Audio URLs -> MP3 320k, Video URLs -> Best Video)
      - 'video_best': Best Video MP4
      - 'audio_mp3': Audio MP3 320k
      - 'audio_flac': Audio FLAC Lossless
      - 'video_1080p': 1080p FHD MP4
    """
    if not available_presets:
        return "최고 화질 (Best Auto)"

    if intent_mode == "audio_mp3" or (intent_mode == "auto" and media_intent == "audio"):
        for p in available_presets:
            if "MP3 (최고음질 320k)" in p:
                return p
    elif intent_mode == "audio_flac":
        for p in available_presets:
            if "FLAC" in p:
                return p
    elif intent_mode == "video_1080p":
        for p in available_presets:
            if "1080p" in p:
                return p
    elif intent_mode == "video_best":
        for p in available_presets:
            if "최고 화질" in p or "원본 MP4" in p:
                return p

    return available_presets[0]


def extract_video_info(
    url: str,
    browser_cookie: Optional[str] = None,
    custom_headers: Optional[Dict[str, str]] = None,
    intent_mode: str = "auto",
) -> Dict[str, Any]:
    """
    Universal 4-Stage Metadata & Stream Extractor.
    Stage 1: Music Bridge / yt-dlp extraction
    Stage 2: DeepWebScanner (HTML + Packed JS + Base64 + Iframe)
    Stage 3: Direct M3U8 / MPD / Audio / Video URL parser
    Stage 4: Automatic Browser-Context CDP Session Escalation (Zero Dead-Ends)
    """
    url = clean_media_url(url)
    clean_url_lower = url.lower()
    media_intent = detect_media_intent(url)
    prefer_audio = (intent_mode in ("audio_mp3", "audio_flac")) or (intent_mode == "auto" and media_intent == "audio")

    is_direct_m3u8 = ".m3u8" in clean_url_lower
    is_direct_mpd = ".mpd" in clean_url_lower

    # Fast-path for known session-locked HLS sites like upload18.org
    if "upload18." in clean_url_lower:
        title = "보안 스트림 영상"
        m_slug = re.search(r'play/index/([^/?]+)', url)
        if m_slug:
            title = m_slug.group(1).split("-clone")[0]
        thumb = ""
        try:
            r = curl_requests.get(url, impersonate="chrome", timeout=5)
            if r.status_code == 200:
                t_m = re.search(r'<title>(.*?)</title>', r.text)
                if t_m:
                    title = t_m.group(1).replace(" Coppy", "").strip()
                p_m = re.search(r'"thumb"\s*:\s*"([^"]+)"', r.text)
                if p_m:
                    thumb = p_m.group(1).replace(r'\/', '/')
        except Exception:
            pass

        presets = get_available_presets([1080, 720], prefer_audio=prefer_audio)
        selected_preset = select_preset_for_mode(presets, intent_mode, media_intent)
        return {
            'url': url,
            'page_url': url,
            'is_playlist': False,
            'title': f"[보안 스트림] {title}",
            'channel': urllib.parse.urlparse(url).netloc,
            'duration': None,
            'duration_str': '고화질 스트림',
            'thumbnail_url': thumb,
            'available_presets': presets,
            'selected_preset': selected_preset,
            'media_intent': media_intent,
            'is_live': False,
            'stream_type': '보안 웹 비디오',
            'use_browser_fetcher': True,
            'headers': custom_headers or {},
            'raw_info': {'id': title, 'extractor': 'BrowserFetcher'},
        }

    # Optional Music DRM Bridge (Spotify, Melon, Genie, Bugs, Apple Music -> Official Audio Search)
    music_bridge = _try_resolve_music_bridge(url)
    target_extract_url = music_bridge[0] if music_bridge else url
    if music_bridge:
        media_intent = "audio"
        prefer_audio = True

    is_explicit_playlist = any(p in clean_url_lower for p in ["/playlist", "/sets/", "/album/"])

    ydl_opts: Dict[str, Any] = {
        'skip_download': True,
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        'noplaylist': not is_explicit_playlist,
    }

    if browser_cookie:
        ydl_opts['cookiesfrombrowser'] = (browser_cookie,)

    if custom_headers:
        ydl_opts['http_headers'] = custom_headers

    info = None
    ytdl_error: Optional[Exception] = None

    # Stage 1: Standard yt-dlp extraction
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(target_extract_url, download=False)
    except Exception as e:
        ytdl_error = e
        err_str = str(e).lower()
        if browser_cookie and ("cookie" in err_str or "permission" in err_str or "dpapi" in err_str):
            try:
                ydl_opts.pop('cookiesfrombrowser', None)
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(target_extract_url, download=False)
                ytdl_error = None
            except Exception as e2:
                ytdl_error = e2

    # Unwrap ytsearch1: result if used by Music Bridge
    if info and 'entries' in info and target_extract_url.startswith("ytsearch"):
        entries = [e for e in (info.get('entries') or []) if e]
        if entries:
            info = entries[0]
            if music_bridge and music_bridge[2]:
                info['thumbnail'] = music_bridge[2]

    # Stage 2: DeepWebScanner fallback (HTML + Packed JS + Base64 + Iframes)
    if (not info or (not info.get('formats') and 'entries' not in info)) and not (is_direct_m3u8 or is_direct_mpd):
        deep_res = scan_page_for_streams(url)
        if deep_res:
            stream_url = deep_res["url"]
            merged_headers = deep_res.get("headers", {})
            if custom_headers:
                merged_headers.update(custom_headers)

            if deep_res.get("is_audio_only"):
                media_intent = "audio"
                prefer_audio = True

            m3u8_info = parse_m3u8_info(stream_url, merged_headers) if ".m3u8" in stream_url.lower() else {"heights": [], "is_live": False}
            presets = get_available_presets(m3u8_info["heights"], prefer_audio=prefer_audio)
            selected_preset = select_preset_for_mode(presets, intent_mode, media_intent)

            return {
                'url': stream_url,
                'page_url': deep_res.get("page_url", url),
                'is_playlist': False,
                'title': deep_res["title"],
                'channel': deep_res["channel"],
                'duration': None,
                'duration_str': "🔴 실시간 방송" if m3u8_info["is_live"] else ("🎵 웹 음원" if deep_res.get("is_audio_only") else "웹 스트림"),
                'thumbnail_url': deep_res.get("thumbnail_url", ""),
                'available_presets': presets,
                'selected_preset': selected_preset,
                'media_intent': media_intent,
                'is_live': m3u8_info["is_live"],
                'stream_type': deep_res.get("stream_type", "웹 스트림"),
                'headers': merged_headers,
                'raw_info': {'id': 'deep_scanned', 'extractor': 'DeepWebScanner'},
            }

    # Stage 3: Direct M3U8 / MPD manifest fallback
    if not info and (is_direct_m3u8 or is_direct_mpd):
        m3u8_info = parse_m3u8_info(url, custom_headers) if is_direct_m3u8 else {"heights": [], "is_live": False}
        stream_type = "HLS (m3u8)" if is_direct_m3u8 else "DASH (mpd)"
        filename = url.split("?")[0].split("/")[-1] or "stream"
        presets = get_available_presets(m3u8_info["heights"], prefer_audio=prefer_audio)
        selected_preset = select_preset_for_mode(presets, intent_mode, media_intent)

        return {
            'url': url,
            'page_url': custom_headers.get("Referer", "") if custom_headers else "",
            'is_playlist': False,
            'title': f"[{stream_type}] {filename}",
            'channel': urllib.parse.urlparse(url).netloc,
            'duration': None,
            'duration_str': "🔴 실시간 방송" if m3u8_info["is_live"] else "스트림",
            'thumbnail_url': "",
            'available_presets': presets,
            'selected_preset': selected_preset,
            'media_intent': media_intent,
            'is_live': m3u8_info["is_live"],
            'stream_type': stream_type,
            'headers': custom_headers or {},
            'raw_info': {'id': filename, 'extractor': 'DirectStream'},
        }

    # Stage 4: Automatic Universal Browser Session Fallback (Zero Dead-Ends for dynamic JS/Cloudflare sites)
    if not info:
        parsed_u = urllib.parse.urlparse(url)
        if parsed_u.scheme in ("http", "https") and parsed_u.netloc:
            page_html = fetch_page_content(url)
            title = parsed_u.netloc
            thumb = ""
            if page_html:
                t_m = re.search(r'<title[^>]*>(.*?)</title>', page_html, re.I | re.S)
                if t_m:
                    title = html.unescape(re.sub(r'\s+', ' ', t_m.group(1)).strip())
                og_img = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', page_html, re.I)
                if og_img:
                    thumb = urllib.parse.urljoin(url, html.unescape(og_img.group(1)))

            presets = get_available_presets([1080, 720], prefer_audio=prefer_audio)
            selected_preset = select_preset_for_mode(presets, intent_mode, media_intent)
            return {
                'url': url,
                'page_url': url,
                'is_playlist': False,
                'title': f"[자동 보안세션] {title}",
                'channel': parsed_u.netloc,
                'duration': None,
                'duration_str': "자동 브라우저 추출",
                'thumbnail_url': thumb,
                'available_presets': presets,
                'selected_preset': selected_preset,
                'media_intent': media_intent,
                'is_live': False,
                'stream_type': '보안 웹 스트림',
                'use_browser_fetcher': True,
                'headers': custom_headers or {},
                'raw_info': {'id': parsed_u.netloc, 'extractor': 'BrowserFetcher'},
            }

        if ytdl_error:
            raise ytdl_error
        raise ValueError("영상 또는 음원 정보를 가져올 수 없습니다.")

    # Handle yt-dlp Playlist result
    is_playlist = 'entries' in info and info['entries'] is not None
    if is_playlist:
        entries = [e for e in list(info['entries']) if e]
        first_entry = entries[0] if entries else {}
        title = info.get('title') or "재생목록"
        uploader = info.get('uploader') or first_entry.get('uploader') or "알 수 없음"
        thumbnail = info.get('thumbnail') or first_entry.get('thumbnail') or ""
        count = len(entries)
        presets = get_available_presets([], prefer_audio=prefer_audio)
        selected_preset = select_preset_for_mode(presets, intent_mode, media_intent)
        return {
            'url': info.get('webpage_url') or url,
            'page_url': url,
            'is_playlist': True,
            'playlist_count': count,
            'title': f"[재생목록] {title} ({count}개 항목)",
            'channel': uploader,
            'duration_str': f"{count}개 항목",
            'thumbnail_url': thumbnail,
            'available_presets': presets,
            'selected_preset': selected_preset,
            'media_intent': media_intent,
            'is_live': False,
            'stream_type': '재생목록',
            'headers': custom_headers or {},
        }

    title = info.get('title', '제목 없음')
    uploader = info.get('uploader') or info.get('channel') or info.get('artist') or '알 수 없는 채널'
    duration = info.get('duration')
    thumbnail = info.get('thumbnail') or ""
    formats = info.get('formats') or []
    is_live = bool(info.get('is_live') or info.get('was_live'))

    heights = set()
    has_video = False
    for f in formats:
        h = f.get('height')
        vcodec = f.get('vcodec')
        if h and isinstance(h, int) and h > 0:
            heights.add(h)
            has_video = True
        elif vcodec and vcodec != 'none':
            has_video = True

    if not has_video and formats:
        media_intent = "audio"
        prefer_audio = True

    extractor = (info.get('extractor') or info.get('extractor_key') or '').lower()
    if music_bridge:
        stream_type = '🎵 음원 브릿지'
    elif media_intent == 'audio':
        stream_type = '🎵 MUSIC / 음원'
    elif 'youtube' in extractor:
        stream_type = 'YouTube'
    elif 'tiktok' in extractor:
        stream_type = 'TikTok'
    elif 'twitter' in extractor or 'x' in extractor:
        stream_type = 'X (Twitter)'
    elif 'instagram' in extractor:
        stream_type = 'Instagram'
    elif 'soundcloud' in extractor:
        stream_type = 'SoundCloud'
    elif 'chzzk' in extractor or 'naver' in extractor:
        stream_type = 'Naver / Chzzk'
    elif 'afreeca' in extractor or 'soop' in extractor:
        stream_type = 'SOOP'
    elif 'bilibili' in extractor:
        stream_type = 'Bilibili'
    elif is_direct_m3u8:
        stream_type = 'HLS (m3u8)'
    elif is_direct_mpd:
        stream_type = 'DASH (mpd)'
    else:
        stream_type = info.get('extractor_key') or '웹 미디어'

    presets = get_available_presets(sorted(list(heights), reverse=True), prefer_audio=prefer_audio)
    selected_preset = select_preset_for_mode(presets, intent_mode, media_intent)

    # Use resolved webpage_url if music_bridge resolved a ytsearch query
    final_download_url = (info.get('webpage_url') or info.get('url') or url) if music_bridge else url

    return {
        'url': final_download_url,
        'page_url': url,
        'is_playlist': False,
        'title': title,
        'channel': uploader,
        'duration': duration,
        'duration_str': "🔴 실시간 라이브" if is_live else format_duration(duration),
        'thumbnail_url': thumbnail,
        'available_presets': presets,
        'selected_preset': selected_preset,
        'media_intent': media_intent,
        'is_live': is_live,
        'stream_type': stream_type,
        'headers': custom_headers or {},
        'raw_info': {
            'id': info.get('id'),
            'view_count': info.get('view_count'),
            'extractor': extractor,
        }
    }


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

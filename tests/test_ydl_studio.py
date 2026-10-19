"""
Automated Unit Tests for YDL Studio Core Parsing, Intent Classification,
JS Deobfuscation, and HLS M3U8 Resolution Logic.
"""
import base64
import os
import sys
import unittest

# Ensure project root is on sys.path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from app.utils.clipboard import (
    clean_media_url,
    detect_media_intent,
    extract_all_urls,
    extract_media_url,
    is_valid_url,
)
from app.core.deep_scanner import (
    _expand_obfuscated_content,
    _extract_page_metadata,
    _extract_streams_from_html,
)
from app.core.browser_fetcher import _resolve_master_m3u8, _parse_media_m3u8
from app.core.metadata import (
    format_duration,
    get_available_presets,
    select_preset_for_mode,
)


class TestClipboardAndUrlParsing(unittest.TestCase):
    """Verify URL sanitization, multi-URL extraction, and media intent detection."""

    def test_clean_youtube_mix_url_strips_radio_params(self):
        raw_url = (
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
            "&list=RDdQw4w9WgXcQ&start_radio=1&rv=xyz123&index=2"
        )
        cleaned = clean_media_url(raw_url)
        self.assertEqual(cleaned, "https://www.youtube.com/watch?v=dQw4w9WgXcQ")

    def test_clean_youtube_dedicated_playlist_preserves_list_id(self):
        playlist_url = "https://www.youtube.com/playlist?list=PL1234567890ABCDEF"
        cleaned = clean_media_url(playlist_url)
        self.assertEqual(cleaned, "https://www.youtube.com/playlist?list=PL1234567890ABCDEF")

    def test_clean_tiktok_url_strips_tracking_query(self):
        tiktok_url = "https://www.tiktok.com/@user/video/7123456789?is_from_webapp=1&sender_device=pc"
        self.assertEqual(clean_media_url(tiktok_url), "https://www.tiktok.com/@user/video/7123456789")

    def test_detect_media_intent_audio_vs_video(self):
        # Audio domains and extensions
        self.assertEqual(detect_media_intent("https://music.youtube.com/watch?v=abc12345"), "audio")
        self.assertEqual(detect_media_intent("https://soundcloud.com/artist/track-name"), "audio")
        self.assertEqual(detect_media_intent("https://open.spotify.com/track/4cOdK2wGLETKBW3PvgPWqT"), "audio")
        self.assertEqual(detect_media_intent("https://www.melon.com/song/detail.htm?songId=12345"), "audio")
        self.assertEqual(detect_media_intent("https://cdn.example.com/audio/sample.flac?token=1"), "audio")

        # Video domains and extensions
        self.assertEqual(detect_media_intent("https://www.youtube.com/watch?v=dQw4w9WgXcQ"), "video")
        self.assertEqual(detect_media_intent("https://upload18.org/play/index/12345"), "video")
        self.assertEqual(detect_media_intent("https://cdn.example.com/stream/master.m3u8"), "video")

    def test_extract_all_urls_deduplicates_and_strips_punctuation(self):
        messy_text = (
            "Check out these links:\n"
            "1) (https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=RDdQw4w9WgXcQ),\n"
            "2) https://soundcloud.com/artist/song!\n"
            "Duplicate: https://www.youtube.com/watch?v=dQw4w9WgXcQ."
        )
        urls = extract_all_urls(messy_text)
        self.assertEqual(
            urls,
            [
                "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                "https://soundcloud.com/artist/song",
            ],
        )
        self.assertEqual(extract_media_url(messy_text), "https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        self.assertTrue(is_valid_url(messy_text))


class TestDeepWebScannerDeobfuscation(unittest.TestCase):
    """Verify HTML/JS stream extraction, Dean Edwards unpacker, and Base64 decoding."""

    def test_unpack_dean_edwards_packed_js(self):
        # Packed representation where tokens replace 0..9 in payload
        packed_html = (
            "<script>"
            "eval(function(p,a,c,k,e,d){e=function(c){return c};if(!''.replace(/^/,String)){while(c--){d[c]=k[c]||c}k=[function(e){return d[e]}];e=function(){return'\\\\w+'};c=1};while(c--){if(k[c]){p=p.replace(new RegExp('\\\\b'+e(c)+'\\\\b','g'),k[c])}}return p}("
            "'0.1({2:\"3://4.5.6/7/8.9\"});',10,10,'player|setup|file|https|cdn|example|com|hls|master|m3u8'.split('|'),0,{}))"
            "</script>"
        )
        unpacked = _expand_obfuscated_content(packed_html)
        self.assertIn("https://cdn.example.com/hls/master.m3u8", unpacked)

        found = []
        _extract_streams_from_html(packed_html, "https://example.com", found)
        urls = [s["url"] for s in found]
        self.assertIn("https://cdn.example.com/hls/master.m3u8", urls)

    def test_decode_base64_atob_calls(self):
        secret_url = "https://media.example.org/stream/video_1080p.mp4"
        b64_str = base64.b64encode(secret_url.encode("utf-8")).decode("ascii")
        html = f'<script>const src = atob("{b64_str}");</script>'

        decoded = _expand_obfuscated_content(html)
        self.assertIn(secret_url, decoded)

        found = []
        _extract_streams_from_html(html, "https://example.org", found)
        urls = [s["url"] for s in found]
        self.assertIn(secret_url, urls)

    def test_extract_streams_filters_thumbnails_and_ads(self):
        html = """
        <script>
            var thumb = "https://cdn.example.com/thumb/preview.mp4";
            var real = "https://cdn.example.com/videos/feature_film.m3u8?token=abc";
        </script>
        """
        found = []
        _extract_streams_from_html(html, "https://example.com", found)
        urls = [s["url"] for s in found]
        self.assertEqual(urls, ["https://cdn.example.com/videos/feature_film.m3u8?token=abc"])

    def test_extract_page_metadata_parses_opengraph(self):
        html = """
        <html><head>
            <meta property="og:title" content="Sample Stream &amp; Clip">
            <meta property="og:image" content="/assets/cover.jpg">
        </head></html>
        """
        meta = _extract_page_metadata(html, "https://example.com/watch/1")
        self.assertEqual(meta["title"], "Sample Stream & Clip")
        self.assertEqual(meta["thumbnail"], "https://example.com/assets/cover.jpg")


class TestHlsM3u8Parsing(unittest.TestCase):
    """Verify Master M3U8 variant selection and Media M3U8 segment/key parsing."""

    def test_resolve_master_m3u8_picks_highest_resolution(self):
        master_text = """#EXTM3U
#EXT-X-VERSION:3
#EXT-X-STREAM-INF:BANDWIDTH=800000,RESOLUTION=640x360
360p/index.m3u8
#EXT-X-STREAM-INF:BANDWIDTH=4500000,RESOLUTION=1920x1080
1080p/index.m3u8
#EXT-X-STREAM-INF:BANDWIDTH=2000000,RESOLUTION=1280x720
720p/index.m3u8
"""
        base_url = "https://stream.example.com/vod/master.m3u8"
        best_variant = _resolve_master_m3u8(master_text, base_url)
        self.assertEqual(best_variant, "https://stream.example.com/vod/1080p/index.m3u8")

    def test_parse_media_m3u8_resolves_segments_map_and_aes128_key(self):
        media_text = """#EXTM3U
#EXT-X-VERSION:7
#EXT-X-TARGETDURATION:6
#EXT-X-MAP:URI="init.mp4"
#EXT-X-KEY:METHOD=AES-128,URI="/keys/enc.key",IV=0x00000000000000000000000000000005
#EXTINF:6.000,
seg-001.ts
#EXTINF:6.000,
https://cdn2.example.com/vod/seg-002.ts
#EXT-X-ENDLIST
"""
        media_url = "https://stream.example.com/vod/1080p/index.m3u8"
        parsed = _parse_media_m3u8(media_text, media_url)

        self.assertEqual(parsed["init_map"], "https://stream.example.com/vod/1080p/init.mp4")
        self.assertEqual(parsed["key_uri"], "https://stream.example.com/keys/enc.key")
        self.assertEqual(parsed["key_iv"], bytes.fromhex("00000000000000000000000000000005"))
        self.assertEqual(
            parsed["segments"],
            [
                "https://stream.example.com/vod/1080p/seg-001.ts",
                "https://cdn2.example.com/vod/seg-002.ts",
            ],
        )


class TestSmartPresetResolution(unittest.TestCase):
    """Verify Smart Auto mode selection vs explicit preset overrides."""

    def test_smart_auto_selects_mp3_for_audio_intent(self):
        presets = get_available_presets([1080, 720], prefer_audio=True)
        resolved = select_preset_for_mode(presets, intent_mode="auto", media_intent="audio")
        self.assertEqual(resolved, "오디오 MP3 (최고음질 320k)")

    def test_smart_auto_selects_best_video_for_video_intent(self):
        presets = get_available_presets([2160, 1080, 720], prefer_audio=False)
        resolved = select_preset_for_mode(presets, intent_mode="auto", media_intent="video")
        self.assertEqual(resolved, "최고 화질 (Best Auto)")

    def test_explicit_preset_overrides_smart_auto(self):
        presets = get_available_presets([1080, 720], prefer_audio=False)
        resolved_flac = select_preset_for_mode(presets, intent_mode="audio_flac", media_intent="video")
        self.assertEqual(resolved_flac, "오디오 FLAC (무손실 음원)")
        resolved_1080p = select_preset_for_mode(presets, intent_mode="video_1080p", media_intent="audio")
        self.assertEqual(resolved_1080p, "1080p FHD MP4")

    def test_format_duration(self):
        self.assertEqual(format_duration(None), "00:00")
        self.assertEqual(format_duration(125), "02:05")
        self.assertEqual(format_duration(3661), "01:01:01")


if __name__ == "__main__":
    unittest.main()

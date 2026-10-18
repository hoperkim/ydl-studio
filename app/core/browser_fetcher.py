"""
Universal Browser-Context Stream Downloader for session-locked, Cloudflare-protected,
and dynamic JavaScript streaming sites (upload18.org, embedded HLS/MP4 players, etc.).
Runs inside Chrome/Edge CDP to capture and fetch streams via the browser's authenticated session,
supporting Master M3U8 playlists, relative segment URLs, AES-128 encryption, and audio extraction.
"""
import asyncio
import base64
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import urllib.parse
import urllib.request
from typing import Any, Callable, Dict, List, Optional
import websockets

from app.core.browser_sniffer import find_browser_executable, find_free_port


def _resolve_master_m3u8(playlist_text: str, base_m3u8_url: str) -> Optional[str]:
    """
    If playlist_text is an HLS Master Playlist (#EXT-X-STREAM-INF),
    pick the highest resolution/bandwidth variant and return its absolute URL.
    """
    if "#EXT-X-STREAM-INF" not in playlist_text:
        return None

    lines = [l.strip() for l in playlist_text.splitlines() if l.strip()]
    best_url = None
    best_score = -1

    for idx, line in enumerate(lines):
        if line.startswith("#EXT-X-STREAM-INF"):
            score = 0
            bw_m = re.search(r'BANDWIDTH=(\d+)', line, re.I)
            res_m = re.search(r'RESOLUTION=\d+x(\d+)', line, re.I)
            if res_m:
                score += int(res_m.group(1)) * 10_000_000
            if bw_m:
                score += int(bw_m.group(1))
            # Next non-comment line is the variant URL
            for next_line in lines[idx + 1:]:
                if not next_line.startswith("#"):
                    cand_url = urllib.parse.urljoin(base_m3u8_url, next_line)
                    if score >= best_score:
                        best_score = score
                        best_url = cand_url
                    break

    return best_url


def _parse_media_m3u8(playlist_text: str, media_m3u8_url: str) -> Dict[str, Any]:
    """
    Parse a media M3U8 playlist into absolute segment URLs, optional init map URL,
    and optional AES-128 key info.
    """
    segment_urls: List[str] = []
    init_map_url: Optional[str] = None
    key_uri: Optional[str] = None
    key_iv: Optional[bytes] = None

    for raw_line in playlist_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#EXT-X-MAP:"):
            m_uri = re.search(r'URI=["\']([^"\']+)["\']', line, re.I)
            if m_uri:
                init_map_url = urllib.parse.urljoin(media_m3u8_url, m_uri.group(1))
        elif line.startswith("#EXT-X-KEY:"):
            if "METHOD=AES-128" in line.upper():
                m_uri = re.search(r'URI=["\']([^"\']+)["\']', line, re.I)
                if m_uri:
                    key_uri = urllib.parse.urljoin(media_m3u8_url, m_uri.group(1))
                m_iv = re.search(r'IV=0x([0-9a-fA-F]+)', line, re.I)
                if m_iv:
                    try:
                        key_iv = bytes.fromhex(m_iv.group(1).zfill(32))
                    except Exception:
                        pass
        elif not line.startswith("#"):
            abs_seg = urllib.parse.urljoin(media_m3u8_url, line)
            if abs_seg.lower().startswith(("http://", "https://")):
                segment_urls.append(abs_seg)

    return {
        "segments": segment_urls,
        "init_map": init_map_url,
        "key_uri": key_uri,
        "key_iv": key_iv,
    }


class BrowserStreamDownloader:
    """Downloads streams from any dynamic or session-locked site via Chrome/Edge CDP."""

    def __init__(
        self,
        page_url: str,
        output_dir: str,
        preset: str = "최고 화질 (Best Auto)",
        on_progress: Optional[Callable[[float, str, str], None]] = None,
        on_status: Optional[Callable[[str, str], None]] = None,
        on_finish: Optional[Callable[[str], None]] = None,
    ):
        self.page_url = page_url
        self.output_dir = output_dir
        self.preset = preset
        self.on_progress = on_progress
        self.on_status = on_status
        self.on_finish = on_finish
        self.is_cancelled = False

    def cancel(self):
        self.is_cancelled = True

    async def _eval_js(self, ws, expression: str, msg_id: int, intercepted_urls: List[str], timeout_loops: int = 25) -> Any:
        """Send Runtime.evaluate and collect network events while waiting for response."""
        await ws.send(json.dumps({
            "id": msg_id,
            "method": "Runtime.evaluate",
            "params": {"expression": expression, "awaitPromise": True, "returnByValue": True}
        }))
        for _ in range(timeout_loops):
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=1.0)
                d = json.loads(raw)
                # Capture any network request URLs seen on the wire
                method = d.get("method", "")
                if method == "Network.requestWillBeSent":
                    req_url = d.get("params", {}).get("request", {}).get("url", "")
                    if req_url and any(ext in req_url.lower() for ext in [".m3u8", ".mpd", ".mp4", ".m4a", ".mp3"]):
                        if not any(ign in req_url.lower() for ign in ["preview", "sprite", "thumb", "ads", "doubleclick"]):
                            if req_url not in intercepted_urls:
                                intercepted_urls.append(req_url)
                if d.get("id") == msg_id:
                    return d.get("result", {}).get("result", {}).get("value")
            except asyncio.TimeoutError:
                continue
        return None

    async def _fetch_text_in_browser(self, ws, target_url: str, msg_id: int, intercepted_urls: List[str]) -> Optional[str]:
        url_json = json.dumps(target_url)
        expr = f"""
        (async function() {{
            try {{
                var r = await fetch({url_json}, {{ headers: {{ 'Range': 'bytes=0-' }} }});
                if (!r.ok && r.status !== 206) {{
                    r = await fetch({url_json});
                }}
                return await r.text();
            }} catch(e) {{
                return null;
            }}
        }})()
        """
        return await self._eval_js(ws, expr, msg_id, intercepted_urls, timeout_loops=20)

    async def _fetch_bytes_in_browser(self, ws, target_url: str, msg_id: int, intercepted_urls: List[str]) -> Optional[bytes]:
        url_json = json.dumps(target_url)
        expr = f"""
        (async function() {{
            try {{
                var r = await fetch({url_json}, {{ headers: {{ 'Range': 'bytes=0-' }} }});
                if (!r.ok && r.status !== 206) {{
                    r = await fetch({url_json});
                }}
                var buf = await r.arrayBuffer();
                var bytes = new Uint8Array(buf);
                var binary = '';
                for (var j = 0; j < bytes.byteLength; j++) {{
                    binary += String.fromCharCode(bytes[j]);
                }}
                return btoa(binary);
            }} catch(e) {{
                return null;
            }}
        }})()
        """
        b64 = await self._eval_js(ws, expr, msg_id, intercepted_urls, timeout_loops=25)
        if b64 and isinstance(b64, str):
            try:
                return base64.b64decode(b64)
            except Exception:
                return None
        return None

    async def run_async(self, max_segments: Optional[int] = None) -> Optional[str]:
        chrome_exe = find_browser_executable()
        if not chrome_exe:
            raise RuntimeError("Chrome 또는 Edge 브라우저를 찾을 수 없습니다.")

        port = find_free_port(9300)
        temp_dir = tempfile.mkdtemp(prefix="ydl_browser_dl_")

        if self.on_status:
            self.on_status("STARTING", "브라우저 보안 세션 자동 연결 중…")

        cmd = [
            chrome_exe,
            f"--remote-debugging-port={port}",
            f"--user-data-dir={temp_dir}",
            "--no-first-run",
            "--no-default-browser-check",
            "--autoplay-policy=no-user-gesture-required",
            "--mute-audio",
            "--window-position=-32000,-32000",
            "--window-size=1280,720",
            self.page_url
        ]

        proc = subprocess.Popen(cmd)
        ts_output_path = None
        final_output_path = None
        intercepted_urls: List[str] = []

        try:
            # Wait for browser CDP endpoint
            page_tab = None
            for _ in range(25):
                if self.is_cancelled:
                    raise RuntimeError("다운로드가 취소되었습니다.")
                await asyncio.sleep(0.4)
                try:
                    with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=1) as resp:
                        tabs = json.loads(resp.read().decode())
                    page_tab = next((t for t in tabs if t.get("type") == "page"), None)
                    if page_tab and page_tab.get("webSocketDebuggerUrl"):
                        break
                except Exception:
                    pass

            if not page_tab:
                raise RuntimeError("브라우저 보안 탭을 초기화할 수 없습니다.")

            ws_url = page_tab.get("webSocketDebuggerUrl")
            title = page_tab.get("title", "video").replace(" Coppy", "").strip()

            async with websockets.connect(ws_url, max_size=60 * 1024 * 1024) as ws:
                # Enable Network monitoring on the page
                await ws.send(json.dumps({"id": 1, "method": "Network.enable"}))
                await ws.send(json.dumps({"id": 2, "method": "Page.enable"}))

                if self.on_status:
                    self.on_status("ANALYZING", "웹 플레이어 구동 및 미디어 스트림 자동 포착 중…")

                # Wait briefly for page DOM & scripts to load while collecting network events
                for _ in range(8):
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=0.5)
                        d = json.loads(raw)
                        if d.get("method") == "Network.requestWillBeSent":
                            req_url = d.get("params", {}).get("request", {}).get("url", "")
                            if req_url and any(ext in req_url.lower() for ext in [".m3u8", ".mpd", ".mp4", ".m4a", ".mp3"]):
                                if not any(ign in req_url.lower() for ign in ["preview", "sprite", "thumb", "ads"]):
                                    intercepted_urls.append(req_url)
                    except asyncio.TimeoutError:
                        pass

                # Universal Player Auto-Starter (JWPlayer, Video.js, Plyr, HTML5 Video/Audio, Play Buttons)
                auto_play_js = """
                (function() {
                    try { if (typeof jwplayer !== 'undefined') jwplayer().play(); } catch(e) {}
                    try {
                        document.querySelectorAll('video, audio').forEach(v => {
                            v.muted = true;
                            v.play().catch(()=>{});
                        });
                    } catch(e) {}
                    try {
                        var selectors = ['.vjs-big-play-button', '.jw-icon-display', '.plyr__control--overlaid', '.play-button', '[aria-label="Play"]'];
                        selectors.forEach(s => {
                            var el = document.querySelector(s);
                            if (el) el.click();
                        });
                    } catch(e) {}
                })()
                """
                await self._eval_js(ws, auto_play_js, 10, intercepted_urls, timeout_loops=5)
                await asyncio.sleep(2.5)

                # Universal Stream Probe in JS (JWPlayer, PLAYER_CONFIG, HTML5 video/audio, Performance Resource Timing)
                probe_js = """
                (async function() {
                    var candidates = [];
                    try {
                        if (typeof jwplayer !== 'undefined' && jwplayer().getPlaylist) {
                            var pl = jwplayer().getPlaylist();
                            if (pl && pl[0]) {
                                if (pl[0].file) candidates.push(pl[0].file);
                                if (pl[0].sources) pl[0].sources.forEach(s => { if (s.file) candidates.push(s.file); });
                            }
                        }
                    } catch(e) {}
                    try {
                        if (window.PLAYER_CONFIG && window.PLAYER_CONFIG.m3u8) {
                            candidates.push(window.PLAYER_CONFIG.m3u8);
                        }
                    } catch(e) {}
                    try {
                        document.querySelectorAll('video, audio, source').forEach(el => {
                            if (el.currentSrc && !el.currentSrc.startsWith('blob:')) candidates.push(el.currentSrc);
                            if (el.src && !el.src.startsWith('blob:')) candidates.push(el.src);
                        });
                    } catch(e) {}
                    try {
                        performance.getEntriesByType('resource').forEach(r => {
                            var n = r.name || '';
                            if (/\\.(m3u8|mpd|mp4|m4a|mp3)(\\?|$)/i.test(n) && !/(preview|sprite|thumb|ads)/i.test(n)) {
                                candidates.push(n);
                            }
                        });
                    } catch(e) {}
                    return { candidates: candidates, title: document.title || 'video' };
                })()
                """
                probe_res = await self._eval_js(ws, probe_js, 20, intercepted_urls, timeout_loops=15)
                if probe_res and isinstance(probe_res, dict):
                    if probe_res.get("title"):
                        title = probe_res["title"].replace(" Coppy", "").strip()
                    for c in probe_res.get("candidates", []):
                        if c and c not in intercepted_urls:
                            intercepted_urls.append(c)

                if not intercepted_urls:
                    raise RuntimeError("브라우저 세션에서 재생 가능한 미디어 스트림을 찾지 못했습니다.")

                # Prioritize .m3u8 > .mp4/.m4a/.mp3
                m3u8_candidates = [u for u in intercepted_urls if ".m3u8" in u.lower()]
                stream_url = m3u8_candidates[0] if m3u8_candidates else intercepted_urls[0]

                safe_title = re.sub(r'[\\/*?:"<>|]', "_", title).strip()
                if not safe_title:
                    safe_title = f"media_{int(time.time())}"

                # Determine final output extension based on user preset
                is_audio_preset = "오디오" in self.preset or "MP3" in self.preset or "M4A" in self.preset or "FLAC" in self.preset
                if "FLAC" in self.preset:
                    out_ext = "flac"
                elif "M4A" in self.preset:
                    out_ext = "m4a"
                elif is_audio_preset:
                    out_ext = "mp3"
                else:
                    out_ext = "mp4"

                final_output_path = os.path.join(self.output_dir, f"{safe_title}.{out_ext}")
                ts_output_path = os.path.join(self.output_dir, f"{safe_title}.ts.temp")

                # Case A: Direct MP4 / MP3 / M4A file (not M3U8)
                if ".m3u8" not in stream_url.lower():
                    if self.on_status:
                        self.on_status("DOWNLOADING", "브라우저 직접 미디어 스트림 다운로드 중…")
                    raw_bytes = await self._fetch_bytes_in_browser(ws, stream_url, 30, intercepted_urls)
                    if not raw_bytes:
                        raise RuntimeError("직접 미디어 스트림 데이터를 가져오지 못했습니다.")
                    with open(ts_output_path, "wb") as f:
                        f.write(raw_bytes)
                else:
                    # Case B: HLS (.m3u8) Playlist
                    playlist_text = await self._fetch_text_in_browser(ws, stream_url, 31, intercepted_urls)
                    if not playlist_text:
                        raise RuntimeError("M3U8 플레이리스트 응답을 가져오지 못했습니다.")

                    # Check if Master Playlist (#EXT-X-STREAM-INF)
                    variant_url = _resolve_master_m3u8(playlist_text, stream_url)
                    if variant_url:
                        stream_url = variant_url
                        playlist_text = await self._fetch_text_in_browser(ws, stream_url, 32, intercepted_urls) or ""

                    parsed_hls = _parse_media_m3u8(playlist_text, stream_url)
                    segment_urls = parsed_hls["segments"]
                    init_map_url = parsed_hls["init_map"]
                    key_uri = parsed_hls["key_uri"]
                    key_iv = parsed_hls["key_iv"]

                    if not segment_urls:
                        raise RuntimeError("플레이리스트에서 다운로드할 세그먼트 조각을 찾을 수 없습니다.")

                    if max_segments:
                        segment_urls = segment_urls[:max_segments]

                    # Optional AES-128 key fetch
                    aes_key: Optional[bytes] = None
                    if key_uri:
                        aes_key = await self._fetch_bytes_in_browser(ws, key_uri, 33, intercepted_urls)

                    total_segments = len(segment_urls)
                    if self.on_status:
                        self.on_status("DOWNLOADING", f"고속 병렬 세그먼트 수집 중 (총 {total_segments}조각)")

                    batch_size = 6
                    downloaded_count = 0
                    start_time = time.time()
                    total_bytes = 0

                    with open(ts_output_path, "wb") as ts_file:
                        # Write fMP4 init map if present
                        if init_map_url:
                            init_bytes = await self._fetch_bytes_in_browser(ws, init_map_url, 34, intercepted_urls)
                            if init_bytes:
                                ts_file.write(init_bytes)
                                total_bytes += len(init_bytes)

                        for i in range(0, total_segments, batch_size):
                            if self.is_cancelled:
                                raise RuntimeError("사용자에 의해 다운로드가 취소되었습니다.")

                            batch = segment_urls[i:i + batch_size]
                            batch_json = json.dumps(batch)

                            fetch_batch_expr = f"""
                            (async function() {{
                                var urls = {batch_json};
                                var results = await Promise.all(urls.map(async u => {{
                                    try {{
                                        var r = await fetch(u, {{ headers: {{ 'Range': 'bytes=0-' }} }});
                                        if (!r.ok && r.status !== 206) {{
                                            r = await fetch(u);
                                        }}
                                        var buf = await r.arrayBuffer();
                                        var bytes = new Uint8Array(buf);
                                        var binary = '';
                                        var chunk = 8192;
                                        for (var j = 0; j < bytes.length; j += chunk) {{
                                            binary += String.fromCharCode.apply(null, bytes.subarray(j, j + chunk));
                                        }}
                                        return btoa(binary);
                                    }} catch(e) {{
                                        return null;
                                    }}
                                }}));
                                return results;
                            }})()
                            """

                            batch_data = await self._eval_js(ws, fetch_batch_expr, 100 + i, intercepted_urls, timeout_loops=35)
                            if batch_data and isinstance(batch_data, list):
                                for offset, b64 in enumerate(batch_data):
                                    if b64:
                                        raw = base64.b64decode(b64)
                                        if aes_key and len(aes_key) == 16:
                                            try:
                                                from Cryptodome.Cipher import AES
                                                iv = key_iv or (i + offset).to_bytes(16, byteorder="big")
                                                cipher = AES.new(aes_key, AES.MODE_CBC, iv)
                                                raw = cipher.decrypt(raw)
                                            except Exception:
                                                pass
                                        ts_file.write(raw)
                                        total_bytes += len(raw)
                                        downloaded_count += 1

                            percent = (downloaded_count / total_segments) * 100.0
                            elapsed = max(time.time() - start_time, 0.001)
                            speed_mb = (total_bytes / 1024 / 1024) / elapsed
                            speed_str = f"{speed_mb:.2f} MB/s"

                            rem_sec = int((total_segments - downloaded_count) / (downloaded_count / elapsed)) if downloaded_count > 0 else 0
                            eta_str = f"남은 시간: {rem_sec}초" if rem_sec < 3600 else f"남은 시간: {rem_sec // 60}분"

                            if self.on_progress:
                                self.on_progress(percent, speed_str, eta_str)
                            if self.on_status:
                                self.on_status("DOWNLOADING", f"{percent:.1f}% ({downloaded_count}/{total_segments} 조각 • {speed_str})")

                # Convert/Remux using FFmpeg according to video or audio preset
                if self.on_status:
                    self.on_status("PROCESSING", f"FFmpeg {out_ext.upper()} 변환 및 후처리 중…")

                from app.utils.ffmpeg_manager import find_ffmpeg_binary
                ffmpeg_bin = find_ffmpeg_binary() or shutil.which("ffmpeg") or r"C:\FFmpeg\bin\ffmpeg.exe"
                if is_audio_preset:
                    if out_ext == "flac":
                        cmd_ffmpeg = [ffmpeg_bin, "-y", "-i", ts_output_path, "-vn", "-c:a", "flac", final_output_path]
                    elif out_ext == "m4a":
                        cmd_ffmpeg = [ffmpeg_bin, "-y", "-i", ts_output_path, "-vn", "-c:a", "aac", "-b:a", "256k", final_output_path]
                    else:
                        bitrate = "320k" if "320" in self.preset else "192k"
                        cmd_ffmpeg = [ffmpeg_bin, "-y", "-i", ts_output_path, "-vn", "-c:a", "libmp3lame", "-b:a", bitrate, final_output_path]
                else:
                    cmd_ffmpeg = [
                        ffmpeg_bin, "-y",
                        "-i", ts_output_path,
                        "-c", "copy",
                        "-bsf:a", "aac_adtstoasc",
                        final_output_path
                    ]

                subprocess.run(
                    cmd_ffmpeg,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
                    check=True
                )

                try:
                    os.remove(ts_output_path)
                except Exception:
                    pass

                if self.on_status:
                    self.on_status("FINISHED", "다운로드 완료!")
                if self.on_finish:
                    self.on_finish(final_output_path)

                return final_output_path

        finally:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except Exception:
                pass
            shutil.rmtree(temp_dir, ignore_errors=True)
            if ts_output_path and os.path.exists(ts_output_path) and not final_output_path:
                try:
                    os.remove(ts_output_path)
                except Exception:
                    pass

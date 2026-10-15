"""
Browser-Context Stream Downloader for session-locked and Cloudflare-protected streaming sites.
Runs inside Chrome CDP to fetch segments via browser's authenticated session,
then remuxes directly into MP4 using FFmpeg.
"""
import asyncio
import base64
import json
import os
import shutil
import subprocess
import tempfile
import time
import urllib.request
from typing import Callable, Optional
import websockets

from app.core.browser_sniffer import find_browser_executable, find_free_port


class BrowserStreamDownloader:
    """Downloads streams from sites like upload18.org that require in-browser authentication."""

    def __init__(
        self,
        page_url: str,
        output_dir: str,
        on_progress: Optional[Callable[[float, str, str], None]] = None,
        on_status: Optional[Callable[[str, str], None]] = None,
        on_finish: Optional[Callable[[str], None]] = None,
    ):
        self.page_url = page_url
        self.output_dir = output_dir
        self.on_progress = on_progress
        self.on_status = on_status
        self.on_finish = on_finish
        self.is_cancelled = False

    def cancel(self):
        self.is_cancelled = True

    async def run_async(self, max_segments: Optional[int] = None) -> Optional[str]:
        chrome_exe = find_browser_executable()
        if not chrome_exe:
            raise RuntimeError("Chrome 또는 Edge 브라우저를 찾을 수 없습니다.")

        port = find_free_port(9300)
        temp_dir = tempfile.mkdtemp(prefix="ydl_browser_dl_")

        if self.on_status:
            self.on_status("STARTING", "브라우저 보안 세션 연결 중…")

        cmd = [
            chrome_exe,
            f"--remote-debugging-port={port}",
            f"--user-data-dir={temp_dir}",
            "--no-first-run",
            "--no-default-browser-check",
            self.page_url
        ]

        proc = subprocess.Popen(cmd)
        ts_output_path = None
        final_mp4_path = None

        try:
            # Wait for browser to initialize
            await asyncio.sleep(4)
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list") as resp:
                tabs = json.loads(resp.read().decode())
            page_tab = next((t for t in tabs if t.get("type") == "page"), None)
            if not page_tab:
                raise RuntimeError("브라우저 탭을 열 수 없습니다.")

            ws_url = page_tab.get("webSocketDebuggerUrl")
            title = page_tab.get("title", "video").replace(" Coppy", "").strip()

            async with websockets.connect(ws_url, max_size=50 * 1024 * 1024) as ws:
                if self.on_status:
                    self.on_status("ANALYZING", "영상 플레이어 및 M3U8 주소 추출 중…")

                # Trigger video playback in jwplayer
                await ws.send(json.dumps({
                    "id": 1,
                    "method": "Runtime.evaluate",
                    "params": {"expression": "if (typeof jwplayer !== 'undefined') { jwplayer().play(); }"}
                }))

                await asyncio.sleep(3)

                # Extract playlist text
                expr_m3u8 = """
                (async function() {
                    try {
                        var item = (typeof jwplayer !== 'undefined') ? jwplayer().getPlaylist()[0] : null;
                        var m3u8Url = item ? item.file : (window.PLAYER_CONFIG ? window.PLAYER_CONFIG.m3u8 : null);
                        if (!m3u8Url) return { error: '플레이리스트 URL을 찾을 수 없습니다.' };
                        
                        var r = await fetch(m3u8Url, { headers: { 'Range': 'bytes=0-' } });
                        var text = await r.text();
                        return { url: m3u8Url, text: text, title: document.title };
                    } catch(e) {
                        return { error: e.toString() };
                    }
                })()
                """
                await ws.send(json.dumps({
                    "id": 2,
                    "method": "Runtime.evaluate",
                    "params": {"expression": expr_m3u8, "awaitPromise": True, "returnByValue": True}
                }))

                m3u8_info = None
                for _ in range(20):
                    msg = await ws.recv()
                    d = json.loads(msg)
                    if d.get("id") == 2:
                        m3u8_info = d.get("result", {}).get("result", {}).get("value")
                        break

                if not m3u8_info or "error" in m3u8_info:
                    err = m3u8_info.get("error") if m3u8_info else "M3U8 추출 타임아웃"
                    raise RuntimeError(f"영상 스트림을 추출하지 못했습니다: {err}")

                playlist_text = m3u8_info["text"]
                if m3u8_info.get("title"):
                    title = m3u8_info["title"].replace(" Coppy", "").strip()

                # Parse segment URLs
                segment_urls = [
                    line.strip() for line in playlist_text.splitlines()
                    if line.strip().startswith("http") and not line.strip().startswith("#")
                ]

                if not segment_urls:
                    raise RuntimeError("플레이리스트에서 다운로드할 영상 세그먼트를 찾을 수 없습니다.")

                if max_segments:
                    segment_urls = segment_urls[:max_segments]

                total_segments = len(segment_urls)
                safe_title = "".join(c for c in title if c.isalnum() or c in (" ", "-", "_")).strip()
                if not safe_title:
                    safe_title = "downloaded_video"

                final_mp4_path = os.path.join(self.output_dir, f"{safe_title}.mp4")
                ts_output_path = os.path.join(self.output_dir, f"{safe_title}.ts.temp")

                if self.on_status:
                    self.on_status("DOWNLOADING", f"세그먼트 다운로드 시작 (총 {total_segments}개)")

                # Download in batches of 4 segments concurrently via in-browser fetch
                batch_size = 4
                downloaded_count = 0
                start_time = time.time()
                total_bytes = 0

                with open(ts_output_path, "wb") as ts_file:
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
                                    var buf = await r.arrayBuffer();
                                    var bytes = new Uint8Array(buf);
                                    var binary = '';
                                    var len = bytes.byteLength;
                                    for (var j = 0; j < len; j++) {{
                                        binary += String.fromCharCode(bytes[j]);
                                    }}
                                    return btoa(binary);
                                }} catch(e) {{
                                    return null;
                                }}
                            }}));
                            return results;
                        }})()
                        """

                        await ws.send(json.dumps({
                            "id": 100 + i,
                            "method": "Runtime.evaluate",
                            "params": {"expression": fetch_batch_expr, "awaitPromise": True, "returnByValue": True}
                        }))

                        batch_data = None
                        for _ in range(30):
                            msg = await ws.recv()
                            d = json.loads(msg)
                            if d.get("id") == 100 + i:
                                batch_data = d.get("result", {}).get("result", {}).get("value")
                                break

                        if batch_data:
                            for b64 in batch_data:
                                if b64:
                                    raw = base64.b64decode(b64)
                                    ts_file.write(raw)
                                    total_bytes += len(raw)
                                    downloaded_count += 1

                        # Calculate progress and speed
                        percent = (downloaded_count / total_segments) * 100.0
                        elapsed = time.time() - start_time
                        speed_mb = (total_bytes / 1024 / 1024) / elapsed if elapsed > 0 else 0
                        speed_str = f"{speed_mb:.2f} MB/s"

                        rem_sec = int((total_segments - downloaded_count) / (downloaded_count / elapsed)) if downloaded_count > 0 else 0
                        eta_str = f"남은 시간: {rem_sec}초" if rem_sec < 3600 else f"남은 시간: {rem_sec//60}분"

                        if self.on_progress:
                            self.on_progress(percent, speed_str, eta_str)
                        if self.on_status:
                            self.on_status("DOWNLOADING", f"{percent:.1f}% ({downloaded_count}/{total_segments} 조각 | {speed_str})")

                # Remux .ts to .mp4 using FFmpeg
                if self.on_status:
                    self.on_status("PROCESSING", "FFmpeg 무손실 MP4 변환 및 병합 중…")

                ffmpeg_bin = shutil.which("ffmpeg") or r"C:\FFmpeg\bin\ffmpeg.exe"
                cmd_ffmpeg = [
                    ffmpeg_bin, "-y",
                    "-i", ts_output_path,
                    "-c", "copy",
                    "-bsf:a", "aac_adtstoasc",
                    final_mp4_path
                ]
                subprocess.run(
                    cmd_ffmpeg,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
                    check=True
                )

                # Clean up temporary .ts
                try:
                    os.remove(ts_output_path)
                except Exception:
                    pass

                if self.on_status:
                    self.on_status("FINISHED", "다운로드 완료!")
                if self.on_finish:
                    self.on_finish(final_mp4_path)

                return final_mp4_path

        finally:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except Exception:
                pass
            shutil.rmtree(temp_dir, ignore_errors=True)
            if ts_output_path and os.path.exists(ts_output_path) and not final_mp4_path:
                try:
                    os.remove(ts_output_path)
                except Exception:
                    pass

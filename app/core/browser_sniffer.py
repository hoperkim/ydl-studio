"""
Browser Stream Sniffer module for YDL Studio.
Leverages Chrome DevTools Protocol (CDP) to capture media streams (HLS m3u8, DASH mpd, MP4, WebM)
and casting streams from Chrome / Edge browsers in real time.
"""
import asyncio
import json
import os
import re
import socket
import subprocess
import threading
import time
import urllib.request
from typing import Any, Callable, Dict, List, Optional
import websockets


def find_browser_executable(preferred: str = "auto") -> Optional[str]:
    """Find Google Chrome or Microsoft Edge executable on Windows."""
    candidates = []

    chrome_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    ]
    edge_paths = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe"),
    ]

    if preferred == "edge":
        candidates = edge_paths + chrome_paths
    elif preferred == "chrome":
        candidates = chrome_paths + edge_paths
    else:  # auto
        candidates = chrome_paths + edge_paths

    for p in candidates:
        if os.path.exists(p):
            return p
    return None


def find_free_port(start_port: int = 9222) -> int:
    """Find an available TCP port for remote debugging."""
    for port in range(start_port, start_port + 50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(('127.0.0.1', port)) != 0:
                return port
    return start_port


MEDIA_EXT_PATTERN = re.compile(
    r'\.(m3u8|mpd|mp4|webm|m4v|m4a|ts)(?:\?|$|#)', re.IGNORECASE
)
MEDIA_MIME_TYPES = {
    'application/vnd.apple.mpegurl',
    'application/x-mpegurl',
    'application/dash+xml',
    'video/mp4',
    'video/webm',
    'video/ogg',
    'video/x-flv',
}

# Substrings to ignore (analytics, trackers, non-content beacons, audio sprites, ads)
IGNORE_KEYWORDS = [
    'google-analytics', 'doubleclick', 'telemetry', 'analytics', 'pixel',
    'beacon', 'facebook.com/tr', 'hotjar', 'amplitude', 'adservice'
]


class BrowserSniffer:
    """
    Manages browser launch with CDP enabled and listens to network traffic
    to intercept streaming URLs and authentication headers.
    """

    def __init__(
        self,
        on_stream_detected: Optional[Callable[[Dict[str, Any]], None]] = None,
        preferred_browser: str = "auto",
        port: int = 9222,
    ) -> None:
        self.on_stream_detected = on_stream_detected
        self.preferred_browser = preferred_browser
        self.port = port
        self.browser_proc: Optional[subprocess.Popen] = None
        self.is_running = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self.detected_urls: set = set()
        self.detected_streams: List[Dict[str, Any]] = []

    def launch_and_start(self, initial_url: str = "about:blank") -> bool:
        """Launch browser and start CDP sniffer thread."""
        browser_exe = find_browser_executable(self.preferred_browser)
        if not browser_exe:
            raise FileNotFoundError("Chrome 또는 Edge 브라우저를 찾을 수 없습니다.")

        # Ensure port is open or find a free one
        self.port = find_free_port(self.port)

        # Dedicated user data profile for sniffer to prevent interfering with default user sessions
        profile_dir = os.path.join(
            os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
            "YDLStudio",
            "SnifferBrowserProfile"
        )
        os.makedirs(profile_dir, exist_ok=True)

        cmd = [
            browser_exe,
            f"--remote-debugging-port={self.port}",
            f"--user-data-dir={profile_dir}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-popup-blocking",
            initial_url
        ]

        self.browser_proc = subprocess.Popen(cmd)
        self.is_running = True

        # Wait a moment for browser CDP endpoint to come alive
        self._thread = threading.Thread(target=self._run_async_loop, daemon=True)
        self._thread.start()
        return True

    def stop(self) -> None:
        """Stop sniffing and terminate browser if opened by us."""
        self.is_running = False
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)

        if self.browser_proc:
            try:
                self.browser_proc.terminate()
            except Exception:
                pass
            self.browser_proc = None

    def _run_async_loop(self) -> None:
        """Run asyncio event loop in background thread."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._listen_cdp())
        except Exception:
            pass
        finally:
            self.is_running = False

    async def _listen_cdp(self) -> None:
        """Connect to browser CDP and monitor network traffic."""
        # Wait up to 5 seconds for CDP endpoint
        browser_ws = None
        for _ in range(25):
            if not self.is_running:
                return
            try:
                req = urllib.request.Request(f"http://127.0.0.1:{self.port}/json/version")
                with urllib.request.urlopen(req, timeout=1) as resp:
                    data = json.loads(resp.read().decode())
                    browser_ws = data.get("webSocketDebuggerUrl")
                    if browser_ws:
                        break
            except Exception:
                await asyncio.sleep(0.2)

        if not browser_ws:
            return

        try:
            async with websockets.connect(browser_ws, max_size=10 * 1024 * 1024) as ws:
                # Tell browser to auto-attach to all targets (pages, iframes)
                await ws.send(json.dumps({
                    "id": 1,
                    "method": "Target.setAutoAttach",
                    "params": {
                        "autoAttach": True,
                        "waitForDebuggerOnStart": False,
                        "flatten": True
                    }
                }))

                # Map session IDs to tab info
                sessions: Dict[str, Dict[str, Any]] = {}

                while self.is_running:
                    try:
                        msg = await asyncio.wait_for(ws.recv(), timeout=1.0)
                        data = json.loads(msg)
                        method = data.get("method", "")
                        session_id = data.get("sessionId")

                        if method == "Target.attachedToTarget":
                            params = data.get("params", {})
                            sid = params.get("sessionId")
                            tinfo = params.get("targetInfo", {})
                            if sid and tinfo.get("type") == "page":
                                sessions[sid] = tinfo
                                # Enable network on this session
                                await ws.send(json.dumps({
                                    "id": 2,
                                    "sessionId": sid,
                                    "method": "Network.enable"
                                }))

                        elif method == "Target.targetInfoChanged":
                            params = data.get("params", {})
                            tinfo = params.get("targetInfo", {})
                            # Update title/url if available
                            for sid, info in sessions.items():
                                if info.get("targetId") == tinfo.get("targetId"):
                                    info.update(tinfo)

                        elif method == "Network.requestWillBeSent":
                            self._handle_request_event(data.get("params", {}), sessions.get(session_id))

                        elif method == "Network.responseReceived":
                            self._handle_response_event(data.get("params", {}), sessions.get(session_id))

                    except asyncio.TimeoutError:
                        continue
                    except websockets.exceptions.ConnectionClosed:
                        break
                    except Exception:
                        pass
        except Exception:
            pass

    def _handle_request_event(self, params: Dict[str, Any], tab_info: Optional[Dict[str, Any]]) -> None:
        """Inspect outgoing network request for media streams."""
        request = params.get("request", {})
        url = request.get("url", "")
        if not url or url.startswith("data:") or url.startswith("blob:"):
            return

        # Filter out noisy analytics
        if any(ign in url.lower() for ign in IGNORE_KEYWORDS):
            return

        # Check if URL matches media patterns
        if MEDIA_EXT_PATTERN.search(url):
            self._register_stream(
                url=url,
                headers=request.get("headers", {}),
                tab_info=tab_info,
                source_event="request"
            )

    def _handle_response_event(self, params: Dict[str, Any], tab_info: Optional[Dict[str, Any]]) -> None:
        """Inspect response headers for media MIME types."""
        response = params.get("response", {})
        url = response.get("url", "")
        mime = (response.get("mimeType") or "").lower()
        if not url or any(ign in url.lower() for ign in IGNORE_KEYWORDS):
            return

        is_media_mime = any(m in mime for m in MEDIA_MIME_TYPES)
        if is_media_mime or MEDIA_EXT_PATTERN.search(url):
            self._register_stream(
                url=url,
                headers=response.get("requestHeaders", {}),
                tab_info=tab_info,
                mime_type=mime,
                source_event="response"
            )

    def _register_stream(
        self,
        url: str,
        headers: Dict[str, Any],
        tab_info: Optional[Dict[str, Any]],
        mime_type: str = "",
        source_event: str = ""
    ) -> None:
        """Deduplicate and register a newly detected media stream."""
        # For TS chunks, only register if it's not a flood
        clean_key = url.split("?")[0]
        if clean_key in self.detected_urls:
            return

        # If it's a .ts chunk, check if we already have an m3u8 from the same host/path
        if clean_key.endswith(".ts"):
            # If we already have m3u8, skip individual TS fragments to prevent flooding
            for existing in self.detected_urls:
                if existing.endswith(".m3u8"):
                    return

        self.detected_urls.add(clean_key)

        # Detect stream type
        url_lower = url.lower()
        if ".m3u8" in url_lower or "mpegurl" in mime_type:
            stream_type = "HLS (m3u8)"
        elif ".mpd" in url_lower or "dash" in mime_type:
            stream_type = "DASH (mpd)"
        elif ".mp4" in url_lower or "video/mp4" in mime_type:
            stream_type = "Direct MP4"
        elif ".webm" in url_lower:
            stream_type = "WebM"
        else:
            stream_type = "미디어 스트림"

        # Tab metadata
        page_title = (tab_info.get("title") if tab_info else "") or "스트림 영상"
        page_url = (tab_info.get("url") if tab_info else "") or headers.get("Referer") or ""

        # Normalize headers
        req_headers = {}
        for k, v in headers.items():
            k_lower = k.lower()
            if k_lower in ("referer", "user-agent", "origin", "cookie", "authorization"):
                req_headers[k] = v

        stream_item = {
            "url": url,
            "page_title": page_title,
            "page_url": page_url,
            "stream_type": stream_type,
            "headers": req_headers,
            "detected_time": time.strftime("%H:%M:%S"),
        }

        self.detected_streams.append(stream_item)

        if self.on_stream_detected:
            try:
                self.on_stream_detected(stream_item)
            except Exception:
                pass

"""
Portable FFmpeg & FFprobe Auto-Locator and Zero-Click Bootstrapper.
Ensures that even on a clean Windows PC without FFmpeg installed, YDL Studio
automatically locates or downloads portable ffmpeg.exe/ffprobe.exe into
%LOCALAPPDATA%\\YDLStudio\\bin and injects it into PATH and yt-dlp.
"""
import io
import os
import shutil
import sys
import threading
import urllib.request
import zipfile
from typing import Callable, Optional


FFMPEG_PORTABLE_ZIP_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"


def get_portable_bin_dir() -> str:
    """Return persistent local appdata directory for portable binaries."""
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    bin_dir = os.path.join(base, "YDLStudio", "bin")
    os.makedirs(bin_dir, exist_ok=True)
    return bin_dir


def find_ffmpeg_binary() -> Optional[str]:
    """
    Locate ffmpeg.exe across:
    1. Current executable directory (portable folder)
    2. %LOCALAPPDATA%\\YDLStudio\\bin
    3. System PATH
    4. Common Windows install paths (C:\\FFmpeg\\bin, winget, chocolatey)
    """
    exe_dir = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.getcwd()
    portable_bin = get_portable_bin_dir()

    candidates = [
        os.path.join(exe_dir, "ffmpeg.exe"),
        os.path.join(portable_bin, "ffmpeg.exe"),
        r"C:\FFmpeg\bin\ffmpeg.exe",
    ]

    for c in candidates:
        if os.path.isfile(c):
            _ensure_dir_in_path(os.path.dirname(c))
            return c

    which_ff = shutil.which("ffmpeg")
    if which_ff and os.path.isfile(which_ff):
        return which_ff

    return None


def _ensure_dir_in_path(directory: str) -> None:
    """Prepend directory to process PATH so yt-dlp and subprocess find ffmpeg/ffprobe."""
    current_path = os.environ.get("PATH", "")
    if directory.lower() not in current_path.lower():
        os.environ["PATH"] = directory + os.pathsep + current_path


def ensure_ffmpeg_async(
    on_status: Optional[Callable[[str], None]] = None,
    on_ready: Optional[Callable[[bool, str], None]] = None,
) -> None:
    """
    Check if FFmpeg is available; if missing on a clean PC, automatically download
    and extract portable ffmpeg.exe & ffprobe.exe in the background.
    """
    existing = find_ffmpeg_binary()
    if existing:
        if on_ready:
            on_ready(True, existing)
        return

    def _worker():
        target_dir = get_portable_bin_dir()
        try:
            if on_status:
                on_status("⚙️ 최초 1회: 포터블 FFmpeg 고화질/음원 변환 엔진 자동 준비 중…")

            req = urllib.request.Request(
                FFMPEG_PORTABLE_ZIP_URL,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                total = int(resp.headers.get("Content-Length", 0) or 0)
                chunks = []
                downloaded = 0
                while True:
                    chunk = resp.read(256 * 1024)
                    if not chunk:
                        break
                    chunks.append(chunk)
                    downloaded += len(chunk)
                    if total > 0 and on_status:
                        pct = int(downloaded * 100 / total)
                        on_status(f"⚙️ 최초 1회: 포터블 FFmpeg 엔진 자동 다운로드 중… ({pct}%)")

                zip_bytes = b"".join(chunks)

            if on_status:
                on_status("⚙️ 포터블 FFmpeg 압축 해제 및 등록 중…")

            with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
                for member in zf.namelist():
                    lower = member.lower()
                    if lower.endswith("ffmpeg.exe") or lower.endswith("ffprobe.exe"):
                        fname = os.path.basename(member)
                        out_path = os.path.join(target_dir, fname)
                        with zf.open(member) as src, open(out_path, "wb") as dst:
                            shutil.copyfileobj(src, dst)

            _ensure_dir_in_path(target_dir)
            ff_path = os.path.join(target_dir, "ffmpeg.exe")
            if os.path.isfile(ff_path):
                if on_ready:
                    on_ready(True, ff_path)
            else:
                if on_ready:
                    on_ready(False, "FFmpeg 실행 파일을 추출하지 못했습니다.")
        except Exception as e:
            if on_ready:
                on_ready(False, str(e))

    threading.Thread(target=_worker, daemon=True).start()

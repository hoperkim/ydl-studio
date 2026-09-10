"""
yt-dlp Core in-app updater module.
"""
import subprocess
import sys
import threading
from typing import Callable, Optional, Tuple
import requests
import yt_dlp.version


def get_current_version() -> str:
    """Return the installed version of yt-dlp."""
    return yt_dlp.version.__version__


def check_for_update() -> Tuple[bool, str, str]:
    """
    Check PyPI for the latest yt-dlp release.
    Returns (has_update, current_version, latest_version).
    """
    curr = get_current_version()
    try:
        resp = requests.get("https://pypi.org/pypi/yt-dlp/json", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            latest = data.get("info", {}).get("version", curr)
            return (latest > curr, curr, latest)
    except Exception:
        pass
    return (False, curr, curr)


def run_update_async(
    on_complete: Optional[Callable[[bool, str], None]] = None
) -> None:
    """
    Run yt-dlp upgrade in a background thread using pip.
    Calls on_complete(success, message).
    """
    def _worker():
        try:
            # Use current python executable to upgrade yt-dlp
            cmd = [sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp"]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            )
            if result.returncode == 0:
                if on_complete:
                    on_complete(True, "yt-dlp가 최신 버전으로 업데이트되었습니다! 프로그램을 재시작하면 적용됩니다.")
            else:
                if on_complete:
                    on_complete(False, f"업데이트 실패:\n{result.stderr}")
        except Exception as e:
            if on_complete:
                on_complete(False, f"오류 발생: {e}")

    threading.Thread(target=_worker, daemon=True).start()

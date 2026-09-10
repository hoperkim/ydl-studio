"""
YDL Studio - Entry Point
Modern YouTube and Media Downloader GUI powered by yt-dlp & CustomTkinter.
"""
import sys
import os

# Ensure project root is in sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app.ui.main_window import MainWindow


def main():
    # Enable high-DPI scaling on Windows
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass

    app = MainWindow()
    app.mainloop()


if __name__ == "__main__":
    main()
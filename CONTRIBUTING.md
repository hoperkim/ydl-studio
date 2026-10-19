# Contributing to YDL Studio

Thank you for your interest in improving **YDL Studio**. We welcome bug reports, extractor fallback improvements, UI polish, and documentation updates.

## 1. Reporting Extraction or Download Bugs

Because streaming sites change frequently, please include the following when opening an issue:
- **Failing URL or domain** (redact private session tokens if applicable).
- **Selected mode/preset** (e.g., `Smart Auto`, `MP3 320k`, `1080p FHD MP4`).
- **Stage where it failed** (e.g., Stage 1 `yt-dlp`, Stage 2 `DeepWebScanner`, Stage 4 `BrowserFetcher`).
- **Error message** displayed on the download card or terminal output.

> **Note on Scope**: Please do not submit issues requesting circumvention of commercial DRM systems (Widevine, PlayReady, FairPlay, Netflix, Spotify direct server ripping, etc.).

## 2. Local Development Setup

```powershell
git clone https://github.com/hoperkim/ydl-studio.git
cd ydl-studio

python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt

python main.py
```

## 3. Architecture Overview

- `main.py` — Application entry point and Windows DPI initialization.
- `app/ui/` — CustomTkinter GUI windows and components (`main_window.py`, `url_input_bar.py`, `download_card.py`, `sniffer_modal.py`, `settings_modal.py`).
- `app/core/metadata.py` — Multi-stage metadata analyzer and preset selector.
- `app/core/deep_scanner.py` — Static HTML/iframe scanner, Dean Edwards packed-JS unpacker, and Base64 URL decoder.
- `app/core/browser_fetcher.py` & `app/core/browser_sniffer.py` — Chrome/Edge DevTools Protocol (CDP) stream capture and HLS segment downloader.
- `app/core/downloader.py` — Background download worker wrapping `yt-dlp`, `FFmpeg`, and `BrowserStreamDownloader`.
- `app/utils/` — URL sanitization & intent detection (`clipboard.py`), `FFmpeg` bootstrap (`ffmpeg_manager.py`), and JSON settings (`config.py`).

## 4. Running Tests Before Submitting a PR

Run the unit test suite and ensure all tests pass:

```powershell
python -m unittest discover -s tests -v
```

If you modify URL sanitization (`app/utils/clipboard.py`), M3U8 parsing (`app/core/browser_fetcher.py`), or HTML/JS stream extraction (`app/core/deep_scanner.py`), please add a corresponding test case in `tests/test_ydl_studio.py`.

"""
Asynchronous Download Worker module for yt-dlp.
Supports real-time progress callbacks, individual cancellation, and format mappings.
"""
import os
import threading
from typing import Any, Callable, Dict, Optional
import yt_dlp
from app.utils.clipboard import clean_media_url


class DownloadTask:
    """Represents an individual download task with cancellation and progress reporting."""

    def __init__(
        self,
        url: str,
        save_dir: str,
        preset: str,
        browser_cookie: Optional[str] = None,
        embed_thumb: bool = True,
        embed_metadata: bool = True,
        auto_subs: bool = False,
        sub_langs: str = "",
        on_progress: Optional[Callable[[float, str, str], None]] = None,
        on_status_change: Optional[Callable[[str, str], None]] = None,
        on_finish: Optional[Callable[[str], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
    ) -> None:
        self.url = clean_media_url(url)
        self.save_dir = save_dir
        self.preset = preset
        self.browser_cookie = browser_cookie
        self.embed_thumb = embed_thumb
        self.embed_metadata = embed_metadata
        self.auto_subs = auto_subs
        self.sub_langs = sub_langs

        self.on_progress = on_progress
        self.on_status_change = on_status_change
        self.on_finish = on_finish
        self.on_error = on_error

        self.is_cancelled = False
        self.thread: Optional[threading.Thread] = None
        self.output_filepath: Optional[str] = None

    def cancel(self) -> None:
        """Flag the task for cancellation."""
        self.is_cancelled = True
        if self.on_status_change:
            self.on_status_change("CANCELLED", "다운로드가 취소되었습니다.")

    def start(self) -> None:
        """Start download in a background thread."""
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _progress_hook(self, d: Dict[str, Any]) -> None:
        if self.is_cancelled:
            # Raising exception inside hook cancels yt-dlp safely
            raise yt_dlp.utils.DownloadCancelled("User cancelled download.")

        status = d.get('status')
        if status == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
            downloaded = d.get('downloaded_bytes', 0)
            percent = (downloaded / total * 100.0) if total > 0 else 0.0

            speed = d.get('speed')
            speed_str = f"{speed / 1024 / 1024:.2f} MB/s" if speed else ""

            eta = d.get('eta')
            eta_str = f"남은 시간: {int(eta)}초" if eta is not None else ""

            if self.on_progress:
                self.on_progress(percent, speed_str, eta_str)
            if self.on_status_change:
                self.on_status_change("DOWNLOADING", f"{percent:.1f}% ({speed_str})")

        elif status == 'finished':
            filename = d.get('filename')
            if filename:
                self.output_filepath = filename
            if self.on_progress:
                self.on_progress(100.0, "", "")
            if self.on_status_change:
                self.on_status_change("PROCESSING", "인코딩 및 후처리 중…")

    def _build_ydl_opts(self) -> Dict[str, Any]:
        outtmpl = os.path.join(self.save_dir, '%(title)s [%(id)s].%(ext)s')
        opts: Dict[str, Any] = {
            'outtmpl': outtmpl,
            'progress_hooks': [self._progress_hook],
            'noprogress': True,
            'quiet': True,
            'no_warnings': True,
            'postprocessors': [],
        }

        if self.browser_cookie:
            opts['cookiesfrombrowser'] = (self.browser_cookie,)

        # Format mapping based on preset selection
        p = self.preset
        if "최고 화질" in p or "Best" in p:
            opts['format'] = 'bv*+ba/best'
        elif "2160p" in p or "4K" in p:
            opts['format'] = 'bestvideo[height<=2160]+bestaudio/best[height<=2160]'
        elif "1440p" in p or "2K" in p:
            opts['format'] = 'bestvideo[height<=1440]+bestaudio/best[height<=1440]'
        elif "1080p" in p:
            opts['format'] = 'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]'
        elif "720p" in p:
            opts['format'] = 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]'
        elif "480p" in p:
            opts['format'] = 'bestvideo[height<=480]+bestaudio/best[height<=480]'
        elif "오디오 MP3 (최고음질 320k)" in p:
            opts['format'] = 'bestaudio/best'
            opts['postprocessors'].append({
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '320',
            })
        elif "오디오 MP3" in p:
            opts['format'] = 'bestaudio/best'
            opts['postprocessors'].append({
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            })
        elif "오디오 M4A" in p:
            opts['format'] = 'bestaudio[ext=m4a]/bestaudio/best'
            opts['postprocessors'].append({
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'm4a',
            })

        # Subtitles
        if self.sub_langs:
            langs = [l.strip() for l in self.sub_langs.split(',') if l.strip()]
            if langs:
                opts['writesubtitles'] = True
                opts['subtitleslangs'] = langs
                opts['writeautomaticsub'] = self.auto_subs
        elif self.auto_subs:
            opts['writeautomaticsub'] = True
            opts['subtitleslangs'] = ['ko', 'en']

        # Embeddings
        if self.embed_thumb and "MP3" not in p:
            opts['postprocessors'].append({'key': 'EmbedThumbnail'})
        if self.embed_metadata:
            opts['postprocessors'].append({'key': 'FFmpegMetadata'})

        return opts

    def _run(self) -> None:
        try:
            if self.on_status_change:
                self.on_status_change("DOWNLOADING", "다운로드 준비 중…")
            opts = self._build_ydl_opts()

            info = None
            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(self.url, download=True)
            except Exception as e:
                err_str = str(e).lower()
                if self.browser_cookie and ("cookie" in err_str or "permission" in err_str):
                    # Fallback retry without browser cookies
                    opts.pop('cookiesfrombrowser', None)
                    with yt_dlp.YoutubeDL(opts) as ydl:
                        info = ydl.extract_info(self.url, download=True)
                else:
                    raise e

            if info:
                # Resolve final output filepath
                requested_downloads = info.get('requested_downloads')
                if requested_downloads and len(requested_downloads) > 0:
                    for req in requested_downloads:
                        fp = req.get('filepath')
                        if fp and not fp.endswith('.part') and 'fhls-audio' not in fp:
                            self.output_filepath = fp
                            break
                    if not self.output_filepath:
                        self.output_filepath = requested_downloads[0].get('filepath')
                if not self.output_filepath:
                    with yt_dlp.YoutubeDL(opts) as ydl:
                        self.output_filepath = ydl.prepare_filename(info)

            if not self.is_cancelled:
                if self.on_status_change:
                    self.on_status_change("FINISHED", "다운로드 완료!")
                if self.on_finish:
                    self.on_finish(self.output_filepath or self.save_dir)

        except yt_dlp.utils.DownloadCancelled:
            if self.on_status_change:
                self.on_status_change("CANCELLED", "다운로드가 취소되었습니다.")
        except Exception as e:
            if not self.is_cancelled:
                error_msg = str(e)
                if "Sign in to confirm" in error_msg or "bot" in error_msg.lower():
                    error_msg = "유튜브 봇 감지 차단: [설정]에서 브라우저 쿠키를 연동해 주세요."
                if self.on_status_change:
                    self.on_status_change("ERROR", f"오류: {error_msg}")
                if self.on_error:
                    self.on_error(error_msg)

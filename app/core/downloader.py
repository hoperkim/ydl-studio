"""
Asynchronous Download Worker module for yt-dlp and FFmpeg Universal Stream Engine.
Supports real-time progress callbacks, individual cancellation, live recording stop,
custom header injection (Referer/User-Agent/Cookie), and direct HLS fallback.
"""
import os
import re
import shutil
import subprocess
import threading
import time
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
        headers: Optional[Dict[str, str]] = None,
        is_live: bool = False,
        title: Optional[str] = None,
        use_browser_fetcher: bool = False,
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
        self.headers = headers or {}
        self.is_live = is_live
        self.title = title or "media"
        self.use_browser_fetcher = use_browser_fetcher or ("upload18.org" in self.url)
        self.embed_thumb = embed_thumb
        self.embed_metadata = embed_metadata
        self.auto_subs = auto_subs
        self.sub_langs = sub_langs

        self.on_progress = on_progress
        self.on_status_change = on_status_change
        self.on_finish = on_finish
        self.on_error = on_error

        self.is_cancelled = False
        self.is_stopping_live = False
        self.start_time = 0.0
        self.thread: Optional[threading.Thread] = None
        self.ffmpeg_proc: Optional[subprocess.Popen] = None
        self.browser_dl: Optional[Any] = None
        self.output_filepath: Optional[str] = None
        self.last_part_file: Optional[str] = None

    def cancel(self) -> None:
        """Flag the task for cancellation."""
        if self.is_live:
            self.stop_live_recording()
            return

        self.is_cancelled = True
        if self.browser_dl:
            try:
                self.browser_dl.cancel()
            except Exception:
                pass
        if self.ffmpeg_proc:
            try:
                self.ffmpeg_proc.terminate()
            except Exception:
                pass
        if self.on_status_change:
            self.on_status_change("CANCELLED", "다운로드가 취소되었습니다.")

    def stop_live_recording(self) -> None:
        """Gracefully stop a live stream recording and finalize media container."""
        self.is_stopping_live = True
        if self.on_status_change:
            self.on_status_change("PROCESSING", "실시간 녹화 종료 중… 파일 마무리 작업 중")

        if self.ffmpeg_proc:
            try:
                # Send 'q' to ffmpeg for clean exit
                self.ffmpeg_proc.stdin.write(b"q\n")
                self.ffmpeg_proc.stdin.flush()
            except Exception:
                try:
                    self.ffmpeg_proc.terminate()
                except Exception:
                    pass

    def start(self) -> None:
        """Start download in a background thread."""
        self.start_time = time.time()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _progress_hook(self, d: Dict[str, Any]) -> None:
        if self.is_cancelled:
            raise yt_dlp.utils.DownloadCancelled("User cancelled download.")
        if self.is_stopping_live:
            raise yt_dlp.utils.DownloadCancelled("Live recording stopped cleanly by user.")

        status = d.get('status')
        if status == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
            downloaded = d.get('downloaded_bytes', 0)
            percent = (downloaded / total * 100.0) if total > 0 else 0.0

            speed = d.get('speed')
            speed_str = f"{speed / 1024 / 1024:.2f} MB/s" if speed else ""

            eta = d.get('eta')
            eta_str = f"남은 시간: {int(eta)}초" if eta is not None else ""

            tmp_filename = d.get('tmpfilename') or d.get('filename')
            if tmp_filename:
                self.last_part_file = tmp_filename

            if self.is_live:
                elapsed = int(time.time() - self.start_time)
                m, s = divmod(elapsed, 60)
                h, m = divmod(m, 60)
                dur_str = f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"
                size_mb = downloaded / 1024 / 1024
                status_text = f"🔴 녹화 중 ({dur_str} / {size_mb:.1f}MB)"
                if self.on_progress:
                    self.on_progress(100.0, f"{speed_str}", f"녹화 시간: {dur_str}")
                if self.on_status_change:
                    self.on_status_change("LIVE_RECORDING", status_text)
            else:
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

        # Inject custom headers (Referer, Origin, User-Agent, etc.)
        if self.headers:
            opts['http_headers'] = self.headers
            if 'Referer' in self.headers:
                opts['referer'] = self.headers['Referer']
            if 'User-Agent' in self.headers:
                opts['user_agent'] = self.headers['User-Agent']

        if self.browser_cookie:
            opts['cookiesfrombrowser'] = (self.browser_cookie,)

        # Format mapping based on preset selection
        p = self.preset
        if "최고 화질" in p or "Best" in p:
            opts['format'] = 'bv*+ba/b/best'
        elif "2160p" in p or "4K" in p:
            opts['format'] = 'bestvideo[height<=2160]+bestaudio/best[height<=2160]/best'
        elif "1440p" in p or "2K" in p:
            opts['format'] = 'bestvideo[height<=1440]+bestaudio/best[height<=1440]/best'
        elif "1080p" in p:
            opts['format'] = 'bestvideo[height<=1080]+bestaudio/best[height<=1080]/best'
        elif "720p" in p:
            opts['format'] = 'bestvideo[height<=720]+bestaudio/best[height<=720]/best'
        elif "480p" in p:
            opts['format'] = 'bestvideo[height<=480]+bestaudio/best[height<=480]/best'
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
        if self.embed_thumb and "MP3" not in p and not self.is_live:
            opts['postprocessors'].append({'key': 'EmbedThumbnail'})
        if self.embed_metadata and not self.is_live:
            opts['postprocessors'].append({'key': 'FFmpegMetadata'})

        return opts

    def _run(self) -> None:
        if self.use_browser_fetcher:
            self._run_browser_fetcher()
            return

        try:
            if self.on_status_change:
                status_msg = "실시간 방송 녹화 시작 중…" if self.is_live else "다운로드 준비 중…"
                self.on_status_change("DOWNLOADING", status_msg)
            opts = self._build_ydl_opts()

            info = None
            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(self.url, download=True)
            except Exception as e:
                err_str = str(e).lower()
                # Browser cookie lock fallback
                if self.browser_cookie and ("cookie" in err_str or "permission" in err_str):
                    opts.pop('cookiesfrombrowser', None)
                    with yt_dlp.YoutubeDL(opts) as ydl:
                        info = ydl.extract_info(self.url, download=True)
                # If HLS/M3U8 error in yt-dlp, try direct FFmpeg fallback
                elif (".m3u8" in self.url.lower() or ".mpd" in self.url.lower()) and not self.is_cancelled:
                    if self.on_status_change:
                        self.on_status_change("DOWNLOADING", "yt-dlp 스트림 재시도: FFmpeg 만능 엔진으로 다운로드 중…")
                    self._run_ffmpeg_fallback()
                    return
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
            if self.is_stopping_live:
                # Finalize live part file to playable MP4
                self._finalize_live_part_file()
            else:
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

    def _run_ffmpeg_fallback(self) -> None:
        """Direct stream download fallback using FFmpeg."""
        ffmpeg_bin = shutil.which("ffmpeg") or r"C:\FFmpeg\bin\ffmpeg.exe"
        if not os.path.exists(ffmpeg_bin) and not shutil.which("ffmpeg"):
            raise RuntimeError("FFmpeg를 찾을 수 없습니다.")

        safe_title = re.sub(r'[\\/*?:"<>|]', "_", self.title or "stream_video").strip()
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        target_name = f"{safe_title} [{timestamp}].mp4"
        out_path = os.path.join(self.save_dir, target_name)
        self.output_filepath = out_path

        headers_str = ""
        for k, v in self.headers.items():
            headers_str += f"{k}: {v}\r\n"

        cmd = [ffmpeg_bin, "-y"]
        if headers_str:
            cmd.extend(["-headers", headers_str])
        cmd.extend([
            "-i", self.url,
            "-c", "copy",
            "-bsf:a", "aac_adtstoasc",
            out_path
        ])

        self.ffmpeg_proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )

        # Parse FFmpeg progress from stderr
        time_pattern = re.compile(r'time=(\d+):(\d+):(\d+\.\d+)')
        for line in self.ffmpeg_proc.stderr:
            if self.is_cancelled or self.is_stopping_live:
                break
            m = time_pattern.search(line)
            if m:
                h, mins, s = m.groups()
                dur_str = f"{h}:{mins}:{int(float(s)):02d}"
                if self.is_live:
                    if self.on_status_change:
                        self.on_status_change("LIVE_RECORDING", f"🔴 녹화 중 ({dur_str})")
                else:
                    if self.on_status_change:
                        self.on_status_change("DOWNLOADING", f"다운로드 중 ({dur_str})")
                if self.on_progress:
                    self.on_progress(100.0, "FFmpeg 처리 중", dur_str)

        self.ffmpeg_proc.wait()
        if not self.is_cancelled:
            if self.on_status_change:
                self.on_status_change("FINISHED", "다운로드 완료!")
            if self.on_finish:
                self.on_finish(out_path)

    def _finalize_live_part_file(self) -> None:
        """Remux leftover .part file into valid playable MP4 upon live stop."""
        ffmpeg_bin = shutil.which("ffmpeg") or r"C:\FFmpeg\bin\ffmpeg.exe"
        if not self.last_part_file or not os.path.exists(self.last_part_file):
            # Check save dir for recent .part file
            for f in os.listdir(self.save_dir):
                if f.endswith(".part"):
                    self.last_part_file = os.path.join(self.save_dir, f)
                    break

        if self.last_part_file and os.path.exists(self.last_part_file):
            final_path = self.last_part_file.replace(".part", "")
            if not final_path.endswith(".mp4"):
                final_path += ".mp4"
            try:
                subprocess.run(
                    [ffmpeg_bin, "-y", "-i", self.last_part_file, "-c", "copy", final_path],
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
                    check=False
                )
                try:
                    os.remove(self.last_part_file)
                except Exception:
                    pass
                self.output_filepath = final_path
                if self.on_status_change:
                    self.on_status_change("FINISHED", "실시간 녹화 완료 및 저장!")
                if self.on_finish:
                    self.on_finish(final_path)
                return
            except Exception:
                pass

        if self.on_status_change:
            self.on_status_change("FINISHED", "녹화가 중지되었습니다.")
        if self.on_finish:
            self.on_finish(self.save_dir)

    def _run_browser_fetcher(self) -> None:
        """Download stream via authenticated in-browser fetch pipeline."""
        from app.core.browser_fetcher import BrowserStreamDownloader
        import asyncio

        self.browser_dl = BrowserStreamDownloader(
            page_url=self.url,
            output_dir=self.save_dir,
            on_progress=self.on_progress,
            on_status=self.on_status_change,
            on_finish=self.on_finish
        )
        try:
            final_file = asyncio.run(self.browser_dl.run_async())
            self.output_filepath = final_file
        except Exception as e:
            if not self.is_cancelled:
                if self.on_status_change:
                    self.on_status_change("ERROR", f"오류: {e}")
                if self.on_error:
                    self.on_error(str(e))

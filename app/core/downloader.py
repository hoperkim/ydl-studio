"""
Asynchronous Download Worker module for yt-dlp, FFmpeg Universal Stream Engine,
and Browser-Context CDP Downloader (v2.0 Universal).
Features 8x turbo fragment downloading, FLAC/MP3/M4A album cover embedding,
and automatic 3-stage download self-healing (yt-dlp -> FFmpeg -> BrowserSession).
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
    """Represents an individual download task with cancellation, progress reporting, and auto-fallback."""

    def __init__(
        self,
        url: str,
        save_dir: str,
        preset: str,
        page_url: Optional[str] = None,
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
        self.page_url = clean_media_url(page_url) if page_url else self.url
        self.save_dir = save_dir
        self.preset = preset
        self.browser_cookie = browser_cookie
        self.headers = headers or {}
        self.is_live = is_live
        self.title = title or "media"
        self.use_browser_fetcher = use_browser_fetcher or ("upload18." in self.url.lower())
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
                self.on_status_change("PROCESSING", "고속 병합 및 메타데이터 후처리 중…")

    def _is_audio_preset(self) -> bool:
        p = self.preset
        return any(k in p for k in ("오디오", "MP3", "M4A", "FLAC", "음원"))

    def _build_ydl_opts(self) -> Dict[str, Any]:
        is_explicit_playlist = any(p in self.url.lower() for p in ["/playlist", "/sets/", "/album/"])
        outtmpl = os.path.join(self.save_dir, '%(title).150B [%(id)s].%(ext)s')
        opts: Dict[str, Any] = {
            'outtmpl': outtmpl,
            'progress_hooks': [self._progress_hook],
            'noprogress': True,
            'quiet': True,
            'no_warnings': True,
            'noplaylist': not is_explicit_playlist,
            'concurrent_fragment_downloads': 8,
            'retries': 10,
            'fragment_retries': 10,
            'file_access_retries': 5,
            'postprocessors': [],
        }

        if self.headers:
            opts['http_headers'] = self.headers
            if 'Referer' in self.headers:
                opts['referer'] = self.headers['Referer']
            if 'User-Agent' in self.headers:
                opts['user_agent'] = self.headers['User-Agent']

        if self.browser_cookie:
            opts['cookiesfrombrowser'] = (self.browser_cookie,)

        p = self.preset
        is_audio = self._is_audio_preset()

        if "FLAC" in p:
            opts['format'] = 'bestaudio/best'
            opts['postprocessors'].append({
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'flac',
            })
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
        else:
            # Video formats: ensure final merged container is universally playable MP4
            opts['merge_output_format'] = 'mp4'
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
            else:
                opts['format'] = 'bv*+ba/b/best'

        # Subtitles (for video modes)
        if not is_audio:
            if self.sub_langs:
                langs = [l.strip() for l in self.sub_langs.split(',') if l.strip()]
                if langs:
                    opts['writesubtitles'] = True
                    opts['subtitleslangs'] = langs
                    opts['writeautomaticsub'] = self.auto_subs
            elif self.auto_subs:
                opts['writeautomaticsub'] = True
                opts['subtitleslangs'] = ['ko', 'en']

        # Thumbnail & Metadata Embedding (supports both Video MP4 and Audio MP3/FLAC/M4A!)
        if not self.is_live:
            if self.embed_thumb:
                opts['writethumbnail'] = True
                opts['postprocessors'].append({
                    'key': 'FFmpegThumbnailsConvertor',
                    'format': 'jpg',
                })
                opts['postprocessors'].append({'key': 'EmbedThumbnail'})
            if self.embed_metadata:
                opts['postprocessors'].append({'key': 'FFmpegMetadata'})

        return opts

    def _run(self) -> None:
        if self.use_browser_fetcher:
            self._run_browser_fetcher()
            return

        try:
            if self.on_status_change:
                status_msg = "실시간 방송 녹화 시작 중…" if self.is_live else "초고속 다운로드 준비 중…"
                self.on_status_change("DOWNLOADING", status_msg)
            opts = self._build_ydl_opts()

            info = None
            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(self.url, download=True)
            except Exception as e:
                err_str = str(e).lower()
                # Retry without browser cookies if locked
                if self.browser_cookie and ("cookie" in err_str or "permission" in err_str or "dpapi" in err_str):
                    opts.pop('cookiesfrombrowser', None)
                    try:
                        with yt_dlp.YoutubeDL(opts) as ydl:
                            info = ydl.extract_info(self.url, download=True)
                    except Exception as e_inner:
                        e = e_inner
                        err_str = str(e_inner).lower()
                    else:
                        e = None

                if e is not None and not self.is_cancelled:
                    # Retry without EmbedThumbnail if thumbnail embedding failed
                    if "thumbnail" in err_str or "postprocessing" in err_str:
                        opts['writethumbnail'] = False
                        opts['postprocessors'] = [
                            pp for pp in opts.get('postprocessors', [])
                            if pp.get('key') not in ('EmbedThumbnail', 'FFmpegThumbnailsConvertor')
                        ]
                        with yt_dlp.YoutubeDL(opts) as ydl:
                            info = ydl.extract_info(self.url, download=True)
                    # Fallback 1: Direct FFmpeg engine for M3U8/MPD/direct streams
                    elif any(ext in self.url.lower() for ext in (".m3u8", ".mpd", ".mp4", ".mp3", ".m4a")):
                        if self.on_status_change:
                            self.on_status_change("DOWNLOADING", "FFmpeg 만능 스트림 엔진으로 자동 전환 중…")
                        self._run_ffmpeg_fallback()
                        return
                    # Fallback 2: Universal Browser-Context CDP Downloader for blocked/dynamic web pages
                    else:
                        if self.on_status_change:
                            self.on_status_change("DOWNLOADING", "보안 브라우저 세션 엔진으로 자동 우회 중…")
                        self._run_browser_fetcher()
                        return

            if info:
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
        """Direct stream download fallback using FFmpeg (supports both Video MP4 and Audio MP3/FLAC/M4A)."""
        ffmpeg_bin = shutil.which("ffmpeg") or r"C:\FFmpeg\bin\ffmpeg.exe"
        if not os.path.exists(ffmpeg_bin) and not shutil.which("ffmpeg"):
            raise RuntimeError("FFmpeg를 찾을 수 없습니다.")

        safe_title = re.sub(r'[\\/*?:"<>|]', "_", self.title or "stream_media").strip()
        timestamp = time.strftime("%Y%m%d_%H%M%S")

        is_audio = self._is_audio_preset()
        if "FLAC" in self.preset:
            ext = "flac"
        elif "M4A" in self.preset:
            ext = "m4a"
        elif is_audio:
            ext = "mp3"
        else:
            ext = "mp4"

        target_name = f"{safe_title} [{timestamp}].{ext}"
        out_path = os.path.join(self.save_dir, target_name)
        self.output_filepath = out_path

        headers_str = ""
        for k, v in self.headers.items():
            headers_str += f"{k}: {v}\r\n"

        cmd = [ffmpeg_bin, "-y"]
        if headers_str:
            cmd.extend(["-headers", headers_str])
        cmd.extend(["-i", self.url])

        if is_audio:
            if ext == "flac":
                cmd.extend(["-vn", "-c:a", "flac", out_path])
            elif ext == "m4a":
                cmd.extend(["-vn", "-c:a", "aac", "-b:a", "256k", out_path])
            else:
                bitrate = "320k" if "320" in self.preset else "192k"
                cmd.extend(["-vn", "-c:a", "libmp3lame", "-b:a", bitrate, out_path])
        else:
            cmd.extend([
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
                        self.on_status_change("DOWNLOADING", f"스트림 수집 중 ({dur_str})")
                if self.on_progress:
                    self.on_progress(100.0, "FFmpeg 엔진", dur_str)

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

        target_page = self.page_url or self.url
        self.browser_dl = BrowserStreamDownloader(
            page_url=target_page,
            output_dir=self.save_dir,
            preset=self.preset,
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

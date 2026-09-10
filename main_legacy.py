import os
import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import urllib.request
import zipfile
import io


class YDLStudio(tk.Tk):
    """
    A GUI wrapper around yt‑dlp designed for novice users.

    This version displays bilingual (Korean/English) labels for all controls, uses a
    larger default window size suitable for playlist or channel downloads, and can
    automatically download FFmpeg binaries when missing.
    """

    def __init__(self) -> None:
        super().__init__()
        self.title("YDL Studio (YDL 스튜디오)")
        self.resizable(True, True)
        # Increase default window size so that playlist/channel lists fit comfortably.
        # The original version relied on automatic sizing.  A larger geometry
        # improves usability when downloading playlists or channels with many items.
        self.geometry("800x600")

        # Variables
        self.download_dir = tk.StringVar(value=os.getcwd())
        self.preset = tk.StringVar(value="최고 화질 (Best Video)")
        self.sub_langs = tk.StringVar(value="")
        self.embed_thumb = tk.BooleanVar(value=False)
        self.embed_metadata = tk.BooleanVar(value=False)
        self.auto_subs = tk.BooleanVar(value=False)

        # URL input
        # Label displays Korean first with English translation in parentheses for clarity
        url_label = ttk.Label(self, text="비디오 주소 (Video URLs, 한 줄에 하나씩):")
        url_label.grid(row=0, column=0, sticky="w", padx=5, pady=(5, 0))
        # Increase text area size for easier playlist/channel entry
        self.urls_text = tk.Text(self, height=8, width=80)
        self.urls_text.grid(row=1, column=0, columnspan=3, sticky="we", padx=5)

        # Create a simple right‑click context menu for the URL text widget.
        # Show both Korean and English on the context menu
        self._url_menu = tk.Menu(self, tearoff=0)
        self._url_menu.add_command(label="붙여넣기 (Paste)",
                                   command=lambda: self.urls_text.event_generate("<Control-v>"))
        # Bind right‑click (button 3) to show the context menu.
        self.urls_text.bind("<Button-3>", self._show_url_menu)

        # Download directory chooser
        # Display Korean first with English translation
        dir_label = ttk.Label(self, text="저장 위치 (Save to):")
        dir_label.grid(row=2, column=0, sticky="w", padx=5, pady=5)
        dir_entry = ttk.Entry(self, textvariable=self.download_dir, width=40)
        dir_entry.grid(row=2, column=1, sticky="we", padx=5, pady=5)
        dir_btn = ttk.Button(self, text="찾기… (Browse…)", command=self.browse_dir)
        dir_btn.grid(row=2, column=2, sticky="we", padx=5, pady=5)

        # Preset dropdown
        preset_label = ttk.Label(self, text="프리셋 (Preset):")
        preset_label.grid(row=3, column=0, sticky="w", padx=5)
        # Each preset name includes both Korean and English for clarity
        presets = [
            "최고 화질 (Best Video)",
            "1080p MP4 (1080p MP4)",
            "오디오만 (MP3) (Audio Only)",
            "자막만 (Subtitles Only)"
        ]
        preset_menu = ttk.OptionMenu(self, self.preset, self.preset.get(), *presets)
        preset_menu.grid(row=3, column=1, sticky="we", padx=5)

        # Subtitle languages entry
        sub_label = ttk.Label(self, text="자막 언어 (Sub languages, 쉼표로 구분):")
        sub_label.grid(row=4, column=0, sticky="w", padx=5)
        sub_entry = ttk.Entry(self, textvariable=self.sub_langs, width=40)
        sub_entry.grid(row=4, column=1, sticky="we", padx=5)

        # Optional flags
        opts_frame = ttk.Frame(self)
        opts_frame.grid(row=5, column=0, columnspan=3, sticky="w", padx=5)
        thumb_check = ttk.Checkbutton(opts_frame, text="썸네일 삽입 (Embed thumbnail)",
                                      variable=self.embed_thumb)
        thumb_check.grid(row=0, column=0, sticky="w", padx=5)
        meta_check = ttk.Checkbutton(opts_frame, text="메타데이터 삽입 (Embed metadata)",
                                     variable=self.embed_metadata)
        meta_check.grid(row=0, column=1, sticky="w", padx=5)
        auto_sub_check = ttk.Checkbutton(opts_frame, text="자동 자막 (Auto subtitles)",
                                         variable=self.auto_subs)
        auto_sub_check.grid(row=0, column=2, sticky="w", padx=5)

        # Control buttons
        btn_frame = ttk.Frame(self)
        btn_frame.grid(row=6, column=0, columnspan=3, sticky="we", padx=5)
        start_btn = ttk.Button(btn_frame, text="시작 (Start)", command=self.start_downloads)
        start_btn.pack(side="left", padx=(0, 10), pady=5)
        howto_btn = ttk.Button(btn_frame, text="사용법 (How to Use)", command=self.show_how_to)
        howto_btn.pack(side="left", pady=5)

        # Progress bar
        self.progress = ttk.Progressbar(self, mode="determinate")
        self.progress.grid(row=7, column=0, columnspan=3, sticky="we", padx=5, pady=(0, 5))

        # Log output
        log_label = ttk.Label(self, text="로그 (Log):")
        log_label.grid(row=8, column=0, sticky="w", padx=5)
        self.log_text = tk.Text(self, height=10, width=80, state="disabled")
        self.log_text.grid(row=9, column=0, columnspan=3, sticky="nsew", padx=5, pady=(0, 5))

        # Configure resizing
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(9, weight=1)

    def browse_dir(self) -> None:
        """Open a folder selection dialog and update the download directory."""
        directory = filedialog.askdirectory(initialdir=self.download_dir.get())
        if directory:
            self.download_dir.set(directory)

    def _show_url_menu(self, event: tk.Event) -> None:
        """Display the right‑click context menu for the URL text widget."""
        try:
            self._url_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self._url_menu.grab_release()

    def log(self, message: str) -> None:
        """Append a message to the log text widget in a thread‑safe manner."""
        def append():
            self.log_text.configure(state="normal")
            self.log_text.insert("end", message + "\n")
            self.log_text.see("end")
            self.log_text.configure(state="disabled")
        self.after(0, append)

    def update_progress(self, percent: float) -> None:
        """Update the progress bar percentage in a thread‑safe manner."""
        def set_value():
            self.progress['value'] = max(0.0, min(100.0, percent))
        self.after(0, set_value)

    def progress_hook(self, d: dict) -> None:
        """Handle progress callbacks from yt_dlp.YoutubeDL."""
        status = d.get('status')
        if status == 'downloading':
            total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
            downloaded_bytes = d.get('downloaded_bytes', 0)
            percent = (downloaded_bytes / total_bytes * 100) if total_bytes else 0.0
            speed = d.get('speed')
            eta = d.get('eta')
            msg_parts = []
            if speed:
                msg_parts.append(f"{speed/1024/1024:.2f} MB/s")
            if eta:
                msg_parts.append(f"ETA {int(eta)}s")
            self.log(f"다운로드 중: {percent:.1f}% {' '.join(msg_parts)} (Downloading...)")
            self.update_progress(percent)
        elif status == 'finished':
            self.log("다운로드 완료, 후처리 중… (Download finished, post‑processing…)")
            self.update_progress(100.0)
        elif status == 'error':
            self.log(f"오류: {d.get('filename', 'Unknown')} 다운로드 실패. (Error: file failed to download.)")

    def build_options(self, url: str) -> dict:
        """Construct yt_dlp options based on current UI selections."""
        outtmpl = os.path.join(self.download_dir.get(), '%(title)s.%(ext)s')
        options: dict = {
            'outtmpl': outtmpl,
            'progress_hooks': [self.progress_hook],
            'postprocessors': [],
            'noprogress': True,
            'quiet': True,
            'writesubtitles': False,
            'subtitleslangs': [],
            'format': None,
        }
        # Extract the Korean or English key before parentheses to support bilingual labels.
        preset_raw = self.preset.get().split('(')[0].strip()
        # Map Korean and English names to yt‑dlp format strings
        if preset_raw in ("최고 화질", "Best Video"):
            options['format'] = 'bv*+ba/best'
        elif preset_raw == "1080p MP4":
            options['format'] = 'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]'
        elif preset_raw in ("오디오만", "Audio Only (MP3)"):
            options['format'] = 'bestaudio'
            options['postprocessors'].append({
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            })
        elif preset_raw in ("자막만", "Subtitles Only"):
            options['skip_download'] = True
            options['writesubtitles'] = True
            options['writeautomaticsub'] = self.auto_subs.get()

        # Subtitle languages
        langs = [l.strip() for l in self.sub_langs.get().split(',') if l.strip()]
        if langs:
            options['subtitleslangs'] = langs
            options['writesubtitles'] = True
            options['writeautomaticsub'] = self.auto_subs.get()

        # Optional embedding
        if self.embed_thumb.get():
            options['postprocessors'].append({'key': 'EmbedThumbnail'})
        if self.embed_metadata.get():
            options['postprocessors'].append({'key': 'FFmpegMetadata'})

        return options

    def download_worker(self, urls: list[str]) -> None:
        """Worker thread that performs the downloads sequentially."""
        try:
            import yt_dlp  # type: ignore
        except ImportError:
            self.log("오류: yt_dlp 라이브러리가 설치되어 있지 않습니다. (yt_dlp is not installed.)")
            return
        for url in urls:
            opts = self.build_options(url)
            try:
                self.log(f"다운로드 시작: {url} (Starting download: {url})")
                with yt_dlp.YoutubeDL(opts) as ydl:
                    ydl.download([url])
                self.log(f"다운로드 완료: {url} (Completed download)")
            except Exception as e:
                self.log(f"{url} 다운로드 실패: {e} (Failed to download {url}: {e})")
        self.update_progress(0)
        self.log("모든 작업이 완료되었습니다. (All tasks completed.)")

    def start_downloads(self) -> None:
        """Validate inputs and start the download thread."""
        urls = [u.strip() for u in self.urls_text.get('1.0', 'end').splitlines() if u.strip()]
        if not urls:
            messagebox.showerror("오류 (Error)",
                                 "비디오 URL을 하나 이상 입력하세요. (Please enter at least one video URL.)")
            return
        if not os.path.isdir(self.download_dir.get()):
            messagebox.showerror("오류 (Error)",
                                 "유효한 다운로드 폴더를 선택하세요. (Please select a valid download directory.)")
            return
        self.update_progress(0)
        self.log("다운로드 시작… (Starting downloads…)")
        threading.Thread(target=self.download_worker, args=(urls,), daemon=True).start()

    def show_how_to(self) -> None:
        """Display the contents of the user guide in a new window."""
        # Determine the path to the user guide. When packaged with PyInstaller,
        # resources are extracted to a temporary directory pointed to by sys._MEIPASS.
        if getattr(sys, 'frozen', False):
            base_path = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))
        guide_path = os.path.join(base_path, 'user_guide.txt')
        if not os.path.isfile(guide_path):
            exe_dir = os.path.dirname(sys.argv[0])
            alt_path = os.path.join(exe_dir, 'user_guide.txt')
            if os.path.isfile(alt_path):
                guide_path = alt_path
        try:
            with open(guide_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception:
            messagebox.showerror("오류 (Error)", f"사용법 파일을 찾을 수 없습니다: {guide_path}\n(User guide not found at {guide_path})")
            return
        win = tk.Toplevel(self)
        win.title("사용법 (How to Use)")
        win.geometry("600x400")
        txt = tk.Text(win, wrap="word")
        txt.insert("1.0", content)
        txt.configure(state="disabled")
        txt.pack(fill="both", expand=True)
        scrollbar = ttk.Scrollbar(win, command=txt.yview)
        txt.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")

    def check_ffmpeg(self) -> None:
        """
        Verify that ffmpeg.exe and ffprobe.exe exist in the application directory.
        If missing, prompt the user to download the FFmpeg essentials archive and extract the required binaries.
        """
        # Determine base directory depending on whether the application is frozen.
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
        ffmpeg_path = os.path.join(base_dir, 'ffmpeg.exe')
        ffprobe_path = os.path.join(base_dir, 'ffprobe.exe')
        # Only handle Windows; on other platforms rely on system FFmpeg.
        if os.name != 'nt':
            return
        if os.path.isfile(ffmpeg_path) and os.path.isfile(ffprobe_path):
            return
        if not messagebox.askyesno(
            "FFmpeg 누락 (FFmpeg missing)",
            "고화질 병합과 오디오 추출을 위해 FFmpeg가 필요합니다.\n"
            "ffmpeg.exe와 ffprobe.exe를 다운로드하시겠습니까?\n"
            "(FFmpeg is required for merging high quality streams and extracting audio. "
            "Would you like to download ffmpeg.exe and ffprobe.exe now?)"
        ):
            self.log("FFmpeg가 설치되지 않았습니다. 일부 기능이 동작하지 않을 수 있습니다. (FFmpeg is missing; some features may not work.)")
            return
        try:
            url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
            self.log("FFmpeg 다운로드 중… (Downloading FFmpeg…)")
            with urllib.request.urlopen(url) as resp:
                data = resp.read()
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                for name in zf.namelist():
                    lower = name.lower()
                    if lower.endswith('ffmpeg.exe') or lower.endswith('ffprobe.exe'):
                        target_path = os.path.join(base_dir, os.path.basename(name))
                        with zf.open(name) as src, open(target_path, 'wb') as dst:
                            dst.write(src.read())
            messagebox.showinfo(
                "FFmpeg 다운로드 완료 (FFmpeg downloaded)",
                "FFmpeg가 성공적으로 다운로드되었습니다. 프로그램을 다시 시작하세요.\n"
                "(FFmpeg downloaded successfully. Please restart the application.)"
            )
            self.log("FFmpeg 다운로드 완료. (FFmpeg download completed.)")
        except Exception as e:
            messagebox.showerror(
                "FFmpeg 다운로드 실패 (FFmpeg download failed)",
                f"FFmpeg 다운로드 중 오류가 발생했습니다: {e}\n"
                "(An error occurred while downloading FFmpeg.)"
            )
            self.log(f"FFmpeg 다운로드 실패: {e}")


def main() -> None:
    app = YDLStudio()
    # Check for FFmpeg on startup
    app.check_ffmpeg()
    app.mainloop()


if __name__ == '__main__':
    main()
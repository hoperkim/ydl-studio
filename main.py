import os
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

try:
    # Attempt to import yt_dlp if available. If not, fallback to None.
    import yt_dlp  # type: ignore
except ImportError:
    yt_dlp = None


class YDLStudio(tk.Tk):
    """
    A simple GUI wrapper around yt‑dlp designed for novice users.

    This application allows users to paste one or more video URLs, pick a
    destination folder, choose a quality preset, set optional flags such as
    subtitle languages or embedding thumbnails, and then start the download
    process. Progress and status messages are streamed to a log panel. A
    separate "How to use" window reads from the bundled `user_guide.txt` to
    provide step‑by‑step instructions without requiring an internet
    connection.
    """

    def __init__(self) -> None:
        super().__init__()
        self.title("YDL Studio")
        self.resizable(True, True)

        # Variables
        self.download_dir = tk.StringVar(value=os.getcwd())
        self.preset = tk.StringVar(value="Best Video")
        self.sub_langs = tk.StringVar(value="")
        self.embed_thumb = tk.BooleanVar(value=False)
        self.embed_metadata = tk.BooleanVar(value=False)
        self.auto_subs = tk.BooleanVar(value=False)

        # URL input
        # Label includes a Korean translation in parentheses for clarity
        url_label = ttk.Label(self, text="Video URLs (비디오 URL/링크, 한 줄에 하나씩):")
        url_label.grid(row=0, column=0, sticky="w", padx=5, pady=(5, 0))
        self.urls_text = tk.Text(self, height=6, width=60)
        self.urls_text.grid(row=1, column=0, columnspan=3, sticky="we", padx=5)

        # Create a simple right‑click context menu for the URL text widget.
        # This enables users to paste with the mouse, which is helpful when copying
        # links from the browser. Without this, Windows users may need to use
        # Ctrl+V. The context menu contains only a paste command, but can be
        # extended later if necessary.
        self._url_menu = tk.Menu(self, tearoff=0)
        self._url_menu.add_command(label="Paste", command=lambda: self.urls_text.event_generate("<<Paste>>"))

        # Bind right‑click (button 3) to show the context menu. On macOS, you may
        # need to adjust to <Button-2> depending on the system configuration.
        self.urls_text.bind("<Button-3>", self._show_url_menu)

        # Download directory chooser
        # Display English with Korean translation
        dir_label = ttk.Label(self, text="Save to (저장 폴더):")
        dir_label.grid(row=2, column=0, sticky="w", padx=5, pady=5)
        dir_entry = ttk.Entry(self, textvariable=self.download_dir, width=40)
        dir_entry.grid(row=2, column=1, sticky="we", padx=5, pady=5)
        dir_btn = ttk.Button(self, text="Browse…", command=self.browse_dir)
        dir_btn.grid(row=2, column=2, sticky="we", padx=5, pady=5)

        # Preset dropdown
        preset_label = ttk.Label(self, text="Preset (프리셋):")
        preset_label.grid(row=3, column=0, sticky="w", padx=5)
        # Each preset name includes a short Korean description in parentheses
        presets = [
            "Best Video (최고 화질)",
            "1080p MP4 (1080p MP4)",
            "Audio Only (MP3) (오디오만)",
            "Subtitles Only (자막만)"
        ]
        preset_menu = ttk.OptionMenu(self, self.preset, self.preset.get(), *presets)
        preset_menu.grid(row=3, column=1, sticky="we", padx=5)

        # Subtitle languages entry
        sub_label = ttk.Label(self, text="Sub languages (자막 언어, 쉼표로 구분):")
        sub_label.grid(row=4, column=0, sticky="w", padx=5)
        sub_entry = ttk.Entry(self, textvariable=self.sub_langs, width=40)
        sub_entry.grid(row=4, column=1, sticky="we", padx=5)

        # Optional flags
        opts_frame = ttk.Frame(self)
        opts_frame.grid(row=5, column=0, columnspan=3, sticky="w", padx=5)
        thumb_check = ttk.Checkbutton(opts_frame, text="Embed thumbnail (썸네일 삽입)", variable=self.embed_thumb)
        thumb_check.grid(row=0, column=0, sticky="w", padx=5)
        meta_check = ttk.Checkbutton(opts_frame, text="Embed metadata (메타데이터 삽입)", variable=self.embed_metadata)
        meta_check.grid(row=0, column=1, sticky="w", padx=5)
        auto_sub_check = ttk.Checkbutton(opts_frame, text="Auto subtitles (자동 자막)", variable=self.auto_subs)
        auto_sub_check.grid(row=0, column=2, sticky="w", padx=5)

        # Control buttons
        btn_frame = ttk.Frame(self)
        btn_frame.grid(row=6, column=0, columnspan=3, sticky="we", padx=5)
        start_btn = ttk.Button(btn_frame, text="Start (시작)", command=self.start_downloads)
        start_btn.pack(side="left", padx=(0, 10), pady=5)
        howto_btn = ttk.Button(btn_frame, text="How to Use (사용법)", command=self.show_how_to)
        howto_btn.pack(side="left", pady=5)

        # Progress bar
        self.progress = ttk.Progressbar(self, mode="determinate")
        self.progress.grid(row=7, column=0, columnspan=3, sticky="we", padx=5, pady=(0, 5))

        # Log output
        log_label = ttk.Label(self, text="Log (로그):")
        log_label.grid(row=8, column=0, sticky="w", padx=5)
        self.log_text = tk.Text(self, height=10, width=60, state="disabled")
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
            # Display the menu at the position of the mouse click
            self._url_menu.tk_popup(event.x_root, event.y_root)
        finally:
            # Release the grab so other widgets can receive events
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
            # Some downloads may not provide accurate percent; clamp to [0,100]
            self.progress['value'] = max(0.0, min(100.0, percent))
        self.after(0, set_value)

    def progress_hook(self, d: dict) -> None:
        """Handle progress callbacks from yt_dlp.YoutubeDL."""
        status = d.get('status')
        if status == 'downloading':
            total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
            downloaded_bytes = d.get('downloaded_bytes', 0)
            if total_bytes:
                percent = downloaded_bytes / total_bytes * 100
            else:
                percent = 0.0
            speed = d.get('speed')
            eta = d.get('eta')
            msg_parts = []
            if speed:
                msg_parts.append(f"{speed/1024/1024:.2f} MB/s")
            if eta:
                msg_parts.append(f"ETA {int(eta)}s")
            self.log(f"Downloading: {percent:.1f}% {' '.join(msg_parts)}")
            self.update_progress(percent)
        elif status == 'finished':
            self.log("Download finished, post‑processing…")
            self.update_progress(100.0)
        elif status == 'error':
            self.log(f"Error: {d.get('filename', 'Unknown')} failed to download.")

    def build_options(self, url: str) -> dict:
        """Construct yt_dlp options based on current UI selections."""
        # Base output template: save into chosen directory with title as file name
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

        # Preset selection
        # Extract the English key before parentheses so that the logic works with
        # labels that include Korean translations, e.g. "Best Video (최고 화질)"
        preset_raw = self.preset.get().split('(')[0].strip()
        if preset_raw == "Best Video":
            options['format'] = 'bv*+ba/best'
        elif preset_raw == "1080p MP4":
            options['format'] = 'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]'
        elif preset_raw == "Audio Only (MP3)":
            options['format'] = 'bestaudio'
            # Postprocessor to convert audio to mp3
            options['postprocessors'].append({
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            })
        elif preset_raw == "Subtitles Only":
            options['skip_download'] = True
            options['writesubtitles'] = True
            options['writeautomaticsub'] = self.auto_subs.get()

        # Subtitle languages
        langs = [l.strip() for l in self.sub_langs.get().split(',') if l.strip()]
        if langs:
            options['subtitleslangs'] = langs
            options['writesubtitles'] = True
            # Only auto subtitles if requested
            options['writeautomaticsub'] = self.auto_subs.get()

        # Optional embedding
        if self.embed_thumb.get():
            options['postprocessors'].append({'key': 'EmbedThumbnail'})
        if self.embed_metadata.get():
            options['postprocessors'].append({'key': 'FFmpegMetadata'})

        return options

    def download_worker(self, urls: list[str]) -> None:
        """Worker thread that performs the downloads sequentially."""
        if yt_dlp is None:
            self.log("Error: yt_dlp library is not installed. Please install yt_dlp via pip.")
            return
        for url in urls:
            opts = self.build_options(url)
            try:
                self.log(f"Starting download: {url}")
                with yt_dlp.YoutubeDL(opts) as ydl:
                    ydl.download([url])
                self.log(f"Completed download: {url}")
            except Exception as e:
                self.log(f"Failed to download {url}: {e}")
        self.update_progress(0)
        self.log("All tasks completed.")

    def start_downloads(self) -> None:
        """Validate inputs and start the download thread."""
        # Extract non‑empty URLs
        urls = [u.strip() for u in self.urls_text.get('1.0', 'end').splitlines() if u.strip()]
        if not urls:
            messagebox.showerror("Error", "Please enter at least one video URL.")
            return
        # Validate directory
        if not os.path.isdir(self.download_dir.get()):
            messagebox.showerror("Error", "Please select a valid download directory.")
            return
        # Reset progress bar and log
        self.update_progress(0)
        self.log("Starting downloads…")
        # Launch worker thread
        threading.Thread(target=self.download_worker, args=(urls,), daemon=True).start()

    def show_how_to(self) -> None:
        """Display the contents of the user guide in a new window."""
        # Determine the path to the user guide. When packaged with PyInstaller,
        # resources are extracted to a temporary directory pointed to by
        # sys._MEIPASS. In a regular Python environment, __file__ works.
        import sys  # imported here to avoid top‑level cost when not needed
        if getattr(sys, 'frozen', False):
            base_path = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))
        guide_path = os.path.join(base_path, 'user_guide.txt')

        # If the file isn't found in the expected location, also check next to
        # the executable (useful when the guide is kept alongside the exe)
        if not os.path.isfile(guide_path):
            exe_dir = os.path.dirname(sys.argv[0])
            alt_path = os.path.join(exe_dir, 'user_guide.txt')
            if os.path.isfile(alt_path):
                guide_path = alt_path

        # Attempt to read the user guide
        try:
            with open(guide_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception:
            messagebox.showerror("Error", f"User guide not found at {guide_path}")
            return

        win = tk.Toplevel(self)
        win.title("How to Use")
        win.geometry("600x400")
        txt = tk.Text(win, wrap="word")
        txt.insert("1.0", content)
        txt.configure(state="disabled")
        txt.pack(fill="both", expand=True)
        scrollbar = ttk.Scrollbar(win, command=txt.yview)
        txt.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")


def main() -> None:
    app = YDLStudio()
    app.mainloop()


if __name__ == '__main__':
    main()
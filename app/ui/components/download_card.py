"""
Download Card Component representing a queued or active download (v2.0 Universal).
Features thumbnail, platform/audio badge, smart preset pre-selection, auto-start support,
progress bar, live recording stop control, one-click play, and folder open.
"""
import os
import subprocess
import threading
from typing import Any, Callable, Dict, Optional
import customtkinter as ctk
from PIL import Image
from app.core.downloader import DownloadTask
from app.core.metadata import fetch_thumbnail_image
from app.ui.theme import COLORS, FONTS


class DownloadCard(ctk.CTkFrame):
    """Modern card widget for an individual video or audio item in the download queue."""

    def __init__(
        self,
        master,
        info: Dict[str, Any],
        get_download_dir: Callable[[], str],
        get_browser_cookie: Callable[[], Optional[str]],
        on_remove: Callable[["DownloadCard"], None],
        **kwargs
    ):
        super().__init__(
            master,
            fg_color=COLORS["card_bg"],
            corner_radius=12,
            border_width=1,
            border_color=COLORS["card_border"],
            **kwargs
        )

        self.info = info
        self.get_download_dir = get_download_dir
        self.get_browser_cookie = get_browser_cookie
        self.on_remove = on_remove

        self.is_live = bool(info.get('is_live', False))
        self.task: Optional[DownloadTask] = None
        self.output_filepath: Optional[str] = None
        self.is_downloading = False
        self.is_finished = False

        self._build_ui()
        self._load_thumbnail_async()

    def _build_ui(self):
        self.grid_columnconfigure(1, weight=1)

        # 1. Left: Thumbnail container
        media_intent = self.info.get('media_intent', 'video')
        placeholder_icon = "🎵 음원\n불러오는 중…" if media_intent == "audio" else "🎬 미리보기\n불러오는 중…"
        self.thumb_label = ctk.CTkLabel(
            self,
            text=placeholder_icon,
            width=150,
            height=85,
            corner_radius=8,
            fg_color=("gray85", "gray20"),
            font=FONTS["caption"]
        )
        self.thumb_label.grid(row=0, column=0, rowspan=3, padx=(12, 10), pady=12, sticky="nsw")

        # 2. Top-Right: Title & Remove button
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.grid(row=0, column=1, sticky="ew", padx=(0, 12), pady=(12, 0))
        header_frame.grid_columnconfigure(1, weight=1)

        # Platform / Stream Type Badge
        stream_type = self.info.get('stream_type', '영상')
        badge_color = "#3b82f6"
        if self.is_live:
            badge_color = "#ef4444"
            badge_text = "🔴 LIVE"
        elif "음원" in stream_type or "music" in stream_type.lower() or "soundcloud" in stream_type.lower():
            badge_color = "#f59e0b"
            badge_text = stream_type
        elif "보안" in stream_type:
            badge_color = "#10b981"
            badge_text = stream_type
        elif "m3u8" in stream_type.lower() or "hls" in stream_type.lower():
            badge_color = "#ec4899"
            badge_text = "HLS (m3u8)"
        elif "mpd" in stream_type.lower() or "dash" in stream_type.lower():
            badge_color = "#8b5cf6"
            badge_text = "DASH (mpd)"
        elif "tiktok" in stream_type.lower():
            badge_color = "#06b6d4"
            badge_text = "TikTok"
        elif "twitter" in stream_type.lower() or "x" in stream_type.lower():
            badge_color = "#64748b"
            badge_text = "X"
        else:
            badge_text = stream_type

        self.badge_label = ctk.CTkLabel(
            header_frame,
            text=f" {badge_text} ",
            font=FONTS["caption_bold"],
            text_color="white",
            fg_color=badge_color,
            corner_radius=5
        )
        self.badge_label.grid(row=0, column=0, padx=(0, 8), sticky="w")

        raw_title = self.info.get('title', '미디어 제목')
        title_text = raw_title if len(raw_title) <= 54 else raw_title[:51] + "..."
        self.title_label = ctk.CTkLabel(
            header_frame,
            text=title_text,
            font=FONTS["header"],
            anchor="w",
            justify="left"
        )
        self.title_label.grid(row=0, column=1, sticky="w")

        # Close/Remove button [✕]
        self.btn_close = ctk.CTkButton(
            header_frame,
            text="✕",
            width=28,
            height=28,
            font=FONTS["body_bold"],
            fg_color="transparent",
            hover_color=("gray80", "gray30"),
            text_color=("gray40", "gray70"),
            command=self._handle_remove
        )
        self.btn_close.grid(row=0, column=2, sticky="e")

        # Subtitle: Channel name and duration
        channel = self.info.get('channel', '채널명')
        duration_str = self.info.get('duration_str', '')
        if self.is_live:
            info_sub = f"📺 {channel}  •  🔴 실시간 방송 (원하는 만큼 녹화 후 종료)"
        else:
            info_sub = f"📺 {channel}" + (f"  •  ⏱️ {duration_str}" if duration_str else "")

        self.sub_label = ctk.CTkLabel(
            header_frame,
            text=info_sub,
            font=FONTS["caption"],
            text_color=COLORS["text_muted"],
            anchor="w"
        )
        self.sub_label.grid(row=1, column=0, columnspan=3, sticky="w", pady=(2, 4))

        # 3. Middle-Right: Option selector & Action buttons
        ctrl_frame = ctk.CTkFrame(self, fg_color="transparent")
        ctrl_frame.grid(row=1, column=1, sticky="ew", padx=(0, 12), pady=(0, 6))
        ctrl_frame.grid_columnconfigure(0, weight=1)

        presets = self.info.get('available_presets', ["최고 화질 (Best Auto)"])
        initial_preset = self.info.get('selected_preset') or presets[0]
        if initial_preset not in presets:
            initial_preset = presets[0]

        self.preset_var = ctk.StringVar(value=initial_preset)
        self.opt_preset = ctk.CTkOptionMenu(
            ctrl_frame,
            values=presets,
            variable=self.preset_var,
            width=220,
            height=34,
            font=FONTS["body"],
            dropdown_font=FONTS["body"]
        )
        self.opt_preset.grid(row=0, column=0, sticky="w", padx=(0, 8))

        btn_action_text = "🔴 녹화 시작" if self.is_live else "⬇️ 다운로드"
        btn_action_color = "#ef4444" if self.is_live else COLORS["accent_primary"]
        btn_action_hover = "#dc2626" if self.is_live else COLORS["accent_hover"]

        self.btn_action = ctk.CTkButton(
            ctrl_frame,
            text=btn_action_text,
            width=110,
            height=34,
            font=FONTS["body_bold"],
            fg_color=btn_action_color,
            hover_color=btn_action_hover,
            command=self._toggle_download
        )
        self.btn_action.grid(row=0, column=1, padx=(0, 6))

        # Play File button (initially hidden)
        self.btn_play = ctk.CTkButton(
            ctrl_frame,
            text="▶️ 바로 재생",
            width=95,
            height=34,
            font=FONTS["body_bold"],
            fg_color="#10b981",
            hover_color="#059669",
            text_color="white",
            command=self._play_file
        )

        # Open Folder button (initially hidden)
        self.btn_folder = ctk.CTkButton(
            ctrl_frame,
            text="📂 폴더 열기",
            width=100,
            height=34,
            font=FONTS["body_bold"],
            fg_color=("gray80", "gray25"),
            hover_color=("gray70", "gray35"),
            text_color=("black", "white"),
            command=self._open_folder
        )

        # 4. Bottom-Right: Progress bar and status label
        progress_frame = ctk.CTkFrame(self, fg_color="transparent")
        progress_frame.grid(row=2, column=1, sticky="ew", padx=(0, 12), pady=(0, 12))
        progress_frame.grid_columnconfigure(0, weight=1)

        self.progress_bar = ctk.CTkProgressBar(
            progress_frame,
            height=8,
            corner_radius=4,
            progress_color=COLORS["accent_primary"]
        )
        self.progress_bar.set(0.0)
        self.progress_bar.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 4))

        self.status_label = ctk.CTkLabel(
            progress_frame,
            text="대기 중",
            font=FONTS["caption"],
            text_color=COLORS["text_muted"],
            anchor="w"
        )
        self.status_label.grid(row=1, column=0, sticky="w")

        self.speed_label = ctk.CTkLabel(
            progress_frame,
            text="",
            font=FONTS["caption"],
            text_color=COLORS["text_muted"],
            anchor="e"
        )
        self.speed_label.grid(row=1, column=1, sticky="e")

    def _load_thumbnail_async(self):
        thumb_url = self.info.get('thumbnail_url')
        if not thumb_url:
            return

        def _fetch():
            pil_img = fetch_thumbnail_image(thumb_url, size=(150, 85))
            if pil_img:
                def _update_ui():
                    if self.winfo_exists():
                        ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(150, 85))
                        self.thumb_label.configure(image=ctk_img, text="")
                self.after(0, _update_ui)

        threading.Thread(target=_fetch, daemon=True).start()

    def start_download(self):
        """Public helper to start download if not already running or finished."""
        if not self.is_downloading and not self.is_finished:
            self._toggle_download()

    def _toggle_download(self):
        if self.is_downloading:
            if self.task:
                self.task.cancel()
            self.is_downloading = False
            if self.is_live:
                self.btn_action.configure(
                    text="🔴 다시 녹화",
                    fg_color="#ef4444",
                    hover_color="#dc2626"
                )
                self.status_label.configure(text="녹화가 중지되었습니다.", text_color=COLORS["accent_warning"])
            else:
                self.btn_action.configure(
                    text="⬇️ 다시 받기",
                    fg_color=COLORS["accent_primary"],
                    hover_color=COLORS["accent_hover"]
                )
                self.status_label.configure(text="다운로드 취소됨", text_color=COLORS["accent_warning"])
            self.opt_preset.configure(state="normal")
        else:
            self.is_downloading = True
            self.is_finished = False
            self.opt_preset.configure(state="disabled")
            stop_btn_text = "⏹️ 녹화 종료" if self.is_live else "⏹️ 취소"
            self.btn_action.configure(
                text=stop_btn_text,
                fg_color=COLORS["accent_danger"],
                hover_color="#DC2626"
            )
            self.progress_bar.set(0.0)
            self.status_label.configure(
                text="녹화 시작…" if self.is_live else "자동 다운로드 시작…",
                text_color=COLORS["text_muted"]
            )
            self.speed_label.configure(text="")

            save_dir = self.get_download_dir()
            browser_cookie = self.get_browser_cookie()

            self.task = DownloadTask(
                url=self.info['url'],
                page_url=self.info.get('page_url') or self.info['url'],
                save_dir=save_dir,
                preset=self.preset_var.get(),
                browser_cookie=browser_cookie,
                headers=self.info.get('headers'),
                is_live=self.is_live,
                title=self.info.get('title'),
                use_browser_fetcher=self.info.get('use_browser_fetcher', False),
                on_progress=self._on_progress,
                on_status_change=self._on_status_change,
                on_finish=self._on_finish,
                on_error=self._on_error
            )
            self.task.start()

    def _on_progress(self, percent: float, speed_str: str, eta_str: str):
        def _update():
            if not self.winfo_exists():
                return
            if not self.is_live:
                self.progress_bar.set(percent / 100.0)
                meta_parts = [f"{percent:.1f}%"]
                if speed_str:
                    meta_parts.append(speed_str)
                self.status_label.configure(text=" • ".join(meta_parts))
                self.speed_label.configure(text=eta_str)
            else:
                self.progress_bar.set(1.0)
                self.progress_bar.configure(progress_color="#ef4444")
                self.speed_label.configure(text=eta_str)
        self.after(0, _update)

    def _on_status_change(self, status: str, message: str):
        def _update():
            if not self.winfo_exists():
                return
            if status in ("STARTING", "ANALYZING", "PROCESSING"):
                self.status_label.configure(text=message, text_color=COLORS["accent_primary"])
            elif status == "DOWNLOADING":
                self.status_label.configure(text=message, text_color=COLORS["text_primary"] if "text_primary" in COLORS else "white")
            elif status == "LIVE_RECORDING":
                self.status_label.configure(text=message, text_color="#ef4444")
            elif status == "CANCELLED":
                self.status_label.configure(text=message, text_color=COLORS["accent_warning"])
            elif status == "FINISHED":
                self.status_label.configure(text=message, text_color=COLORS["accent_success"])
            elif status == "ERROR":
                self.status_label.configure(text=message, text_color=COLORS["accent_danger"])
        self.after(0, _update)

    def _on_finish(self, filepath: str):
        def _update():
            if not self.winfo_exists():
                return
            self.is_downloading = False
            self.is_finished = True
            self.output_filepath = filepath
            self.progress_bar.set(1.0)
            self.progress_bar.configure(progress_color=COLORS["accent_success"])
            self.btn_action.grid_forget()
            if filepath and os.path.isfile(filepath):
                self.btn_play.grid(row=0, column=1, padx=(0, 6))
                self.btn_folder.grid(row=0, column=2, padx=(0, 6))
            else:
                self.btn_folder.grid(row=0, column=1, padx=(0, 6))
            self.speed_label.configure(text="")
        self.after(0, _update)

    def _on_error(self, error_msg: str):
        def _update():
            if not self.winfo_exists():
                return
            self.is_downloading = False
            self.opt_preset.configure(state="normal")
            self.btn_action.configure(
                text="🔄 재시도",
                fg_color=COLORS["accent_warning"],
                hover_color="#D97706"
            )
            self.speed_label.configure(text="")
        self.after(0, _update)

    def _play_file(self):
        if self.output_filepath and os.path.isfile(self.output_filepath):
            try:
                os.startfile(os.path.normpath(self.output_filepath))
            except Exception:
                self._open_folder()

    def _open_folder(self):
        target = self.output_filepath or self.get_download_dir()
        if os.path.exists(target):
            if os.path.isfile(target):
                subprocess.run(['explorer', '/select,', os.path.normpath(target)])
            else:
                subprocess.run(['explorer', os.path.normpath(target)])
        else:
            download_dir = self.get_download_dir()
            if os.path.exists(download_dir):
                subprocess.run(['explorer', os.path.normpath(download_dir)])

    def _handle_remove(self):
        if self.is_downloading and self.task:
            self.task.cancel()
        self.on_remove(self)

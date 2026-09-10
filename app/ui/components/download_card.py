"""
Download Card Component representing a queued or active download.
Features thumbnail, title, channel info, preset selector, progress bar, cancel, and folder open.
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
    """Modern card widget for an individual video in the download queue."""

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

        self.task: Optional[DownloadTask] = None
        self.output_filepath: Optional[str] = None
        self.is_downloading = False

        self._build_ui()
        self._load_thumbnail_async()

    def _build_ui(self):
        self.grid_columnconfigure(1, weight=1)

        # 1. Left: Thumbnail container
        self.thumb_label = ctk.CTkLabel(
            self,
            text="미리보기\n불러오는 중…",
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
        header_frame.grid_columnconfigure(0, weight=1)

        raw_title = self.info.get('title', '영상 제목')
        title_text = raw_title if len(raw_title) <= 55 else raw_title[:52] + "..."
        self.title_label = ctk.CTkLabel(
            header_frame,
            text=title_text,
            font=FONTS["header"],
            anchor="w",
            justify="left"
        )
        self.title_label.grid(row=0, column=0, sticky="w")

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
        self.btn_close.grid(row=0, column=1, sticky="e")

        # Subtitle: Channel name and duration
        channel = self.info.get('channel', '채널명')
        duration_str = self.info.get('duration_str', '')
        info_sub = f"📺 {channel}" + (f"  •  ⏱️ {duration_str}" if duration_str else "")
        self.sub_label = ctk.CTkLabel(
            header_frame,
            text=info_sub,
            font=FONTS["caption"],
            text_color=COLORS["text_muted"],
            anchor="w"
        )
        self.sub_label.grid(row=1, column=0, columnspan=2, sticky="w", pady=(2, 4))

        # 3. Middle-Right: Option selector & Action buttons
        ctrl_frame = ctk.CTkFrame(self, fg_color="transparent")
        ctrl_frame.grid(row=1, column=1, sticky="ew", padx=(0, 12), pady=(0, 6))
        ctrl_frame.grid_columnconfigure(0, weight=1)

        # Preset drop-down
        presets = self.info.get('available_presets', ["최고 화질 (Best Auto)"])
        self.preset_var = ctk.StringVar(value=presets[0])
        self.opt_preset = ctk.CTkOptionMenu(
            ctrl_frame,
            values=presets,
            variable=self.preset_var,
            width=200,
            height=34,
            font=FONTS["body"],
            dropdown_font=FONTS["body"]
        )
        self.opt_preset.grid(row=0, column=0, sticky="w", padx=(0, 8))

        # Action button (Download / Cancel / Open Folder)
        self.btn_action = ctk.CTkButton(
            ctrl_frame,
            text="⬇️ 다운로드",
            width=110,
            height=34,
            font=FONTS["body_bold"],
            fg_color=COLORS["accent_primary"],
            hover_color=COLORS["accent_hover"],
            command=self._toggle_download
        )
        self.btn_action.grid(row=0, column=1, padx=(0, 6))

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
                    ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(150, 85))
                    self.thumb_label.configure(image=ctk_img, text="")
                self.after(0, _update_ui)

        threading.Thread(target=_fetch, daemon=True).start()

    def _toggle_download(self):
        if self.is_downloading:
            # Cancel
            if self.task:
                self.task.cancel()
            self.is_downloading = False
            self.btn_action.configure(
                text="⬇️ 다시 받기",
                fg_color=COLORS["accent_primary"],
                hover_color=COLORS["accent_hover"]
            )
            self.status_label.configure(text="다운로드 취소됨", text_color=COLORS["accent_warning"])
            self.opt_preset.configure(state="normal")
        else:
            # Start
            self.is_downloading = True
            self.opt_preset.configure(state="disabled")
            self.btn_action.configure(
                text="⏹️ 취소",
                fg_color=COLORS["accent_danger"],
                hover_color="#DC2626"
            )
            self.progress_bar.set(0.0)
            self.status_label.configure(text="다운로드 시작…", text_color=COLORS["text_muted"])
            self.speed_label.configure(text="")

            save_dir = self.get_download_dir()
            browser_cookie = self.get_browser_cookie()

            self.task = DownloadTask(
                url=self.info['url'],
                save_dir=save_dir,
                preset=self.preset_var.get(),
                browser_cookie=browser_cookie,
                on_progress=self._on_progress,
                on_status_change=self._on_status_change,
                on_finish=self._on_finish,
                on_error=self._on_error
            )
            self.task.start()

    def _on_progress(self, percent: float, speed_str: str, eta_str: str):
        def _update():
            self.progress_bar.set(percent / 100.0)
            meta_parts = [f"{percent:.1f}%"]
            if speed_str:
                meta_parts.append(speed_str)
            self.status_label.configure(text=" • ".join(meta_parts))
            self.speed_label.configure(text=eta_str)
        self.after(0, _update)

    def _on_status_change(self, status: str, message: str):
        def _update():
            if status == "PROCESSING":
                self.status_label.configure(text=message, text_color=COLORS["accent_primary"])
            elif status == "CANCELLED":
                self.status_label.configure(text=message, text_color=COLORS["accent_warning"])
            elif status == "FINISHED":
                self.status_label.configure(text=message, text_color=COLORS["accent_success"])
            elif status == "ERROR":
                self.status_label.configure(text=message, text_color=COLORS["accent_danger"])
        self.after(0, _update)

    def _on_finish(self, filepath: str):
        def _update():
            self.is_downloading = False
            self.output_filepath = filepath
            self.progress_bar.set(1.0)
            self.progress_bar.configure(progress_color=COLORS["accent_success"])
            self.btn_action.grid_forget()
            self.btn_folder.grid(row=0, column=1, padx=(0, 6))
            self.speed_label.configure(text="")
        self.after(0, _update)

    def _on_error(self, error_msg: str):
        def _update():
            self.is_downloading = False
            self.opt_preset.configure(state="normal")
            self.btn_action.configure(
                text="🔄 재시도",
                fg_color=COLORS["accent_warning"],
                hover_color="#D97706"
            )
            self.speed_label.configure(text="")
        self.after(0, _update)

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

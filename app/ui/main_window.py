"""
Main Application Window for YDL Studio.
Orchestrates URL input, metadata extraction, download queue, settings, and clipboard monitoring.
"""
import os
import threading
from tkinter import messagebox
from typing import List, Optional
import customtkinter as ctk

from app.core.metadata import extract_video_info
from app.core.updater import get_current_version
from app.ui.components.download_card import DownloadCard
from app.ui.components.settings_modal import SettingsModal
from app.ui.components.url_input_bar import UrlInputBar
from app.ui.theme import COLORS, FONTS
from app.utils.clipboard import extract_media_url
from app.utils.config import load_config, save_config


class MainWindow(ctk.CTk):
    """Main window for YDL Studio."""

    def __init__(self):
        super().__init__()

        # Load user configuration
        self.config = load_config()

        # Appearance setup
        ctk.set_appearance_mode(self.config.get("theme", "Dark"))
        ctk.set_default_color_theme("blue")

        self.title("YDL Studio - 모던 미디어 다운로더")
        self.geometry("900x700")
        self.minsize(800, 550)

        # State variables
        self.cards: List[DownloadCard] = []
        self.last_clipboard_text = ""
        self.auto_clip_enabled = self.config.get("auto_clipboard", True)

        self._build_layout()
        self._start_clipboard_monitor()

    def _build_layout(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)  # Queue scroll area expands

        # 1. Header (Brand Logo & Title)
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=(15, 8))
        header_frame.grid_columnconfigure(0, weight=1)

        title_label = ctk.CTkLabel(
            header_frame,
            text="⚡ YDL Studio",
            font=FONTS["title"],
            text_color=COLORS["accent_primary"],
            anchor="w"
        )
        title_label.grid(row=0, column=0, sticky="w")

        subtitle_label = ctk.CTkLabel(
            header_frame,
            text="고화질 영상 & 오디오 다운로더 • yt-dlp 기반",
            font=FONTS["body"],
            text_color=COLORS["text_muted"],
            anchor="w"
        )
        subtitle_label.grid(row=1, column=0, sticky="w")

        # 2. URL Input Bar
        self.input_bar = UrlInputBar(
            self,
            on_analyze=self.handle_add_url,
            on_open_settings=self.open_settings,
            on_clipboard_toggle=self.toggle_clipboard_auto
        )
        self.input_bar.auto_clip_var.set(self.auto_clip_enabled)
        self.input_bar.grid(row=1, column=0, sticky="ew", padx=15, pady=(0, 10))

        # 3. Queue Scrollable Frame
        self.queue_frame = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            corner_radius=10,
        )
        self.queue_frame.grid(row=2, column=0, sticky="nsew", padx=15, pady=(0, 10))
        self.queue_frame.grid_columnconfigure(0, weight=1)

        # Empty state placeholder
        self.empty_label = ctk.CTkLabel(
            self.queue_frame,
            text="📥 다운로드 대기열이 비어 있습니다.\n\n상단에 유튜브 주소를 입력하거나 붙여넣어 주세요.",
            font=FONTS["subtitle"],
            text_color=COLORS["text_muted"],
            justify="center"
        )
        self.empty_label.pack(pady=100)

        # 4. Status Bar
        status_bar = ctk.CTkFrame(self, height=36, fg_color=COLORS["card_bg"], corner_radius=0)
        status_bar.grid(row=3, column=0, sticky="ew")
        status_bar.grid_columnconfigure(1, weight=1)

        save_dir = self.config.get("download_dir", "")
        self.lbl_status_path = ctk.CTkLabel(
            status_bar,
            text=f"📁 {save_dir}",
            font=FONTS["caption"],
            text_color=COLORS["text_muted"]
        )
        self.lbl_status_path.grid(row=0, column=0, padx=15, pady=4, sticky="w")

        self.lbl_queue_count = ctk.CTkLabel(
            status_bar,
            text="대기열: 0개",
            font=FONTS["caption"],
            text_color=COLORS["text_muted"]
        )
        self.lbl_queue_count.grid(row=0, column=2, padx=15, pady=4, sticky="e")

        engine_ver = get_current_version()
        self.lbl_engine = ctk.CTkLabel(
            status_bar,
            text=f"엔진 v{engine_ver}",
            font=FONTS["caption"],
            text_color=COLORS["text_muted"]
        )
        self.lbl_engine.grid(row=0, column=3, padx=(0, 15), pady=4, sticky="e")

    def handle_add_url(self, url: str):
        """Analyze a URL in background and append a card to the queue."""
        clean_url = extract_media_url(url) or url.strip()

        # Temporary status banner
        loading_popup = ctk.CTkToplevel(self)
        loading_popup.title("분석 중")
        loading_popup.geometry("320x100")
        loading_popup.resizable(False, False)
        loading_popup.transient(self)
        loading_popup.grab_set()

        ctk.CTkLabel(
            loading_popup,
            text="🔍 영상 정보 분석 중입니다…\n잠시만 기다려 주세요.",
            font=FONTS["body"],
            justify="center"
        ).pack(expand=True, fill="both")

        def _worker():
            browser_cookie = self.config.get("browser_cookie")
            try:
                info = extract_video_info(clean_url, browser_cookie=browser_cookie)
                def _success():
                    loading_popup.destroy()
                    self._add_card(info)
                self.after(0, _success)
            except Exception as e:
                def _error():
                    loading_popup.destroy()
                    messagebox.showerror(
                        "분석 실패",
                        f"영상 정보를 가져오지 못했습니다:\n{e}\n\n"
                        "💡 팁: [설정]에서 브라우저 쿠키 연동을 켜면 봇 차단을 우회할 수 있습니다."
                    )
                self.after(0, _error)

        threading.Thread(target=_worker, daemon=True).start()

    def _add_card(self, info: dict):
        if self.empty_label.winfo_ismapped():
            self.empty_label.pack_forget()

        card = DownloadCard(
            master=self.queue_frame,
            info=info,
            get_download_dir=lambda: self.config.get("download_dir", os.getcwd()),
            get_browser_cookie=lambda: self.config.get("browser_cookie"),
            on_remove=self._remove_card,
        )
        card.pack(fill="x", expand=True, pady=6)
        self.cards.append(card)
        self._update_queue_count()

    def _remove_card(self, card: DownloadCard):
        card.destroy()
        if card in self.cards:
            self.cards.remove(card)
        if not self.cards:
            self.empty_label.pack(pady=100)
        self._update_queue_count()

    def _update_queue_count(self):
        self.lbl_queue_count.configure(text=f"대기열: {len(self.cards)}개")

    def open_settings(self):
        SettingsModal(
            master=self,
            current_save_dir=self.config.get("download_dir", os.getcwd()),
            current_browser_cookie=self.config.get("browser_cookie"),
            on_save=self._on_settings_saved
        )

    def _on_settings_saved(self, new_dir: str, browser_cookie: Optional[str]):
        if new_dir:
            self.config["download_dir"] = new_dir
            self.lbl_status_path.configure(text=f"📁 {new_dir}")
        self.config["browser_cookie"] = browser_cookie
        save_config(self.config)

    def toggle_clipboard_auto(self, enabled: bool):
        self.auto_clip_enabled = enabled
        self.config["auto_clipboard"] = enabled
        save_config(self.config)

    def _start_clipboard_monitor(self):
        """Poll clipboard every 1.5 seconds for new media URLs."""
        def _poll():
            if self.auto_clip_enabled:
                try:
                    text = self.clipboard_get()
                    if text and text != self.last_clipboard_text:
                        self.last_clipboard_text = text
                        url = extract_media_url(text)
                        if url:
                            self.input_bar.set_url(url)
                except Exception:
                    pass
            self.after(1500, _poll)

        self.after(1500, _poll)

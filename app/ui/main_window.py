"""
Main Application Window for YDL Studio v2.0.0 (Smart Zero-Click Universal Edition).
Orchestrates multi-URL input, non-blocking inline analysis, smart video/audio intent detection,
automatic one-stop downloading, clipboard monitoring, and Browser/Chromecast Stream Sniffing.
"""
import os
import subprocess
import threading
from tkinter import messagebox
from typing import Any, Dict, List, Optional
import customtkinter as ctk

from app.core.browser_sniffer import BrowserSniffer
from app.core.metadata import extract_video_info
from app.core.updater import get_current_version
from app.ui.components.download_card import DownloadCard
from app.ui.components.settings_modal import SettingsModal
from app.ui.components.sniffer_modal import SnifferModal
from app.ui.components.url_input_bar import UrlInputBar
from app.ui.theme import COLORS, FONTS
from app.utils.clipboard import extract_all_urls, extract_media_url
from app.utils.config import load_config, save_config


class MainWindow(ctk.CTk):
    """Main window for YDL Studio v2.0.0."""

    def __init__(self):
        super().__init__()

        self.config = load_config()

        ctk.set_appearance_mode(self.config.get("theme", "Dark"))
        ctk.set_default_color_theme("blue")

        self.title("YDL Studio v2.0.0 - 스마트 원클릭 만능 미디어 & 음원 다운로더 (2026-10-19 업데이트)")
        self.geometry("980x740")
        self.minsize(860, 600)

        self._set_window_icon()

        # State variables
        self.cards: List[DownloadCard] = []
        self.active_urls: set = set()
        self.last_clipboard_text = ""
        self.auto_clip_enabled = self.config.get("auto_clipboard", True)
        self.auto_start_enabled = self.config.get("auto_start_download", True)
        self.intent_mode = self.config.get("intent_mode", "auto")

        # Browser Sniffer instance
        self.sniffer = BrowserSniffer(
            on_stream_detected=self._on_stream_detected,
            preferred_browser=self.config.get("preferred_browser", "auto")
        )
        self.sniffer_modal: Optional[SnifferModal] = None

        self._build_layout()
        self._start_clipboard_monitor()

        # Global Ctrl+V shortcut when entry is not focused
        self.bind("<Control-v>", self._on_global_paste)
        self.bind("<Control-V>", self._on_global_paste)

        self.protocol("WM_DELETE_WINDOW", self._on_window_close)

    def _set_window_icon(self):
        """Set window icon from assets folder."""
        import sys
        if getattr(sys, 'frozen', False):
            base_dir = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
            paths = [
                os.path.join(base_dir, "app", "assets", "icon.ico"),
                os.path.join(base_dir, "assets", "icon.ico"),
            ]
        else:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            paths = [os.path.join(base_dir, "assets", "icon.ico")]

        for p in paths:
            if os.path.exists(p):
                try:
                    self.iconbitmap(p)
                    break
                except Exception:
                    pass

    def _build_layout(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # 1. Header (Brand Logo & Title)
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=(15, 8))
        header_frame.grid_columnconfigure(1, weight=1)

        import sys
        if getattr(sys, 'frozen', False):
            base_dir = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
            png_paths = [
                os.path.join(base_dir, "app", "assets", "icon.png"),
                os.path.join(base_dir, "assets", "icon.png")
            ]
        else:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            png_paths = [os.path.join(base_dir, "assets", "icon.png")]

        for p in png_paths:
            if os.path.exists(p):
                try:
                    from PIL import Image
                    pil_logo = Image.open(p)
                    logo_img = ctk.CTkImage(light_image=pil_logo, dark_image=pil_logo, size=(42, 42))
                    logo_lbl = ctk.CTkLabel(header_frame, image=logo_img, text="")
                    logo_lbl.grid(row=0, column=0, rowspan=2, padx=(0, 12), sticky="w")
                    break
                except Exception:
                    pass

        title_label = ctk.CTkLabel(
            header_frame,
            text="YDL Studio v2.0.0",
            font=FONTS["title"],
            text_color=COLORS["accent_primary"],
            anchor="w"
        )
        title_label.grid(row=0, column=1, sticky="w")

        subtitle_label = ctk.CTkLabel(
            header_frame,
            text="스마트 원클릭 만능 다운로더 • 2026-10-19 업데이트 • 주소만 복붙하면 영상(MP4) / 음원(MP3·FLAC) 자동 판별 및 4단계 우회 다운로드",
            font=FONTS["body"],
            text_color=COLORS["text_muted"],
            anchor="w"
        )
        subtitle_label.grid(row=1, column=1, sticky="w")

        # 2. URL Input Bar with Smart Intent & Auto-Start
        self.input_bar = UrlInputBar(
            self,
            on_analyze=self.handle_add_url,
            on_open_settings=self.open_settings,
            on_clipboard_toggle=self.toggle_clipboard_auto,
            on_auto_start_toggle=self.toggle_auto_start,
            on_intent_mode_change=self.change_intent_mode,
            on_open_sniffer=self.open_sniffer
        )
        self.input_bar.auto_clip_var.set(self.auto_clip_enabled)
        self.input_bar.auto_start_var.set(self.auto_start_enabled)
        self.input_bar.set_intent_mode(self.intent_mode)
        self.input_bar.grid(row=1, column=0, sticky="ew", padx=15, pady=(0, 10))

        # 3. Queue Scrollable Frame
        self.queue_frame = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            corner_radius=10,
        )
        self.queue_frame.grid(row=2, column=0, sticky="nsew", padx=15, pady=(0, 10))
        self.queue_frame.grid_columnconfigure(0, weight=1)

        self.empty_label = ctk.CTkLabel(
            self.queue_frame,
            text=(
                "📥 다운로드 대기열이 비어 있습니다.\n\n"
                "💡 원하는 영상이나 음원 주소를 복사한 뒤 [📋 원클릭 복붙] (또는 Ctrl+V)만 누르세요!\n"
                "유튜브, 음원 사이트(멜론·스포티파이·사운드클라우드), 틱톡, 인스타, 보안 스트리밍까지\n"
                "알아서 영상/음원을 판별하여 즉시 다운로드합니다."
            ),
            font=FONTS["subtitle"],
            text_color=COLORS["text_muted"],
            justify="center"
        )
        self.empty_label.pack(pady=95)

        # 4. Bottom Status & Batch Action Bar
        status_bar = ctk.CTkFrame(self, height=40, fg_color=COLORS["card_bg"], corner_radius=0)
        status_bar.grid(row=3, column=0, sticky="ew")
        status_bar.grid_columnconfigure(1, weight=1)

        save_dir = self.config.get("download_dir", "")
        self.btn_open_save_dir = ctk.CTkButton(
            status_bar,
            text=f"📁 저장 폴더: {save_dir}",
            height=28,
            font=FONTS["caption"],
            fg_color="transparent",
            hover_color=("gray80", "gray25"),
            text_color=COLORS["text_muted"],
            anchor="w",
            command=self._open_default_save_dir
        )
        self.btn_open_save_dir.grid(row=0, column=0, padx=10, pady=4, sticky="w")

        batch_frame = ctk.CTkFrame(status_bar, fg_color="transparent")
        batch_frame.grid(row=0, column=2, padx=10, pady=4, sticky="e")

        self.btn_start_all = ctk.CTkButton(
            batch_frame,
            text="⬇️ 대기항목 전체 시작",
            width=125,
            height=26,
            font=FONTS["caption_bold"],
            fg_color=("gray80", "gray25"),
            hover_color=("gray70", "gray35"),
            text_color=("black", "white"),
            command=self._start_all_pending
        )
        self.btn_start_all.pack(side="left", padx=4)

        self.btn_clear_done = ctk.CTkButton(
            batch_frame,
            text="🧹 완료 정리",
            width=85,
            height=26,
            font=FONTS["caption"],
            fg_color=("gray80", "gray25"),
            hover_color=("gray70", "gray35"),
            text_color=("black", "white"),
            command=self._clear_completed_cards
        )
        self.btn_clear_done.pack(side="left", padx=4)

        self.lbl_queue_count = ctk.CTkLabel(
            status_bar,
            text="대기열: 0개",
            font=FONTS["caption"],
            text_color=COLORS["text_muted"]
        )
        self.lbl_queue_count.grid(row=0, column=3, padx=10, pady=4, sticky="e")

        engine_ver = get_current_version()
        self.lbl_engine = ctk.CTkLabel(
            status_bar,
            text=f"만능 엔진 v{engine_ver} • v2.0 스마트 제로클릭",
            font=FONTS["caption"],
            text_color=COLORS["text_muted"]
        )
        self.lbl_engine.grid(row=0, column=4, padx=(0, 15), pady=4, sticky="e")

    def _on_global_paste(self, event=None):
        """Allow pressing Ctrl+V anywhere in the window to immediately add clipboard URLs."""
        focused = self.focus_get()
        # If focus is already inside the URL entry widget, let default Entry paste work
        if focused and str(focused).startswith(str(self.input_bar.entry)):
            return
        try:
            clip_text = self.clipboard_get().strip()
            if clip_text:
                self.handle_add_url(clip_text)
        except Exception:
            pass

    def _create_analyzing_card(self, url: str) -> ctk.CTkFrame:
        """Create a non-blocking inline placeholder card while analyzing the URL."""
        if self.empty_label.winfo_ismapped():
            self.empty_label.pack_forget()

        card = ctk.CTkFrame(
            self.queue_frame,
            fg_color=COLORS["card_bg"],
            corner_radius=12,
            border_width=1,
            border_color=COLORS["accent_primary"],
        )
        card.pack(fill="x", expand=True, pady=6)
        card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            card,
            text="🔍 분석 중…",
            width=120,
            height=64,
            corner_radius=8,
            fg_color=("gray85", "gray20"),
            font=FONTS["body_bold"],
            text_color=COLORS["accent_primary"]
        ).grid(row=0, column=0, padx=12, pady=12)

        disp_url = url if len(url) <= 75 else url[:72] + "..."
        ctk.CTkLabel(
            card,
            text=f"⚡ 미디어 & 스트림 자동 분석 중: {disp_url}\n4단계 만능 추출 엔진이 최적의 영상/음원 스트림을 탐색하고 있습니다…",
            font=FONTS["body"],
            justify="left",
            anchor="w"
        ).grid(row=0, column=1, padx=10, pady=12, sticky="w")

        return card

    def handle_add_url(self, raw_input: str):
        """Extract one or multiple URLs from input, analyze non-blockingly, and auto-start download."""
        urls = extract_all_urls(raw_input)
        if not urls:
            single = extract_media_url(raw_input, allow_generic_http=True) or raw_input.strip()
            if single:
                urls = [single]

        for clean_url in urls:
            self._analyze_and_enqueue_single(clean_url)

    def _analyze_and_enqueue_single(self, clean_url: str):
        placeholder = self._create_analyzing_card(clean_url)
        current_intent_mode = self.input_bar.get_intent_mode()

        def _worker():
            browser_cookie = self.config.get("browser_cookie")
            try:
                info = extract_video_info(
                    clean_url,
                    browser_cookie=browser_cookie,
                    intent_mode=current_intent_mode
                )

                def _success():
                    try:
                        placeholder.destroy()
                    except Exception:
                        pass
                    card = self._add_card(info)
                    if self.auto_start_enabled and not info.get("is_live", False):
                        card.start_download()

                self.after(0, _success)
            except Exception as e:
                err_msg = str(e)

                def _error(msg=err_msg):
                    try:
                        placeholder.destroy()
                    except Exception:
                        pass
                    if not self.cards:
                        self.empty_label.pack(pady=95)
                    messagebox.showerror(
                        "분석 실패",
                        f"미디어 정보를 가져오지 못했습니다:\n{msg}\n\n"
                        "💡 팁: 로그인이 필요하거나 특수 보안이 걸린 사이트는 상단의 [🌐 브라우저 감지기]를 열어 재생하시면 100% 포착됩니다!"
                    )

                self.after(0, _error)

        threading.Thread(target=_worker, daemon=True).start()

    def handle_add_stream_item(self, stream_item: Dict[str, Any]):
        """Directly add a sniffed stream to queue with headers and auto-start."""
        url = stream_item.get("url", "")
        headers = stream_item.get("headers", {})
        current_intent_mode = self.input_bar.get_intent_mode()

        placeholder = self._create_analyzing_card(url)

        def _worker():
            try:
                browser_cookie = self.config.get("browser_cookie")
                info = extract_video_info(
                    url,
                    browser_cookie=browser_cookie,
                    custom_headers=headers,
                    intent_mode=current_intent_mode
                )
                if "stream" in info["title"].lower() or "웹" in info["title"]:
                    if stream_item.get("page_title"):
                        info["title"] = f"[{stream_item.get('stream_type', '스트림')}] {stream_item.get('page_title')}"

                def _success():
                    try:
                        placeholder.destroy()
                    except Exception:
                        pass
                    card = self._add_card(info)
                    if self.auto_start_enabled and not info.get("is_live", False):
                        card.start_download()

                self.after(0, _success)
            except Exception as e:
                err_msg = str(e)

                def _error(msg=err_msg):
                    try:
                        placeholder.destroy()
                    except Exception:
                        pass
                    messagebox.showerror("스트림 추가 실패", f"스트림 분석 실패: {msg}")

                self.after(0, _error)

        threading.Thread(target=_worker, daemon=True).start()

    def _add_card(self, info: dict) -> DownloadCard:
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
        return card

    def _remove_card(self, card: DownloadCard):
        card.destroy()
        if card in self.cards:
            self.cards.remove(card)
        if not self.cards:
            self.empty_label.pack(pady=95)
        self._update_queue_count()

    def _start_all_pending(self):
        for card in self.cards:
            if not card.is_downloading and not card.is_finished:
                card.start_download()

    def _clear_completed_cards(self):
        completed = [c for c in self.cards if c.is_finished]
        for c in completed:
            self._remove_card(c)

    def _open_default_save_dir(self):
        save_dir = self.config.get("download_dir", os.getcwd())
        if os.path.exists(save_dir):
            subprocess.run(['explorer', os.path.normpath(save_dir)])

    def _update_queue_count(self):
        self.lbl_queue_count.configure(text=f"대기열: {len(self.cards)}개")

    def open_sniffer(self):
        """Open or focus the Browser Stream Sniffer dashboard."""
        if self.sniffer_modal and self.sniffer_modal.winfo_exists():
            self.sniffer_modal.focus()
            return

        self.sniffer_modal = SnifferModal(
            master=self,
            is_sniffer_running=self.sniffer.is_running,
            detected_streams=self.sniffer.detected_streams,
            on_launch_browser=self._launch_sniffer_browser,
            on_stop_sniffer=self._stop_sniffer_browser,
            on_add_stream_to_queue=self.handle_add_stream_item,
            on_clear_streams=self._clear_sniffed_streams,
        )

    def _launch_sniffer_browser(self):
        try:
            self.sniffer.launch_and_start()
        except Exception as e:
            messagebox.showerror("브라우저 실행 실패", f"스니퍼 브라우저를 실행할 수 없습니다:\n{e}")

    def _stop_sniffer_browser(self):
        self.sniffer.stop()

    def _clear_sniffed_streams(self):
        self.sniffer.detected_streams.clear()
        self.sniffer.detected_urls.clear()
        self.input_bar.update_sniffer_badge(0)

    def _on_stream_detected(self, stream_info: Dict[str, Any]):
        """Invoked when the CDP sniffer intercepts a new media stream."""
        def _update():
            count = len(self.sniffer.detected_streams)
            self.input_bar.update_sniffer_badge(count)
            if self.sniffer_modal and self.sniffer_modal.winfo_exists():
                self.sniffer_modal.add_single_stream(stream_info)
        self.after(0, _update)

    def open_settings(self):
        SettingsModal(
            master=self,
            current_save_dir=self.config.get("download_dir", os.getcwd()),
            current_browser_cookie=self.config.get("browser_cookie"),
            current_preferred_browser=self.config.get("preferred_browser", "auto"),
            on_save=self._on_settings_saved
        )

    def _on_settings_saved(self, new_dir: str, browser_cookie: Optional[str], preferred_browser: str = "auto"):
        if new_dir:
            self.config["download_dir"] = new_dir
            self.btn_open_save_dir.configure(text=f"📁 저장 폴더: {new_dir}")
        self.config["browser_cookie"] = browser_cookie
        self.config["preferred_browser"] = preferred_browser
        self.sniffer.preferred_browser = preferred_browser
        save_config(self.config)

    def toggle_clipboard_auto(self, enabled: bool):
        self.auto_clip_enabled = enabled
        self.config["auto_clipboard"] = enabled
        save_config(self.config)

    def toggle_auto_start(self, enabled: bool):
        self.auto_start_enabled = enabled
        self.config["auto_start_download"] = enabled
        save_config(self.config)

    def change_intent_mode(self, mode_code: str):
        self.intent_mode = mode_code
        self.config["intent_mode"] = mode_code
        save_config(self.config)

    def _start_clipboard_monitor(self):
        """Poll clipboard every 1.2 seconds for new media URLs."""
        try:
            init_clip = self.clipboard_get()
            if init_clip:
                self.last_clipboard_text = init_clip
        except Exception:
            pass

        def _poll():
            if self.auto_clip_enabled:
                try:
                    text = self.clipboard_get()
                    if text and text != self.last_clipboard_text:
                        self.last_clipboard_text = text
                        url = extract_media_url(text, allow_generic_http=False)
                        if url:
                            self.input_bar.set_url(url)
                except Exception:
                    pass
            self.after(1200, _poll)

        self.after(1200, _poll)

    def _on_window_close(self):
        """Clean shutdown hook."""
        try:
            self.sniffer.stop()
        except Exception:
            pass
        self.destroy()

    def report_callback_exception(self, exc, val, tb):
        """Safe exception reporter preventing OSError 22 on Windows GUI without console."""
        try:
            import traceback, sys
            err_msg = "".join(traceback.format_exception(exc, val, tb))
            if sys.stderr and hasattr(sys.stderr, "write"):
                try:
                    sys.stderr.write(err_msg)
                except Exception:
                    pass
        except Exception:
            pass

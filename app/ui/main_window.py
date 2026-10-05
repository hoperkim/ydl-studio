"""
Main Application Window for YDL Studio.
Orchestrates URL input, metadata extraction, download queue, settings,
clipboard monitoring, and real-time Browser/Chromecast Stream Sniffing.
"""
import os
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

        self.title("YDL Studio - 모던 만능 미디어 다운로더")
        self.geometry("920x720")
        self.minsize(820, 580)

        # Set Window Icon
        self._set_window_icon()

        # State variables
        self.cards: List[DownloadCard] = []
        self.last_clipboard_text = ""
        self.auto_clip_enabled = self.config.get("auto_clipboard", True)

        # Browser Sniffer instance
        self.sniffer = BrowserSniffer(
            on_stream_detected=self._on_stream_detected,
            preferred_browser=self.config.get("preferred_browser", "auto")
        )
        self.sniffer_modal: Optional[SnifferModal] = None

        self._build_layout()
        self._start_clipboard_monitor()

        # Handle window close
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
        self.grid_rowconfigure(2, weight=1)  # Queue scroll area expands

        # 1. Header (Brand Logo & Title)
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=(15, 8))
        header_frame.grid_columnconfigure(1, weight=1)

        # App Logo Icon
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
                    logo_img = ctk.CTkImage(light_image=pil_logo, dark_image=pil_logo, size=(40, 40))
                    logo_lbl = ctk.CTkLabel(header_frame, image=logo_img, text="")
                    logo_lbl.grid(row=0, column=0, rowspan=2, padx=(0, 12), sticky="w")
                    break
                except Exception:
                    pass

        title_label = ctk.CTkLabel(
            header_frame,
            text="YDL Studio",
            font=FONTS["title"],
            text_color=COLORS["accent_primary"],
            anchor="w"
        )
        title_label.grid(row=0, column=1, sticky="w")

        subtitle_label = ctk.CTkLabel(
            header_frame,
            text="만능 미디어 다운로더 • YouTube, SNS, 웹 비디오 & 실시간 크롬캐스트 스트림 감지",
            font=FONTS["body"],
            text_color=COLORS["text_muted"],
            anchor="w"
        )
        subtitle_label.grid(row=1, column=1, sticky="w")

        # 2. URL Input Bar with Browser Sniffer
        self.input_bar = UrlInputBar(
            self,
            on_analyze=self.handle_add_url,
            on_open_settings=self.open_settings,
            on_clipboard_toggle=self.toggle_clipboard_auto,
            on_open_sniffer=self.open_sniffer
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
            text="📥 다운로드 대기열이 비어 있습니다.\n\n상단에 주소를 입력하거나, [🌐 브라우저 감지기]로 원하는 영상을 재생해 보세요.",
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
            text=f"만능 엔진 v{engine_ver}",
            font=FONTS["caption"],
            text_color=COLORS["text_muted"]
        )
        self.lbl_engine.grid(row=0, column=3, padx=(0, 15), pady=4, sticky="e")

    def handle_add_url(self, url: str):
        """Analyze a URL in background and append a card to the queue."""
        clean_url = extract_media_url(url) or url.strip()

        loading_popup = ctk.CTkToplevel(self)
        loading_popup.title("분석 중")
        loading_popup.geometry("340x110")
        loading_popup.resizable(False, False)
        loading_popup.transient(self)
        loading_popup.grab_set()

        ctk.CTkLabel(
            loading_popup,
            text="🔍 영상 & 스트림 분석 중입니다…\n웹페이지 심층 탐색을 병행합니다.",
            font=FONTS["body"],
            justify="center"
        ).pack(expand=True, fill="both")

        def _worker():
            browser_cookie = self.config.get("browser_cookie")
            try:
                info = extract_video_info(clean_url, browser_cookie=browser_cookie)
                def _success():
                    try:
                        loading_popup.destroy()
                    except Exception:
                        pass
                    self._add_card(info)
                self.after(0, _success)
            except Exception as e:
                def _error():
                    try:
                        loading_popup.destroy()
                    except Exception:
                        pass
                    messagebox.showerror(
                        "분석 실패",
                        f"영상 정보를 가져오지 못했습니다:\n{e}\n\n"
                        "💡 팁: 일반적인 방법으로 분석되지 않는 복잡한 사이트는 상단의 [🌐 브라우저 감지기]를 켜고 브라우저에서 직접 영상을 재생하면 100% 감지됩니다!"
                    )
                self.after(0, _error)

        threading.Thread(target=_worker, daemon=True).start()

    def handle_add_stream_item(self, stream_item: Dict[str, Any]):
        """Directly add a sniffed stream to queue with headers."""
        url = stream_item.get("url", "")
        headers = stream_item.get("headers", {})

        def _worker():
            try:
                browser_cookie = self.config.get("browser_cookie")
                info = extract_video_info(url, browser_cookie=browser_cookie, custom_headers=headers)
                # Ensure title reflects page title if generic
                if "stream" in info["title"].lower() or "웹" in info["title"]:
                    if stream_item.get("page_title"):
                        info["title"] = f"[{stream_item.get('stream_type', '스트림')}] {stream_item.get('page_title')}"
                def _success():
                    self._add_card(info)
                self.after(0, _success)
            except Exception as e:
                def _error():
                    messagebox.showerror("스트림 추가 실패", f"스트림 분석 실패: {e}")
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
            self.lbl_status_path.configure(text=f"📁 {new_dir}")
        self.config["browser_cookie"] = browser_cookie
        self.config["preferred_browser"] = preferred_browser
        self.sniffer.preferred_browser = preferred_browser
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

    def _on_window_close(self):
        """Clean shutdown hook."""
        try:
            self.sniffer.stop()
        except Exception:
            pass
        self.destroy()

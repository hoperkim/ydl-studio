"""
Browser Stream Sniffer Modal Dialog.
Provides real-time visualization and one-click queue insertion of media streams
captured via Chrome DevTools Protocol from browser playback and Chromecast casting.
"""
from typing import Any, Callable, Dict, List, Optional
import customtkinter as ctk
from app.ui.theme import COLORS, FONTS


class SnifferModal(ctk.CTkToplevel):
    """Real-time browser stream sniffer dashboard."""

    def __init__(
        self,
        master,
        is_sniffer_running: bool,
        detected_streams: List[Dict[str, Any]],
        on_launch_browser: Callable[[], None],
        on_stop_sniffer: Callable[[], None],
        on_add_stream_to_queue: Callable[[Dict[str, Any]], None],
        on_clear_streams: Callable[[], None],
    ):
        super().__init__(master)
        self.master_ref = master
        self.on_launch_browser = on_launch_browser
        self.on_stop_sniffer = on_stop_sniffer
        self.on_add_stream_to_queue = on_add_stream_to_queue
        self.on_clear_streams = on_clear_streams

        self.title("🌐 브라우저 스트림 감지기 (만능 웹 & 크롬캐스트)")
        self.geometry("750x600")
        self.minsize(680, 480)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self._build_header()
        self._build_control_bar(is_sniffer_running)
        self._build_stream_list()

        # Render existing detected streams
        self.render_streams(detected_streams)

    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=(15, 8))
        header.grid_columnconfigure(0, weight=1)

        lbl_title = ctk.CTkLabel(
            header,
            text="🌐 실시간 브라우저 & 크롬캐스트 스트림 감지기",
            font=FONTS["title"],
            text_color=COLORS["accent_primary"],
            anchor="w"
        )
        lbl_title.grid(row=0, column=0, sticky="w")

        lbl_guide = ctk.CTkLabel(
            header,
            text="브라우저에서 원하는 웹사이트의 영상을 재생하거나 크롬캐스트로 전송하세요.\n암호화/토큰이 포함된 원본 HLS(.m3u8), DASH(.mpd), MP4 스트림과 인증 헤더가 자동으로 캡처됩니다.",
            font=FONTS["caption"],
            text_color=COLORS["text_muted"],
            justify="left",
            anchor="w"
        )
        lbl_guide.grid(row=1, column=0, sticky="w", pady=(4, 0))

    def _build_control_bar(self, is_running: bool):
        ctrl_frame = ctk.CTkFrame(self, fg_color=COLORS["card_bg"], corner_radius=10)
        ctrl_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=8)
        ctrl_frame.grid_columnconfigure(1, weight=1)

        status_text = "🟢 감지 작동 중 (Chrome/Edge 연동)" if is_running else "⚪ 대기 중 (브라우저 열기 필요)"
        status_color = "#10b981" if is_running else "gray60"

        self.lbl_status = ctk.CTkLabel(
            ctrl_frame,
            text=status_text,
            font=FONTS["body_bold"],
            text_color=status_color
        )
        self.lbl_status.grid(row=0, column=0, padx=15, pady=10, sticky="w")

        btn_container = ctk.CTkFrame(ctrl_frame, fg_color="transparent")
        btn_container.grid(row=0, column=2, padx=10, pady=8, sticky="e")

        self.btn_launch = ctk.CTkButton(
            btn_container,
            text="🚀 브라우저 열기",
            width=120,
            height=34,
            font=FONTS["body_bold"],
            fg_color=COLORS["accent_primary"],
            hover_color=COLORS["accent_hover"],
            command=self._handle_launch
        )
        self.btn_launch.pack(side="left", padx=4)

        self.btn_stop = ctk.CTkButton(
            btn_container,
            text="⏹️ 중지",
            width=70,
            height=34,
            font=FONTS["body"],
            fg_color="gray30",
            hover_color="gray40",
            command=self._handle_stop
        )
        self.btn_stop.pack(side="left", padx=4)

        self.btn_clear = ctk.CTkButton(
            btn_container,
            text="🗑️ 목록 비우기",
            width=90,
            height=34,
            font=FONTS["caption"],
            fg_color="transparent",
            border_width=1,
            border_color="gray40",
            command=self._handle_clear
        )
        self.btn_clear.pack(side="left", padx=4)

    def _build_stream_list(self):
        self.scroll_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll_frame.grid(row=2, column=0, sticky="nsew", padx=20, pady=(0, 15))
        self.scroll_frame.grid_columnconfigure(0, weight=1)

        self.empty_lbl = ctk.CTkLabel(
            self.scroll_frame,
            text="📡 아직 감지된 미디어 스트림이 없습니다.\n\n[🚀 브라우저 열기]를 누른 뒤 웹사이트에서 영상을 재생하거나\n크롬캐스트로 전송해 보세요.",
            font=FONTS["body"],
            text_color=COLORS["text_muted"],
            justify="center"
        )
        self.empty_lbl.pack(pady=80)

    def update_status(self, is_running: bool):
        if is_running:
            self.lbl_status.configure(text="🟢 감지 작동 중 (Chrome/Edge 연동)", text_color="#10b981")
        else:
            self.lbl_status.configure(text="⚪ 대기 중 (브라우저 열기 필요)", text_color="gray60")

    def _handle_launch(self):
        self.on_launch_browser()
        self.update_status(True)

    def _handle_stop(self):
        self.on_stop_sniffer()
        self.update_status(False)

    def _handle_clear(self):
        self.on_clear_streams()
        for w in self.scroll_frame.winfo_children():
            w.destroy()
        self.empty_lbl = ctk.CTkLabel(
            self.scroll_frame,
            text="📡 아직 감지된 미디어 스트림이 없습니다.\n\n[🚀 브라우저 열기]를 누른 뒤 웹사이트에서 영상을 재생해 보세요.",
            font=FONTS["body"],
            text_color=COLORS["text_muted"],
            justify="center"
        )
        self.empty_lbl.pack(pady=80)

    def render_streams(self, streams: List[Dict[str, Any]]):
        for w in self.scroll_frame.winfo_children():
            w.destroy()

        if not streams:
            self.empty_lbl = ctk.CTkLabel(
                self.scroll_frame,
                text="📡 아직 감지된 미디어 스트림이 없습니다.\n\n[🚀 브라우저 열기]를 누른 뒤 웹사이트에서 영상을 재생해 보세요.",
                font=FONTS["body"],
                text_color=COLORS["text_muted"],
                justify="center"
            )
            self.empty_lbl.pack(pady=80)
            return

        for item in reversed(streams):
            self._create_stream_item_card(item)

    def add_single_stream(self, stream_info: Dict[str, Any]):
        if self.empty_lbl and self.empty_lbl.winfo_ismapped():
            self.empty_lbl.pack_forget()
        self._create_stream_item_card(stream_info, pack_top=True)

    def _create_stream_item_card(self, item: Dict[str, Any], pack_top: bool = False):
        card = ctk.CTkFrame(self.scroll_frame, fg_color=COLORS["card_bg"], corner_radius=8)
        if pack_top:
            card.pack(fill="x", expand=True, pady=4, before=self.scroll_frame.winfo_children()[0] if self.scroll_frame.winfo_children() else None)
        else:
            card.pack(fill="x", expand=True, pady=4)

        card.grid_columnconfigure(1, weight=1)

        # Badge Frame
        badge_frame = ctk.CTkFrame(card, fg_color="transparent")
        badge_frame.grid(row=0, column=0, padx=12, pady=10, sticky="nw")

        badge_color = "#3b82f6"
        st = item.get("stream_type", "")
        if "m3u8" in st.lower():
            badge_color = "#ec4899"
        elif "mpd" in st.lower():
            badge_color = "#8b5cf6"
        elif "mp4" in st.lower():
            badge_color = "#10b981"

        badge = ctk.CTkLabel(
            badge_frame,
            text=f" {st} ",
            font=FONTS["caption_bold"],
            text_color="white",
            fg_color=badge_color,
            corner_radius=6
        )
        badge.pack()

        time_lbl = ctk.CTkLabel(
            badge_frame,
            text=item.get("detected_time", ""),
            font=FONTS["caption"],
            text_color=COLORS["text_muted"]
        )
        time_lbl.pack(pady=(4, 0))

        # Info Frame
        info_frame = ctk.CTkFrame(card, fg_color="transparent")
        info_frame.grid(row=0, column=1, padx=6, pady=10, sticky="ew")
        info_frame.grid_columnconfigure(0, weight=1)

        title = item.get("page_title") or "감지된 미디어 스트림"
        lbl_title = ctk.CTkLabel(
            info_frame,
            text=title,
            font=FONTS["body_bold"],
            anchor="w",
            wraplength=400
        )
        lbl_title.grid(row=0, column=0, sticky="w")

        url_str = item.get("url", "")
        url_display = url_str if len(url_str) <= 70 else url_str[:67] + "…"
        lbl_url = ctk.CTkLabel(
            info_frame,
            text=url_display,
            font=FONTS["caption"],
            text_color=COLORS["text_muted"],
            anchor="w"
        )
        lbl_url.grid(row=1, column=0, sticky="w", pady=(2, 0))

        # Add to Queue Button
        btn_add = ctk.CTkButton(
            card,
            text="📥 대기열 추가",
            width=110,
            height=34,
            font=FONTS["body_bold"],
            fg_color=COLORS["accent_primary"],
            hover_color=COLORS["accent_hover"],
            command=lambda: self._on_add_clicked(item, btn_add)
        )
        btn_add.grid(row=0, column=2, padx=12, pady=10, sticky="e")

    def _on_add_clicked(self, item: Dict[str, Any], btn: ctk.CTkButton):
        btn.configure(text="✅ 추가됨", state="disabled", fg_color="gray40")
        self.on_add_stream_to_queue(item)

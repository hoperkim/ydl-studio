"""
URL Input Bar Component with Paste and Quick-Action Buttons.
"""
from typing import Callable, Optional
import customtkinter as ctk
from app.ui.theme import FONTS, COLORS


class UrlInputBar(ctk.CTkFrame):
    """Top bar for URL entry, analysis, clipboard toggle, and settings button."""

    def __init__(
        self,
        master,
        on_analyze: Callable[[str], None],
        on_open_settings: Callable[[], None],
        on_clipboard_toggle: Callable[[bool], None],
        **kwargs
    ):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.on_analyze = on_analyze
        self.on_open_settings = on_open_settings
        self.on_clipboard_toggle = on_clipboard_toggle

        # Grid configuration
        self.grid_columnconfigure(0, weight=1)

        # Input row container
        row_frame = ctk.CTkFrame(self, fg_color=COLORS["card_bg"], corner_radius=10)
        row_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=(5, 5))
        row_frame.grid_columnconfigure(0, weight=1)

        # Entry
        self.entry = ctk.CTkEntry(
            row_frame,
            placeholder_text="다운로드할 유튜브 또는 영상 URL을 입력하세요 (예: https://www.youtube.com/watch?v=...)",
            height=40,
            font=FONTS["body"],
            border_width=0,
            fg_color="transparent",
        )
        self.entry.grid(row=0, column=0, sticky="ew", padx=(15, 10), pady=8)
        self.entry.bind("<Return>", lambda event: self._submit())

        # Paste & Add Button
        self.btn_paste = ctk.CTkButton(
            row_frame,
            text="📋 붙여넣기",
            width=90,
            height=34,
            font=FONTS["caption"],
            fg_color=("gray85", "gray25"),
            hover_color=("gray75", "gray35"),
            text_color=("black", "white"),
            command=self._paste_and_submit
        )
        self.btn_paste.grid(row=0, column=1, padx=(0, 8), pady=8)

        # Analyze & Add Button
        self.btn_analyze = ctk.CTkButton(
            row_frame,
            text="⚡ 영상 추가",
            width=100,
            height=34,
            font=FONTS["body_bold"],
            fg_color=COLORS["accent_primary"],
            hover_color=COLORS["accent_hover"],
            command=self._submit
        )
        self.btn_analyze.grid(row=0, column=2, padx=(0, 10), pady=8)

        # Sub-row for options & settings
        opt_frame = ctk.CTkFrame(self, fg_color="transparent")
        opt_frame.grid(row=1, column=0, sticky="ew", padx=5, pady=(0, 5))
        opt_frame.grid_columnconfigure(1, weight=1)

        # Clipboard auto-detect checkbox
        self.auto_clip_var = ctk.BooleanVar(value=True)
        self.chk_auto_clip = ctk.CTkCheckBox(
            opt_frame,
            text="클립보드 링크 복사 시 자동 감지",
            variable=self.auto_clip_var,
            font=FONTS["caption"],
            checkbox_width=18,
            checkbox_height=18,
            command=self._on_toggle_clip
        )
        self.chk_auto_clip.grid(row=0, column=0, sticky="w", padx=10)

        # Settings button
        self.btn_settings = ctk.CTkButton(
            opt_frame,
            text="⚙️ 환경 설정",
            width=90,
            height=26,
            font=FONTS["caption"],
            fg_color="transparent",
            border_width=1,
            border_color=("gray70", "gray40"),
            text_color=("gray20", "gray80"),
            command=self.on_open_settings
        )
        self.btn_settings.grid(row=0, column=2, sticky="e", padx=5)

    def _submit(self):
        url = self.entry.get().strip()
        if url:
            self.on_analyze(url)
            self.entry.delete(0, "end")

    def _paste_and_submit(self):
        try:
            clipboard_text = self.clipboard_get().strip()
            if clipboard_text:
                self.entry.delete(0, "end")
                self.entry.insert(0, clipboard_text)
                self._submit()
        except Exception:
            pass

    def _on_toggle_clip(self):
        self.on_clipboard_toggle(self.auto_clip_var.get())

    def set_url(self, url: str):
        self.entry.delete(0, "end")
        self.entry.insert(0, url)

"""
Settings Modal Window for YDL Studio.
Configures download path, browser cookies, stream sniffer preferences, and yt-dlp updates.
"""
from typing import Callable, Optional
import customtkinter as ctk
from tkinter import filedialog, messagebox
from app.core.updater import get_current_version, run_update_async
from app.ui.theme import COLORS, FONTS
from app.utils.browser_cookies import get_browser_code_by_label, get_browser_options, get_label_by_code


SNIFFER_BROWSER_OPTIONS = [
    "자동 감지 (Chrome/Edge 우선)",
    "Google Chrome",
    "Microsoft Edge"
]

SNIFFER_CODE_MAP = {
    "자동 감지 (Chrome/Edge 우선)": "auto",
    "Google Chrome": "chrome",
    "Microsoft Edge": "edge"
}

REVERSE_SNIFFER_MAP = {
    "auto": "자동 감지 (Chrome/Edge 우선)",
    "chrome": "Google Chrome",
    "edge": "Microsoft Edge"
}


class SettingsModal(ctk.CTkToplevel):
    """Modern popup dialog for application settings."""

    def __init__(
        self,
        master,
        current_save_dir: str,
        current_browser_cookie: Optional[str],
        current_preferred_browser: str = "auto",
        on_save: Optional[Callable[[str, Optional[str], str], None]] = None,
        **kwargs
    ):
        super().__init__(master, **kwargs)
        self.title("YDL Studio 환경 설정")
        self.geometry("580x560")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        self.on_save = on_save
        self.save_dir = current_save_dir
        self.browser_cookie = current_browser_cookie
        self.preferred_browser = current_preferred_browser

        self._build_ui()

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)

        # 1. Download Path Section
        path_frame = ctk.CTkFrame(self, fg_color=COLORS["card_bg"], corner_radius=10)
        path_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=(15, 8))
        path_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            path_frame,
            text="📁 기본 다운로드 위치",
            font=FONTS["header"],
            anchor="w"
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=15, pady=(10, 4))

        self.path_entry = ctk.CTkEntry(
            path_frame,
            height=36,
            font=FONTS["body"]
        )
        self.path_entry.insert(0, self.save_dir)
        self.path_entry.grid(row=1, column=0, sticky="ew", padx=(15, 8), pady=(0, 10))

        ctk.CTkButton(
            path_frame,
            text="찾아보기",
            width=90,
            height=36,
            font=FONTS["body"],
            command=self._browse_path
        ).grid(row=1, column=1, padx=(0, 15), pady=(0, 10))

        # 2. Browser Cookie Section
        cookie_frame = ctk.CTkFrame(self, fg_color=COLORS["card_bg"], corner_radius=10)
        cookie_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=8)
        cookie_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            cookie_frame,
            text="🍪 브라우저 쿠키 연동 (봇 차단/연령 제한 우회)",
            font=FONTS["header"],
            anchor="w"
        ).grid(row=0, column=0, sticky="w", padx=15, pady=(10, 2))

        ctk.CTkLabel(
            cookie_frame,
            text="자주 사용하는 브라우저를 선택하면 로그인 세션을 활용해 유튜브 봇 감지를 우회합니다.",
            font=FONTS["caption"],
            text_color=COLORS["text_muted"],
            justify="left",
            anchor="w"
        ).grid(row=1, column=0, sticky="w", padx=15, pady=(0, 6))

        browser_opts = get_browser_options()
        init_label = get_label_by_code(self.browser_cookie)
        self.browser_var = ctk.StringVar(value=init_label)
        self.opt_browser = ctk.CTkOptionMenu(
            cookie_frame,
            values=browser_opts,
            variable=self.browser_var,
            width=220,
            height=34,
            font=FONTS["body"],
            dropdown_font=FONTS["body"],
        )
        self.opt_browser.grid(row=2, column=0, sticky="w", padx=15, pady=(0, 10))

        # 3. Stream Sniffer Browser Preference
        sniffer_frame = ctk.CTkFrame(self, fg_color=COLORS["card_bg"], corner_radius=10)
        sniffer_frame.grid(row=2, column=0, sticky="ew", padx=20, pady=8)
        sniffer_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            sniffer_frame,
            text="🌐 실시간 스트림 감지기 브라우저 선택",
            font=FONTS["header"],
            anchor="w"
        ).grid(row=0, column=0, sticky="w", padx=15, pady=(10, 2))

        ctk.CTkLabel(
            sniffer_frame,
            text="[🌐 브라우저 감지기] 실행 시 우선적으로 띄울 웹 브라우저를 지정합니다.",
            font=FONTS["caption"],
            text_color=COLORS["text_muted"],
            justify="left",
            anchor="w"
        ).grid(row=1, column=0, sticky="w", padx=15, pady=(0, 6))

        init_sniffer_label = REVERSE_SNIFFER_MAP.get(self.preferred_browser, SNIFFER_BROWSER_OPTIONS[0])
        self.sniffer_var = ctk.StringVar(value=init_sniffer_label)
        self.opt_sniffer_browser = ctk.CTkOptionMenu(
            sniffer_frame,
            values=SNIFFER_BROWSER_OPTIONS,
            variable=self.sniffer_var,
            width=240,
            height=34,
            font=FONTS["body"],
            dropdown_font=FONTS["body"],
        )
        self.opt_sniffer_browser.grid(row=2, column=0, sticky="w", padx=15, pady=(0, 10))

        # 4. Engine Update Section
        engine_frame = ctk.CTkFrame(self, fg_color=COLORS["card_bg"], corner_radius=10)
        engine_frame.grid(row=3, column=0, sticky="ew", padx=20, pady=8)
        engine_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            engine_frame,
            text="⚡ yt-dlp 다운로드 엔진 관리",
            font=FONTS["header"],
            anchor="w"
        ).grid(row=0, column=0, sticky="w", padx=15, pady=(10, 2))

        curr_ver = get_current_version()
        self.lbl_engine_status = ctk.CTkLabel(
            engine_frame,
            text=f"현재 설치된 엔진 버전: v{curr_ver}",
            font=FONTS["caption"],
            text_color=COLORS["text_muted"],
            anchor="w"
        )
        self.lbl_engine_status.grid(row=1, column=0, sticky="w", padx=15, pady=(0, 6))

        self.btn_update_engine = ctk.CTkButton(
            engine_frame,
            text="엔진 최신 버전으로 업데이트",
            height=34,
            font=FONTS["body"],
            fg_color=("gray75", "gray30"),
            hover_color=("gray65", "gray40"),
            text_color=("black", "white"),
            command=self._update_engine
        )
        self.btn_update_engine.grid(row=2, column=0, sticky="w", padx=15, pady=(0, 10))

        # Bottom Button
        btn_box = ctk.CTkFrame(self, fg_color="transparent")
        btn_box.grid(row=4, column=0, sticky="ew", padx=20, pady=(10, 10))
        btn_box.grid_columnconfigure(0, weight=1)

        ctk.CTkButton(
            btn_box,
            text="확인 및 저장",
            width=130,
            height=38,
            font=FONTS["body_bold"],
            fg_color=COLORS["accent_primary"],
            hover_color=COLORS["accent_hover"],
            command=self._save_and_close
        ).grid(row=0, column=1, sticky="e")

    def _browse_path(self):
        folder = filedialog.askdirectory(initialdir=self.path_entry.get())
        if folder:
            self.path_entry.delete(0, "end")
            self.path_entry.insert(0, folder)

    def _update_engine(self):
        self.btn_update_engine.configure(state="disabled", text="업데이트 확인 및 설치 중…")
        self.lbl_engine_status.configure(text="최신 yt-dlp 패키지 확인 중…")

        def _on_done(success: bool, msg: str):
            def _ui():
                self.btn_update_engine.configure(state="normal", text="엔진 최신 버전으로 업데이트")
                curr = get_current_version()
                self.lbl_engine_status.configure(text=f"현재 엔진 버전: v{curr}")
                if success:
                    messagebox.showinfo("업데이트 성공", msg)
                else:
                    messagebox.showerror("업데이트 오류", msg)
            self.after(0, _ui)

        run_update_async(on_complete=_on_done)

    def _save_and_close(self):
        new_dir = self.path_entry.get().strip()
        selected_browser_label = self.browser_var.get()
        browser_code = get_browser_code_by_label(selected_browser_label)
        sniffer_code = SNIFFER_CODE_MAP.get(self.sniffer_var.get(), "auto")

        if self.on_save:
            self.on_save(new_dir, browser_code, sniffer_code)
        self.destroy()

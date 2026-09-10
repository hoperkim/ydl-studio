"""
Settings Modal Window for YDL Studio.
Configures download path, browser cookies, themes, and yt-dlp updates.
"""
from typing import Callable, Optional
import customtkinter as ctk
from tkinter import filedialog, messagebox
from app.core.updater import get_current_version, run_update_async
from app.ui.theme import COLORS, FONTS
from app.utils.browser_cookies import get_browser_code_by_label, get_browser_options, get_label_by_code


class SettingsModal(ctk.CTkToplevel):
    """Modern popup dialog for application settings."""

    def __init__(
        self,
        master,
        current_save_dir: str,
        current_browser_cookie: Optional[str],
        on_save: Callable[[str, Optional[str]], None],
        **kwargs
    ):
        super().__init__(master, **kwargs)
        self.title("YDL Studio 환경 설정")
        self.geometry("520x450")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        self.on_save = on_save
        self.save_dir = current_save_dir
        self.browser_cookie = current_browser_cookie

        self._build_ui()

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)

        # 1. Download Path Section
        path_frame = ctk.CTkFrame(self, fg_color=COLORS["card_bg"], corner_radius=10)
        path_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 10))
        path_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            path_frame,
            text="📁 기본 다운로드 위치",
            font=FONTS["header"],
            anchor="w"
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=15, pady=(12, 6))

        self.path_entry = ctk.CTkEntry(
            path_frame,
            height=32,
            font=FONTS["caption"]
        )
        self.path_entry.insert(0, self.save_dir)
        self.path_entry.grid(row=1, column=0, sticky="ew", padx=(15, 8), pady=(0, 12))

        ctk.CTkButton(
            path_frame,
            text="찾아보기",
            width=80,
            height=32,
            font=FONTS["caption"],
            command=self._browse_path
        ).grid(row=1, column=1, padx=(0, 15), pady=(0, 12))

        # 2. Browser Cookie Section
        cookie_frame = ctk.CTkFrame(self, fg_color=COLORS["card_bg"], corner_radius=10)
        cookie_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=10)
        cookie_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            cookie_frame,
            text="🍪 브라우저 쿠키 연동 (봇 차단/연령 제한 우회)",
            font=FONTS["header"],
            anchor="w"
        ).grid(row=0, column=0, sticky="w", padx=15, pady=(12, 4))

        ctk.CTkLabel(
            cookie_frame,
            text="자주 사용하는 브라우저를 선택하면 해당 브라우저의 로그인 세션을 활용해\n유튜브 차단(봇 감지 및 1080p 이상 제한)을 완벽하게 우회합니다.",
            font=FONTS["caption"],
            text_color=COLORS["text_muted"],
            justify="left",
            anchor="w"
        ).grid(row=1, column=0, sticky="w", padx=15, pady=(0, 8))

        browser_opts = get_browser_options()
        init_label = get_label_by_code(self.browser_cookie)
        self.browser_var = ctk.StringVar(value=init_label)
        self.opt_browser = ctk.CTkOptionMenu(
            cookie_frame,
            values=browser_opts,
            variable=self.browser_var,
            width=200,
            height=32,
            font=FONTS["body"],
        )
        self.opt_browser.grid(row=2, column=0, sticky="w", padx=15, pady=(0, 12))

        # 3. Engine Update Section
        engine_frame = ctk.CTkFrame(self, fg_color=COLORS["card_bg"], corner_radius=10)
        engine_frame.grid(row=2, column=0, sticky="ew", padx=20, pady=10)
        engine_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            engine_frame,
            text="⚡ yt-dlp 다운로드 엔진 관리",
            font=FONTS["header"],
            anchor="w"
        ).grid(row=0, column=0, sticky="w", padx=15, pady=(12, 4))

        curr_ver = get_current_version()
        self.lbl_engine_status = ctk.CTkLabel(
            engine_frame,
            text=f"현재 설치된 엔진 버전: v{curr_ver}",
            font=FONTS["caption"],
            text_color=COLORS["text_muted"],
            anchor="w"
        )
        self.lbl_engine_status.grid(row=1, column=0, sticky="w", padx=15, pady=(0, 8))

        self.btn_update_engine = ctk.CTkButton(
            engine_frame,
            text="엔진 최신 버전으로 업데이트",
            height=30,
            font=FONTS["caption"],
            fg_color=("gray75", "gray30"),
            hover_color=("gray65", "gray40"),
            text_color=("black", "white"),
            command=self._update_engine
        )
        self.btn_update_engine.grid(row=2, column=0, sticky="w", padx=15, pady=(0, 12))

        # Bottom Button
        btn_box = ctk.CTkFrame(self, fg_color="transparent")
        btn_box.grid(row=3, column=0, sticky="ew", padx=20, pady=(15, 10))
        btn_box.grid_columnconfigure(0, weight=1)

        ctk.CTkButton(
            btn_box,
            text="확인 및 저장",
            width=120,
            height=36,
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
        self.on_save(new_dir, browser_code)
        self.destroy()

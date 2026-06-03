# -*- coding: utf-8 -*-
import os
import sys

# Force Python to use UTF-8 for all I/O (fixes Vietnamese mojibake on cp1252 Windows)
os.environ["PYTHONUTF8"] = "1"
os.environ["PYTHONIOENCODING"] = "utf-8"

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
import json
import subprocess
import tempfile
import random
from datetime import datetime

# Đảm bảo thư mục làm việc luôn là thư mục chứa gui.py (cần thiết khi double-click)
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(_BASE_DIR)
if _BASE_DIR not in sys.path:
    sys.path.insert(0, _BASE_DIR)

from database import Database
from gemlogin_api import GemLoginAPI
from gpmlogin_api import GPMLoginAPI
from facebook_automator import FacebookAutomator
import time
import webbrowser
import psutil

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Công Cụ Đăng Reels Tự Động - Phiên bản v1.0.0 (GPM/GemLogin)")
        self.geometry("1100x700")
        self.minsize(900, 600)

        self.db = Database()
        self.automator = None
        self.stop_flag = False
        self.active_procs = [] # Track worker subprocesses

        # Background caching structures for smooth non-blocking UI
        self._profile_cache = {}
        self.card_widgets = []
        self.card_comboboxes = {}
        
        self._resize_after_id = None
        self._canvas_resize_after_id = None
        self._search_after_id = None

        # Shopee mode state (loaded from DB, synced on change)
        self.shopee_mode_var = tk.BooleanVar(value=self.db.get_shopee_mode())
        self.shopee_file_path = tk.StringVar(value=self.db.get_shopee_file())

        self._build_ui()
        self.refresh_ui()

        # Hook close event
        self.protocol("WM_DELETE_WINDOW", self.on_app_exit)

    def _build_ui(self):
        # ─── TOP TOOLBAR ──────────────────────────────────────
        self.toolbar = tk.Frame(self, bg="#f8f9fa", relief="raised", bd=1, pady=5)
        self.toolbar.pack(side="top", fill="x")

        # Group 1: Page Management
        mgmt_frame = tk.LabelFrame(self.toolbar, text="Quản Lý Fanpage", bg="#f8f9fa", font=("Arial", 9, "bold"))
        mgmt_frame.pack(side="left", padx=5, pady=2)

        btn_opts = dict(cursor="hand2", padx=10, pady=5, font=("Arial", 9))

        btn_add_page = tk.Button(mgmt_frame, text="+ Thêm Page", command=self.add_fanpage_ui, **btn_opts)
        btn_add_page.pack(side="left", padx=2)
        self.style_button(btn_add_page, "#1a73e8", "#1557b0")

        btn_clear_all = tk.Button(mgmt_frame, text="🗑️ Xóa Hết", command=self.clear_all_ui, **btn_opts)
        btn_clear_all.pack(side="left", padx=2)
        self.style_button(btn_clear_all, "#ea4335", "#c5221f")

        btn_groups = tk.Button(mgmt_frame, text="👥 Nhóm", command=self.group_management_ui, **btn_opts)
        btn_groups.pack(side="left", padx=2)
        self.style_button(btn_groups, "#1a73e8", "#1557b0")

        btn_auto_folder = tk.Button(mgmt_frame, text="🪄 Auto Folder", command=self.auto_map_folders_ui, **btn_opts)
        btn_auto_folder.pack(side="left", padx=2)
        self.style_button(btn_auto_folder, "#2e7d32", "#225c25")

        # Group 2: Settings & Global Actions
        settings_frame = tk.LabelFrame(self.toolbar, text="Cài Đặt Tổng", bg="#f8f9fa", font=("Arial", 9, "bold"))
        settings_frame.pack(side="left", padx=5, pady=2)

        btn_comment = tk.Button(settings_frame, text="💬 Bình Luận", command=self.set_comment_ui, **btn_opts)
        btn_comment.pack(side="left", padx=2)
        self.style_button(btn_comment, "#7c5cbf", "#6242a3")

        btn_sched = tk.Button(settings_frame, text="📅 Lịch Chạy", command=self.scheduling_settings_ui, **btn_opts)
        btn_sched.pack(side="left", padx=2)
        self.style_button(btn_sched, "#e07b39", "#be5f23")

        btn_profile = tk.Button(settings_frame, text="🌐 Profile", command=self.browser_settings_ui, **btn_opts)
        btn_profile.pack(side="left", padx=2)
        self.style_button(btn_profile, "#e67e22", "#c66c1b")

        btn_stats = tk.Button(settings_frame, text="📊 Log/Thống Kê", command=self.show_video_log_ui, **btn_opts)
        btn_stats.pack(side="left", padx=2)
        self.style_button(btn_stats, "#3a9a5c", "#2d7647")

        btn_done = tk.Button(settings_frame, text="⚠️ Lỗi Done", command=self.show_done_errors_ui, **btn_opts)
        btn_done.pack(side="left", padx=2)
        self.style_button(btn_done, "#c0392b", "#a93226")

        # Selection Control (inside settings frame)
        sel_frame = tk.Frame(settings_frame, bg="#f8f9fa")
        sel_frame.pack(side="left", padx=5)
        
        sel_opts = dict(cursor="hand2", padx=5, pady=2, font=("Arial", 8))
        
        btn_sel_all = tk.Button(sel_frame, text="Chọn Hết", command=lambda: self.set_all_enabled(True), **sel_opts)
        btn_sel_all.pack(pady=1)
        self.style_button(btn_sel_all, "#3a9a5c", "#2d7647")

        btn_sel_none = tk.Button(sel_frame, text="Bỏ Chọn", command=lambda: self.set_all_enabled(False), **sel_opts)
        btn_sel_none.pack(pady=1)
        self.style_button(btn_sel_none, "#5f6368", "#474a4d")

        btn_bulk = tk.Button(sel_frame, text="Gán Profile", command=self.bulk_assign_ui, **sel_opts)
        btn_bulk.pack(pady=1)
        self.style_button(btn_bulk, "#e07b39", "#be5f23")

        # Group 3: Execution Control
        exec_frame = tk.LabelFrame(self.toolbar, text="Điều Khiển Chạy", bg="#f8f9fa", font=("Arial", 9, "bold"))
        exec_frame.pack(side="left", padx=5, pady=2)

        # Mode Selection
        self.run_mode_var = tk.StringVar()
        mode_map = {"post_and_comment": "Đăng + Comment", "post_only": "Chỉ Đăng", "comment_only": "Chỉ Comment"}
        self.run_mode_var.set(mode_map.get(self.db.get_run_mode(), "Đăng + Comment"))
        
        mode_combo = ttk.Combobox(exec_frame, textvariable=self.run_mode_var,
                                   values=["Đăng + Comment", "Chỉ Đăng", "Chỉ Comment"],
                                   state="readonly", width=15)
        mode_combo.pack(side="left", padx=5)
        mode_combo.bind("<<ComboboxSelected>>", self._on_mode_change)
        self._disable_combo_scroll(mode_combo, redirect_to_canvas=False)

        self.btn_start = tk.Button(exec_frame, text="▶ BẮT ĐẦU", command=self.start_posting, font=("Arial", 10, "bold"), padx=15, pady=4)
        self.btn_start.pack(side="left", padx=5)
        self.style_button(self.btn_start, "#3a9a5c", "#2d7647")
        
        self.btn_stop = tk.Button(exec_frame, text="■ DỪNG", command=self.stop_posting, state="disabled", font=("Arial", 10, "bold"), padx=15, pady=4)
        self.btn_stop.pack(side="left", padx=5)
        self.style_button(self.btn_stop, "#c0392b", "#a93226")

        # Group 4: Options
        opts_frame = tk.LabelFrame(self.toolbar, text="Tùy Chọn", bg="#f8f9fa", font=("Arial", 9, "bold"))
        opts_frame.pack(side="left", padx=5, pady=2)

        self.skip_commented_var = tk.BooleanVar(value=self.db.get_skip_commented())
        tk.Checkbutton(opts_frame, text="Bỏ qua bài cũ", variable=self.skip_commented_var,
                       bg="#f8f9fa", command=lambda: self.db.set_skip_commented(self.skip_commented_var.get())).pack(anchor="w")
        
        self.auto_delete_var = tk.BooleanVar(value=self.db.get_auto_delete_videos())
        tk.Checkbutton(opts_frame, text="Tự xóa video", variable=self.auto_delete_var,
                       bg="#f8f9fa", command=self.toggle_auto_delete).pack(anchor="w")

        # Group 5: Search
        search_frame = tk.LabelFrame(self.toolbar, text="Tìm Kiếm Fanpage", bg="#f8f9fa", font=("Arial", 9, "bold"))
        search_frame.pack(side="left", padx=5, pady=2)

        self.search_var = tk.StringVar()
        search_ent = tk.Entry(search_frame, textvariable=self.search_var, font=("Arial", 10), width=18, bd=1, relief="solid")
        search_ent.pack(side="left", padx=5, pady=3)

        def clear_search():
            self.search_var.set("")
            self.filter_cards("")

        btn_clear_search = tk.Button(search_frame, text="✖", command=clear_search, font=("Arial", 9, "bold"), padx=5)
        btn_clear_search.pack(side="left", padx=(0, 5))
        self.style_button(btn_clear_search, "#5f6368", "#474a4d")

        def on_search_change(*args):
            if hasattr(self, '_search_after_id') and self._search_after_id:
                self.after_cancel(self._search_after_id)
            try:
                self._search_after_id = self.after(150, lambda: self.filter_cards(self.search_var.get()) if self.winfo_exists() else None)
            except Exception:
                pass

        self.search_var.trace_add("write", on_search_change)

        # Group 6: Shopee Mode
        shopee_frame = tk.LabelFrame(self.toolbar, text="Rải Link Shopee", bg="#f8f9fa",
                                      font=("Arial", 9, "bold"), fg="#e07b39")
        shopee_frame.pack(side="left", padx=5, pady=2)

        def on_shopee_toggle():
            self.db.set_shopee_mode(self.shopee_mode_var.get())
            state = "BẬT" if self.shopee_mode_var.get() else "TẮT"
            self.log(f"Chế độ Rải Link Shopee: {state}")
            self._update_shopee_ui_state()

        self.chk_shopee = tk.Checkbutton(
            shopee_frame, text="Bật Rải Link Shopee",
            variable=self.shopee_mode_var, bg="#f8f9fa",
            font=("Arial", 9, "bold"), fg="#e07b39", selectcolor="#fff8f0",
            command=on_shopee_toggle, cursor="hand2")
        self.chk_shopee.pack(anchor="w", padx=5)

        # Row for Shopee Groups selection
        shopee_group_row = tk.Frame(shopee_frame, bg="#f8f9fa")
        shopee_group_row.pack(fill="x", padx=5, pady=(0, 3))
        
        tk.Label(shopee_group_row, text="Nhóm áp dụng:", bg="#f8f9fa", font=("Arial", 8, "bold")).pack(side="left")
        
        self.shopee_all_groups_var = tk.BooleanVar(value=self.db.get_shopee_all_groups())
        self.shopee_group_vars = {}
        
        self.btn_shopee_groups = tk.Menubutton(
            shopee_group_row, text="Đang tải...",
            relief="raised", bd=1, bg="#ffffff", cursor="hand2", font=("Arial", 8)
        )
        self.btn_shopee_groups.pack(side="left", padx=5)
        
        self.shopee_group_menu = tk.Menu(
            self.btn_shopee_groups, tearoff=0,
            postcommand=self.rebuild_shopee_group_menu
        )
        self.btn_shopee_groups["menu"] = self.shopee_group_menu
        
        # Initialize button text
        self.update_shopee_groups_button_text()

        shopee_file_row = tk.Frame(shopee_frame, bg="#f8f9fa")
        shopee_file_row.pack(fill="x", padx=5, pady=(0, 3))

        self.lbl_shopee_file = tk.Label(
            shopee_file_row, textvariable=self.shopee_file_path,
            bg="#f8f9fa", font=("Arial", 8), fg="#555", width=22,
            anchor="w", wraplength=160)
        self.lbl_shopee_file.pack(side="left")

        def pick_shopee_file():
            path = filedialog.askopenfilename(
                title="Chọn file danh sách sản phẩm Shopee",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
            if path:
                self.shopee_file_path.set(path)
                self.db.set_shopee_file(path)
                self.log(f"Đã chọn file Shopee: {path}")

        def open_shopee_file():
            fp = self.shopee_file_path.get()
            if fp and os.path.exists(fp):
                os.startfile(fp)
            elif fp:
                messagebox.showwarning("Không tìm thấy", f"File không tồn tại:\n{fp}")
            else:
                messagebox.showinfo("Chưa chọn file", "Bạn chưa chọn file Shopee nào.")

        btn_pick_shopee = tk.Button(shopee_file_row, text="📂 Chọn File",
                                    command=pick_shopee_file, padx=5, pady=2,
                                    cursor="hand2", font=("Arial", 8))
        btn_pick_shopee.pack(side="left", padx=(3, 1))
        self.style_button(btn_pick_shopee, "#e07b39", "#be5f23")

        btn_open_shopee = tk.Button(shopee_file_row, text="✏️",
                                    command=open_shopee_file, padx=4, pady=2,
                                    cursor="hand2", font=("Arial", 8))
        btn_open_shopee.pack(side="left", padx=(1, 3))
        self.style_button(btn_open_shopee, "#5f6368", "#474a4d")

        # Store references for state management
        self._shopee_file_btn = btn_pick_shopee
        self._shopee_open_btn = btn_open_shopee
        self._shopee_file_row = shopee_file_row
        self._update_shopee_ui_state()

        # ── MAIN CONTENT ─────────────────────────────────────
        self.paned_window = tk.PanedWindow(self, orient=tk.HORIZONTAL, sashwidth=5, sashrelief=tk.RAISED, bg="#d9d9d9")
        self.paned_window.pack(fill="both", expand=True)

        # Main Scrollable list for Fanpages (in left pane)
        list_container = tk.Frame(self.paned_window, bg="#ffffff")
        self.paned_window.add(list_container, stretch="always")

        self.canvas = tk.Canvas(list_container, bg="#ffffff", highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(list_container, orient="vertical", command=self.canvas.yview)

        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        # Log box (in right pane)
        log_container = tk.Frame(self.paned_window, bg="#f0f0f0", width=300)
        log_container.pack_propagate(False)
        self.paned_window.add(log_container, minsize=200)

        self.log_text = scrolledtext.ScrolledText(log_container, font=("Consolas", 9), state="normal", wrap="word")
        self.log_text.pack(fill="both", expand=True, padx=5, pady=5)

        # Single main_frame inside canvas
        self.main_frame = tk.Frame(self.canvas, bg="#e8e8e8")
        self.canvas_window = self.canvas.create_window((0, 0), window=self.main_frame, anchor="nw")

        # --- Global Folders Section ---
        self.global_folders_frame = tk.LabelFrame(self.main_frame, text=" 📂 Thư Mục Video Dùng Chung (Tất cả Fanpage) ",
                                                 font=("Arial", 11, "bold"), bg="#ffffff", relief="groove", bd=2)
        self.global_folders_frame.pack(fill="x", padx=10, pady=10)
        
        self.global_list_frame = tk.Frame(self.global_folders_frame, bg="#ffffff")
        self.global_list_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        tk.Button(self.global_folders_frame, text="+ Thêm Thư Mục Chung",
                                    bg="#4a90d9", fg="white", relief="flat", padx=10,
                                    command=self.add_global_folder_ui).pack(pady=5)
        
        # --- Global Video Limits ---
        limit_frame = tk.Frame(self.global_folders_frame, bg="#ffffff")
        limit_frame.pack(fill="x", padx=10, pady=5)
        
        tk.Label(limit_frame, text="Số video mỗi lần chạy (áp dụng tất cả Fanpage):", 
                 bg="#ffffff", font=("Arial", 9, "bold")).pack(side="left")
        
        g_min, g_max = self.db.get_global_video_limits()
        
        self.global_min_entry = tk.Entry(limit_frame, width=5, bd=1, relief="solid")
        self.global_min_entry.insert(0, str(g_min))
        self.global_min_entry.pack(side="left", padx=(10, 2))
        
        tk.Label(limit_frame, text="-", bg="#ffffff").pack(side="left")
        
        self.global_max_entry = tk.Entry(limit_frame, width=5, bd=1, relief="solid")
        self.global_max_entry.insert(0, str(g_max))
        self.global_max_entry.pack(side="left", padx=(2, 10))
        
        def save_global_limits(event=None):
            try:
                vmin = int(self.global_min_entry.get())
                vmax = int(self.global_max_entry.get())
                if vmin > 0 and vmax >= vmin:
                    self.db.set_global_video_limits(vmin, vmax)
            except: pass
            
        self.global_min_entry.bind("<FocusOut>", save_global_limits)
        self.global_max_entry.bind("<FocusOut>", save_global_limits)

        self._refresh_global_folders_ui()

        self.main_frame.bind("<Configure>", self._on_frame_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        # Bind mousewheel only on the canvas widget itself, not all children
        self.canvas.bind("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind("<Enter>", lambda e: self.canvas.bind_all("<MouseWheel>", self._on_mousewheel))
        self.canvas.bind("<Leave>", lambda e: self.canvas.unbind_all("<MouseWheel>"))

    # Debounce timer for resize events
    _resize_after_id = None

    def _on_frame_configure(self, event):
        # Debounce: only update scrollregion after resize settles (50ms)
        if self._resize_after_id:
            self.after_cancel(self._resize_after_id)
        self._resize_after_id = self.after(50, lambda: self.canvas.configure(
            scrollregion=self.canvas.bbox("all")) if self.canvas.winfo_exists() else None)

    def _on_canvas_configure(self, event):
        if self._canvas_resize_after_id:
            self.after_cancel(self._canvas_resize_after_id)
        self._canvas_resize_after_id = self.after(50, lambda w=event.width: self.canvas.itemconfig(self.canvas_window, width=w) if self.canvas.winfo_exists() else None)

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _disable_combo_scroll(self, combo, redirect_to_canvas=True):
        """Disable changing combobox value via mouse wheel when dropdown is closed."""
        def handle_mousewheel(event):
            if redirect_to_canvas and hasattr(self, 'canvas') and self.canvas.winfo_exists():
                self._on_mousewheel(event)
            return "break"
        combo.bind("<MouseWheel>", handle_mousewheel)

    def _on_mode_change(self, event=None):
        map_mode = {"Đăng + Comment": "post_and_comment",
                    "Chỉ Đăng": "post_only",
                    "Chỉ Comment": "comment_only"}
        choice = self.run_mode_var.get()
        self.db.set_run_mode(map_mode.get(choice, "post_and_comment"))
        self.log(f"Đã chọn chế độ: {choice}")

    def style_button(self, btn, bg_color, active_color, fg_color="white", disabled_fg="#a0a0a0"):
        btn.configure(bg=bg_color, fg=fg_color, activebackground=active_color, activeforeground=fg_color,
                      disabledforeground=disabled_fg, relief="flat")
        def on_enter(e):
            try:
                if btn.cget("state") != "disabled":
                    btn.configure(bg=active_color)
            except Exception: pass
        def on_leave(e):
            try:
                if btn.cget("state") != "disabled":
                    btn.configure(bg=bg_color)
            except Exception: pass
        btn.bind("<Enter>", on_enter)
        btn.bind("<Leave>", on_leave)

    def _update_shopee_ui_state(self):
        """Dim/enable the file-picker and group-picker based on shopee checkbox state."""
        try:
            enabled = self.shopee_mode_var.get()
            state = "normal" if enabled else "disabled"
            fg = "#333" if enabled else "#aaa"
            self._shopee_file_btn.configure(state=state)
            self._shopee_open_btn.configure(state=state)
            self.lbl_shopee_file.configure(fg=fg if enabled else "#aaa")
            if hasattr(self, 'btn_shopee_groups') and self.btn_shopee_groups.winfo_exists():
                self.btn_shopee_groups.configure(state=state)
        except Exception:
            pass

    def update_shopee_groups_button_text(self):
        groups = self.db.get_groups()
        if not groups:
            self.btn_shopee_groups.configure(text="Không có nhóm ▼")
            return
            
        all_groups = self.shopee_all_groups_var.get()
        if all_groups:
            self.btn_shopee_groups.configure(text="Tất cả nhóm ▼")
        else:
            checked_groups = [g for g in groups if self.shopee_group_vars.get(g['id']) and self.shopee_group_vars[g['id']].get()]
            self.btn_shopee_groups.configure(text=f"Đã chọn {len(checked_groups)} nhóm ▼")

    def rebuild_shopee_group_menu(self):
        self.shopee_group_menu.delete(0, "end")
        groups = self.db.get_groups()
        
        if not groups:
            self.shopee_group_menu.add_command(label="(Chưa có nhóm nào)", state="disabled")
            self.shopee_all_groups_var.set(True)
            self.db.set_shopee_all_groups(True)
            self.db.set_shopee_groups([])
            self.update_shopee_groups_button_text()
            return

        db_all = self.db.get_shopee_all_groups()
        db_selected = self.db.get_shopee_groups()
        
        self.shopee_all_groups_var.set(db_all)
        
        for g in groups:
            g_id = g['id']
            if g_id not in self.shopee_group_vars:
                val = db_all or (g_id in db_selected)
                self.shopee_group_vars[g_id] = tk.BooleanVar(value=val)
            else:
                val = db_all or (g_id in db_selected)
                self.shopee_group_vars[g_id].set(val)

        self.shopee_group_menu.add_checkbutton(
            label="Áp dụng tất cả group fanpage",
            variable=self.shopee_all_groups_var,
            command=lambda: self.on_shopee_group_toggled("all")
        )
        
        self.shopee_group_menu.add_separator()
        
        for g in groups:
            g_id = g['id']
            g_name = g['name']
            self.shopee_group_menu.add_checkbutton(
                label=g_name,
                variable=self.shopee_group_vars[g_id],
                command=lambda gid=g_id: self.on_shopee_group_toggled(gid)
            )

    def on_shopee_group_toggled(self, target):
        groups = self.db.get_groups()
        if not groups:
            self.shopee_all_groups_var.set(True)
            self.db.set_shopee_all_groups(True)
            self.db.set_shopee_groups([])
            self.update_shopee_groups_button_text()
            return
            
        all_checked = self.shopee_all_groups_var.get()
        
        if target == "all":
            if all_checked:
                for g in groups:
                    g_id = g['id']
                    if g_id in self.shopee_group_vars:
                        self.shopee_group_vars[g_id].set(True)
            else:
                # If unchecked "Apply all", keep all group checkboxes checked, 
                # so the user can then start deselecting individual ones.
                for g in groups:
                    g_id = g['id']
                    if g_id in self.shopee_group_vars:
                        self.shopee_group_vars[g_id].set(True)
        else:
            checked_count = sum(1 for g in groups if self.shopee_group_vars.get(g['id']) and self.shopee_group_vars[g['id']].get())
            
            if checked_count == 0:
                # Revert unchecking because absolutely at least one must be checked!
                if target in self.shopee_group_vars:
                    self.shopee_group_vars[target].set(True)
                messagebox.showwarning("Cảnh báo", "Bạn phải chọn ít nhất 1 nhóm hoặc áp dụng tất cả!")
            else:
                if checked_count == len(groups):
                    self.shopee_all_groups_var.set(True)
                else:
                    self.shopee_all_groups_var.set(False)
                    
        db_all = self.shopee_all_groups_var.get()
        self.db.set_shopee_all_groups(db_all)
        
        db_selected = []
        if not db_all:
            db_selected = [g['id'] for g in groups if self.shopee_group_vars.get(g['id']) and self.shopee_group_vars[g['id']].get()]
        else:
            db_selected = [g['id'] for g in groups]
            
        self.db.set_shopee_groups(db_selected)
        self.update_shopee_groups_button_text()

    @staticmethod
    def parse_shopee_file(filepath):
        """
        Parse a shopee .txt file.
        Format per line:  stt|tên sản phẩm|url
        Returns list of dicts: [{'stt': int, 'name': str, 'url': str}, ...]
        """
        products = []
        if not filepath or not os.path.exists(filepath):
            return products
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    parts = line.split('|')
                    if len(parts) >= 3:
                        try:
                            stt = int(parts[0].strip())
                        except ValueError:
                            continue
                        name = parts[1].strip()
                        url = parts[2].strip()
                        if name and url:
                            products.append({'stt': stt, 'name': name, 'url': url})
        except Exception:
            pass
        return products

    def refresh_ui(self):
        if threading.current_thread() != threading.main_thread():
            try:
                self.after(0, self.refresh_ui)
            except Exception:
                pass
            return

        # Tạm thời gỡ main_frame khỏi canvas để tránh vẽ/reflow trung gian cho từng card
        self.canvas.itemconfig(self.canvas_window, window="")

        # Clear existing cards (keep global_folders_frame)
        for widget in self.main_frame.winfo_children():
            if widget != self.global_folders_frame:
                widget.destroy()

        # Only refresh global folders UI if it's the first build
        # (avoid destroying/rebuilding on every refresh_ui call)
        if not hasattr(self, '_global_folders_built'):
            self._refresh_global_folders_ui()
            self._global_folders_built = True

        self.card_widgets = []
        self.card_comboboxes = {}
        self.card_enabled_vars = {}
        self.cards_info = []

        fanpages = self.db.get_fanpages()

        # ── Pre-fetch ALL expensive data ONCE before building cards ──────────
        # Prevents N×db.get_groups() + N×os.listdir() calls on main thread
        groups_cache = self.db.get_groups()

        # Collect all unique folder paths across all pages, count videos once
        all_folders = set()
        for page in fanpages:
            for f in page.get('folders', []):
                all_folders.add(f)
        video_count_cache = {}
        for folder in all_folders:
            video_count_cache[folder] = self.db.get_video_count(folder)
        # ─────────────────────────────────────────────────────────────────────

        # Re-build unified dropdown data once for all cards
        self._rebuild_unified_profiles_data()

        for i, page in enumerate(fanpages):
            self._build_page_card(i, page, groups_cache, video_count_cache)

        if hasattr(self, 'search_var'):
            self.filter_cards(self.search_var.get())

        # Gắn lại main_frame vào canvas sau khi toàn bộ cards đã dựng xong
        self.canvas.itemconfig(self.canvas_window, window=self.main_frame)
        
        # Cập nhật scrollregion một lần duy nhất sau khi gắn lại
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

        # Trigger non-blocking async update of profile cache on startup/refresh
        self.refresh_profiles_async(show_msg=False)

    def refresh_profiles_async(self, show_msg=True):
        if show_msg:
            self.log("Đang làm mới danh sách profile từ các trình duyệt...")
        
        def run():
            browsers = self.db.get_browsers()
            all_profiles_by_id = {}
            for b in browsers:
                b_id = b['id']
                try:
                    # Explicit short timeout to keep it quick
                    api = GemLoginAPI(b['api_url']) if b['type'] == 'gemlogin' else GPMLoginAPI(b['api_url'])
                    profiles = api.get_profiles()
                    all_profiles_by_id[b_id] = profiles if profiles is not None else []
                except Exception as e:
                    all_profiles_by_id[b_id] = []
            
            # Post cache update thread-safely
            try:
                self.after(0, lambda: self._on_cache_updated(all_profiles_by_id, show_msg))
            except Exception:
                pass

        threading.Thread(target=run, daemon=True).start()

    def _on_cache_updated(self, new_cache, show_msg):
        self._profile_cache = new_cache
        self._rebuild_unified_profiles_data()
        if show_msg:
            self.log("Đã làm mới xong danh sách profile.")
        self._update_all_card_profile_dropdowns()

    def _update_all_card_profile_dropdowns(self):
        for idx, combo in self.card_comboboxes.items():
            try:
                if combo.winfo_exists():
                    self._update_card_profiles(idx, combo)
            except Exception:
                pass

    def filter_cards(self, query):
        query = query.strip().lower()
        if not hasattr(self, 'cards_info'):
            return
        for card_info in self.cards_info:
            widget = card_info['widget']
            name = card_info['name']
            link = card_info['link']
            if not query or query in name or query in link:
                widget.pack(fill="x", padx=8, pady=5, ipady=5)
            else:
                widget.pack_forget()

    def refresh_card(self, idx):
        if idx < 0 or idx >= len(self.card_widgets):
            return
        card = self.card_widgets[idx]
        page = self.db.get_fanpages()[idx]
        
        # Update metadata in cards_info
        if hasattr(self, 'cards_info'):
            for info in self.cards_info:
                if info['widget'] == card:
                    info['name'] = page.get('name', '').lower()
                    info['link'] = page.get('link', '').lower()
                    break
        
        # Clear child elements of the card
        for widget in card.winfo_children():
            widget.destroy()
        
        # Build with fresh data for this single card
        groups_cache = self.db.get_groups()
        video_count_cache = {f: self.db.get_video_count(f) for f in page.get('folders', [])}
        self._build_card_contents(idx, card, page, groups_cache, video_count_cache)

    def _build_page_card(self, i, page, groups_cache=None, video_count_cache=None):
        card = tk.LabelFrame(self.main_frame, text="",
                             bg="#ffffff", relief="groove", bd=1)
        card.pack(fill="x", padx=8, pady=5, ipady=5)
        self.card_widgets.append(card)
        
        if not hasattr(self, 'cards_info'):
            self.cards_info = []
        self.cards_info.append({
            'widget': card,
            'name': page.get('name', '').lower(),
            'link': page.get('link', '').lower()
        })
        
        if groups_cache is None:
            groups_cache = self.db.get_groups()
        if video_count_cache is None:
            video_count_cache = {f: self.db.get_video_count(f) for f in page.get('folders', [])}
        
        self._build_card_contents(i, card, page, groups_cache, video_count_cache)

    def _build_card_contents(self, i, card, page, groups_cache=None, video_count_cache=None):
        if groups_cache is None:
            groups_cache = self.db.get_groups()
        if video_count_cache is None:
            video_count_cache = {f: self.db.get_video_count(f) for f in page.get('folders', [])}

        # Row 1: Checkbox + Name + Link
        row1 = tk.Frame(card, bg="#ffffff")
        row1.pack(fill="x", padx=8, pady=(5, 2))

        enabled_var = tk.BooleanVar(value=page.get('enabled', True))
        self.card_enabled_vars[i] = enabled_var
        
        def toggle_enable(idx=i, var=enabled_var):
            self.db.update_page_enabled(idx, var.get())
        
        tk.Checkbutton(row1, variable=enabled_var, bg="#ffffff", command=toggle_enable).pack(side="left")
        
        tk.Label(row1, text=f"#{i+1}", font=("Arial", 10, "bold"), bg="#ffffff").pack(side="left", padx=5)

        tk.Label(row1, text="Tên:", bg="#ffffff", width=5, anchor="w").pack(side="left")
        name_entry = tk.Entry(row1, font=("Arial", 10), bd=1, relief="solid")
        name_entry.insert(0, page.get('name', ''))
        name_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        name_entry.bind("<FocusOut>", lambda e, idx=i, ent=name_entry:
                        self.db.update_fanpage_name(idx, ent.get()))

        # Group selection — use cached groups list
        tk.Label(row1, text="Nhóm:", bg="#ffffff", width=6, anchor="w").pack(side="left", padx=(10, 0))
        groups = groups_cache  # already fetched, no DB call
        group_names = [g['name'] for g in groups]
        g_combo = ttk.Combobox(row1, values=["(Không nhóm)"] + group_names, state="readonly", width=15)
        g_combo.pack(side="left")
        self._disable_combo_scroll(g_combo, redirect_to_canvas=True)
        
        # Set current group
        curr_g_id = page.get('group_id', '')
        curr_g_name = "(Không nhóm)"
        if curr_g_id:
            for g in groups:
                if g['id'] == curr_g_id:
                    curr_g_name = g['name']
                    break
        g_combo.set(curr_g_name)

        def on_group_change(event, p_idx=i, cb=g_combo, grps=groups):
            choice = cb.get()
            new_g_id = ""
            if choice != "(Không nhóm)":
                for g in grps:
                    if g['name'] == choice:
                        new_g_id = g['id']
                        break
            self.db.update_page_group(p_idx, new_g_id)
            self.log(f"Đã gán Fanpage #{p_idx+1} vào nhóm: {choice}")
            # Refresh card to show browser changes instantly and in-place
            self.refresh_card(p_idx)
        
        g_combo.bind("<<ComboboxSelected>>", on_group_change)

        # Row 2: Link
        row2 = tk.Frame(card, bg="#ffffff")
        row2.pack(fill="x", padx=8, pady=2)

        tk.Label(row2, text="Link:", bg="#ffffff", width=5, anchor="w").pack(side="left")
        link_entry = tk.Entry(row2, font=("Arial", 9), bd=1, relief="solid", fg="#333")
        link_entry.insert(0, page.get('link', ''))
        link_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        link_entry.bind("<FocusOut>", lambda e, idx=i, ent=link_entry:
                        self.db.update_link(idx, ent.get()))

        # Unified Selection
        tk.Label(row2, text="Profile:", bg="#ffffff", width=7, anchor="w").pack(side="left", padx=(10, 0))
        
        # Unified profile names will be like "[Gem] Profile 1"
        p_combo = ttk.Combobox(row2, state="readonly", width=35)
        p_combo.pack(side="left")
        self._disable_combo_scroll(p_combo, redirect_to_canvas=True)
        self.card_comboboxes[i] = p_combo

        def refresh_unified_profiles(idx_val=i, combo=p_combo):
            combo.set("Đang làm mới...")
            self.refresh_profiles_async(show_msg=True)

        btn_refresh = tk.Button(row2, text="🔄", command=refresh_unified_profiles, padx=5, font=("Arial", 9))
        btn_refresh.pack(side="left", padx=2)
        self.style_button(btn_refresh, "#f0f0f0", "#e0e0e0", fg_color="#333333")
        
        # Initialize profiles for this card
        self._init_card_profile(i, p_combo)

        # Row 3: Buttons
        row3 = tk.Frame(card, bg="#ffffff")
        row3.pack(fill="x", padx=8, pady=2)

        # Action buttons (right side)
        btn_opts = dict(cursor="hand2", padx=8, pady=3, font=("Arial", 9))

        btn_log = tk.Button(row3, text="Log Ngày", command=lambda name=page.get('name', ''): self.show_video_log_ui(filter_name=name), **btn_opts)
        btn_log.pack(side="right", padx=2)
        self.style_button(btn_log, "#3a9a5c", "#2b7545")

        btn_folder_f = tk.Button(row3, text="Thêm Folder", command=lambda idx=i: self.browse_folders(idx), **btn_opts)
        btn_folder_f.pack(side="right", padx=2)
        self.style_button(btn_folder_f, "#1a73e8", "#1557b0")

        btn_folder_m = tk.Button(row3, text="Thêm Path", command=lambda idx=i: self.add_folder_manual(idx), **btn_opts)
        btn_folder_m.pack(side="right", padx=2)
        self.style_button(btn_folder_m, "#2e7d32", "#225c25")

        btn_delete = tk.Button(row3, text="Xóa", command=lambda idx=i: self.remove_page(idx), **btn_opts)
        btn_delete.pack(side="right", padx=2)
        self.style_button(btn_delete, "#ea4335", "#c5221f")

        btn_comment = tk.Button(row3, text="Bình Luận", command=lambda idx=i: self.set_page_comment_ui(idx), **btn_opts)
        btn_comment.pack(side="right", padx=2)
        self.style_button(btn_comment, "#9b59b6", "#804399")

        btn_history = tk.Button(row3, text="Lịch Sử", command=lambda idx=i: self.view_log_ui(idx), **btn_opts)
        btn_history.pack(side="right", padx=2)
        self.style_button(btn_history, "#7c5cbf", "#6242a3")

        # Row 4: Folders
        row4 = tk.Frame(card, bg="#ffffff")
        row4.pack(fill="x", padx=8, pady=(2, 5))

        if not page.get('folders'):
            tk.Label(row4, text="⚠️ Chưa có thư mục video", fg="#ea4335",
                     bg="#ffffff", font=("Arial", 9, "bold italic")).pack(anchor="w")
        else:
            for j, folder in enumerate(page['folders']):
                f_row = tk.Frame(row4, bg="#ffffff")
                f_row.pack(fill="x", pady=1)
                
                # Use cached count — no os.listdir on main thread
                v_count = video_count_cache.get(folder, 0)
                count_color = "#3a9a5c" if v_count > 0 else "#ea4335"
                count_text = f"({v_count} videos)" if v_count > 0 else "(0 videos - EMPTY)"
                
                tk.Label(f_row, text=f"📁 {folder}", anchor="w",
                         bg="#ffffff", font=("Arial", 9)).pack(side="left")
                
                tk.Label(f_row, text=count_text, bg="#ffffff", 
                         fg=count_color, font=("Arial", 8, "bold")).pack(side="left", padx=5)

                btn_del_folder = tk.Button(f_row, text="x", fg="gray", bg="#ffffff", relief="flat", cursor="hand2", font=("Arial", 9, "bold"),
                          command=lambda p_idx=i, f_idx=j: self.remove_folder(p_idx, f_idx))
                btn_del_folder.pack(side="right")
                # Hover effect for delete button
                def on_e(e, b=btn_del_folder): b.configure(fg="red")
                def on_l(e, b=btn_del_folder): b.configure(fg="gray")
                btn_del_folder.bind("<Enter>", on_e)
                btn_del_folder.bind("<Leave>", on_l)

    def _rebuild_unified_profiles_data(self):
        """Build the unified profile list and mapping once to cache it."""
        browsers = self.db.get_browsers()
        all_options = []
        unified_p_map = {} # Map option string -> (browser_id, profile_id, profile_name)
        
        if not hasattr(self, '_profile_cache'):
            self._profile_cache = {}
            
        for b in browsers:
            b_id = b['id']
            b_name = b['name']
            profiles = self._profile_cache.get(b_id, [])
            for p in profiles:
                p_name = p.get('name', p.get('title', p.get('profile_name', 'Unknown')))
                p_id = p.get('id', p.get('profile_id'))
                opt = f"[{b_name}] {p_name}"
                all_options.append(opt)
                unified_p_map[opt] = (b_id, p_id, p_name)
                
        self._unified_profile_options = all_options
        self._unified_profile_map = unified_p_map

    def _update_card_profiles(self, idx, combo):
        # Ensure we have pre-built unified profile options and mapping
        if not hasattr(self, '_unified_profile_options') or not hasattr(self, '_unified_profile_map'):
            self._rebuild_unified_profiles_data()
            
        all_options = self._unified_profile_options
        unified_p_map = self._unified_profile_map
        
        combo['values'] = all_options
        
        # --- SET INITIAL VALUE FROM DB ---
        fanpages = self.db.get_fanpages()
        if idx < len(fanpages):
            fanpage = fanpages[idx]
            curr_b_id = fanpage.get('browser_id')
            curr_p_id = fanpage.get('profile_id')
            
            if curr_b_id and curr_p_id:
                # Find matching option in our unified map
                found_opt = None
                for opt, (b_id, p_id, p_name) in unified_p_map.items():
                    if b_id == curr_b_id and str(p_id) == str(curr_p_id):
                        found_opt = opt
                        break
                
                final_val = ""
                if found_opt:
                    final_val = found_opt
                else:
                    # If profile not found in current API list, show placeholder using stored name
                    p_name_stored = fanpage.get('profile_name', 'Unknown')
                    b_name_stored = "Unknown"
                    target_b = self.db.get_browser_by_id(curr_b_id)
                    if target_b: b_name_stored = target_b['name']
                    final_val = f"[{b_name_stored}] {p_name_stored}"
                
                if final_val:
                    # Use after to ensure it takes effect after packing
                    try:
                        self.after(50, lambda v=final_val, cb=combo: cb.set(v) if cb.winfo_exists() else None)
                    except Exception:
                        pass
        
        # Store the map for this page card
        if not hasattr(self, '_page_unified_maps'):
            self._page_unified_maps = {}
        self._page_unified_maps[idx] = unified_p_map

        def on_unified_select(event, p_idx=idx, p_var=None, card_combo=combo):
            opt = card_combo.get()
            if opt in unified_p_map:
                b_id, p_id, p_name = unified_p_map[opt]
                self.db.update_page_browser(p_idx, b_id)
                self.db.update_page_profile(p_idx, p_id, p_name)
                self.log(f"Đã gán {opt} cho Fanpage #{p_idx+1}")

        combo.bind("<<ComboboxSelected>>", on_unified_select)

    def _init_card_profile(self, idx, combo):
        # Initial population of the dropdown
        self._update_card_profiles(idx, combo)

    # ── Popup Windows ─────────────────────────────────────────

    def view_log_ui(self, index):
        page = self.db.get_fanpages()[index]
        logs = self.db.get_logs(page['link'])

        win = tk.Toplevel(self)
        win.title(f"Lịch Sử: {page.get('name', page['link'])}")
        win.geometry("700x450")
        win.attributes("-topmost", True)

        frame = tk.Frame(win)
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        tk.Label(frame, text="Lịch Sử Đăng Bài", font=("Arial", 13, "bold")).pack(anchor="w", pady=(0, 8))

        txt = scrolledtext.ScrolledText(frame, font=("Consolas", 10), wrap="word")
        txt.pack(fill="both", expand=True)

        if not logs:
            txt.insert("1.0", "Chưa có lịch sử.")
        else:
            for log in reversed(logs):
                status_mark = "✓" if "Success" in log.get('status', '') else "✗"
                line = f"[{log.get('timestamp', '')}] {status_mark} {log.get('video', '')} - {log.get('status', '')}"
                if log.get('link') and "Captured" not in log.get('link', ''):
                    line += f"\n  → {log.get('link', '')}"
                txt.insert("end", line + "\n\n")

        txt.configure(state="disabled")

    def show_done_errors_ui(self):
        log_file = "loi_done.txt"
        if not os.path.exists(log_file):
            messagebox.showinfo("Thông báo", "Hiện chưa có lỗi 'Done' nào được ghi nhận.")
            return

        win = tk.Toplevel(self)
        win.title("Báo cáo lỗi Nút Done (Retry 10 lần thất bại)")
        win.geometry("800x500")
        win.attributes("-topmost", True)

        txt = scrolledtext.ScrolledText(win, font=("Consolas", 10), wrap="word")
        txt.pack(fill="both", expand=True, padx=10, pady=10)

        try:
            with open(log_file, "r", encoding="utf-8") as f:
                content = f.read()
                txt.insert("1.0", content)
        except Exception as e:
            txt.insert("1.0", f"Lỗi khi đọc file: {e}")

        txt.configure(state="disabled")
        
        btn_frame = tk.Frame(win)
        btn_frame.pack(fill="x", padx=10, pady=(0, 10))
        
        def clear_log():
            if messagebox.askyesno("Xác nhận", "Bạn có muốn xóa toàn bộ log lỗi Done không?"):
                try:
                    os.remove(log_file)
                    win.destroy()
                    self.log("Đã xóa file log lỗi Done.")
                except: pass
        
        tk.Button(btn_frame, text="Xóa Toàn Bộ Log", bg="#c0392b", fg="white", command=clear_log, padx=10, pady=5).pack(side="right")

    def set_comment_ui(self):
        win = tk.Toplevel(self)
        win.title("Cài Đặt Bình Luận")
        win.geometry("600x690") # Tăng chiều cao để chứa thêm checkbox
        win.attributes("-topmost", True)

        # --- Top Checkbox ---
        all_pages_var = tk.BooleanVar(value=self.db.get_comment_all_fanpages())
        chk_all = tk.Checkbutton(win, text="Bình luận cho tất cả fanpage", variable=all_pages_var,
                                 font=("Arial", 11, "bold"), fg="#7c5cbf")
        chk_all.pack(padx=15, pady=(15, 5), anchor="w")

        # --- Template Section ---
        tk.Label(win, text="Mẫu Bình Luận Chung (hỗ trợ {a|b|c})",
                 font=("Arial", 12, "bold")).pack(padx=15, pady=(10, 5), anchor="w")

        txt = scrolledtext.ScrolledText(win, font=("Arial", 11), height=10, wrap="word")
        txt.pack(fill="x", padx=15, pady=5)
        txt.insert("1.0", self.db.get_comment_template())

        # --- Strategy Section ---
        strat_frame = tk.LabelFrame(win, text=" Chiến thuật bình luận (Thứ tự ưu tiên từ trên xuống) ",
                                     font=("Arial", 11, "bold"), padx=10, pady=10)
        strat_frame.pack(fill="both", expand=True, padx=15, pady=10)

        strategies = self.db.get_comment_strategies()
        vars = {}
        
        strat_labels = {
            "home_scroll": "1. Bình luận qua Trang chủ (Home Scroll)",
            "feed_grid": "2. Bình luận qua Bảng feed & Lưới (Feed & Grid)",
            "published_panel": "3. Bình luận qua Bài viết đã đăng (Bảng chi tiết)",
            "published_inline": "4. Bình luận qua Bài viết đã đăng (Trực tiếp trên danh sách)",
            "insight_overview": "5. Bình luận qua Insights: Tổng quan nội dung",
            "insight_content": "6. Bình luận qua Insights: Tất cả nội dung"
        }

        for key, label in strat_labels.items():
            var = tk.BooleanVar(value=strategies.get(key, True))
            vars[key] = var
            tk.Checkbutton(strat_frame, text=label, variable=var, font=("Arial", 10)).pack(anchor="w", pady=2)

        # --- Buttons ---
        btn_frame = tk.Frame(win)
        btn_frame.pack(fill="x", padx=15, pady=10)

        def save():
            # Save template
            self.db.set_comment_template(txt.get("1.0", "end-1c"))
            
            # Save comment_all_fanpages
            self.db.set_comment_all_fanpages(all_pages_var.get())
            
            # Save strategies
            new_strats = {k: v.get() for k, v in vars.items()}
            self.db.set_comment_strategies(new_strats)
            
            self.log("Đã lưu mẫu và chiến thuật bình luận.")
            win.destroy()

        tk.Button(btn_frame, text="Hủy", relief="flat", bg="#888", fg="white",
                  padx=15, pady=5, command=win.destroy).pack(side="right", padx=5)
        tk.Button(btn_frame, text="Lưu Cài Đặt", relief="flat", bg="#7c5cbf", fg="white",
                  padx=15, pady=5, command=save).pack(side="right", padx=5)

    def set_page_comment_ui(self, index):
        page = self.db.get_fanpages()[index]
        page_name = page.get('name') or f"Fanpage {index+1}"
        
        win = tk.Toplevel(self)
        win.title(f"Cài Đặt Bình Luận - {page_name}")
        win.geometry("550x450")
        win.attributes("-topmost", True)
        
        tk.Label(win, text=f"Mẫu Bình Luận Riêng cho Fanpage:", font=("Arial", 12, "bold")).pack(padx=15, pady=(15, 2), anchor="w")
        tk.Label(win, text=f"{page_name} ({page['link']})", font=("Arial", 10, "italic"), fg="gray").pack(padx=15, pady=(0, 10), anchor="w")
        
        txt = scrolledtext.ScrolledText(win, font=("Arial", 11), height=10, wrap="word")
        txt.pack(fill="both", expand=True, padx=15, pady=5)
        txt.insert("1.0", page.get('comment_template', ""))
        
        btn_frame = tk.Frame(win)
        btn_frame.pack(fill="x", padx=15, pady=10)
        
        def save():
            template_text = txt.get("1.0", "end-1c")
            self.db.update_page_comment_template(index, template_text)
            self.log(f"Đã lưu mẫu bình luận riêng cho fanpage {page_name}.")
            win.destroy()
            
        tk.Button(btn_frame, text="Hủy", relief="flat", bg="#888", fg="white",
                  padx=15, pady=5, command=win.destroy).pack(side="right", padx=5)
        tk.Button(btn_frame, text="Lưu Cài Đặt", relief="flat", bg="#7c5cbf", fg="white",
                  padx=15, pady=5, command=save).pack(side="right", padx=5)

    def browser_settings_ui(self):
        win = tk.Toplevel(self)
        win.title("Cấu Hình Trình Duyệt")
        win.geometry("700x500")
        win.attributes("-topmost", True)

        main_frame = tk.Frame(win, padx=15, pady=15)
        main_frame.pack(fill="both", expand=True)

        # Browser Connections Section
        tk.Label(main_frame, text="Quản Lý Kết Nối Đa Điểm (Song Song)", font=("Arial", 12, "bold")).pack(anchor="w", pady=(0, 15))

        list_frame = tk.Frame(main_frame)
        list_frame.pack(fill="both", expand=True)

        def refresh_list():
            for widget in list_frame.winfo_children():
                widget.destroy()
            
            # --- DEDICATED SLOTS FOR MULTI-POINT ---
            browsers = self.db.get_browsers()
            
            for b_id in ["gemlogin_default", "gpmlogin_default"]:
                b = self.db.get_browser_by_id(b_id)
                if not b: continue
                
                row = tk.Frame(list_frame, pady=8, bg="#f0f4f8", relief="groove", bd=1)
                row.pack(fill="x", pady=4)
                
                tk.Label(row, text="Tên:", font=("Arial", 9), bg="#f0f4f8").pack(side="left", padx=(10, 0))
                name_ent = tk.Entry(row, width=15, font=("Arial", 10, "bold"))
                name_ent.insert(0, b['name'])
                name_ent.pack(side="left", padx=5)

                tk.Label(row, text="Loại:", font=("Arial", 9), bg="#f0f4f8").pack(side="left", padx=(5, 0))
                type_var = tk.StringVar(value=b['type'])
                type_combo = ttk.Combobox(row, textvariable=type_var, values=["gemlogin", "gpmlogin"], width=10, state="readonly")
                type_combo.pack(side="left", padx=2)
                self._disable_combo_scroll(type_combo, redirect_to_canvas=False)
                
                tk.Label(row, text="API URL:", font=("Arial", 9), bg="#f0f4f8").pack(side="left", padx=(10, 0))
                url_ent = tk.Entry(row, width=25, font=("Consolas", 10))
                url_ent.insert(0, b['api_url'])
                url_ent.pack(side="left", padx=5)
                
                def make_save(bid=b_id, n_ent=name_ent, t_var=type_var, u_ent=url_ent):
                    def _s():
                        new_name = n_ent.get().strip()
                        new_type = t_var.get()
                        new_url = u_ent.get().strip()
                        self.db.update_browser(bid, new_name, new_type, new_url)
                        self.log(f"Đã lưu cấu hình {new_name} ({new_type})")
                        self.refresh_ui()
                    return _s

                def make_test(t_var=type_var, ent=url_ent):
                    def _t():
                        url = ent.get().strip()
                        t = t_var.get()
                        self.log(f"Đang kiểm tra {t} tại {url}...")
                        
                        def run_test():
                            try:
                                api = GemLoginAPI(url) if t == "gemlogin" else GPMLoginAPI(url)
                                profiles = api.get_profiles()
                                if profiles is not None:
                                    self.after(0, lambda: messagebox.showinfo("Kết nối", f"Kết nối {t} thành công!\nTìm thấy {len(profiles)} profiles."))
                                    self.log(f"Kết nối {t} thành công: {len(profiles)} profiles.")
                                else:
                                    self.after(0, lambda: messagebox.showerror("Kết nối", f"Không thể kết nối đến {t} hoặc URL không đúng."))
                                    self.log(f"Kết nối {t} thất bại.")
                            except Exception as e:
                                self.after(0, lambda: messagebox.showerror("Lỗi", f"Lỗi hệ thống: {e}"))
                        
                        threading.Thread(target=run_test, daemon=True).start()
                    return _t

                btn_save = tk.Button(row, text="Lưu", command=make_save(), width=8)
                btn_save.pack(side="left", padx=5)
                self.style_button(btn_save, "#2e7d32", "#225c25")

                btn_test = tk.Button(row, text="Test", command=make_test(), width=8)
                btn_test.pack(side="left", padx=5)
                self.style_button(btn_test, "#1976d2", "#115293")

            ttk.Separator(list_frame).pack(fill="x", pady=15)
            
            # --- CUSTOM / REMOTE Hubs ---
            tk.Label(list_frame, text="Thêm Kết Nối Khác (Tùy Chình):", font=("Arial", 10, "bold")).pack(anchor="w", pady=(0, 5))
            
            add_row = tk.Frame(list_frame)
            add_row.pack(fill="x", pady=5)
            
            n_new = tk.Entry(add_row, width=15)
            n_new.insert(0, "Sub Hub")
            n_new.pack(side="left", padx=2)
            
            t_new = ttk.Combobox(add_row, values=["gemlogin", "gpmlogin"], width=10, state="readonly")
            t_new.set("gpmlogin")
            t_new.pack(side="left", padx=2)
            self._disable_combo_scroll(t_new, redirect_to_canvas=False)
            
            u_new = tk.Entry(add_row, width=20)
            u_new.insert(0, "http://")
            u_new.pack(side="left", padx=2)
            
            def add_new():
                name = n_new.get().strip()
                if name:
                    self.db.add_browser(name, t_new.get(), u_new.get().strip())
                    refresh_list()
            
            btn_add = tk.Button(add_row, text="+ Thêm Hub", command=add_new, padx=10)
            btn_add.pack(side="left", padx=5)
            self.style_button(btn_add, "#7b1fa2", "#5e157d")

            # List existing others
            others = [b for b in browsers if b['id'] not in ["gemlogin_default", "gpmlogin_default"]]
            for b in others:
                orow = tk.Frame(list_frame, pady=2)
                orow.pack(fill="x")
                tk.Label(orow, text=f"• {b['name']} ({b['type']})", width=25, anchor="w").pack(side="left")
                tk.Label(orow, text=b['api_url'], width=30, anchor="w").pack(side="left")
                
                btn_del = tk.Button(orow, text="Xóa", command=lambda bid=b['id']: [self.db.remove_browser(bid), refresh_list()], padx=8)
                btn_del.pack(side="left", padx=5)
                self.style_button(btn_del, "#ea4335", "#c5221f")

        refresh_list()

        def on_close():
            if hasattr(self, '_profile_cache'):
                self._profile_cache.clear() # Clear cache when settings change
            self.refresh_ui()
            win.destroy()

        btn_close = tk.Button(main_frame, text="Đóng", command=on_close, pady=5, width=10)
        btn_close.pack(pady=10)
        self.style_button(btn_close, "#5f6368", "#474a4d")
        win.protocol("WM_DELETE_WINDOW", on_close)

    def scheduling_settings_ui(self):
        config = self.db.get_scheduling_config()
        win = tk.Toplevel(self)
        win.title("Cài Đặt Lịch Chạy")
        win.geometry("450x400")
        win.attributes("-topmost", True)
        win.resizable(False, False)

        pad = dict(padx=15, pady=5)

        tk.Label(win, text="Cấu Hình Lịch Chạy", font=("Arial", 13, "bold")).pack(**pad, anchor="w")
        ttk.Separator(win).pack(fill="x", padx=10)

        # Loop mode
        tk.Label(win, text="Chế Độ Lặp:", font=("Arial", 10, "bold")).pack(**pad, anchor="w")
        loop_mode_var = tk.StringVar(value=config['loop_mode'])
        for val, label in [("once", "Chạy 1 lần"), ("infinite", "Vòng lặp vô hạn")]:
            tk.Radiobutton(win, text=label, variable=loop_mode_var, value=val).pack(padx=25, anchor="w")

        count_row = tk.Frame(win)
        count_row.pack(fill="x", padx=25)
        tk.Radiobutton(count_row, text="Chạy N lần:", variable=loop_mode_var, value="count").pack(side="left")
        count_entry = tk.Entry(count_row, width=8, bd=1, relief="solid")
        count_entry.insert(0, str(config['loop_count']))
        count_entry.pack(side="left", padx=8)

        ttk.Separator(win).pack(fill="x", padx=10, pady=8)

        # Rest interval
        tk.Label(win, text="Nghỉ Giữa Các Lần (phút):", font=("Arial", 10, "bold")).pack(**pad, anchor="w")
        rest_row = tk.Frame(win)
        rest_row.pack(fill="x", padx=25)
        tk.Label(rest_row, text="Min:").pack(side="left")
        rest_min = tk.Entry(rest_row, width=8, bd=1, relief="solid")
        rest_min.insert(0, str(config['rest_min']))
        rest_min.pack(side="left", padx=8)
        tk.Label(rest_row, text="Max:").pack(side="left")
        rest_max = tk.Entry(rest_row, width=8, bd=1, relief="solid")
        rest_max.insert(0, str(config['rest_max']))
        rest_max.pack(side="left", padx=8)

        ttk.Separator(win).pack(fill="x", padx=10, pady=8)

        # Time window
        tk.Label(win, text="Khung Giờ Hoạt Động (HH:MM):", font=("Arial", 10, "bold")).pack(**pad, anchor="w")
        time_row = tk.Frame(win)
        time_row.pack(fill="x", padx=25)
        tk.Label(time_row, text="Từ:").pack(side="left")
        time_start = tk.Entry(time_row, width=8, bd=1, relief="solid")
        time_start.insert(0, config['time_start'])
        time_start.pack(side="left", padx=8)
        tk.Label(time_row, text="Đến:").pack(side="left")
        time_end = tk.Entry(time_row, width=8, bd=1, relief="solid")
        time_end.insert(0, config['time_end'])
        time_end.pack(side="left", padx=8)

        ttk.Separator(win).pack(fill="x", padx=10, pady=8)

        # Parallel Workers
        tk.Label(win, text="Số Luồng Chạy Song Song:", font=("Arial", 10, "bold")).pack(**pad, anchor="w")
        p_row = tk.Frame(win)
        p_row.pack(fill="x", padx=25)
        tk.Label(p_row, text="Max threads:").pack(side="left")
        p_count_entry = tk.Entry(p_row, width=8, bd=1, relief="solid")
        p_count_entry.insert(0, str(self.db.get_max_parallel_workers()))
        p_count_entry.pack(side="left", padx=8)

        # Buttons
        btn_frame = tk.Frame(win)
        btn_frame.pack(fill="x", padx=15, pady=15)

        def save_settings():
            try:
                self.db.set_scheduling_config(
                    loop_mode_var.get(),
                    int(count_entry.get()),
                    int(rest_min.get()),
                    int(rest_max.get()),
                    time_start.get(),
                    time_end.get()
                )
                self.db.set_max_parallel_workers(int(p_count_entry.get()))
                messagebox.showinfo("Thành công", "Đã lưu cài đặt lịch chạy.")
                win.destroy()
            except Exception as e:
                messagebox.showerror("Lỗi", f"Dữ liệu không hợp lệ: {e}")

        tk.Button(btn_frame, text="Hủy", relief="flat", bg="#888", fg="white",
                  padx=15, pady=5, command=win.destroy).pack(side="right", padx=5)
        tk.Button(btn_frame, text="Lưu Cài Đặt", relief="flat", bg="#3a9a5c", fg="white",
                  padx=15, pady=5, command=save_settings).pack(side="right", padx=5)

    def browse_folders(self, page_index):
        win = tk.Toplevel(self)
        win.title("Chọn Thư Mục")
        win.geometry("550x380")
        win.attributes("-topmost", True)

        tk.Label(win, text="Thư Mục Đã Chọn", font=("Arial", 12, "bold")).pack(padx=15, pady=(15, 5), anchor="w")

        list_frame = tk.Frame(win, relief="sunken", bd=1)
        list_frame.pack(fill="both", expand=True, padx=15, pady=5)

        txt = scrolledtext.ScrolledText(list_frame, font=("Arial", 10), state="disabled", height=12)
        txt.pack(fill="both", expand=True)

        self.temp_folders = []

        def refresh():
            txt.configure(state="normal")
            txt.delete("1.0", "end")
            if not self.temp_folders:
                txt.insert("1.0", "(Chưa chọn thư mục nào)")
            else:
                for p in self.temp_folders:
                    txt.insert("end", f"📁 {p}\n")
            txt.configure(state="disabled")

        def add_folder():
            folder = filedialog.askdirectory(parent=win)
            if folder and folder not in self.temp_folders:
                self.temp_folders.append(folder)
                refresh()

        def remove_last():
            if self.temp_folders:
                self.temp_folders.pop()
                refresh()

        def save_all():
            for folder in self.temp_folders:
                self.db.add_folder(page_index, folder)
            self.refresh_card(page_index)
            win.destroy()

        refresh()

        btn_frame = tk.Frame(win)
        btn_frame.pack(fill="x", padx=15, pady=10)
        tk.Button(btn_frame, text="+ Thêm Thư Mục", relief="flat", bg="#4a90d9", fg="white",
                  padx=10, pady=5, command=add_folder).pack(side="left", padx=2)
        tk.Button(btn_frame, text="Xóa Cuối", relief="flat", bg="#c0392b", fg="white",
                  padx=10, pady=5, command=remove_last).pack(side="left", padx=2)
        tk.Button(btn_frame, text="Hủy", relief="flat", bg="#888", fg="white",
                  padx=10, pady=5, command=win.destroy).pack(side="right", padx=2)
        tk.Button(btn_frame, text="Lưu Tất Cả", relief="flat", bg="#3a9a5c", fg="white",
                  padx=10, pady=5, command=save_all).pack(side="right", padx=2)

    def add_folder_manual(self, page_index):
        win = tk.Toplevel(self)
        win.title("Nhập Đường Dẫn")
        win.geometry("500x150")
        win.attributes("-topmost", True)
        win.resizable(False, False)

        tk.Label(win, text="Nhập đường dẫn thư mục:", font=("Arial", 11, "bold")).pack(padx=15, pady=(15, 5), anchor="w")
        path_entry = tk.Entry(win, font=("Arial", 10), bd=1, relief="solid")
        path_entry.pack(fill="x", padx=15, pady=5)
        path_entry.focus()

        def save_path():
            path = path_entry.get().strip()
            if path:
                self.db.add_folder(page_index, path)
                self.refresh_card(page_index)
                win.destroy()

        path_entry.bind("<Return>", lambda e: save_path())

        btn_frame = tk.Frame(win)
        btn_frame.pack(fill="x", padx=15, pady=10)
        tk.Button(btn_frame, text="Hủy", relief="flat", bg="#888", fg="white",
                  padx=12, pady=4, command=win.destroy).pack(side="right", padx=5)
        tk.Button(btn_frame, text="Thêm", relief="flat", bg="#3a9a5c", fg="white",
                  padx=12, pady=4, command=save_path).pack(side="right", padx=5)

    def add_fanpage_ui(self):
        win = tk.Toplevel(self)
        win.title("Thêm Fanpage")
        win.geometry("350x130")
        win.attributes("-topmost", True)
        win.resizable(False, False)

        tk.Label(win, text="Số lượng Fanpage muốn thêm:", font=("Arial", 11)).pack(padx=15, pady=(15, 5), anchor="w")
        entry = tk.Entry(win, bd=1, relief="solid", width=10)
        entry.insert(0, "1")
        entry.pack(padx=15, pady=5, anchor="w")
        entry.focus()

        def do_add():
            try:
                count = int(entry.get())
                if count > 0:
                    for i in range(count):
                        self.db.add_fanpage("https://facebook.com/...", save=(i == count - 1))
                    self.refresh_ui()
                    win.destroy()
            except ValueError:
                pass

        entry.bind("<Return>", lambda e: do_add())
        btn_frame = tk.Frame(win)
        btn_frame.pack(fill="x", padx=15, pady=8)
        tk.Button(btn_frame, text="Hủy", relief="flat", bg="#888", fg="white",
                  padx=12, pady=4, command=win.destroy).pack(side="right", padx=5)
        tk.Button(btn_frame, text="Thêm", relief="flat", bg="#4a90d9", fg="white",
                  padx=12, pady=4, command=do_add).pack(side="right", padx=5)

    def remove_page(self, index):
        if messagebox.askyesno("Xác Nhận", "Xóa Fanpage này?"):
            self.db.remove_fanpage(index)
            self.refresh_ui()

    def clear_all_ui(self):
        if messagebox.askyesno("Xác Nhận", "Bạn có chắc muốn xóa TẤT CẢ fanpages?"):
            self.db.clear_all()
            self.refresh_ui()

    def remove_folder(self, page_index, folder_index):
        self.db.remove_folder(page_index, folder_index)
        self.refresh_card(page_index)

    def toggle_auto_delete(self):
        val = self.auto_delete_var.get()
        self.db.set_auto_delete_videos(val)
        self.log(f"Tự xóa video: {'Bật' if val else 'Tắt'}")

    def show_video_log_ui(self, filter_name=None):
        log_file = "thongke_ngay.txt"
        win = tk.Toplevel(self)
        title = f"Log Ngày: {filter_name}" if filter_name else "Thống Kê Log Hệ Thống"
        win.title(title)
        win.geometry("900x600")
        win.attributes("-topmost", True)

        tk.Label(win, text=title, font=("Arial", 13, "bold")).pack(padx=15, pady=(10, 5), anchor="w")

        txt = scrolledtext.ScrolledText(win, font=("Consolas", 10), wrap="word")
        txt.pack(fill="both", expand=True, padx=10, pady=5)

        def populate():
            txt.configure(state="normal")
            txt.delete("1.0", "end")
            if not os.path.exists(log_file):
                txt.insert("1.0", "Chưa có dữ liệu log.")
                txt.configure(state="disabled")
                return
            try:
                with open(log_file, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                filtered = []
                for line in reversed(lines):
                    line = line.strip()
                    if not line:
                        continue
                    if filter_name and f"Page: {filter_name}" not in line:
                        continue
                    filtered.append(line)
                txt.insert("1.0", "\n".join(filtered))
            except Exception as e:
                txt.insert("1.0", f"Lỗi đọc log: {e}")
            txt.configure(state="disabled")

        populate()

        btn_frame = tk.Frame(win)
        btn_frame.pack(fill="x", padx=10, pady=8)

        def clear_logs():
            if messagebox.askyesno("Xác nhận", "Xóa toàn bộ log hôm nay?", parent=win):
                if os.path.exists(log_file):
                    os.remove(log_file)
                populate()

        tk.Button(btn_frame, text="Xoá Log", relief="flat", bg="#c0392b", fg="white",
                  padx=12, pady=4, command=clear_logs).pack(side="left", padx=5)
        tk.Button(btn_frame, text="Làm Mới", relief="flat", bg="#4a90d9", fg="white",
                  padx=12, pady=4, command=populate).pack(side="left", padx=5)
        tk.Button(btn_frame, text="Đóng", relief="flat", bg="#888", fg="white",
                  padx=12, pady=4, command=win.destroy).pack(side="right", padx=5)

    def set_all_enabled(self, status):
        self.db.update_pages_enabled_bulk(status)
        if hasattr(self, 'card_enabled_vars'):
            for idx, var in self.card_enabled_vars.items():
                try:
                    var.set(status)
                except Exception:
                    pass

    def bulk_assign_ui(self):
        # Find which fanpages are selected
        fanpages = self.db.get_fanpages()
        selected_indices = [i for i, p in enumerate(fanpages) if p.get('enabled', True)]
        
        # Get groups
        groups = self.db.get_groups()
        group_names = [g['name'] for g in groups]

        win = tk.Toplevel(self)
        win.title("Gán Hàng Loạt Profile")
        win.geometry("500x250")
        win.attributes("-topmost", True)
        win.resizable(False, False)

        main_frame = tk.Frame(win, padx=20, pady=20)
        main_frame.pack(fill="both", expand=True)

        tk.Label(main_frame, text="Thiết lập gán profile hàng loạt", font=("Arial", 11, "bold")).pack(pady=(0, 15))

        # Row 1: Target Selection (All enabled vs Specific Group)
        row_target = tk.Frame(main_frame)
        row_target.pack(fill="x", pady=5)
        tk.Label(row_target, text="Đối tượng gán:", width=12, anchor="w").pack(side="left")
        
        target_var = tk.StringVar()
        target_options = [f"Tất cả trang được tích chọn ({len(selected_indices)} page)"] + [f"Nhóm: {name}" for name in group_names]
        target_combo = ttk.Combobox(row_target, textvariable=target_var, values=target_options, state="readonly", width=45)
        target_combo.pack(side="left")
        target_combo.set(target_options[0])
        self._disable_combo_scroll(target_combo, redirect_to_canvas=False)

        # Row 2: Unified Profile Selection
        row_profile = tk.Frame(main_frame)
        row_profile.pack(fill="x", pady=5)
        tk.Label(row_profile, text="Profile:", width=12, anchor="w").pack(side="left")
        p_var = tk.StringVar(value="Đang tải danh sách...")
        p_combo = ttk.Combobox(row_profile, textvariable=p_var, state="readonly", width=45)
        p_combo.pack(side="left")
        self._disable_combo_scroll(p_combo, redirect_to_canvas=False)

        bulk_unified_map = {}

        def update_bulk_profiles():
            nonlocal bulk_unified_map
            browsers = self.db.get_browsers()
            all_opts = []
            if not hasattr(self, '_profile_cache'): self._profile_cache = {}
            
            for b in browsers:
                b_id = b['id']
                b_name = b['name']
                
                # Use cache if available
                profiles = self._profile_cache.get(b_id)
                
                if profiles is None:
                    # If not in cache, try fetching once
                    try:
                        api = GemLoginAPI(b['api_url']) if b['type'] == 'gemlogin' else GPMLoginAPI(b['api_url'])
                        profiles = api.get_profiles() or []
                        self._profile_cache[b_id] = profiles
                    except:
                        self._profile_cache[b_id] = []
                        profiles = []
                
                for p in profiles:
                    p_name = p.get('name', p.get('title', p.get('profile_name', 'Unknown')))
                    p_id = p.get('id', p.get('profile_id'))
                    opt = f"[{b_name}] {p_name}"
                    all_opts.append(opt)
                    bulk_unified_map[opt] = (b_id, p_id, p_name)
            
            p_combo['values'] = all_opts
            if all_opts: p_var.set(all_opts[0])
            else: p_var.set("Không tìm thấy profile nào")

        update_bulk_profiles()

        def apply_bulk():
            opt = p_var.get()
            if opt in bulk_unified_map:
                b_id, p_id, p_name = bulk_unified_map[opt]
                
                # Determine targets
                sel_target = target_var.get()
                targets = []
                
                if sel_target.startswith("Tất cả trang"):
                    targets = selected_indices
                    if not targets:
                        messagebox.showwarning("Cảnh báo", "Vui lòng tích chọn ít nhất một Fanpage để gán.")
                        return
                else:
                    g_name = sel_target.replace("Nhóm: ", "")
                    target_g_id = ""
                    for g in groups:
                        if g['name'] == g_name:
                            target_g_id = g['id']
                            break
                    if target_g_id:
                        targets = [idx for idx, p in enumerate(fanpages) if p.get('group_id') == target_g_id]
                    if not targets:
                        messagebox.showwarning("Cảnh báo", f"Không có Fanpage nào thuộc nhóm '{g_name}' để gán.")
                        return

                for i, idx in enumerate(targets):
                    is_last = (i == len(targets) - 1)
                    self.db.update_page_browser(idx, b_id, save=False)
                    self.db.update_page_profile(idx, p_id, p_name, save=is_last)
                    if hasattr(self, 'card_comboboxes') and idx in self.card_comboboxes:
                        try:
                            self.card_comboboxes[idx].set(opt)
                        except Exception:
                            pass
                
                self.log(f"Đã gán hàng loạt {opt} cho {len(targets)} Fanpage.")
                win.destroy()
            else:
                messagebox.showerror("Lỗi", "Vui lòng chọn một profile hợp lệ.")

        btn_frame = tk.Frame(main_frame)
        btn_frame.pack(fill="x", pady=20)
        tk.Button(btn_frame, text="Hủy", command=win.destroy, bg="#888", fg="white", width=10, relief="flat").pack(side="right", padx=5)
        tk.Button(btn_frame, text="Áp Dụng", command=apply_bulk, bg="#3a9a5c", fg="white", width=15, relief="flat", font=("Arial", 10, "bold")).pack(side="right", padx=5)

    # ── Log buffering: accumulate messages, flush periodically to avoid UI jank ──
    _log_buffer = []
    _log_flush_scheduled = False

    def log(self, message):
        timestamp = time.strftime("%H:%M:%S")
        msg = f"[{timestamp}] {message}\n"
        print(f"[{timestamp}] [LOG] {message}")

        if not hasattr(self, 'log_text'):
            return

        self._log_buffer.append(msg)
        if not self._log_flush_scheduled:
            self._log_flush_scheduled = True
            self.after(100, self._flush_log_buffer)

    def _flush_log_buffer(self):
        """Write all buffered log lines to log_text in one batch."""
        self._log_flush_scheduled = False
        if not self._log_buffer:
            return
        batch = "".join(self._log_buffer)
        self._log_buffer.clear()
        try:
            self.log_text.configure(state="normal")
            self.log_text.insert("end", batch)
            # Keep only last 2000 lines to prevent memory growth
            line_count = int(self.log_text.index("end-1c").split(".")[0])
            if line_count > 2000:
                self.log_text.delete("1.0", f"{line_count - 2000}.0")
            self.log_text.see("end")
            self.log_text.configure(state="disabled")
        except Exception:
            pass

    def write_thongke(self, message):
        log_file = "thongke_ngay.txt"
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {message}\n")

    def auto_map_folders_ui(self):
        # Ask for base directory
        base_dir = filedialog.askdirectory(title="Chọn thư mục chứa các folder video (vd: downloads)",
                                         initialdir=r"G:\Documentss\Antigravity_Gams_Youtubedownload\downloads")
        if not base_dir:
            return
            
        mapped_count, details = self.db.auto_map_folders(base_dir)
        
        if mapped_count > 0:
            msg = f"Đã tự động gán {mapped_count} folder mới cho các Fanpage.\n\nChi tiết:\n" + "\n".join(details[:10])
            if len(details) > 10:
                msg += f"\n... và {len(details)-10} page khác."
            messagebox.showinfo("Thành công", msg)
            self.refresh_ui()
        else:
            messagebox.showwarning("Thông báo", "Không tìm thấy folder nào khớp với tên Fanpage (hoặc các page đã có folder).")

    def view_comment_history(self):
        win = tk.Toplevel(self)
        win.title("Lịch Sử Comment")
        win.geometry("700x500")
        win.lift()
        win.focus_force()

        txt = scrolledtext.ScrolledText(win, font=("Consolas", 10))
        txt.pack(fill="both", expand=True, padx=10, pady=10)

        history = self.db.comment_history
        if not history:
            txt.insert("1.0", "Chưa có lịch sử comment nào.")
        else:
            text = ""
            for page, entries in history.items():
                text += f"=== Page: {page} ===\n"
                for entry in entries:
                    text += f"[{entry.get('timestamp')}] Video: {entry.get('video')} -> {entry.get('post_link')}\n"
                text += "\n"
            txt.insert("1.0", text)
        txt.configure(state="disabled")

    # ── Start / Stop ──────────────────────────────────────────

    def start_posting(self):
        self.stop_flag = False
        self.btn_start.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        threading.Thread(target=self._start_posting_thread, daemon=True).start()

    def stop_posting(self):
        self.stop_flag = True
        self.log("Stop requested. Đang dừng sau video hiện tại...")
        self.btn_stop.configure(state="disabled")

    def _start_posting_thread(self):
        try:
            self.db.reload()

            run_number = 0

            config = self.db.get_scheduling_config()
            loop_mode = config['loop_mode']
            loop_count = config['loop_count']
            rest_min = config['rest_min']
            rest_max = config['rest_max']
            time_start = config['time_start']
            time_end = config['time_end']

            import concurrent.futures
            
            while True:
                if self.stop_flag:
                    self.log("Đã dừng theo yêu cầu.")
                    break
                current_time = datetime.now().strftime("%H:%M")
                if not (time_start <= current_time <= time_end):
                    self.log(f"Ngoài khung giờ hoạt động ({time_start}-{time_end}). Hiện tại: {current_time}")
                    self.log(f"Chờ đến {time_start}...")
                    while not self.stop_flag:
                        current_time = datetime.now().strftime("%H:%M")
                        if time_start <= current_time <= time_end:
                            break
                        time.sleep(60)
                    if self.stop_flag:
                        break
                    self.log("Đã vào khung giờ hoạt động. Bắt đầu chạy...")

                run_number += 1

                if loop_mode == 'once':
                    self.log("Bắt đầu chạy 1 lần...")
                elif loop_mode == 'count':
                    self.log(f"Lần chạy {run_number}/{loop_count}...")
                else:
                    self.log(f"Vòng lặp #{run_number} (vô hạn)...")

                fanpages = self.db.get_fanpages()
                run_mode = self.db.get_run_mode()
                skip_commented = self.skip_commented_var.get()
                auto_delete = self.auto_delete_var.get()
                max_workers = self.db.get_max_parallel_workers()

                # ── Shopee mode: load product pool once per run ──────────────
                shopee_mode = self.shopee_mode_var.get()
                shopee_products = []   # shuffled pool for this session
                if shopee_mode:
                    shopee_file = self.shopee_file_path.get()
                    shopee_products = self.parse_shopee_file(shopee_file)
                    if shopee_products:
                        random.shuffle(shopee_products)
                        self.log(f"[Shopee] Đã tải {len(shopee_products)} sản phẩm từ file. Bắt đầu phân bổ...")
                    else:
                        self.log("[Shopee] ⚠️ Chế độ Rải Link bật nhưng file sản phẩm rỗng / không đọc được. Tắt chế độ Shopee phiên này.")
                        shopee_mode = False
                shopee_pool_index = 0   # pointer into shuffled pool

                enabled_pages = [p for p in fanpages if p.get('enabled', True)]
                if not enabled_pages:
                    self.log("Không có Fanpage nào được chọn để chạy.")
                else:
                    total_en = len(enabled_pages)
                    # ─── PHASE 1: PRE-SCAN (no browser needed) ─────────────────────────
                    self.log(f"Quét công việc của {total_en} Fanpage...")
                    
                    global_folders = self.db.get_global_folders()
                    profile_groups = {}  # key=(b_id, p_id), value=list of page work dicts
                    
                    for idx, page in enumerate(enabled_pages, 1):
                        if self.stop_flag: break
                        page_name = page.get('name', '?')
                        stt = f"[{idx}/{total_en}]"
                        page_folders = page.get('folders', [])
                        folders = list(set(page_folders + global_folders))
                        
                        if not folders:
                            self.log(f"{stt} [{page_name}] Bỏ qua (Chưa cấu hình thư mục video)")
                            continue
                        
                        unposted_files = []
                        to_comment_historic = []
                        
                        if run_mode != 'comment_only':
                            existing_logs = self.db.get_logs(page['link'])
                            posted_set = {log.get('video') for log in (existing_logs or [])
                                          if log.get('status', '') in ('Success', 'Uploaded', 'Uploaded (No Comment)')}
                            for folder in folders:
                                if os.path.exists(folder):
                                    try:
                                        v_files = [f for f in os.listdir(folder) if f.lower().endswith(('.mp4', '.mov', '.avi', '.mkv', '.webm'))]
                                        for vf in v_files:
                                            if vf not in posted_set:
                                                unposted_files.append([folder, vf])
                                    except: pass
                        
                        if run_mode == 'comment_only':
                            logs = self.db.get_logs(page['link'])
                            for log_entry in (logs or []):
                                v_name = log_entry.get('video', '')
                                if skip_commented and self.db.has_commented(page['link'], v_name):
                                    continue
                                to_comment_historic.append(v_name)
                        
                        has_work = bool(unposted_files) if run_mode != 'comment_only' else bool(to_comment_historic)
                        if not has_work:
                            self.log(f"{stt} [{page_name}] Bỏ qua (Không có bài mới cần đăng)")
                            continue
                        
                        # Group by (browser_id, profile_id)
                        # We need to find the REAL index of this page in self.db.get_fanpages()
                        p_idx = -1
                        for k, p_raw in enumerate(fanpages):
                            if p_raw['link'] == page['link']:
                                p_idx = k
                                break
                        
                        b_id = self.db.resolve_page_browser_id(p_idx) if p_idx != -1 else page.get('browser_id', 'gemlogin_default')
                        p_id = page.get('profile_id', '')
                        key = (b_id, p_id)
                        if key not in profile_groups:
                            profile_groups[key] = {
                                'pages': [],
                                'profile_name': page.get('profile_name', str(p_id))
                            }
                        
                        profile_groups[key]['pages'].append({
                            'name': page.get('name'),
                            'link': page.get('link'),
                            'group_id': page.get('group_id', ''),
                            'folders': folders,
                            'unposted_files': unposted_files,
                            'to_comment_historic': to_comment_historic,
                        })
                    
                    if not profile_groups:
                        self.log("Không có Fanpage nào có việc cần làm trong vòng này.")
                    else:
                        # ── PHASE 1b: Assign Shopee products — per-fanpage pool ──────
                        # Mỗi fanpage có pool riêng (shuffle độc lập).
                        # Không trùng STT trong cùng 1 fanpage,
                        # nhưng fanpage khác dùng lại thoải mái.
                        if shopee_mode and shopee_products:
                            shopee_all_groups = self.db.get_shopee_all_groups()
                            shopee_active_groups = self.db.get_shopee_groups()
                            
                            for key in profile_groups:
                                for pdata in profile_groups[key]['pages']:
                                    p_group_id = pdata.get('group_id', '')
                                    is_applied = False
                                    if shopee_all_groups:
                                        is_applied = bool(p_group_id)
                                    else:
                                        is_applied = bool(p_group_id and p_group_id in shopee_active_groups)
                                        
                                    unposted = pdata.get('unposted_files', [])
                                    if not unposted or not is_applied:
                                        pdata['shopee_assignment'] = {}
                                        if not is_applied:
                                            self.log(f"[Shopee] [{pdata['name']}] Bỏ qua rải link do nhóm '{p_group_id or '(Không nhóm)'}' không thuộc diện áp dụng.")
                                        continue

                                    # Shuffle toàn bộ pool cho fanpage này
                                    page_pool = shopee_products[:]
                                    random.shuffle(page_pool)

                                    assignment = {}
                                    for idx_v, (folder, vf) in enumerate(unposted):
                                        if idx_v >= len(page_pool):
                                            # Số video > số sản phẩm: vòng lại từ đầu
                                            page_pool_ext = shopee_products[:]
                                            random.shuffle(page_pool_ext)
                                            page_pool = page_pool + page_pool_ext
                                        prod = page_pool[idx_v]
                                        assignment[vf] = prod

                                    pdata['shopee_assignment'] = assignment
                                    names_log = ', '.join(
                                        f"#{p['stt']}:{p['name']}" for p in assignment.values()
                                    )
                                    self.log(f"[Shopee] [{pdata['name']}] Gán {len(assignment)} sản phẩm: {names_log}")

                        # Clear old process handles before starting new ones
                        self.active_procs = [p for p in self.active_procs if p.poll() is None]
                        
                        # Respect Max Parallel Workers
                        all_profile_keys = list(profile_groups.keys())
                        self.log(f"Phát hiện tổng cộng {len(all_profile_keys)} profile có việc.")
                        
                        # Process in chunks of max_workers
                        for i in range(0, len(all_profile_keys), max_workers):
                            chunk_keys = all_profile_keys[i:i + max_workers]
                            current_chunk_procs = []
                            
                            self.log(f"--- Đang chạy nhóm luồng {i//max_workers + 1} (Tối đa {max_workers} luồng song song) ---")
                            
                            for key in chunk_keys:
                                if self.stop_flag: break
                                b_id, p_id = key
                                group_data = profile_groups[key]
                                pages_for_profile = group_data['pages']
                                p_display_name = group_data['profile_name']
                                
                                b_config = self.db.get_browser_by_id(b_id)
                                if not b_config:
                                    self.log(f"Bỏ qua profile {p_id}: Không tìm thấy cấu hình browser.")
                                    continue
                                
                                # Get list of page names for logging
                                page_names_list = ", ".join([p['name'] for p in pages_for_profile])
                                
                                job = {
                                    'run_mode': run_mode,
                                    'skip_commented': skip_commented,
                                    'auto_delete': auto_delete,
                                    'browser_config': b_config,
                                    'profile_id': str(p_id),
                                    'profile_label': str(p_id),
                                    'pages': pages_for_profile,
                                    'shopee_mode': shopee_mode,
                                }
                                tmp = tempfile.NamedTemporaryFile(
                                    mode='w', suffix='.json', delete=False, encoding='utf-8',
                                    dir=_BASE_DIR, prefix=f'job_{p_id}_')
                                json.dump(job, tmp, ensure_ascii=False)
                                tmp.close()
                                
                                worker_script = os.path.join(_BASE_DIR, 'page_worker.py')
                                # Launch process
                                proc = subprocess.Popen(
                                    ['python', worker_script, tmp.name],
                                    creationflags=subprocess.CREATE_NEW_CONSOLE
                                )
                                self.active_procs.append(proc)
                                current_chunk_procs.append(proc)
                                self.log(f"🚀 [{p_display_name}] Đã mở CMD cho {len(pages_for_profile)} Fanpage: {page_names_list}")
                            
                            # Wait for CURRENT chunk to finish before starting next chunk (to respect max_workers)
                            if current_chunk_procs:
                                self.log(f"Đang chờ {len(current_chunk_procs)} CMD Worker của nhóm này hoàn tất...")
                                while not self.stop_flag:
                                    chunk_done = all(p.poll() is not None for p in current_chunk_procs)
                                    if chunk_done: break
                                    time.sleep(2)
                                
                            if self.stop_flag: break

                        self.log(f"===== Đã xử lý xong bộ {total_en} Fanpage =====")

                if self.stop_flag:
                    break

                if loop_mode == 'once':
                    self.log("Hoàn tất chạy 1 lần.")
                    break
                elif loop_mode == 'count' and run_number >= loop_count:
                    self.log(f"Đã hoàn tất {loop_count} lần chạy.")
                    break

                rest_seconds = random.randint(rest_min * 60, rest_max * 60)
                self.log(f"Nghỉ {rest_seconds // 60} phút trước lần chạy tiếp theo...")
                elapsed = 0
                while elapsed < rest_seconds and not self.stop_flag:
                    time.sleep(10)
                    elapsed += 10 # ADDED THIS BUG FIX TOO
        except Exception as global_e:
            self.log(f"!!! CRITICAL ERROR IN WORKER THREAD: {global_e}")
            import traceback
            print(traceback.format_exc())
            self.stop_flag = True
        finally:
            self.log("Hoàn tất.")
            self.is_running = False
            self.btn_start.configure(state="normal")
            self.btn_stop.configure(state="disabled")

    def _process_single_page(self, page, run_mode, skip_commented, auto_delete, is_last_for_profile=True):
        """Worker function for a single page execution in its own thread/browser session"""
        page_name = page.get('name', 'Page_Không_Tên')
        
        # 1. PRE-CHECK: Do we have folders or videos to process?
        page_folders = page.get('folders', [])
        global_folders = self.db.get_global_folders()
        folders = list(set(page_folders + global_folders))
        
        unposted_files = []
        to_comment_historic = []
        
        if not folders:
            self.log(f"[{page_name}] Bỏ qua (Chưa cấu hình thư mục video)")
            return

        # Check for unposted videos (if not 'comment_only')
        if run_mode != 'comment_only':
            existing_logs = self.db.get_logs(page['link'])
            posted_set = {log.get('video') for log in (existing_logs or []) 
                          if log.get('status', '') in ('Success', 'Uploaded', 'Uploaded (No Comment)')}
            
            for folder in folders:
                if os.path.exists(folder):
                    try:
                        v_files = [f for f in os.listdir(folder) if f.lower().endswith(('.mp4', '.mov', '.avi', '.mkv', '.webm'))]
                        for vf in v_files:
                            if vf not in posted_set:
                                unposted_files.append((folder, vf))
                    except: pass

        # Check for historic comments ONLY if in 'comment_only' mode
        if run_mode == 'comment_only':
            logs = self.db.get_logs(page['link'])
            for log_entry in (logs or []):
                v_name = log_entry.get('video', '')
                
                # Check if already commented
                if skip_commented and self.db.has_commented(page['link'], v_name):
                    continue
                
                to_comment_historic.append(v_name)

        # 2. DECIDE: Skip if no work
        if run_mode == 'post_and_comment' or run_mode == 'post_only':
            if not unposted_files:
                self.log(f"[{page_name}] Bỏ qua (Không có bài mới cần đăng)")
                return
        elif run_mode == 'comment_only':
            if not to_comment_historic:
                self.log(f"[{page_name}] Bỏ qua (Không có bài cũ cần comment)")
                return

        # 3. IF WORK EXISTS, THEN START BROWSER
        self.log(f"[{page_name}] Đang khởi tạo...")
        
        target_b_id = page.get('browser_id', 'gemlogin_default')
        target_p_id = page.get('profile_id', '')
        
        b_config = self.db.get_browser_by_id(target_b_id)
        if not b_config:
            self.log(f"[{page_name}] LỖI: Không tìm thấy cấu hình trình duyệt.")
            return

        api = GemLoginAPI(b_config['api_url']) if b_config['type'] == 'gemlogin' else GPMLoginAPI(b_config['api_url'])
            
        # Determine profile
        p_id = target_p_id
        if not p_id:
            profile = api.find_profile_by_name("Đăng bài Fanpage + comment")
            if profile:
                p_id = profile['id'] if isinstance(profile, dict) else profile.get('id')
        
        if not p_id:
            self.log(f"[{page_name}] LỖI: Không tìm thấy profile phù hợp.")
            return

        # Start browser
        launch_data = api.start_profile(p_id)
        if not launch_data or not launch_data.get('success'):
            self.log(f"[{page_name}] Khởi động lỗi, thử force-close trình duyệt...")
            try:
                api.stop_profile(p_id)
                time.sleep(2)
            except: pass
            launch_data = api.start_profile(p_id)
            
        if not launch_data or not launch_data.get('success'):
            err_msg = f"LỖI: Không thể mở trình duyệt ({b_config['type']})."
            if not launch_data:
                err_msg += f" (Không có phản hồi từ API: {b_config['api_url']})"
            else:
                err_msg += f" (API trả về lỗi: {launch_data.get('message', 'Unknown')})"
            self.log(f"[{page_name}] {err_msg} Profile ID: {p_id}")
            return
            
        try:
            data_content = launch_data.get('data', {}) if isinstance(launch_data.get('data'), dict) else {}
            debugger_address = data_content.get('remote_debugging_address') or data_content.get('debugger_address')
            driver_path = data_content.get('driver_path')
            
            from facebook_automator import FacebookAutomator
            strats = self.db.get_comment_strategies()
            automator = FacebookAutomator(debugger_address, driver_path, strats)
            self.log(f"[{page_name}] Đã kết nối trình duyệt.")
            
            # --- EXECUTION LOGIC ---
            # Resolve actual browser settings (Group or Individual)
            # Find the index of this page in the DB
            fanpages = self.db.get_fanpages()
            p_idx = -1
            for k, p in enumerate(fanpages):
                if p['link'] == page['link']:
                    p_idx = k
                    break
            
            # Use resolved browser ID if we found the page
            effective_b_id = target_b_id
            if p_idx != -1:
                effective_b_id = self.db.resolve_page_browser_id(p_idx)
            
            b_config = self.db.get_browser_by_id(effective_b_id)
            if not b_config:
                self.log(f"[{page_name}] LỖI: Không tìm thấy cấu hình browser (Resolved: {effective_b_id})")
                return

            api = GemLoginAPI(b_config['api_url']) if b_config['type'] == 'gemlogin' else GPMLoginAPI(b_config['api_url'])

            min_v, max_v = self.db.get_global_video_limits()
            if min_v > max_v: min_v = max_v
            
            # Phase 1: Commenting phase
            if to_comment_historic:
                self.log(f"[{page_name}] Sẽ comment {len(to_comment_historic)} bài cũ.")
                asset_id = automator.resolve_asset_id(page['link'])
                if asset_id:
                    comment_template = self.db.get_effective_comment_template(page['link'])
                    if comment_template.strip():
                        for video_name in to_comment_historic:
                            if self.stop_flag: break
                            title = os.path.splitext(video_name)[0]
                            ok, link = automator.comment_with_dual_strategy(asset_id, title, comment_template)
                            if ok:
                                self.db.add_comment_history(page['link'], video_name, link or '')
                                self.log(f"[{page_name}] Comment thành công: {video_name}")
                    else:
                        self.log(f"[{page_name}] Mẫu bình luận rỗng. Bỏ qua comment bài viết cũ.")
            
            # Phase 2: Posting phase (and immediate comments)
            if run_mode != 'comment_only' and unposted_files:
                import random
                num_videos = random.randint(min_v, max_v)
                batch_to_post = unposted_files[:num_videos]
                self.log(f"[{page_name}] Đăng {len(batch_to_post)} video mới.")
                
                asset_id = automator.resolve_asset_id(page['link'])
                if asset_id:
                    bulk_batch = []
                    for folder, video_file in batch_to_post:
                        full_p = os.path.join(folder, video_file)
                        title = os.path.splitext(video_file)[0]
                        bulk_batch.append((full_p, title))
                        
                    result = automator.upload_reels_bulk(asset_id, bulk_batch)
                    if "Uploaded Bulk" in result:
                        fanpages = self.db.get_fanpages()
                        p_idx = next((idx for idx, p in enumerate(fanpages) if p['link'] == page['link']), -1)
                        
                        # Loop 1: Immediate Database Logs & File Deletion
                        for folder, video_file in batch_to_post:
                            full_p = os.path.join(folder, video_file)
                            if p_idx != -1:
                                self.db.add_log(p_idx, video_file, "Uploaded", "Success")
                            
                            if auto_delete:
                                try:
                                    os.remove(full_p)
                                    self.log(f"[{page_name}] ✓ Đã xóa video sau khi đăng: {video_file}")
                                except Exception as de:
                                    self.log(f"[{page_name}] ! Không thể xóa video: {video_file} ({de})")
                        
                        # Loop 2: Sequential Commenting (if enabled)
                        if run_mode == 'post_and_comment':
                            comment_template = self.db.get_effective_comment_template(page['link'])
                            if comment_template.strip():
                                for folder, video_file in batch_to_post:
                                    time.sleep(10) # Trả lại 10s cho an toàn sau khi load xong post FB
                                    title = os.path.splitext(video_file)[0]
                                    ok, link = automator.comment_with_dual_strategy(asset_id, title, comment_template)
                                    if ok:
                                        self.db.add_comment_history(page['link'], video_file, link or '')
                                        self.log(f"[{page_name}] Comment post mới thành công: {video_file}")
                            else:
                                self.log(f"[{page_name}] Mẫu bình luận rỗng. Bỏ qua comment bài viết mới.")
        except Exception as e:
            self.log(f"[{page_name}] LỖI luồng: {e}")
        finally:
            if self.stop_flag or is_last_for_profile:
                self.log(f"[{page_name}] Đang dọn dẹp và đóng hẳn trình duyệt...")
                try:
                    api.stop_profile(p_id)
                except: pass
            else:
                self.log(f"[{page_name}] Giữ trình duyệt mở cho Fanpage chung profile kế tiếp...")

        self.log("Hoàn tất.")

    def _refresh_global_folders_ui(self):
        for widget in self.global_list_frame.winfo_children():
            widget.destroy()
            
        folders = self.db.get_global_folders()
        if not folders:
            tk.Label(self.global_list_frame, text="(Chưa có thư mục chung nào)", 
                     font=("Arial", 9, "italic"), bg="#ffffff", fg="#888").pack(pady=5)
            return
            
        for i, path in enumerate(folders):
            f = tk.Frame(self.global_list_frame, bg="#ffffff")
            f.pack(fill="x", pady=1)
            tk.Label(f, text=f"• {path}", bg="#ffffff", font=("Arial", 9), anchor="w").pack(side="left", fill="x", expand=True)
            tk.Button(f, text="x", bg="#ffffff", fg="red", relief="flat", bd=0, cursor="hand2",
                      command=lambda idx=i: self.remove_global_folder_ui(idx)).pack(side="right")

    def add_global_folder_ui(self):
        path = filedialog.askdirectory()
        if path:
            self.db.add_global_folder(path)
            self._refresh_global_folders_ui()

    def remove_global_folder_ui(self, index):
        self.db.remove_global_folder(index)
        self._refresh_global_folders_ui()


    def group_management_ui(self):
        win = tk.Toplevel(self)
        win.title("Quản Lý Nhóm Fanpage")
        win.geometry("650x500")
        win.attributes("-topmost", True)

        main_frame = tk.Frame(win, padx=15, pady=15)
        main_frame.pack(fill="both", expand=True)

        tk.Label(main_frame, text="Danh Sách Nhóm", font=("Arial", 12, "bold")).pack(anchor="w", pady=(0, 10))

        list_frame = tk.Frame(main_frame)
        list_frame.pack(fill="both", expand=True)

        def get_unified_profiles():
            browsers = self.db.get_browsers()
            all_opts = []
            unified_map = {}
            if not hasattr(self, '_profile_cache'): self._profile_cache = {}
            for b in browsers:
                b_id = b['id']
                b_name = b['name']
                profiles = self._profile_cache.get(b_id, [])
                for p in profiles:
                    p_name = p.get('name', p.get('title', p.get('profile_name', 'Unknown')))
                    p_id = p.get('id', p.get('profile_id'))
                    opt = f"[{b_name}] {p_name}"
                    all_opts.append(opt)
                    unified_map[opt] = (b_id, p_id, p_name)
            return all_opts, unified_map

        def refresh_list():
            for widget in list_frame.winfo_children():
                widget.destroy()
            
            groups = self.db.get_groups()
            if not groups:
                tk.Label(list_frame, text="(Chưa có nhóm nào)", font=("Arial", 10, "italic"), fg="#888").pack(pady=20)
            
            for g in groups:
                g_row = tk.Frame(list_frame, pady=5, bg="#f9f9f9", relief="flat")
                g_row.pack(fill="x", pady=2)

                tk.Label(g_row, text="Tên nhóm:", bg="#f9f9f9").pack(side="left", padx=(10, 5))
                name_ent = tk.Entry(g_row, width=20)
                name_ent.insert(0, g['name'])
                name_ent.pack(side="left", padx=5)

                tk.Label(g_row, text="Profile mặc định:", bg="#f9f9f9").pack(side="left", padx=(10, 5))
                
                unified_opts, unified_map = get_unified_profiles()
                
                # Find current opt
                curr_b_id = g.get('browser_id')
                curr_p_id = g.get('profile_id')
                found_opt = ""
                for opt, (b_id, p_id, p_name) in unified_map.items():
                    if b_id == curr_b_id and str(p_id) == str(curr_p_id):
                        found_opt = opt
                        break
                
                if not found_opt and curr_b_id and curr_p_id:
                    # Fallback to stored name
                    b_config = self.db.get_browser_by_id(curr_b_id)
                    b_name_str = b_config['name'] if b_config else "Unknown"
                    found_opt = f"[{b_name_str}] {g.get('profile_name', 'Unknown')}"
                    unified_opts.append(found_opt)
                    unified_map[found_opt] = (curr_b_id, curr_p_id, g.get('profile_name', 'Unknown'))
                
                b_var = tk.StringVar(value=found_opt)
                b_combo = ttk.Combobox(g_row, textvariable=b_var, values=unified_opts, state="readonly", width=30)
                b_combo.pack(side="left", padx=5)
                self._disable_combo_scroll(b_combo, redirect_to_canvas=False)

                def make_save(gid=g['id'], n_ent=name_ent, bv=b_var, umap=unified_map):
                    def _s():
                        new_name = n_ent.get().strip()
                        opt = bv.get()
                        if opt in umap:
                            b_id, p_id, p_name = umap[opt]
                        else:
                            b_id, p_id, p_name = "gemlogin_default", "", ""
                        
                        self.db.update_group(gid, new_name, b_id, p_id, p_name)
                        self.log(f"Đã cập nhật nhóm: {new_name}")
                        refresh_list()
                        self.refresh_ui()
                    return _s

                def make_del(gid=g['id'], name=g['name']):
                    def _d():
                        if messagebox.askyesno("Xác nhận", f"Xóa nhóm '{name}'? Các Fanpage trong nhóm sẽ về trạng thái không nhóm."):
                            self.db.remove_group(gid)
                            self.log(f"Đã xóa nhóm: {name}")
                            refresh_list()
                    return _d

                btn_save = tk.Button(g_row, text="Lưu", command=make_save(), padx=6)
                btn_save.pack(side="left", padx=5)
                self.style_button(btn_save, "#2e7d32", "#225c25")
                
                def open_assign(gid=g['id'], name=g['name']):
                    return lambda: self.assign_fanpages_to_group_ui(gid, name, refresh_callback=refresh_list)
                
                btn_assign = tk.Button(g_row, text="Gán Fanpage", command=open_assign(), padx=6)
                btn_assign.pack(side="left", padx=5)
                self.style_button(btn_assign, "#7c5cbf", "#6242a3")
                
                btn_del = tk.Button(g_row, text="Xóa", command=make_del(), padx=6)
                btn_del.pack(side="left", padx=5)
                self.style_button(btn_del, "#d32f2f", "#b71c1c")

            # Add new group row
            ttk.Separator(list_frame).pack(fill="x", pady=15)
            add_row = tk.Frame(list_frame)
            add_row.pack(fill="x", pady=5)
            
            tk.Label(add_row, text="Tên nhóm mới:", font=("Arial", 10, "bold")).pack(side="left", padx=(0, 5))
            new_name_ent = tk.Entry(add_row, width=20)
            new_name_ent.pack(side="left", padx=5)
            
            def add_new():
                name = new_name_ent.get().strip()
                if name:
                    self.db.add_group(name)
                    self.log(f"Đã thêm nhóm mới: {name}")
                    refresh_list()
                else:
                    messagebox.showwarning("Cảnh báo", "Vui lòng nhập tên nhóm.")

            btn_add = tk.Button(add_row, text="+ Thêm Nhóm", command=add_new, padx=10, pady=2)
            btn_add.pack(side="left", padx=10)
            self.style_button(btn_add, "#7b1fa2", "#5e157d")

        refresh_list()

        def on_close():
            self.refresh_ui()
            win.destroy()

        footer = tk.Frame(main_frame)
        footer.pack(side="bottom", pady=10)
        
        btn_close = tk.Button(footer, text="Đóng", command=on_close, width=10, pady=5)
        btn_close.pack()
        self.style_button(btn_close, "#5f6368", "#474a4d")
        win.protocol("WM_DELETE_WINDOW", on_close)
        win.protocol("WM_DELETE_WINDOW", on_close)

    def assign_fanpages_to_group_ui(self, group_id, group_name, refresh_callback):
        win = tk.Toplevel(self)
        win.title(f"Gán Fanpage vào nhóm: {group_name}")
        win.geometry("500x600")
        win.attributes("-topmost", True)

        main_frame = tk.Frame(win, padx=15, pady=15)
        main_frame.pack(fill="both", expand=True)

        tk.Label(main_frame, text=f"Chọn Fanpage cho nhóm '{group_name}'", font=("Arial", 11, "bold")).pack(anchor="w", pady=(0, 10))

        # Scrollable area for fanpage list
        canvas_frame = tk.Frame(main_frame)
        canvas_frame.pack(fill="both", expand=True)
        
        canvas = tk.Canvas(canvas_frame)
        scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        fanpages = self.db.get_fanpages()
        vars = [] # List of (index, var)
        
        for i, page in enumerate(fanpages):
            is_in_group = page.get('group_id') == group_id
            var = tk.BooleanVar(value=is_in_group)
            vars.append((i, var))
            
            p_row = tk.Frame(scrollable_frame, pady=2)
            p_row.pack(fill="x", anchor="w")
            
            p_name = f"#{i+1} - " + (page.get('name') or page.get('link'))
            cb = tk.Checkbutton(p_row, text=p_name, variable=var)
            cb.pack(side="left")
            
            if page.get('group_id') and page.get('group_id') != group_id:
                # Find other group name
                other_name = "Nhóm khác"
                for g in self.db.get_groups():
                    if g['id'] == page.get('group_id'):
                        other_name = g['name']
                        break
                tk.Label(p_row, text=f"(Đang ở: {other_name})", font=("Arial", 8, "italic"), fg="#888").pack(side="left", padx=5)

        def save_assignment():
            selected_indices = [idx for idx, var in vars if var.get()]
            
            # Clear this group_id from all pages that were in it but now are not
            all_pages = self.db.get_fanpages()
            for i, page in enumerate(all_pages):
                if page.get('group_id') == group_id:
                    if i not in selected_indices:
                        self.db.update_page_group(i, "", save=False)
            
            # Now assign selected (update_pages_group_bulk will call self.save())
            self.db.update_pages_group_bulk(selected_indices, group_id)
            
            self.log(f"Đã cập nhật Fanpage cho nhóm '{group_name}'")
            if refresh_callback: refresh_callback()
            self.refresh_ui()
            win.destroy()

        btn_frame = tk.Frame(main_frame)
        btn_frame.pack(side="bottom", pady=10)
        tk.Button(btn_frame, text="Hủy", command=win.destroy, bg="#888", fg="white", width=10, relief="flat").pack(side="right", padx=5)
        tk.Button(btn_frame, text="Lưu Thay Đổi", command=save_assignment, bg="#3a9a5c", fg="white", width=15, relief="flat", font=("Arial", 10, "bold")).pack(side="right", padx=5)


    def on_app_exit(self):
        """ Cleanup all related processes before exiting """
        self.stop_flag = True
        self.log("Đang đóng ứng dụng, các tiến trình worker vẫn sẽ được giữ lại theo yêu cầu...")
        
        # We no longer terminate self.active_procs or run psutil cleanup here
        # so that worker CMDs and browsers will remain running even if the GUI is closed.
        
        self.destroy()
        sys.exit(0)


if __name__ == "__main__":
    app = App()
    app.mainloop()

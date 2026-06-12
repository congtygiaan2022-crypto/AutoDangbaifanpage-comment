# -*- coding: utf-8 -*-
import os
import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
import json
import subprocess
import tempfile
import random
from datetime import datetime
import time
import webbrowser
import psutil

# Force Python to use UTF-8 for all I/O (fixes Vietnamese mojibake on cp1252 Windows)
os.environ["PYTHONUTF8"] = "1"
os.environ["PYTHONIOENCODING"] = "utf-8"

# Đảm bảo thư mục làm việc luôn là thư mục chứa gui.py (cần thiết khi double-click)
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(_BASE_DIR)
if _BASE_DIR not in sys.path:
    sys.path.insert(0, _BASE_DIR)

from database import Database
from gemlogin_api import GemLoginAPI
from gpmlogin_api import GPMLoginAPI
from facebook_automator import FacebookAutomator

class App(tk.Tk):
    def __init__(self, db_file="database.json", sqlite_file="system.db", profile_name="Profile 1"):
        super().__init__()
        
        # Configure SQLite database path dynamically
        from db_helper import db as sqlite_db
        sqlite_db.db_path = sqlite_file
        
        # Verify schema
        from init_db import init_db
        try:
            init_db(sqlite_file)
        except: pass
        
        self.db = Database(db_file)
        self.profile_name = profile_name
        self.title(f"Gams - Auto Post Reel Fanpage v130626 - [{profile_name}]")
        self.geometry("1200x750")
        self.minsize(1050, 650)

        self.automator = None
        self.stop_flag = False
        self.active_procs = [] # Track worker subprocesses

        # Background caching structures for smooth non-blocking UI
        self._profile_cache = {}
        self._unified_profile_options = []
        self._unified_profile_map = {}
        
        # Selection states
        self.current_selected_page_idx = None
        self.tree_item_to_idx = {}

        # Shopee mode state
        self.shopee_mode_var = tk.BooleanVar(value=self.db.get_shopee_mode())
        self.shopee_file_path = tk.StringVar(value=self.db.get_shopee_file())

        # Options variables
        self.skip_commented_var = tk.BooleanVar(value=self.db.get_skip_commented())
        self.auto_delete_var = tk.BooleanVar(value=self.db.get_auto_delete_videos())

        # Setup design systems & styles
        self._setup_styles()
        
        # Build layout
        self._build_ui()
        self.refresh_ui()

        # Hook close event
        self.protocol("WM_DELETE_WINDOW", self.on_app_exit)

    def _setup_styles(self):
        # Configure fonts
        self.font_main = ("Segoe UI", 9)
        self.font_bold = ("Segoe UI", 9, "bold")
        self.font_title = ("Segoe UI", 12, "bold")
        self.font_header = ("Segoe UI", 10, "bold")
        
        # Base colors
        self.bg_color = "#f8f9fa"
        self.fg_color = "#202124"
        self.accent_color = "#1a73e8"
        self.border_color = "#dadce0"
        
        self.configure(bg=self.bg_color)
        
        # Configure styles
        self.style = ttk.Style(self)
        self.style.theme_use('vista')
        
        # Notebook styling
        self.style.configure('TNotebook', background=self.bg_color, tabmargins=[2, 5, 2, 0])
        self.style.configure('TNotebook.Tab', font=self.font_bold, padding=[15, 6], background="#e8eaed", foreground="#5f6368")
        self.style.map('TNotebook.Tab',
                       background=[('selected', '#ffffff'), ('active', '#f1f3f4')],
                       foreground=[('selected', self.accent_color)])
        
        # Treeview styling
        self.style.configure('Treeview', font=self.font_main, rowheight=24, background='#ffffff', fieldbackground='#ffffff', bordercolor=self.border_color, borderwidth=1)
        self.style.configure('Treeview.Heading', font=self.font_bold, background='#f1f3f4', foreground='#3c4043')
        self.style.map('Treeview',
                       background=[('selected', '#e8f0fe')],
                       foreground=[('selected', '#1a73e8')])
        
        # Combobox styling
        self.style.configure('TCombobox', font=self.font_main)

    def _build_ui(self):
        # Master Notebook
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Tab 1: Dashboard & Live Logs
        self.tab_dashboard = tk.Frame(self.notebook, bg=self.bg_color)
        self.notebook.add(self.tab_dashboard, text="🖥️ Bảng Điều Khiển")
        self._build_dashboard_tab()
        
        # Tab 2: Fanpage Manager (Master-Detail Layout)
        self.tab_fanpages = tk.Frame(self.notebook, bg=self.bg_color)
        self.notebook.add(self.tab_fanpages, text="👥 Quản Lý Fanpage")
        self._build_fanpage_tab()
        
        # Tab 3: System Configs
        self.tab_settings = tk.Frame(self.notebook, bg=self.bg_color)
        self.notebook.add(self.tab_settings, text="⚙️ Cấu Hình Hệ Thống")
        self._build_settings_tab()

    # ─── TAB 1: DASHBOARD & LOGS ──────────────────────────────
    def _build_dashboard_tab(self):
        # Outer grid
        pane = tk.PanedWindow(self.tab_dashboard, orient=tk.HORIZONTAL, bg="#d9d9d9", sashwidth=5, sashrelief=tk.RAISED)
        pane.pack(fill="both", expand=True)
        
        # Left control panel (Scrollable)
        left_scroll = tk.Canvas(pane, bg=self.bg_color, highlightthickness=0)
        left_scrollbar = ttk.Scrollbar(pane, orient="vertical", command=left_scroll.yview)
        left_scroll.configure(yscrollcommand=left_scrollbar.set)
        
        left_col = tk.Frame(left_scroll, bg=self.bg_color, padx=10, pady=10)
        left_scroll.create_window((0, 0), window=left_col, anchor="nw")
        
        def on_left_configure(event):
            left_scroll.configure(scrollregion=left_scroll.bbox("all"))
            left_scroll.itemconfig(1, width=event.width)
        left_scroll.bind("<Configure>", on_left_configure)
        
        # Hook mouse wheel
        left_scroll.bind("<MouseWheel>", lambda e: left_scroll.yview_scroll(int(-1 * (e.delta / 120)), "units"))
        left_scroll.bind("<Enter>", lambda e: left_scroll.bind_all("<MouseWheel>", lambda ev: left_scroll.yview_scroll(int(-1 * (ev.delta / 120)), "units")))
        left_scroll.bind("<Leave>", lambda e: left_scroll.unbind_all("<MouseWheel>"))

        # Right Log Frame
        right_log_frame = tk.Frame(pane, bg="#f0f0f0")
        
        # Add panes
        pane.add(left_scroll, width=420)
        pane.add(right_log_frame, minsize=400)
        
        # 1. Status Display Box
        self.status_frame = tk.Frame(left_col, bg=self.bg_color, pady=5)
        self.status_frame.pack(fill="x", pady=(0, 10))
        self.status_lbl = tk.Label(self.status_frame, text="● HỆ THỐNG ĐANG DỪNG", font=("Segoe UI", 12, "bold"), fg="#c0392b", bg="#fadbd8", bd=1, relief="solid", pady=10)
        self.status_lbl.pack(fill="x")
        
        # 2. Execution Mode & Speed Group
        exec_group = tk.LabelFrame(left_col, text=" ⚙️ Thiết Lập Chạy ", font=self.font_bold, bg="#ffffff", bd=1, relief="solid", padx=10, pady=10)
        exec_group.pack(fill="x", pady=5)
        
        tk.Label(exec_group, text="Chế độ chạy:", bg="#ffffff", font=self.font_bold).grid(row=0, column=0, sticky="w", pady=4)
        self.run_mode_var = tk.StringVar()
        mode_map = {"post_and_comment": "Đăng + Comment", "post_only": "Chỉ Đăng", "comment_only": "Chỉ Comment"}
        self.run_mode_var.set(mode_map.get(self.db.get_run_mode(), "Đăng + Comment"))
        
        mode_combo = ttk.Combobox(exec_group, textvariable=self.run_mode_var, values=["Đăng + Comment", "Chỉ Đăng", "Chỉ Comment"], state="readonly", width=22)
        mode_combo.grid(row=0, column=1, sticky="w", padx=10, pady=4)
        mode_combo.bind("<<ComboboxSelected>>", self._on_mode_change)
        
        tk.Label(exec_group, text="Số luồng chạy song song:", bg="#ffffff", font=self.font_bold).grid(row=1, column=0, sticky="w", pady=4)
        
        # Syncing parallel workers count on change
        self.parallel_workers_var = tk.StringVar(value=str(self.db.get_max_parallel_workers()))
        def save_workers_count(event=None):
            try:
                cnt = int(self.parallel_workers_var.get())
                if cnt > 0:
                    self.db.set_max_parallel_workers(cnt)
                    self.log(f"Cập nhật số luồng song song: {cnt}")
            except:
                pass
        
        workers_spin = tk.Spinbox(exec_group, from_=1, to=20, textvariable=self.parallel_workers_var, width=10, bd=1, relief="solid")
        workers_spin.grid(row=1, column=1, sticky="w", padx=10, pady=4)
        workers_spin.bind("<FocusOut>", save_workers_count)
        workers_spin.bind("<Return>", save_workers_count)
        
        # Quick loop options
        tk.Label(exec_group, text="Cách thức lặp:", bg="#ffffff", font=self.font_bold).grid(row=2, column=0, sticky="w", pady=4)
        config = self.db.get_scheduling_config()
        self.dashboard_loop_var = tk.StringVar(value=config['loop_mode'])
        
        def save_dash_loop():
            self.db.set_scheduling_config(
                self.dashboard_loop_var.get(),
                int(self.dashboard_loop_count_ent.get() or 1),
                int(self.dashboard_rest_min_ent.get() or 30),
                int(self.dashboard_rest_max_ent.get() or 60),
                self.dashboard_time_start_ent.get() or '00:00',
                self.dashboard_time_end_ent.get() or '23:59'
            )
            self.log(f"Đã cập nhật chế độ lặp: {self.dashboard_loop_var.get()}")
            self._update_scheduler_widgets_visibility()
            
        loop_opts_frame = tk.Frame(exec_group, bg="#ffffff")
        loop_opts_frame.grid(row=2, column=1, sticky="w", padx=10, pady=4)
        tk.Radiobutton(loop_opts_frame, text="1 Lần", variable=self.dashboard_loop_var, value="once", bg="#ffffff", command=save_dash_loop).pack(side="left")
        tk.Radiobutton(loop_opts_frame, text="Vô hạn", variable=self.dashboard_loop_var, value="infinite", bg="#ffffff", command=save_dash_loop).pack(side="left", padx=5)
        tk.Radiobutton(loop_opts_frame, text="N Lần:", variable=self.dashboard_loop_var, value="count", bg="#ffffff", command=save_dash_loop).pack(side="left")
        
        self.dashboard_loop_count_ent = tk.Entry(loop_opts_frame, width=5, bd=1, relief="solid")
        self.dashboard_loop_count_ent.insert(0, str(config['loop_count']))
        self.dashboard_loop_count_ent.pack(side="left", padx=2)
        self.dashboard_loop_count_ent.bind("<FocusOut>", lambda e: save_dash_loop())
        
        # Rest and time window
        self.dash_sched_frame = tk.Frame(exec_group, bg="#ffffff")
        self.dash_sched_frame.grid(row=3, column=0, columnspan=2, sticky="ew", pady=5)
        
        tk.Label(self.dash_sched_frame, text="Nghỉ giữa lượt (phút):", bg="#ffffff", font=self.font_bold).grid(row=0, column=0, sticky="w", pady=2)
        rest_inputs = tk.Frame(self.dash_sched_frame, bg="#ffffff")
        rest_inputs.grid(row=0, column=1, sticky="w", padx=10, pady=2)
        self.dashboard_rest_min_ent = tk.Entry(rest_inputs, width=5, bd=1, relief="solid")
        self.dashboard_rest_min_ent.insert(0, str(config['rest_min']))
        self.dashboard_rest_min_ent.pack(side="left")
        self.dashboard_rest_min_ent.bind("<FocusOut>", lambda e: save_dash_loop())
        
        tk.Label(rest_inputs, text="đến", bg="#ffffff").pack(side="left", padx=2)
        
        self.dashboard_rest_max_ent = tk.Entry(rest_inputs, width=5, bd=1, relief="solid")
        self.dashboard_rest_max_ent.insert(0, str(config['rest_max']))
        self.dashboard_rest_max_ent.pack(side="left")
        self.dashboard_rest_max_ent.bind("<FocusOut>", lambda e: save_dash_loop())
        
        tk.Label(self.dash_sched_frame, text="Khung giờ hoạt động:", bg="#ffffff", font=self.font_bold).grid(row=1, column=0, sticky="w", pady=2)
        time_inputs = tk.Frame(self.dash_sched_frame, bg="#ffffff")
        time_inputs.grid(row=1, column=1, sticky="w", padx=10, pady=2)
        self.dashboard_time_start_ent = tk.Entry(time_inputs, width=6, bd=1, relief="solid")
        self.dashboard_time_start_ent.insert(0, config['time_start'])
        self.dashboard_time_start_ent.pack(side="left")
        self.dashboard_time_start_ent.bind("<FocusOut>", lambda e: save_dash_loop())
        
        tk.Label(time_inputs, text="đến", bg="#ffffff").pack(side="left", padx=2)
        
        self.dashboard_time_end_ent = tk.Entry(time_inputs, width=6, bd=1, relief="solid")
        self.dashboard_time_end_ent.insert(0, config['time_end'])
        self.dashboard_time_end_ent.pack(side="left")
        self.dashboard_time_end_ent.bind("<FocusOut>", lambda e: save_dash_loop())
        
        self._update_scheduler_widgets_visibility()

        # 3. Quick Options
        opts_group = tk.LabelFrame(left_col, text=" 💡 Tùy Chọn Đăng ", font=self.font_bold, bg="#ffffff", bd=1, relief="solid", padx=10, pady=10)
        opts_group.pack(fill="x", pady=5)
        
        tk.Checkbutton(opts_group, text="Bỏ qua video đã comment trước đó", variable=self.skip_commented_var, bg="#ffffff",
                       command=lambda: self.db.set_skip_commented(self.skip_commented_var.get())).pack(anchor="w", pady=2)
        tk.Checkbutton(opts_group, text="Tự động xóa video khỏi thư mục sau khi đăng thành công", variable=self.auto_delete_var, bg="#ffffff",
                       command=self.toggle_auto_delete).pack(anchor="w", pady=2)

        # 4. Shopee mode configuration
        shopee_group = tk.LabelFrame(left_col, text=" 🛒 Rải Link Tiếp Thị Shopee ", font=self.font_bold, bg="#ffffff", fg="#e07b39", bd=1, relief="solid", padx=10, pady=10)
        shopee_group.pack(fill="x", pady=5)
        
        def on_shopee_toggle():
            self.db.set_shopee_mode(self.shopee_mode_var.get())
            state = "BẬT" if self.shopee_mode_var.get() else "TẮT"
            self.log(f"Chế độ Rải Link Shopee: {state}")
            self._update_shopee_ui_state()
            
        tk.Checkbutton(shopee_group, text="Kích hoạt rải link affiliate Shopee", variable=self.shopee_mode_var,
                       fg="#e07b39", selectcolor="#fff8f0", bg="#ffffff", font=self.font_bold,
                       command=on_shopee_toggle).pack(anchor="w", pady=(0, 5))
                       
        shopee_details = tk.Frame(shopee_group, bg="#ffffff")
        shopee_details.pack(fill="x", pady=2)
        
        # File selector row
        tk.Label(shopee_details, text="File sản phẩm:", bg="#ffffff", font=self.font_bold).grid(row=0, column=0, sticky="w", pady=4)
        shopee_file_row = tk.Frame(shopee_details, bg="#ffffff")
        shopee_file_row.grid(row=0, column=1, sticky="w", padx=10, pady=4)
        
        self.lbl_shopee_file = tk.Label(shopee_file_row, textvariable=self.shopee_file_path, bg="#ffffff", font=("Segoe UI", 8), fg="#555", width=20, anchor="w")
        self.lbl_shopee_file.pack(side="left")
        
        def pick_shopee_file():
            path = filedialog.askopenfilename(title="Chọn file danh sách sản phẩm Shopee", filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
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
                
        btn_pick_sh = tk.Button(shopee_file_row, text="📂 Chọn", command=pick_shopee_file, font=("Segoe UI", 8), padx=5, pady=1)
        btn_pick_sh.pack(side="left", padx=2)
        self.style_button(btn_pick_sh, "#e07b39", "#be5f23")
        
        btn_open_sh = tk.Button(shopee_file_row, text="✏️ Sửa", command=open_shopee_file, font=("Segoe UI", 8), padx=5, pady=1)
        btn_open_sh.pack(side="left")
        self.style_button(btn_open_sh, "#5f6368", "#474a4d")
        
        # Groups dropdown row
        tk.Label(shopee_details, text="Nhóm áp dụng:", bg="#ffffff", font=self.font_bold).grid(row=1, column=0, sticky="w", pady=4)
        
        self.shopee_all_groups_var = tk.BooleanVar(value=self.db.get_shopee_all_groups())
        self.shopee_group_vars = {}
        
        self.btn_shopee_groups = tk.Menubutton(shopee_details, text="Đang tải...", relief="raised", bd=1, bg="#ffffff", cursor="hand2", font=("Segoe UI", 8))
        self.btn_shopee_groups.grid(row=1, column=1, sticky="w", padx=10, pady=4)
        
        self.shopee_group_menu = tk.Menu(self.btn_shopee_groups, tearoff=0, postcommand=self.rebuild_shopee_group_menu)
        self.btn_shopee_groups["menu"] = self.shopee_group_menu
        self.update_shopee_groups_button_text()
        
        # Save references for dimming
        self._shopee_file_btn = btn_pick_sh
        self._shopee_open_btn = btn_open_sh
        self._update_shopee_ui_state()

        # 5. Core start/stop control actions
        buttons_frame = tk.Frame(left_col, bg=self.bg_color)
        buttons_frame.pack(fill="x", pady=15)
        
        self.btn_start = tk.Button(buttons_frame, text="▶ BẮT ĐẦU CHẠY TOOL", command=self.start_posting, font=("Segoe UI", 11, "bold"), pady=8)
        self.btn_start.pack(fill="x", pady=3)
        self.style_button(self.btn_start, "#27ae60", "#219653")
        
        self.btn_stop = tk.Button(buttons_frame, text="■ DỪNG CHẠY", command=self.stop_posting, state="disabled", font=("Segoe UI", 11, "bold"), pady=8)
        self.btn_stop.pack(fill="x", pady=3)
        self.style_button(self.btn_stop, "#c0392b", "#a93226")

        # Live log box (Right side)
        log_header = tk.Frame(right_log_frame, bg="#f0f0f0", pady=5)
        log_header.pack(fill="x")
        tk.Label(log_header, text="📊 NHẬT KÝ HOẠT ĐỘNG THỜI GIAN THỰC", font=self.font_header, bg="#f0f0f0", fg="#333").pack(side="left", padx=10)
        
        def clear_console():
            self.log_text.configure(state="normal")
            self.log_text.delete("1.0", "end")
            self.log_text.configure(state="disabled")
            self.log("Đã làm sạch ô log hiển thị.")
            
        btn_clear_log = tk.Button(log_header, text="🗑️ Làm sạch log", command=clear_console, font=("Segoe UI", 8), padx=5, pady=2)
        btn_clear_log.pack(side="right", padx=10)
        self.style_button(btn_clear_log, "#5f6368", "#474a4d")

        self.log_text = scrolledtext.ScrolledText(right_log_frame, font=("Consolas", 9), state="normal", wrap="word", bg="#202124", fg="#f1f3f4", insertbackground="white")
        self.log_text.pack(fill="both", expand=True, padx=5, pady=(0, 5))
        self.log_text.configure(state="disabled")

    def _update_scheduler_widgets_visibility(self):
        # Only show rest and time constraints if loop mode is not 'once'
        if self.dashboard_loop_var.get() == "once":
            self.dash_sched_frame.grid_remove()
        else:
            self.dash_sched_frame.grid()

    # ─── TAB 2: FANPAGE MANAGER (MASTER-DETAIL) ─────────────────
    def _build_fanpage_tab(self):
        # 1. Top controls bar
        toolbar = tk.Frame(self.tab_fanpages, bg="#ffffff", bd=1, relief="solid", padx=10, pady=8)
        toolbar.pack(side="top", fill="x")
        
        # Search area
        search_f = tk.Frame(toolbar, bg="#ffffff")
        search_f.pack(side="left", fill="y")
        tk.Label(search_f, text="🔍 Tìm Kiếm:", font=self.font_bold, bg="#ffffff").pack(side="left", padx=2)
        self.search_var = tk.StringVar()
        
        search_ent = tk.Entry(search_f, textvariable=self.search_var, font=self.font_main, width=22, bd=1, relief="solid")
        search_ent.pack(side="left", padx=5)
        
        def clear_search_box():
            self.search_var.set("")
            self.refresh_tree()
            
        btn_clear = tk.Button(search_f, text="✖", command=clear_search_box, font=("Segoe UI", 8, "bold"), padx=5, pady=1)
        btn_clear.pack(side="left")
        self.style_button(btn_clear, "#5f6368", "#474a4d")
        
        def on_search_trigger(*args):
            if hasattr(self, '_search_after_id') and self._search_after_id:
                self.after_cancel(self._search_after_id)
            self._search_after_id = self.after(150, lambda: self.refresh_tree())
        self.search_var.trace_add("write", on_search_trigger)
        
        # Separator
        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=15)
        
        # Selection tools
        sel_f = tk.Frame(toolbar, bg="#ffffff")
        sel_f.pack(side="left")
        
        btn_all = tk.Button(sel_f, text="Tích Hết", command=lambda: [self.set_all_enabled(True), self.refresh_tree()], font=self.font_main, padx=8, pady=2)
        btn_all.pack(side="left", padx=2)
        self.style_button(btn_all, "#27ae60", "#219653")
        
        btn_none = tk.Button(sel_f, text="Bỏ Tích", command=lambda: [self.set_all_enabled(False), self.refresh_tree()], font=self.font_main, padx=8, pady=2)
        btn_none.pack(side="left", padx=2)
        self.style_button(btn_none, "#5f6368", "#474a4d")
        
        btn_bulk_pr = tk.Button(sel_f, text="Gán Profile Loạt", command=self.bulk_assign_ui, font=self.font_main, padx=8, pady=2)
        btn_bulk_pr.pack(side="left", padx=2)
        self.style_button(btn_bulk_pr, "#e07b39", "#be5f23")

        # Separator
        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=15)

        # Page commands
        cmd_f = tk.Frame(toolbar, bg="#ffffff")
        cmd_f.pack(side="right")
        
        btn_add = tk.Button(cmd_f, text="+ Thêm Page", command=self.add_fanpage_ui, font=self.font_bold, padx=10, pady=2)
        btn_add.pack(side="left", padx=2)
        self.style_button(btn_add, "#1a73e8", "#1557b0")
        
        btn_group = tk.Button(cmd_f, text="👥 Quản Lý Nhóm", command=self.group_management_ui, font=self.font_main, padx=10, pady=2)
        btn_group.pack(side="left", padx=2)
        self.style_button(btn_group, "#7c5cbf", "#6242a3")
        
        btn_autom = tk.Button(cmd_f, text="🪄 Tự Động Gán Folder", command=self.auto_map_folders_ui, font=self.font_main, padx=10, pady=2)
        btn_autom.pack(side="left", padx=2)
        self.style_button(btn_autom, "#2e7d32", "#225c25")
        
        btn_clr_all = tk.Button(cmd_f, text="🗑️ Xóa Hết", command=self.clear_all_ui, font=self.font_main, padx=10, pady=2)
        btn_clr_all.pack(side="left", padx=2)
        self.style_button(btn_clr_all, "#ea4335", "#c5221f")

        # 2. Main content area (Horizontal PanedWindow)
        self.pages_pane = tk.PanedWindow(self.tab_fanpages, orient=tk.HORIZONTAL, bg="#d9d9d9", sashwidth=5, sashrelief=tk.RAISED)
        self.pages_pane.pack(fill="both", expand=True, pady=(5, 0))
        
        # Left pane: Treeview Table
        table_container = tk.Frame(self.pages_pane, bg="#ffffff")
        self.pages_pane.add(table_container, width=650, minsize=400)
        
        # Create Treeview
        self.tree_frame = tk.Frame(table_container, bg="#ffffff")
        self.tree_frame.pack(fill="both", expand=True)
        
        self.tree = ttk.Treeview(self.tree_frame, columns=("check", "stt", "name", "group", "profile", "folders"), show="headings", selectmode="browse")
        self.tree.pack(side="left", fill="both", expand=True)
        
        tree_scroll = ttk.Scrollbar(self.tree_frame, orient="vertical", command=self.tree.yview)
        tree_scroll.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=tree_scroll.set)
        
        # Configure columns
        self.tree.heading("check", text="Chạy", anchor="center")
        self.tree.column("check", width=45, minwidth=40, anchor="center")
        self.tree.heading("stt", text="STT", anchor="center")
        self.tree.column("stt", width=40, minwidth=35, anchor="center")
        self.tree.heading("name", text="Tên Fanpage", anchor="w")
        self.tree.column("name", width=160, minwidth=100, anchor="w")
        self.tree.heading("group", text="Nhóm", anchor="w")
        self.tree.column("group", width=90, minwidth=70, anchor="w")
        self.tree.heading("profile", text="Profile Trình Duyệt", anchor="w")
        self.tree.column("profile", width=160, minwidth=100, anchor="w")
        self.tree.heading("folders", text="Folder (Videos)", anchor="w")
        self.tree.column("folders", width=150, minwidth=100, anchor="w")
        
        # Event bindings for Treeview click
        self.tree.bind("<ButtonRelease-1>", self.on_tree_click)
        self.tree.bind("<KeyRelease-Up>", lambda e: self._on_tree_key_nav())
        self.tree.bind("<KeyRelease-Down>", lambda e: self._on_tree_key_nav())

        # Right pane: Detail Editor Panel
        self.detail_container = tk.Frame(self.pages_pane, bg=self.bg_color)
        self.pages_pane.add(self.detail_container, minsize=350)
        
        # Placeholder
        self.placeholder_lbl = tk.Label(self.detail_container, text="👈 Vui lòng chọn một Fanpage ở danh sách bên trái\nđể xem và cấu hình chi tiết.", font=("Segoe UI", 10, "italic"), fg="#777", bg=self.bg_color)
        self.placeholder_lbl.pack(fill="both", expand=True)
        
        # Actual Detail Panel Frame (Hidden initially)
        self.detail_panel = tk.LabelFrame(self.detail_container, text=" ⚙️ CẤU HÌNH CHI TIẾT FANPAGE ", font=self.font_bold, bg="#ffffff", bd=1, relief="solid")
        
        # Scrollable inner wrapper for Detail Panel
        self.detail_canvas = tk.Canvas(self.detail_panel, bg="#ffffff", highlightthickness=0)
        self.detail_scrollbar = ttk.Scrollbar(self.detail_panel, orient="vertical", command=self.detail_canvas.yview)
        self.detail_canvas.configure(yscrollcommand=self.detail_scrollbar.set)
        
        self.detail_inner = tk.Frame(self.detail_canvas, bg="#ffffff", padx=15, pady=10)
        self.detail_canvas_window = self.detail_canvas.create_window((0, 0), window=self.detail_inner, anchor="nw")
        
        def on_det_canvas_config(event):
            self.detail_canvas.configure(scrollregion=self.detail_canvas.bbox("all"))
            self.detail_canvas.itemconfig(self.detail_canvas_window, width=event.width)
        self.detail_canvas.bind("<Configure>", on_det_canvas_config)
        
        # Hook mouse wheel
        self.detail_canvas.bind("<MouseWheel>", lambda e: self.detail_canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))
        self.detail_inner.bind("<MouseWheel>", lambda e: self.detail_canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))
        
        self.detail_scrollbar.pack(side="right", fill="y")
        self.detail_canvas.pack(side="left", fill="both", expand=True)
        
        # Detail Panel Components inside self.detail_inner:
        # Row 1: Header ID
        self.det_id_lbl = tk.Label(self.detail_inner, text="CẤU HÌNH FANPAGE #", font=self.font_title, fg=self.accent_color, bg="#ffffff")
        self.det_id_lbl.pack(anchor="w", pady=(0, 10))
        
        # Row 2: Status tick
        self.det_enable_var = tk.BooleanVar()
        def toggle_det_enable():
            if self.current_selected_page_idx is not None:
                self.db.update_page_enabled(self.current_selected_page_idx, self.det_enable_var.get())
                self.refresh_tree_row(self.current_selected_page_idx)
        chk_det_en = tk.Checkbutton(self.detail_inner, text="Tích chọn hoạt động (Cho phép chạy)", variable=self.det_enable_var, bg="#ffffff", font=self.font_bold, fg=self.fg_color, command=toggle_det_enable)
        chk_det_en.pack(anchor="w", pady=5)
        
        # Inputs layout frame
        inputs_grid = tk.Frame(self.detail_inner, bg="#ffffff")
        inputs_grid.pack(fill="x", pady=5)
        inputs_grid.columnconfigure(1, weight=1)
        
        # Name Entry
        tk.Label(inputs_grid, text="Tên Fanpage:", bg="#ffffff", font=self.font_bold).grid(row=0, column=0, sticky="w", pady=4)
        self.det_name_entry = tk.Entry(inputs_grid, font=self.font_main, bd=1, relief="solid")
        self.det_name_entry.grid(row=0, column=1, sticky="ew", padx=(10, 0), pady=4)
        self.det_name_entry.bind("<FocusOut>", lambda e: self.save_current_page_details())
        self.det_name_entry.bind("<Return>", lambda e: self.save_current_page_details())
        
        # Link Entry
        tk.Label(inputs_grid, text="Link Fanpage:", bg="#ffffff", font=self.font_bold).grid(row=1, column=0, sticky="w", pady=4)
        self.det_link_entry = tk.Entry(inputs_grid, font=self.font_main, bd=1, relief="solid")
        self.det_link_entry.grid(row=1, column=1, sticky="ew", padx=(10, 0), pady=4)
        self.det_link_entry.bind("<FocusOut>", lambda e: self.save_current_page_details())
        self.det_link_entry.bind("<Return>", lambda e: self.save_current_page_details())
        
        # Group Combobox
        tk.Label(inputs_grid, text="Nhóm Page:", bg="#ffffff", font=self.font_bold).grid(row=2, column=0, sticky="w", pady=4)
        self.det_group_combo = ttk.Combobox(inputs_grid, state="readonly")
        self.det_group_combo.grid(row=2, column=1, sticky="ew", padx=(10, 0), pady=4)
        self._disable_combo_scroll(self.det_group_combo)
        self.det_group_combo.bind("<<ComboboxSelected>>", self.on_detail_group_change)
        
        # Profile Browser Combobox
        tk.Label(inputs_grid, text="Profile gán:", bg="#ffffff", font=self.font_bold).grid(row=3, column=0, sticky="w", pady=4)
        prof_f = tk.Frame(inputs_grid, bg="#ffffff")
        prof_f.grid(row=3, column=1, sticky="ew", padx=(10, 0), pady=4)
        prof_f.columnconfigure(0, weight=1)
        
        self.det_profile_combo = ttk.Combobox(prof_f, state="readonly")
        self.det_profile_combo.grid(row=0, column=0, sticky="ew")
        self._disable_combo_scroll(self.det_profile_combo)
        self.det_profile_combo.bind("<<ComboboxSelected>>", self.on_detail_profile_change)
        
        btn_ref_prof = tk.Button(prof_f, text="🔄", command=lambda: self.refresh_profiles_async(show_msg=True), font=("Segoe UI", 8), padx=4)
        btn_ref_prof.grid(row=0, column=1, padx=(3, 0))
        self.style_button(btn_ref_prof, "#f0f0f0", "#e0e0e0", fg_color="#333333")

        # Profiles chạy Listbox (Row 4)
        tk.Label(inputs_grid, text="Profiles chạy:", bg="#ffffff", font=self.font_bold).grid(row=4, column=0, sticky="nw", pady=4)
        list_f = tk.Frame(inputs_grid, bg="#ffffff")
        list_f.grid(row=4, column=1, sticky="ew", padx=(10, 0), pady=4)
        list_f.columnconfigure(0, weight=1)
        
        self.det_profile_listbox = tk.Listbox(list_f, font=self.font_main, height=3, bd=1, relief="solid")
        self.det_profile_listbox.grid(row=0, column=0, sticky="ew")
        
        list_scroll = ttk.Scrollbar(list_f, orient="vertical", command=self.det_profile_listbox.yview)
        list_scroll.grid(row=0, column=1, sticky="ns")
        self.det_profile_listbox.configure(yscrollcommand=list_scroll.set)
        
        btn_f = tk.Frame(list_f, bg="#ffffff")
        btn_f.grid(row=0, column=2, padx=(5, 0), sticky="n")
        
        btn_add = tk.Button(btn_f, text="➕ Thêm", command=self.add_profile_to_page, font=("Segoe UI", 8, "bold"), padx=6, pady=2)
        btn_add.pack(fill="x", pady=1)
        self.style_button(btn_add, "#3a9a5c", "#2d7647")
        
        btn_del = tk.Button(btn_f, text="➖ Xóa", command=self.remove_profile_from_page, font=("Segoe UI", 8, "bold"), padx=6, pady=2)
        btn_del.pack(fill="x", pady=1)
        self.style_button(btn_del, "#ea4335", "#d62516")

        # 3. Individual video folders editor section
        self.folders_grp = tk.LabelFrame(self.detail_inner, text=" 📂 Thư Mục Video Chỉ Định ", font=self.font_bold, bg="#ffffff", bd=1, relief="solid", padx=10, pady=10)
        self.folders_grp.pack(fill="x", pady=10)
        
        # Container to render dynamic folder list
        self.det_folders_container = tk.Frame(self.folders_grp, bg="#ffffff")
        self.det_folders_container.pack(fill="x", pady=3)
        
        # Add folder actions
        fold_btns = tk.Frame(self.folders_grp, bg="#ffffff")
        fold_btns.pack(fill="x", pady=(5, 0))
        
        btn_add_fold = tk.Button(fold_btns, text="+ Chọn Thư Mục", command=self.add_folder_to_page, font=("Segoe UI", 8), padx=8, pady=2)
        btn_add_fold.pack(side="left", padx=2)
        self.style_button(btn_add_fold, "#1a73e8", "#1557b0")
        
        btn_add_path = tk.Button(fold_btns, text="+ Nhập Path", command=self.add_folder_manual_to_page, font=("Segoe UI", 8), padx=8, pady=2)
        btn_add_path.pack(side="left", padx=2)
        self.style_button(btn_add_path, "#2e7d32", "#225c25")

        # 4. Custom Page Comment Editor Panel
        self.comments_grp = tk.LabelFrame(self.detail_inner, text=" 💬 Bình Luận Riêng (Chỉ Page Này) ", font=self.font_bold, bg="#ffffff", bd=1, relief="solid", padx=10, pady=10)
        self.comments_grp.pack(fill="x", pady=5)
        
        self.det_comment_txt = scrolledtext.ScrolledText(self.comments_grp, font=("Segoe UI", 9), height=5, wrap="word", bd=1, relief="solid")
        self.det_comment_txt.pack(fill="x", pady=2)
        self.det_comment_txt.bind("<FocusOut>", lambda e: self.save_current_page_comment())
        
        tk.Label(self.comments_grp, text="*Nhấp ra ngoài để tự động lưu. Hỗ trợ spin {a|b|c}.", font=("Segoe UI", 8, "italic"), fg="#777", bg="#ffffff").pack(anchor="w", pady=2)

        # 5. Core action commands for current selected page
        page_cmds_f = tk.Frame(self.detail_inner, bg="#ffffff")
        page_cmds_f.pack(fill="x", pady=15)
        
        btn_page_log = tk.Button(page_cmds_f, text="📊 Xem Log Ngày", command=lambda: self.show_video_log_ui(filter_name=self.det_name_entry.get()), font=self.font_main, padx=8, pady=4)
        btn_page_log.pack(side="left", padx=2)
        self.style_button(btn_page_log, "#3a9a5c", "#2d7647")
        
        btn_page_hist = tk.Button(page_cmds_f, text="📅 Lịch Sử Đăng", command=lambda: self.view_log_ui(self.current_selected_page_idx), font=self.font_main, padx=8, pady=4)
        btn_page_hist.pack(side="left", padx=2)
        self.style_button(btn_page_hist, "#7c5cbf", "#6242a3")
        
        btn_page_del = tk.Button(page_cmds_f, text="🗑️ Xóa Page", command=lambda: self.remove_page(self.current_selected_page_idx), font=self.font_main, padx=10, pady=4)
        btn_page_del.pack(side="right", padx=2)
        self.style_button(btn_page_del, "#ea4335", "#c5221f")

    def _on_tree_key_nav(self):
        # Trigger page detail loading on arrow key navigation
        items = self.tree.selection()
        if items:
            item_id = items[0]
            db_idx = self.tree_item_to_idx.get(item_id)
            if db_idx is not None:
                self.show_page_details(db_idx)

    # ─── TAB 3: SYSTEM CONFIGS ───────────────────────────────
    def _build_settings_tab(self):
        settings_scroll = tk.Canvas(self.tab_settings, bg=self.bg_color, highlightthickness=0)
        settings_scrollbar = ttk.Scrollbar(self.tab_settings, orient="vertical", command=settings_scroll.yview)
        settings_scroll.configure(yscrollcommand=settings_scrollbar.set)
        settings_scrollbar.pack(side="right", fill="y")
        settings_scroll.pack(side="left", fill="both", expand=True)
        
        container = tk.Frame(settings_scroll, bg=self.bg_color, padx=15, pady=15)
        settings_scroll.create_window((0, 0), window=container, anchor="nw")
        
        def on_set_canvas_config(event):
            settings_scroll.configure(scrollregion=settings_scroll.bbox("all"))
            settings_scroll.itemconfig(1, width=event.width)
        settings_scroll.bind("<Configure>", on_set_canvas_config)

        # Hook mouse wheel
        settings_scroll.bind("<MouseWheel>", lambda e: settings_scroll.yview_scroll(int(-1 * (e.delta / 120)), "units"))
        container.bind("<MouseWheel>", lambda e: settings_scroll.yview_scroll(int(-1 * (e.delta / 120)), "units"))

        # Organize inside a 3-column layout grid
        container.columnconfigure(0, weight=1, minsize=320)
        container.columnconfigure(1, weight=1, minsize=320)
        container.columnconfigure(2, weight=1, minsize=320)
        
        # ──────────────────────────────────────────────────
        # Column 0: Global Comment settings
        # ──────────────────────────────────────────────────
        col0 = tk.Frame(container, bg=self.bg_color)
        col0.grid(row=0, column=0, sticky="nwe", padx=8)
        
        g_comm_grp = tk.LabelFrame(col0, text=" 💬 Mẫu Bình Luận & Chiến Thuật Chung ", font=self.font_bold, bg="#ffffff", bd=1, relief="solid", padx=10, pady=10)
        g_comm_grp.pack(fill="x", pady=5)
        
        self.sett_comm_all_var = tk.BooleanVar(value=self.db.get_comment_all_fanpages())
        tk.Checkbutton(g_comm_grp, text="Bình luận cho tất cả fanpage", variable=self.sett_comm_all_var,
                       font=self.font_bold, fg="#7c5cbf", bg="#ffffff",
                       command=lambda: self.db.set_comment_all_fanpages(self.sett_comm_all_var.get())).pack(anchor="w", pady=(0, 5))
                       
        tk.Label(g_comm_grp, text="Mẫu bình luận chung:", bg="#ffffff", font=self.font_bold).pack(anchor="w", pady=2)
        
        self.sett_comm_txt = scrolledtext.ScrolledText(g_comm_grp, font=self.font_main, height=8, wrap="word", bd=1, relief="solid")
        self.sett_comm_txt.pack(fill="x", pady=2)
        self.sett_comm_txt.insert("1.0", self.db.get_comment_template())
        
        def save_global_comm_tmpl(event=None):
            self.db.set_comment_template(self.sett_comm_txt.get("1.0", "end-1c"))
            self.log("Đã lưu mẫu bình luận chung.")
        self.sett_comm_txt.bind("<FocusOut>", save_global_comm_tmpl)
        
        tk.Label(g_comm_grp, text="*Hỗ trợ spin. Nhấp ra ngoài để lưu tự động.", font=("Segoe UI", 8, "italic"), fg="#777", bg="#ffffff").pack(anchor="w", pady=2)

        # Strategies
        strat_sub = tk.LabelFrame(g_comm_grp, text=" Chiến Thuật Tìm Bài Đăng Để Comment ", font=self.font_bold, bg="#ffffff", bd=1, relief="solid", padx=8, pady=8)
        strat_sub.pack(fill="x", pady=5)
        
        strategies = self.db.get_comment_strategies()
        self.strat_vars = {}
        strat_labels = {
            "home_scroll": "1. Cuộn trang chủ (Home Scroll)",
            "feed_grid": "2. Bảng feed & lưới bài (Feed & Grid)",
            "published_panel": "3. Bảng chi tiết bài viết (Published)",
            "published_inline": "4. Trực tiếp danh sách bài viết",
            "insight_overview": "5. Insights: Tổng quan nội dung",
            "insight_content": "6. Insights: Xem tất cả nội dung"
        }
        
        def save_strats():
            new_s = {k: v.get() for k, v in self.strat_vars.items()}
            self.db.set_comment_strategies(new_s)
            self.log("Đã lưu chiến thuật bình luận mới.")
            
        for key, label in strat_labels.items():
            var = tk.BooleanVar(value=strategies.get(key, True))
            self.strat_vars[key] = var
            tk.Checkbutton(strat_sub, text=label, variable=var, font=self.font_main, bg="#ffffff", command=save_strats).pack(anchor="w", pady=1)

        # ──────────────────────────────────────────────────
        # Column 1: Global folders & video limits & reports
        # ──────────────────────────────────────────────────
        col1 = tk.Frame(container, bg=self.bg_color)
        col1.grid(row=0, column=1, sticky="nwe", padx=8)
        
        # Shared Video Folders
        g_fold_grp = tk.LabelFrame(col1, text=" 📂 Thư Mục Video Dùng Chung (Tất cả Page) ", font=self.font_bold, bg="#ffffff", bd=1, relief="solid", padx=10, pady=10)
        g_fold_grp.pack(fill="x", pady=5)
        
        self.global_list_frame = tk.Frame(g_fold_grp, bg="#ffffff")
        self.global_list_frame.pack(fill="x", pady=3)
        
        btn_add_g_fold = tk.Button(g_fold_grp, text="+ Thêm Thư Mục Dùng Chung", command=self.add_global_folder_ui, font=("Segoe UI", 8), padx=8, pady=2)
        btn_add_g_fold.pack(pady=5)
        self.style_button(btn_add_g_fold, "#1a73e8", "#1557b0")
        
        self._refresh_global_folders_ui()
        
        # Shared limit per run
        limit_f = tk.Frame(g_fold_grp, bg="#ffffff")
        limit_f.pack(fill="x", pady=5)
        
        tk.Label(limit_f, text="Số video mỗi lần chạy:", bg="#ffffff", font=self.font_bold).pack(side="left")
        g_min, g_max = self.db.get_global_video_limits()
        
        self.global_min_entry = tk.Entry(limit_f, width=5, bd=1, relief="solid")
        self.global_min_entry.insert(0, str(g_min))
        self.global_min_entry.pack(side="left", padx=(8, 2))
        
        tk.Label(limit_f, text="-", bg="#ffffff").pack(side="left")
        
        self.global_max_entry = tk.Entry(limit_f, width=5, bd=1, relief="solid")
        self.global_max_entry.insert(0, str(g_max))
        self.global_max_entry.pack(side="left", padx=(2, 8))
        
        def save_global_limits(event=None):
            try:
                vmin = int(self.global_min_entry.get())
                vmax = int(self.global_max_entry.get())
                if vmin > 0 and vmax >= vmin:
                    self.db.set_global_video_limits(vmin, vmax)
                    self.log(f"Cập nhật giới hạn video chung: {vmin} - {vmax}")
            except:
                pass
        self.global_min_entry.bind("<FocusOut>", save_global_limits)
        self.global_max_entry.bind("<FocusOut>", save_global_limits)
        self.global_min_entry.bind("<Return>", save_global_limits)
        self.global_max_entry.bind("<Return>", save_global_limits)

        # Statistics and static logs report buttons
        stats_grp = tk.LabelFrame(col1, text=" 📊 Log Hệ Thống & Báo Cáo ", font=self.font_bold, bg="#ffffff", bd=1, relief="solid", padx=10, pady=10)
        stats_grp.pack(fill="x", pady=10)
        
        btn_err_done = tk.Button(stats_grp, text="⚠️ Báo cáo lỗi Done (Hỏng nút)", command=self.show_done_errors_ui, font=self.font_main, pady=4)
        btn_err_done.pack(fill="x", pady=2)
        self.style_button(btn_err_done, "#c0392b", "#a93226")
        
        btn_comm_hist = tk.Button(stats_grp, text="💬 Lịch sử bình luận", command=self.view_comment_history, font=self.font_main, pady=4)
        btn_comm_hist.pack(fill="x", pady=2)
        self.style_button(btn_comm_hist, "#7c5cbf", "#6242a3")
        
        btn_total_stats = tk.Button(stats_grp, text="📊 Log ngày & Thống kê", command=self.show_video_log_ui, font=self.font_main, pady=4)
        btn_total_stats.pack(fill="x", pady=2)
        self.style_button(btn_total_stats, "#3a9a5c", "#2d7647")

        # ──────────────────────────────────────────────────
        # Column 2: Browser connections configurations
        # ──────────────────────────────────────────────────
        col2 = tk.Frame(container, bg=self.bg_color)
        col2.grid(row=0, column=2, sticky="nwe", padx=8)
        
        self.browser_sett_frame = tk.LabelFrame(col2, text=" 🌐 Quản Lý Trình Duyệt (API Hubs) ", font=self.font_bold, bg="#ffffff", bd=1, relief="solid", padx=10, pady=10)
        self.browser_sett_frame.pack(fill="x", pady=5)
        
        self._build_settings_browser_section()

        # Backup & Restore Group
        backup_grp = tk.LabelFrame(col2, text=" 💾 Sao Lưu & Khôi Phục Dữ Liệu ", font=self.font_bold, bg="#ffffff", bd=1, relief="solid", padx=10, pady=10)
        backup_grp.pack(fill="x", pady=10)
        
        btn_backup = tk.Button(backup_grp, text="📤 Sao Lưu Profile Hiện Tại", command=self.backup_current_profile_ui, font=self.font_main, pady=4)
        btn_backup.pack(fill="x", pady=2)
        self.style_button(btn_backup, "#1a73e8", "#1557b0")
        
        btn_restore = tk.Button(backup_grp, text="📥 Khôi Phục Dữ Liệu Từ File", command=self.restore_current_profile_ui, font=self.font_main, pady=4)
        btn_restore.pack(fill="x", pady=2)
        self.style_button(btn_restore, "#f2994a", "#e28732")

    def _build_settings_browser_section(self):
        # Clear previous elements
        for w in self.browser_sett_frame.winfo_children():
            w.destroy()
            
        browsers = self.db.get_browsers()
        
        # Build connections grid for the defaults
        for b_id in ["gemlogin_default", "gpmlogin_default"]:
            b = self.db.get_browser_by_id(b_id)
            if not b: continue
            
            sub = tk.Frame(self.browser_sett_frame, bg="#f8f9fa", bd=1, relief="solid", pady=8, padx=8)
            sub.pack(fill="x", pady=3)
            
            tk.Label(sub, text=f"Hub: {b['name']}", font=self.font_bold, bg="#f8f9fa").pack(anchor="w")
            
            # API URL Edit Input
            url_row = tk.Frame(sub, bg="#f8f9fa")
            url_row.pack(fill="x", pady=2)
            tk.Label(url_row, text="API URL:", bg="#f8f9fa", font=("Segoe UI", 8)).pack(side="left")
            
            url_ent = tk.Entry(url_row, font=("Consolas", 9), bd=1, relief="solid")
            url_ent.insert(0, b['api_url'])
            url_ent.pack(side="left", fill="x", expand=True, padx=5)
            
            def make_save_api(bid=b_id, ue=url_ent, bname=b['name'], btype=b['type']):
                def _save():
                    url = ue.get().strip()
                    self.db.update_browser(bid, bname, btype, url)
                    self.log(f"Đã cập nhật URL {bname}: {url}")
                    self.refresh_ui()
                return _save
                
            def make_test_api(btype=b['type'], ue=url_ent):
                def _test():
                    url = ue.get().strip()
                    self.log(f"Đang kiểm tra kết nối {btype} tại {url}...")
                    def run():
                        try:
                            api = GemLoginAPI(url) if btype == "gemlogin" else GPMLoginAPI(url)
                            profiles = api.get_profiles()
                            if profiles is not None:
                                self.after(0, lambda: messagebox.showinfo("Thành công", f"Kết nối {btype} thành công!\nTìm thấy {len(profiles)} profiles."))
                                self.log(f"Kết nối {btype} thành công: {len(profiles)} profiles.")
                            else:
                                self.after(0, lambda: messagebox.showerror("Thất bại", f"Không thể kết nối API {btype}."))
                                self.log(f"Kết nối {btype} thất bại.")
                        except Exception as e:
                            self.after(0, lambda: messagebox.showerror("Lỗi", f"Lỗi kết nối: {e}"))
                    threading.Thread(target=run, daemon=True).start()
                return _test
                
            act_row = tk.Frame(sub, bg="#f8f9fa")
            act_row.pack(fill="x", pady=(2, 0))
            
            btn_save = tk.Button(act_row, text="Lưu", command=make_save_api(), font=("Segoe UI", 8), padx=8)
            btn_save.pack(side="left", padx=2)
            self.style_button(btn_save, "#2e7d32", "#225c25")
            
            btn_test = tk.Button(act_row, text="Kiểm thử", command=make_test_api(), font=("Segoe UI", 8), padx=8)
            btn_test.pack(side="left", padx=2)
            self.style_button(btn_test, "#1a73e8", "#1557b0")
            
        ttk.Separator(self.browser_sett_frame).pack(fill="x", pady=10)
        
        # Remote Hub section
        tk.Label(self.browser_sett_frame, text="Thêm Remote Hub Khác:", bg="#ffffff", font=self.font_bold).pack(anchor="w", pady=2)
        add_f = tk.Frame(self.browser_sett_frame, bg="#ffffff")
        add_f.pack(fill="x", pady=2)
        
        n_new = tk.Entry(add_f, font=self.font_main, width=12, bd=1, relief="solid")
        n_new.insert(0, "Sub Hub")
        n_new.pack(side="left", padx=1)
        
        t_new = ttk.Combobox(add_f, values=["gemlogin", "gpmlogin"], width=8, state="readonly")
        t_new.set("gpmlogin")
        t_new.pack(side="left", padx=1)
        self._disable_combo_scroll(t_new)
        
        u_new = tk.Entry(add_f, font=("Consolas", 9), width=18, bd=1, relief="solid")
        u_new.insert(0, "http://")
        u_new.pack(side="left", padx=1)
        
        def add_remote_hub():
            name = n_new.get().strip()
            if name:
                self.db.add_browser(name, t_new.get(), u_new.get().strip())
                self.log(f"Thêm remote hub thành công: {name}")
                self._build_settings_browser_section()
                self.refresh_ui()
                
        btn_add = tk.Button(add_f, text="+", command=add_remote_hub, font=("Segoe UI", 8, "bold"), padx=5)
        btn_add.pack(side="left", padx=2)
        self.style_button(btn_add, "#7b1fa2", "#5e157d")
        
        # Display other hubs
        others = [b for b in browsers if b['id'] not in ["gemlogin_default", "gpmlogin_default"]]
        if others:
            tk.Label(self.browser_sett_frame, text="Danh sách các Hub khác:", bg="#ffffff", font=self.font_bold).pack(anchor="w", pady=(8, 2))
            for b in others:
                row = tk.Frame(self.browser_sett_frame, bg="#ffffff", pady=2)
                row.pack(fill="x")
                tk.Label(row, text=f"• {b['name']} ({b['type']})", bg="#ffffff", font=("Segoe UI", 8)).pack(side="left")
                
                def make_del_hub(bid=b['id'], name=b['name']):
                    def _del():
                        self.db.remove_browser(bid)
                        self.log(f"Đã xóa Hub: {name}")
                        self._build_settings_browser_section()
                        self.refresh_ui()
                    return _del
                    
                btn_del = tk.Button(row, text="Xóa", command=make_del_hub(), font=("Segoe UI", 8), padx=5, pady=1)
                btn_del.pack(side="right")
                self.style_button(btn_del, "#ea4335", "#c5221f")

    def backup_current_profile_ui(self):
        import zipfile
        
        # Determine default backup filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_profile_name = "".join(c for c in self.profile_name if c.isalnum() or c in (' ', '_', '-')).strip().replace(' ', '_')
        default_filename = f"backup_{safe_profile_name}_{timestamp}.zip"
        
        file_path = filedialog.asksaveasfilename(
            title="Chọn nơi lưu bản sao lưu",
            initialfile=default_filename,
            filetypes=[("ZIP files", "*.zip")],
            defaultextension=".zip"
        )
        
        if not file_path:
            return
            
        try:
            # Source files
            db_json_path = self.db.file_path
            from db_helper import db as sqlite_db
            sqlite_path = sqlite_db.db_path
            
            # Create zip
            with zipfile.ZipFile(file_path, 'w', zipfile.ZIP_DEFLATED) as zip_ref:
                # Add database JSON
                if os.path.exists(db_json_path):
                    zip_ref.write(db_json_path, "config.json")
                    
                # Add SQLite DB
                if os.path.exists(sqlite_path):
                    zip_ref.write(sqlite_path, "history.db")
                    
                # Add metadata
                metadata = {
                    "profile_name": self.profile_name,
                    "backup_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "version": "1.1.0"
                }
                zip_ref.writestr("metadata.json", json.dumps(metadata, indent=4, ensure_ascii=False))
                
            messagebox.showinfo("Thành công", f"Đã sao lưu Profile '{self.profile_name}' thành công!")
            self.log(f"Đã sao lưu Profile '{self.profile_name}' vào tệp: {file_path}")
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không thể tạo bản sao lưu: {e}")
            self.log(f"Lỗi khi sao lưu: {e}")

    def restore_current_profile_ui(self):
        import zipfile
        
        file_path = filedialog.askopenfilename(
            title="Chọn tệp sao lưu để khôi phục (.zip)",
            filetypes=[("ZIP files", "*.zip")]
        )
        
        if not file_path:
            return
            
        try:
            # Verify zip content
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                file_list = zip_ref.namelist()
                if "config.json" not in file_list:
                    messagebox.showerror("Lỗi", "Tệp sao lưu không hợp lệ (Không tìm thấy config.json).")
                    return
                
                # Try to read metadata to show a nice prompt
                meta_info = ""
                if "metadata.json" in file_list:
                    try:
                        metadata = json.loads(zip_ref.read("metadata.json").decode('utf-8'))
                        meta_info = f"\n- Profile gốc: {metadata.get('profile_name')}\n- Thời gian sao lưu: {metadata.get('backup_time')}"
                    except: pass
                
                confirm = messagebox.askyesno(
                    "Xác nhận khôi phục",
                    f"Bạn có chắc chắn muốn khôi phục dữ liệu từ tệp sao lưu này?{meta_info}\n\n⚠️ HÀNH ĐỘNG NÀY SẼ GHI ĐÈ TOÀN BỘ cấu hình và lịch sử hiện tại của Profile '{self.profile_name}'!"
                )
                
                if not confirm:
                    return
                
                # Extract and overwrite
                db_json_path = self.db.file_path
                from db_helper import db as sqlite_db
                sqlite_path = sqlite_db.db_path
                
                # Overwrite JSON
                with open(db_json_path, 'wb') as f:
                    f.write(zip_ref.read("config.json"))
                    
                # Overwrite SQLite
                if "history.db" in file_list:
                    with open(sqlite_path, 'wb') as f:
                        f.write(zip_ref.read("history.db"))
                        
            # Reload Database and refresh UI
            self.db = Database(db_json_path)
            self.refresh_ui()
            
            messagebox.showinfo("Thành công", f"Đã khôi phục dữ liệu Profile '{self.profile_name}' thành công!")
            self.log(f"Đã khôi phục dữ liệu Profile '{self.profile_name}' từ tệp: {file_path}")
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không thể khôi phục dữ liệu: {e}")
            self.log(f"Lỗi khi khôi phục: {e}")

    def select_multiple_profiles_dialog(self, title="Chọn nhiều Profile", initial_ids=None):
        """
        Shows a dialog with checkboxes to select multiple browser profiles.
        Returns (b_id, comma_separated_ids, comma_separated_names) or (None, None, None).
        """
        # If no profiles are loaded
        if not self._unified_profile_map:
            messagebox.showwarning("Thông báo", "Không có profile trình duyệt nào được tải.")
            return None, None, None
            
        win = tk.Toplevel(self)
        win.title(title)
        win.geometry("400x500")
        win.resizable(False, False)
        win.attributes("-topmost", True)
        
        # Parse initial_ids
        init_ids_set = set()
        if initial_ids:
            init_ids_set = {pid.strip() for pid in str(initial_ids).split(',') if pid.strip()}
            
        main_frame = tk.Frame(win, padx=15, pady=15)
        main_frame.pack(fill="both", expand=True)
        
        tk.Label(main_frame, text="Tích chọn các Profile muốn gán:", font=self.font_bold).pack(anchor="w", pady=(0, 10))
        
        # Scrollable list of profiles
        canvas = tk.Canvas(main_frame)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scroll_frame = tk.Frame(canvas)
        
        def on_canvas_configure(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        canvas.bind("<Configure>", on_canvas_configure)
        
        # Hook mouse wheel
        canvas.bind("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))
        scroll_frame.bind("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))
        
        # Populate checklist
        vars_list = [] # List of (BooleanVar, b_id, p_id, p_name)
        for opt, (b_id, p_id, p_name) in self._unified_profile_map.items():
            var = tk.BooleanVar(value=(str(p_id) in init_ids_set))
            chk = tk.Checkbutton(scroll_frame, text=opt, variable=var, font=self.font_main)
            chk.pack(anchor="w", pady=2)
            # Bind wheel to checkbuttons too
            chk.bind("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))
            vars_list.append((var, b_id, p_id, p_name))
            
        result = {"b_id": None, "ids": None, "names": None, "submitted": False}
        
        def on_submit():
            selected = [item for item in vars_list if item[0].get()]
            if not selected:
                messagebox.showwarning("Cảnh báo", "Vui lòng chọn ít nhất 1 profile.")
                return
            
            # Ensure all selected profiles belong to the same browser hub
            b_ids_selected = {item[1] for item in selected}
            if len(b_ids_selected) > 1:
                messagebox.showerror("Lỗi", "Tất cả profile được chọn phải thuộc cùng một trình duyệt.")
                return
                
            chosen_b_id = list(b_ids_selected)[0]
            chosen_ids = ",".join(str(item[2]) for item in selected)
            chosen_names = ", ".join(item[3] for item in selected)
            
            result["b_id"] = chosen_b_id
            result["ids"] = chosen_ids
            result["names"] = chosen_names
            result["submitted"] = True
            win.destroy()
            
        footer = tk.Frame(win, pady=10)
        footer.pack(side="bottom")
        
        btn_submit = tk.Button(footer, text="Xác nhận", command=on_submit, width=12, pady=5)
        btn_submit.pack(side="left", padx=5)
        self.style_button(btn_submit, "#1a73e8", "#1557b0")
        
        btn_cancel = tk.Button(footer, text="Hủy", command=win.destroy, width=12, pady=5)
        btn_cancel.pack(side="left", padx=5)
        self.style_button(btn_cancel, "#5f6368", "#474a4d")
        
        win.wait_window()
        
        if result["submitted"]:
            return result["b_id"], result["ids"], result["names"]
        return None, None, None

    # ─── CORE GUI REFRESH & EVENT HANDLERS ───────────────────
    def refresh_ui(self):
        if threading.current_thread() != threading.main_thread():
            try:
                self.after(0, self.refresh_ui)
            except Exception:
                pass
            return
            
        # 1. Update dropdown/cache mappings
        self._rebuild_unified_profiles_data()
        
        # 2. Reset editor selection state
        self.current_selected_page_idx = None
        self.det_id_lbl.configure(text="CẤU HÌNH FANPAGE #")
        self.placeholder_lbl.pack(fill="both", expand=True)
        self.detail_panel.pack_forget()
        
        # 3. Refresh Treeview
        self.refresh_tree()
        
        # 4. Trigger async refresh of browser profiles
        self.refresh_profiles_async(show_msg=False)

    def refresh_tree(self):
        # Clear Treeview
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        self.tree_item_to_idx.clear()
        
        query = self.search_var.get().strip().lower()
        fanpages = self.db.get_fanpages()
        groups = self.db.get_groups()
        
        # Build group map
        group_map = {g['id']: g['name'] for g in groups}
        
        # Collect unique folder paths to bulk count videos (no nested OS calls)
        all_folders = set()
        for page in fanpages:
            for f in page.get('folders', []):
                all_folders.add(f)
        video_count_cache = {f: self.db.get_video_count(f) for f in all_folders}
        
        for idx, page in enumerate(fanpages):
            name = page.get('name', '')
            link = page.get('link', '')
            
            # Search filter
            if query and (query not in name.lower() and query not in link.lower()):
                continue
                
            enabled_str = "☑" if page.get('enabled', True) else "☐"
            
            g_id = page.get('group_id', '')
            g_name = group_map.get(g_id, "(Không nhóm)")
            
            # Browser & Profile display
            b_id = page.get('browser_id', '')
            p_name = page.get('profile_name', '')
            b_config = self.db.get_browser_by_id(b_id)
            b_name = b_config['name'] if b_config else "Unknown"
            profile_str = f"[{b_name}] {p_name}" if p_name else "(Chưa gán)"
            
            # Folder summary
            folders = page.get('folders', [])
            total_videos = sum(video_count_cache.get(f, 0) for f in folders)
            folder_str = f"{len(folders)} thư mục ({total_videos} video)" if folders else "(Chưa gán)"
            
            # Insert Row
            item_id = self.tree.insert("", "end", values=(enabled_str, idx + 1, name or "(Chưa đặt tên)", g_name, profile_str, folder_str))
            self.tree_item_to_idx[item_id] = idx

    def refresh_tree_row(self, db_idx):
        # Find Treeview row mapping to this database index and update it in-place
        for item_id, idx in self.tree_item_to_idx.items():
            if idx == db_idx:
                page = self.db.get_fanpages()[db_idx]
                groups = self.db.get_groups()
                group_map = {g['id']: g['name'] for g in groups}
                
                enabled_str = "☑" if page.get('enabled', True) else "☐"
                g_id = page.get('group_id', '')
                g_name = group_map.get(g_id, "(Không nhóm)")
                
                b_id = page.get('browser_id', '')
                p_name = page.get('profile_name', '')
                b_config = self.db.get_browser_by_id(b_id)
                b_name = b_config['name'] if b_config else "Unknown"
                profile_str = f"[{b_name}] {p_name}" if p_name else "(Chưa gán)"
                
                folders = page.get('folders', [])
                total_videos = sum(self.db.get_video_count(f) for f in folders)
                folder_str = f"{len(folders)} thư mục ({total_videos} video)" if folders else "(Chưa gán)"
                
                self.tree.item(item_id, values=(enabled_str, db_idx + 1, page.get('name') or "(Chưa đặt tên)", g_name, profile_str, folder_str))
                break

    def on_tree_click(self, event):
        region = self.tree.identify_region(event.x, event.y)
        if region == "cell":
            column = self.tree.identify_column(event.x)
            item_id = self.tree.identify_row(event.y)
            if item_id:
                db_idx = self.tree_item_to_idx.get(item_id)
                if db_idx is not None:
                    if column == "#1": # Tích chọn chạy
                        page = self.db.get_fanpages()[db_idx]
                        new_state = not page.get('enabled', True)
                        self.db.update_page_enabled(db_idx, new_state)
                        self.refresh_tree_row(db_idx)
                        if self.current_selected_page_idx == db_idx:
                            self.det_enable_var.set(new_state)
                    else:
                        # Load details
                        self.show_page_details(db_idx)

    def show_page_details(self, db_idx):
        self.current_selected_page_idx = db_idx
        fanpages = self.db.get_fanpages()
        if db_idx >= len(fanpages):
            return
            
        page = fanpages[db_idx]
        
        # Hide placeholder, display editor frame
        self.placeholder_lbl.pack_forget()
        self.detail_panel.pack(fill="both", expand=True)
        
        # Title index
        self.det_id_lbl.configure(text=f"CẤU HÌNH FANPAGE #{db_idx + 1}")
        
        # Status checkbox
        self.det_enable_var.set(page.get('enabled', True))
        
        # Inputs values
        self.det_name_entry.delete(0, "end")
        self.det_name_entry.insert(0, page.get('name', ''))
        
        self.det_link_entry.delete(0, "end")
        self.det_link_entry.insert(0, page.get('link', ''))
        
        # Group Dropdown
        groups = self.db.get_groups()
        group_names = [g['name'] for g in groups]
        self.det_group_combo['values'] = ["(Không nhóm)"] + group_names
        
        curr_g_id = page.get('group_id', '')
        curr_g_name = "(Không nhóm)"
        if curr_g_id:
            for g in groups:
                if g['id'] == curr_g_id:
                    curr_g_name = g['name']
                    break
        self.det_group_combo.set(curr_g_name)
        
        # Profile Dropdown
        self._update_detail_profile_dropdown()
        self.refresh_detail_profile_listbox()
        
        # Comments Template
        self.det_comment_txt.delete("1.0", "end")
        self.det_comment_txt.insert("1.0", page.get('comment_template', ''))
        
        # Folder list display
        self.refresh_detail_folders()

    def _update_detail_profile_dropdown(self):
        if self.current_selected_page_idx is None:
            return
            
        page = self.db.get_fanpages()[self.current_selected_page_idx]
        
        opts = list(self._unified_profile_options) + ["+ Chọn nhiều Profile..."]
        self.det_profile_combo['values'] = opts
        
        curr_b_id = page.get('browser_id')
        curr_p_id = page.get('profile_id')
        
        if curr_b_id and curr_p_id:
            if ',' in str(curr_p_id):
                p_name_stored = page.get('profile_name', 'Multiple Profiles')
                target_b = self.db.get_browser_by_id(curr_b_id)
                b_name_stored = target_b['name'] if target_b else "Unknown"
                opt_str = f"[{b_name_stored}] {p_name_stored}"
                self.det_profile_combo.set(opt_str)
                self._unified_profile_map[opt_str] = (curr_b_id, curr_p_id, p_name_stored)
            else:
                found_opt = None
                for opt, (b_id, p_id, p_name) in self._unified_profile_map.items():
                    if b_id == curr_b_id and str(p_id) == str(curr_p_id):
                        found_opt = opt
                        break
                
                if found_opt:
                    self.det_profile_combo.set(found_opt)
                else:
                    p_name_stored = page.get('profile_name', 'Unknown')
                    target_b = self.db.get_browser_by_id(curr_b_id)
                    b_name_stored = target_b['name'] if target_b else "Unknown"
                    opt_str = f"[{b_name_stored}] {p_name_stored}"
                    self.det_profile_combo.set(opt_str)
                    self._unified_profile_map[opt_str] = (curr_b_id, curr_p_id, p_name_stored)
        else:
            self.det_profile_combo.set("(Chưa gán Profile)")

    def save_current_page_details(self):
        idx = self.current_selected_page_idx
        if idx is None or idx < 0:
            return
            
        name = self.det_name_entry.get().strip()
        link = self.det_link_entry.get().strip()
        
        self.db.update_fanpage_name(idx, name)
        self.db.update_link(idx, link)
        self.refresh_tree_row(idx)

    def save_current_page_comment(self):
        idx = self.current_selected_page_idx
        if idx is None or idx < 0:
            return
            
        text = self.det_comment_txt.get("1.0", "end-1c")
        self.db.update_page_comment_template(idx, text)
        self.log(f"Đã cập nhật mẫu bình luận riêng cho Fanpage #{idx + 1}")

    def on_detail_group_change(self, event=None):
        idx = self.current_selected_page_idx
        if idx is None: return
        
        choice = self.det_group_combo.get()
        new_g_id = ""
        if choice != "(Không nhóm)":
            for g in self.db.get_groups():
                if g['name'] == choice:
                    new_g_id = g['id']
                    break
                    
        self.db.update_page_group(idx, new_g_id)
        self.log(f"Đã gán Fanpage #{idx+1} vào nhóm: {choice}")
        self.show_page_details(idx)
        self.refresh_tree_row(idx)

    def on_detail_profile_change(self, event=None):
        idx = self.current_selected_page_idx
        if idx is None: return
        
        opt = self.det_profile_combo.get()
        if opt == "+ Chọn nhiều Profile...":
            page = self.db.get_fanpages()[idx]
            initial_ids = page.get('profile_id', '')
            b_id, p_ids, p_names = self.select_multiple_profiles_dialog("Chọn nhiều Profile cho Fanpage", initial_ids)
            if p_ids:
                self.db.update_page_browser(idx, b_id)
                self.db.update_page_profile(idx, p_ids, p_names)
                self.log(f"Gán nhiều profile ({p_names}) cho Fanpage #{idx+1}")
                self.show_page_details(idx)
                self.refresh_tree_row(idx)
            else:
                self._update_detail_profile_dropdown()
        elif opt in self._unified_profile_map:
            b_id, p_id, p_name = self._unified_profile_map[opt]
            self.db.update_page_browser(idx, b_id)
            self.db.update_page_profile(idx, p_id, p_name)
            self.log(f"Gán profile {opt} cho Fanpage #{idx+1}")
            self.refresh_tree_row(idx)

    def add_profile_to_page(self):
        idx = self.current_selected_page_idx
        if idx is None: return
        
        opt = self.det_profile_combo.get()
        if not opt or opt == "(Chưa gán Profile)" or opt == "+ Chọn nhiều Profile...":
            messagebox.showwarning("Thông báo", "Vui lòng chọn một Profile trong danh sách trước khi thêm.")
            return
            
        if opt not in self._unified_profile_map:
            messagebox.showwarning("Thông báo", "Profile không hợp lệ.")
            return
            
        b_id, p_id, p_name = self._unified_profile_map[opt]
        
        page = self.db.get_fanpages()[idx]
        curr_b_id = page.get('browser_id')
        
        if curr_b_id and curr_b_id != b_id:
            if not messagebox.askyesno("Xác nhận", f"Profile này thuộc trình duyệt khác ({b_id}) so với trình duyệt của Fanpage ({curr_b_id}).\nBạn có muốn chuyển sang trình duyệt {b_id} và gán profile này không?"):
                return
            p_ids = str(p_id)
            p_names = str(p_name)
        else:
            curr_p_id_str = str(page.get('profile_id', ''))
            curr_p_name_str = str(page.get('profile_name', ''))
            
            p_ids_list = [p.strip() for p in curr_p_id_str.split(',') if p.strip()]
            p_names_list = [n.strip() for n in curr_p_name_str.split(',') if n.strip()]
            
            if str(p_id) in p_ids_list:
                messagebox.showwarning("Thông báo", "Profile này đã được gán rồi.")
                return
                
            p_ids_list.append(str(p_id))
            p_names_list.append(str(p_name))
            
            p_ids = ",".join(p_ids_list)
            p_names = ",".join(p_names_list)
            
        self.db.update_page_browser(idx, b_id, save=False)
        self.db.update_page_profile(idx, p_ids, p_names, save=True)
        self.log(f"Đã thêm profile [{p_name}] cho Fanpage #{idx+1}")
        
        self._update_detail_profile_dropdown()
        self.refresh_detail_profile_listbox()
        self.refresh_tree_row(idx)

    def remove_profile_from_page(self):
        idx = self.current_selected_page_idx
        if idx is None: return
        
        sel_idx = self.det_profile_listbox.curselection()
        if not sel_idx:
            messagebox.showwarning("Thông báo", "Vui lòng chọn một Profile trong danh sách chạy để xóa.")
            return
            
        page = self.db.get_fanpages()[idx]
        curr_p_id_str = str(page.get('profile_id', ''))
        curr_p_name_str = str(page.get('profile_name', ''))
        
        p_ids_list = [p.strip() for p in curr_p_id_str.split(',') if p.strip()]
        p_names_list = [n.strip() for n in curr_p_name_str.split(',') if n.strip()]
        
        del_idx = sel_idx[0]
        if 0 <= del_idx < len(p_ids_list):
            del_name = p_names_list[del_idx]
            
            p_ids_list.pop(del_idx)
            p_names_list.pop(del_idx)
            
            p_ids = ",".join(p_ids_list)
            p_names = ",".join(p_names_list)
            
            self.db.update_page_profile(idx, p_ids, p_names, save=True)
            self.log(f"Đã xóa profile [{del_name}] khỏi Fanpage #{idx+1}")
            
            self._update_detail_profile_dropdown()
            self.refresh_detail_profile_listbox()
            self.refresh_tree_row(idx)

    def refresh_detail_profile_listbox(self):
        if not hasattr(self, 'det_profile_listbox'): return
        self.det_profile_listbox.delete(0, "end")
        idx = self.current_selected_page_idx
        if idx is None: return
        
        page = self.db.get_fanpages()[idx]
        curr_p_id_str = str(page.get('profile_id', ''))
        curr_p_name_str = str(page.get('profile_name', ''))
        
        p_ids_list = [p.strip() for p in curr_p_id_str.split(',') if p.strip()]
        p_names_list = [n.strip() for n in curr_p_name_str.split(',') if n.strip()]
        
        for pid, pname in zip(p_ids_list, p_names_list):
            self.det_profile_listbox.insert("end", f"{pname} (ID: {pid})")

    def refresh_detail_folders(self):
        for w in self.det_folders_container.winfo_children():
            w.destroy()
            
        idx = self.current_selected_page_idx
        if idx is None: return
        
        page = self.db.get_fanpages()[idx]
        folders = page.get('folders', [])
        
        if not folders:
            tk.Label(self.det_folders_container, text="⚠️ Chưa có thư mục video", fg="#ea4335", bg="#ffffff", font=("Segoe UI", 9, "italic bold")).pack(anchor="w", pady=5)
            return
            
        for f_idx, folder in enumerate(folders):
            row = tk.Frame(self.det_folders_container, bg="#ffffff")
            row.pack(fill="x", pady=2)
            
            v_count = self.db.get_video_count(folder)
            count_color = "#2e7d32" if v_count > 0 else "#ea4335"
            count_text = f"({v_count} video)" if v_count > 0 else "(0 video - TRỐNG)"
            
            path_lbl = tk.Label(row, text=f"📁 {folder}", anchor="w", bg="#ffffff", font=self.font_main)
            path_lbl.pack(side="left", fill="x", expand=True)
            
            count_lbl = tk.Label(row, text=count_text, fg=count_color, bg="#ffffff", font=("Segoe UI", 8, "bold"))
            count_lbl.pack(side="left", padx=5)
            
            btn_del = tk.Button(row, text="✖", fg="gray", bg="#ffffff", relief="flat", bd=0, cursor="hand2", font=("Segoe UI", 9, "bold"),
                                command=lambda fi=f_idx: self.remove_folder_from_page(fi))
            btn_del.pack(side="right")
            
            def on_e(e, b=btn_del): b.configure(fg="red")
            def on_l(e, b=btn_del): b.configure(fg="gray")
            btn_del.bind("<Enter>", on_e)
            btn_del.bind("<Leave>", on_l)

    def add_folder_to_page(self):
        idx = self.current_selected_page_idx
        if idx is None: return
        
        folder = filedialog.askdirectory()
        if folder:
            self.db.add_folder(idx, folder)
            self.refresh_detail_folders()
            self.refresh_tree_row(idx)

    def add_folder_manual_to_page(self):
        idx = self.current_selected_page_idx
        if idx is None: return
        
        win = tk.Toplevel(self)
        win.title("Nhập Path Thủ Công")
        win.geometry("400x120")
        win.attributes("-topmost", True)
        win.resizable(False, False)
        
        tk.Label(win, text="Đường dẫn thư mục video:", font=self.font_bold).pack(padx=10, pady=5, anchor="w")
        ent = tk.Entry(win, font=self.font_main, bd=1, relief="solid")
        ent.pack(fill="x", padx=10, pady=5)
        ent.focus()
        
        def save():
            path = ent.get().strip()
            if path:
                self.db.add_folder(idx, path)
                self.refresh_detail_folders()
                self.refresh_tree_row(idx)
                win.destroy()
                
        ent.bind("<Return>", lambda e: save())
        tk.Button(win, text="Thêm Thư Mục", command=save, bg="#2e7d32", fg="white", font=self.font_main, padx=10, pady=3, relief="flat").pack(pady=5)

    def remove_folder_from_page(self, folder_idx):
        idx = self.current_selected_page_idx
        if idx is None: return
        
        self.db.remove_folder(idx, folder_idx)
        self.refresh_detail_folders()
        self.refresh_tree_row(idx)

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

    def _disable_combo_scroll(self, combo):
        combo.bind("<MouseWheel>", lambda e: "break")

    # ─── PROFILE CACHE LOADERS ───────────────────────────────
    def _rebuild_unified_profiles_data(self):
        browsers = self.db.get_browsers()
        all_options = []
        unified_p_map = {}
        
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

    def refresh_profiles_async(self, show_msg=True):
        if show_msg:
            self.log("Đang làm mới danh sách profile từ các trình duyệt...")
        
        def run():
            browsers = self.db.get_browsers()
            all_profiles_by_id = {}
            for b in browsers:
                b_id = b['id']
                try:
                    api = GemLoginAPI(b['api_url']) if b['type'] == 'gemlogin' else GPMLoginAPI(b['api_url'])
                    profiles = api.get_profiles()
                    all_profiles_by_id[b_id] = profiles if profiles is not None else []
                except Exception:
                    all_profiles_by_id[b_id] = []
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
        self._update_detail_profile_dropdown()

    # ─── SHOPEE CONFIGS HELPERS ──────────────────────────────
    def _update_shopee_ui_state(self):
        try:
            enabled = self.shopee_mode_var.get()
            state = "normal" if enabled else "disabled"
            fg = "#333" if enabled else "#aaa"
            self._shopee_file_btn.configure(state=state)
            self._shopee_open_btn.configure(state=state)
            self.lbl_shopee_file.configure(fg=fg)
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
            for g in groups:
                g_id = g['id']
                if g_id in self.shopee_group_vars:
                    self.shopee_group_vars[g_id].set(all_checked)
        else:
            checked_count = sum(1 for g in groups if self.shopee_group_vars.get(g['id']) and self.shopee_group_vars[g['id']].get())
            if checked_count == 0:
                if target in self.shopee_group_vars:
                    self.shopee_group_vars[target].set(True)
                messagebox.showwarning("Cảnh báo", "Bạn phải chọn ít nhất 1 nhóm hoặc áp dụng tất cả!")
            else:
                self.shopee_all_groups_var.set(checked_count == len(groups))
                    
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

    # ─── LOG BUFFERING SYSTEM ────────────────────────────────
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
        self._log_flush_scheduled = False
        if not self._log_buffer:
            return
        batch = "".join(self._log_buffer)
        self._log_buffer.clear()
        try:
            self.log_text.configure(state="normal")
            self.log_text.insert("end", batch)
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

    # ─── ACTIONS & POPUPS ────────────────────────────────────
    def add_fanpage_ui(self):
        win = tk.Toplevel(self)
        win.title("Thêm Fanpage")
        win.geometry("350x130")
        win.attributes("-topmost", True)
        win.resizable(False, False)

        tk.Label(win, text="Số lượng Fanpage muốn thêm:", font=self.font_main).pack(padx=15, pady=(15, 5), anchor="w")
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
        
        btn_cancel = tk.Button(btn_frame, text="Hủy", command=win.destroy, font=self.font_main, padx=12, pady=4)
        btn_cancel.pack(side="right", padx=5)
        self.style_button(btn_cancel, "#888", "#777")
        
        btn_ok = tk.Button(btn_frame, text="Thêm", command=do_add, font=self.font_main, padx=12, pady=4)
        btn_ok.pack(side="right", padx=5)
        self.style_button(btn_ok, "#4a90d9", "#357abd")

    def remove_page(self, index):
        if index is None or index < 0: return
        if messagebox.askyesno("Xác Nhận", f"Xóa Fanpage #{index+1}?"):
            self.db.remove_fanpage(index)
            self.log(f"Đã xóa Fanpage #{index+1}")
            self.refresh_ui()

    def clear_all_ui(self):
        if messagebox.askyesno("Xác Nhận", "Bạn có chắc muốn xóa TẤT CẢ fanpages?"):
            self.db.clear_all()
            self.log("Đã xóa tất cả fanpages.")
            self.refresh_ui()

    def toggle_auto_delete(self):
        val = self.auto_delete_var.get()
        self.db.set_auto_delete_videos(val)
        self.log(f"Tự xóa video sau khi đăng: {'Bật' if val else 'Tắt'}")

    def auto_map_folders_ui(self):
        base_dir = filedialog.askdirectory(title="Chọn thư mục chứa các folder video (vd: downloads)",
                                         initialdir=r"G:\Documentss\Antigravity_Gams_Youtubedownload\downloads")
        if not base_dir: return
        
        mapped_count, details = self.db.auto_map_folders(base_dir)
        
        if mapped_count > 0:
            msg = f"Đã tự động gán {mapped_count} folder mới cho các Fanpage.\n\nChi tiết:\n" + "\n".join(details[:10])
            if len(details) > 10:
                msg += f"\n... và {len(details)-10} page khác."
            messagebox.showinfo("Thành công", msg)
            self.refresh_ui()
        else:
            messagebox.showwarning("Thông báo", "Không tìm thấy folder nào khớp với tên Fanpage (hoặc các page đã có folder).")

    def set_all_enabled(self, status):
        self.db.update_pages_enabled_bulk(status)
        self.log(f"Đã tích {'chọn' if status else 'bỏ chọn'} toàn bộ các Fanpage.")

    def bulk_assign_ui(self):
        fanpages = self.db.get_fanpages()
        selected_indices = [i for i, p in enumerate(fanpages) if p.get('enabled', True)]
        groups = self.db.get_groups()
        group_names = [g['name'] for g in groups]

        win = tk.Toplevel(self)
        win.title("Gán Hàng Loạt Profile")
        win.geometry("500x250")
        win.attributes("-topmost", True)
        win.resizable(False, False)

        main_frame = tk.Frame(win, padx=20, pady=20)
        main_frame.pack(fill="both", expand=True)

        tk.Label(main_frame, text="Thiết lập gán profile hàng loạt", font=self.font_bold).pack(pady=(0, 15))

        # Row 1: Target Selector
        row_target = tk.Frame(main_frame)
        row_target.pack(fill="x", pady=5)
        tk.Label(row_target, text="Đối tượng gán:", width=12, anchor="w").pack(side="left")
        
        target_var = tk.StringVar()
        target_options = [f"Tất cả trang được tích chọn ({len(selected_indices)} page)"] + [f"Nhóm: {name}" for name in group_names]
        target_combo = ttk.Combobox(row_target, textvariable=target_var, values=target_options, state="readonly", width=45)
        target_combo.pack(side="left")
        target_combo.set(target_options[0])
        self._disable_combo_scroll(target_combo)

        # Row 2: Unified Profile Selection
        row_profile = tk.Frame(main_frame)
        row_profile.pack(fill="x", pady=5)
        tk.Label(row_profile, text="Profile gán:", width=12, anchor="w").pack(side="left")
        p_var = tk.StringVar()
        p_combo = ttk.Combobox(row_profile, textvariable=p_var, values=self._unified_profile_options, state="readonly", width=45)
        p_combo.pack(side="left")
        self._disable_combo_scroll(p_combo)
        if self._unified_profile_options:
            p_var.set(self._unified_profile_options[0])
        else:
            p_var.set("Không có profile nào để gán")

        def apply_bulk():
            opt = p_var.get()
            if opt in self._unified_profile_map:
                b_id, p_id, p_name = self._unified_profile_map[opt]
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
                    
                self.log(f"Đã gán profile {opt} cho {len(targets)} Fanpage.")
                self.refresh_ui()
                win.destroy()
            else:
                messagebox.showerror("Lỗi", "Vui lòng chọn một profile hợp lệ.")

        btn_frame = tk.Frame(main_frame)
        btn_frame.pack(fill="x", pady=20)
        
        btn_cancel = tk.Button(btn_frame, text="Hủy", command=win.destroy, bg="#888", fg="white", width=10, relief="flat")
        btn_cancel.pack(side="right", padx=5)
        
        btn_apply = tk.Button(btn_frame, text="Áp Dụng", command=apply_bulk, bg="#3a9a5c", fg="white", width=15, relief="flat", font=self.font_bold)
        btn_apply.pack(side="right", padx=5)

    def view_log_ui(self, index):
        if index is None or index < 0: return
        page = self.db.get_fanpages()[index]
        logs = self.db.get_logs(page['link'])

        win = tk.Toplevel(self)
        win.title(f"Lịch Sử Đăng: {page.get('name') or page['link']}")
        win.geometry("700x450")
        win.attributes("-topmost", True)

        frame = tk.Frame(win, padx=10, pady=10)
        frame.pack(fill="both", expand=True)

        tk.Label(frame, text="Lịch Sử Đăng Reels", font=self.font_title).pack(anchor="w", pady=(0, 8))

        txt = scrolledtext.ScrolledText(frame, font=("Consolas", 10), wrap="word")
        txt.pack(fill="both", expand=True)

        if not logs:
            txt.insert("1.0", "Chưa có lịch sử đăng.")
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
        btn_frame = tk.Frame(win, padx=10, pady=10)
        btn_frame.pack(fill="x")
        
        def clear_log():
            if messagebox.askyesno("Xác nhận", "Bạn có muốn xóa toàn bộ log lỗi Done không?"):
                try:
                    os.remove(log_file)
                    win.destroy()
                    self.log("Đã xóa file log lỗi Done.")
                except: pass
        tk.Button(btn_frame, text="Xóa Toàn Bộ Log", bg="#c0392b", fg="white", command=clear_log, padx=10, pady=5, relief="flat").pack(side="right")

    def show_video_log_ui(self, filter_name=None):
        log_file = "thongke_ngay.txt"
        win = tk.Toplevel(self)
        title = f"Log Ngày: {filter_name}" if filter_name else "Thống Kê Log Hệ Thống"
        win.title(title)
        win.geometry("900x600")
        win.attributes("-topmost", True)

        tk.Label(win, text=title, font=self.font_title).pack(padx=15, pady=(10, 5), anchor="w")

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
                    if not line: continue
                    if filter_name and f"Page: {filter_name}" not in line: continue
                    filtered.append(line)
                txt.insert("1.0", "\n".join(filtered))
            except Exception as e:
                txt.insert("1.0", f"Lỗi đọc log: {e}")
            txt.configure(state="disabled")

        populate()
        btn_frame = tk.Frame(win, padx=10, pady=8)
        btn_frame.pack(fill="x")

        def clear_logs():
            if messagebox.askyesno("Xác nhận", "Xóa toàn bộ log hôm nay?", parent=win):
                if os.path.exists(log_file):
                    os.remove(log_file)
                populate()

        tk.Button(btn_frame, text="Xoá Log", relief="flat", bg="#c0392b", fg="white", padx=12, pady=4, command=clear_logs).pack(side="left", padx=5)
        tk.Button(btn_frame, text="Làm Mới", relief="flat", bg="#4a90d9", fg="white", padx=12, pady=4, command=populate).pack(side="left", padx=5)
        tk.Button(btn_frame, text="Đóng", relief="flat", bg="#888", fg="white", padx=12, pady=4, command=win.destroy).pack(side="right", padx=5)

    def view_comment_history(self):
        win = tk.Toplevel(self)
        win.title("Lịch Sử Comment")
        win.geometry("700x500")
        win.attributes("-topmost", True)

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

    def _refresh_global_folders_ui(self):
        for widget in self.global_list_frame.winfo_children():
            widget.destroy()
            
        folders = self.db.get_global_folders()
        if not folders:
            tk.Label(self.global_list_frame, text="(Chưa có thư mục chung nào)", font=("Segoe UI", 9, "italic"), bg="#ffffff", fg="#888").pack(pady=5)
            return
            
        for i, path in enumerate(folders):
            f = tk.Frame(self.global_list_frame, bg="#ffffff")
            f.pack(fill="x", pady=1)
            tk.Label(f, text=f"• {path}", bg="#ffffff", font=self.font_main, anchor="w").pack(side="left", fill="x", expand=True)
            tk.Button(f, text="x", bg="#ffffff", fg="red", relief="flat", bd=0, cursor="hand2", font=("Segoe UI", 9, "bold"),
                      command=lambda idx=i: self.remove_global_folder_ui(idx)).pack(side="right")

    def add_global_folder_ui(self):
        path = filedialog.askdirectory()
        if path:
            self.db.add_global_folder(path)
            self._refresh_global_folders_ui()

    def remove_global_folder_ui(self, index):
        self.db.remove_global_folder(index)
        self._refresh_global_folders_ui()

    def group_profiles_manager_dialog(self, group_id, group_name, refresh_callback=None):
        win = tk.Toplevel(self)
        win.title(f"Cấu Hình Profiles Nhóm: {group_name}")
        win.geometry("450x380")
        win.resizable(False, False)
        win.attributes("-topmost", True)
        
        main_frame = tk.Frame(win, padx=15, pady=15)
        main_frame.pack(fill="both", expand=True)
        
        tk.Label(main_frame, text=f"Nhóm: {group_name}", font=self.font_bold).pack(anchor="w", pady=(0, 10))
        
        # 1. Selector row
        sel_row = tk.Frame(main_frame)
        sel_row.pack(fill="x", pady=5)
        tk.Label(sel_row, text="Chọn Profile:", font=self.font_bold).pack(side="left", padx=(0, 5))
        
        # Available profiles combobox
        p_combo = ttk.Combobox(sel_row, state="readonly", width=35)
        p_combo.pack(side="left", padx=5)
        self._disable_combo_scroll(p_combo)
        
        # Populate values
        opts = list(self._unified_profile_options)
        p_combo['values'] = opts
        if opts:
            p_combo.set(opts[0])
            
        # 2. Listbox & Scrollbar
        list_frame = tk.Frame(main_frame)
        list_frame.pack(fill="both", expand=True, pady=10)
        
        tk.Label(list_frame, text="Danh sách các Profile chạy song song:", font=self.font_bold).pack(anchor="w", pady=(0, 5))
        
        list_container = tk.Frame(list_frame)
        list_container.pack(fill="both", expand=True)
        
        listbox = tk.Listbox(list_container, font=self.font_main, bd=1, relief="solid")
        listbox.pack(side="left", fill="both", expand=True)
        
        scrollbar = ttk.Scrollbar(list_container, orient="vertical", command=listbox.yview)
        scrollbar.pack(side="right", fill="y")
        listbox.configure(yscrollcommand=scrollbar.set)
        
        # Populate current profiles of the group
        groups = self.db.get_groups()
        g = next((group for group in groups if group['id'] == group_id), {})
        
        curr_b_id = g.get('browser_id')
        curr_p_id_str = str(g.get('profile_id', ''))
        curr_p_name_str = str(g.get('profile_name', ''))
        
        p_ids_list = [p.strip() for p in curr_p_id_str.split(',') if p.strip()]
        p_names_list = [n.strip() for n in curr_p_name_str.split(',') if n.strip()]
        
        # Track local lists
        local_data = {
            'b_id': curr_b_id,
            'ids': p_ids_list,
            'names': p_names_list
        }
        
        def refresh_local_list():
            listbox.delete(0, "end")
            for pid, pname in zip(local_data['ids'], local_data['names']):
                listbox.insert("end", f"{pname} (ID: {pid})")
                
        refresh_local_list()
        
        # Buttons Frame (Add/Remove)
        btns_row = tk.Frame(main_frame)
        btns_row.pack(fill="x", pady=5)
        
        def add_prof():
            opt = p_combo.get()
            if not opt or opt not in self._unified_profile_map:
                messagebox.showwarning("Cảnh báo", "Vui lòng chọn một profile hợp lệ.", parent=win)
                return
                
            b_id, p_id, p_name = self._unified_profile_map[opt]
            
            # If group has a different browser assigned, ask if they want to switch
            if local_data['b_id'] and local_data['b_id'] != b_id:
                if not messagebox.askyesno("Xác nhận", f"Profile này thuộc trình duyệt khác ({b_id}) so với trình duyệt của nhóm ({local_data['b_id']}).\nBạn có muốn chuyển nhóm sang trình duyệt {b_id} và gán profile này không?", parent=win):
                    return
                # Reset since browser changed
                local_data['b_id'] = b_id
                local_data['ids'] = []
                local_data['names'] = []
                
            if not local_data['b_id']:
                local_data['b_id'] = b_id
                
            if str(p_id) in local_data['ids']:
                messagebox.showwarning("Cảnh báo", "Profile này đã được thêm vào danh sách.", parent=win)
                return
                
            local_data['ids'].append(str(p_id))
            local_data['names'].append(str(p_name))
            refresh_local_list()
            
        def remove_prof():
            sel = listbox.curselection()
            if not sel:
                messagebox.showwarning("Cảnh báo", "Vui lòng chọn một profile trong danh sách để xóa.", parent=win)
                return
            del_idx = sel[0]
            if 0 <= del_idx < len(local_data['ids']):
                local_data['ids'].pop(del_idx)
                local_data['names'].pop(del_idx)
                refresh_local_list()
                
        btn_add = tk.Button(btns_row, text="➕ Thêm Profile", command=add_prof, font=("Segoe UI", 9, "bold"), padx=10, pady=4)
        btn_add.pack(side="left", padx=5)
        self.style_button(btn_add, "#3a9a5c", "#2d7647")
        
        btn_del = tk.Button(btns_row, text="➖ Xóa Profile", command=remove_prof, font=("Segoe UI", 9, "bold"), padx=10, pady=4)
        btn_del.pack(side="left", padx=5)
        self.style_button(btn_del, "#ea4335", "#d62516")
        
        # Save & Cancel row
        footer = tk.Frame(win, pady=10)
        footer.pack(side="bottom")
        
        def on_save():
            new_p_ids = ",".join(local_data['ids'])
            new_p_names = ",".join(local_data['names'])
            b_id = local_data['b_id'] or "gemlogin_default"
            
            self.db.update_group(group_id, group_name, b_id, new_p_ids, new_p_names)
            self.log(f"Đã cập nhật danh sách profiles cho Nhóm {group_name}: {new_p_names}")
            
            if refresh_callback:
                refresh_callback()
            self.refresh_ui()
            win.destroy()
            
        btn_save = tk.Button(footer, text="Lưu", command=on_save, width=12, pady=5)
        btn_save.pack(side="left", padx=5)
        self.style_button(btn_save, "#1a73e8", "#1557b0")
        
        btn_cancel = tk.Button(footer, text="Hủy", command=win.destroy, width=12, pady=5)
        btn_cancel.pack(side="left", padx=5)
        self.style_button(btn_cancel, "#5f6368", "#474a4d")
        
        win.wait_window()

    def group_management_ui(self):
        win = tk.Toplevel(self)
        win.title("Quản Lý Nhóm Fanpage")
        win.geometry("780x500")
        win.attributes("-topmost", True)

        main_frame = tk.Frame(win, padx=15, pady=15)
        main_frame.pack(fill="both", expand=True)

        tk.Label(main_frame, text="Danh Sách Nhóm", font=self.font_title).pack(anchor="w", pady=(0, 10))

        list_frame = tk.Frame(main_frame)
        list_frame.pack(fill="both", expand=True)

        def get_unified_profiles():
            browsers = self.db.get_browsers()
            all_opts = []
            unified_map = {}
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
                tk.Label(list_frame, text="(Chưa có nhóm nào)", font=("Segoe UI", 10, "italic"), fg="#888").pack(pady=20)
            
            for g in groups:
                g_row = tk.Frame(list_frame, pady=5, bg="#f9f9f9", relief="flat")
                g_row.pack(fill="x", pady=2)

                tk.Label(g_row, text="Tên nhóm:", bg="#f9f9f9", font=self.font_bold).pack(side="left", padx=(10, 5))
                name_ent = tk.Entry(g_row, width=20, font=self.font_main)
                name_ent.insert(0, g['name'])
                name_ent.pack(side="left", padx=5)

                tk.Label(g_row, text="Profile mặc định:", bg="#f9f9f9", font=self.font_bold).pack(side="left", padx=(10, 5))
                
                unified_opts, unified_map = get_unified_profiles()
                curr_b_id = g.get('browser_id')
                curr_p_id = g.get('profile_id')
                found_opt = ""
                if curr_b_id and curr_p_id:
                    if ',' in str(curr_p_id):
                        b_config = self.db.get_browser_by_id(curr_b_id)
                        b_name_str = b_config['name'] if b_config else "Unknown"
                        found_opt = f"[{b_name_str}] {g.get('profile_name', 'Multiple Profiles')}"
                    else:
                        for opt, (b_id, p_id, p_name) in unified_map.items():
                            if b_id == curr_b_id and str(p_id) == str(curr_p_id):
                                found_opt = opt
                                break
                
                if not found_opt and curr_b_id and curr_p_id:
                    b_config = self.db.get_browser_by_id(curr_b_id)
                    b_name_str = b_config['name'] if b_config else "Unknown"
                    found_opt = f"[{b_name_str}] {g.get('profile_name', 'Unknown')}"
                    unified_opts.append(found_opt)
                    unified_map[found_opt] = (curr_b_id, curr_p_id, g.get('profile_name', 'Unknown'))
                
                b_var = tk.StringVar(value=found_opt)
                combo_opts = list(unified_opts) + ["+ Chọn nhiều Profile..."]
                b_combo = ttk.Combobox(g_row, textvariable=b_var, values=combo_opts, state="readonly", width=20)
                b_combo.pack(side="left", padx=5)
                self._disable_combo_scroll(b_combo)

                # Profiles manager button next to combobox
                btn_profiles = tk.Button(g_row, text="👥 Profiles", command=lambda gid=g['id'], name=g['name']: self.group_profiles_manager_dialog(gid, name, refresh_callback=refresh_list), font=("Segoe UI", 9, "bold"), padx=5)
                btn_profiles.pack(side="left", padx=2)
                self.style_button(btn_profiles, "#7c5cbf", "#6242a3")

                def make_combo_select(bv=b_var, gid=g['id'], name=g['name']):
                    def _select(event=None):
                        opt = bv.get()
                        if opt == "+ Chọn nhiều Profile...":
                            self.group_profiles_manager_dialog(gid, name, refresh_callback=refresh_list)
                    return _select
                
                b_combo.bind("<<ComboboxSelected>>", make_combo_select(b_var, g['id'], g['name']))

                def make_save(gid=g['id'], ne=name_ent, bv=b_var, umap=unified_map):
                    def _save():
                        new_name = ne.get().strip()
                        opt = bv.get()
                        if opt in umap:
                            b_id, p_id, p_name = umap[opt]
                        else:
                            b_id, p_id, p_name = "gemlogin_default", "", ""
                        
                        self.db.update_group(gid, new_name, b_id, p_id, p_name)
                        self.log(f"Đã cập nhật nhóm: {new_name}")
                        refresh_list()
                        self.refresh_ui()
                    return _save

                def make_del(gid=g['id'], name=g['name']):
                    def _del():
                        if messagebox.askyesno("Xác nhận", f"Xóa nhóm '{name}'?"):
                            self.db.remove_group(gid)
                            self.log(f"Đã xóa nhóm: {name}")
                            refresh_list()
                            self.refresh_ui()
                    return _del

                btn_save = tk.Button(g_row, text="Lưu", command=make_save(), padx=6)
                btn_save.pack(side="left", padx=3)
                self.style_button(btn_save, "#2e7d32", "#225c25")
                
                def open_assign(gid=g['id'], name=g['name']):
                    return lambda: self.assign_fanpages_to_group_ui(gid, name, refresh_callback=refresh_list)
                
                btn_assign = tk.Button(g_row, text="Gán Pages", command=open_assign(), padx=6)
                btn_assign.pack(side="left", padx=3)
                self.style_button(btn_assign, "#7c5cbf", "#6242a3")
                
                btn_del = tk.Button(g_row, text="Xóa", command=make_del(), padx=6)
                btn_del.pack(side="left", padx=3)
                self.style_button(btn_del, "#d32f2f", "#b71c1c")

            # Add new group row
            ttk.Separator(list_frame).pack(fill="x", pady=15)
            add_row = tk.Frame(list_frame)
            add_row.pack(fill="x", pady=5)
            
            tk.Label(add_row, text="Tên nhóm mới:", font=self.font_bold).pack(side="left", padx=(0, 5))
            new_name_ent = tk.Entry(add_row, width=20, font=self.font_main)
            new_name_ent.pack(side="left", padx=5)
            
            def add_new():
                name = new_name_ent.get().strip()
                if name:
                    self.db.add_group(name)
                    self.log(f"Đã thêm nhóm mới: {name}")
                    refresh_list()
                    self.refresh_ui()
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

    def assign_fanpages_to_group_ui(self, group_id, group_name, refresh_callback):
        win = tk.Toplevel(self)
        win.title(f"Gán Fanpage vào nhóm: {group_name}")
        win.geometry("500x600")
        win.attributes("-topmost", True)

        main_frame = tk.Frame(win, padx=15, pady=15)
        main_frame.pack(fill="both", expand=True)

        tk.Label(main_frame, text=f"Chọn Fanpage cho nhóm '{group_name}'", font=self.font_bold).pack(anchor="w", pady=(0, 10))

        # Scrollable area
        canvas_frame = tk.Frame(main_frame)
        canvas_frame.pack(fill="both", expand=True)
        
        canvas = tk.Canvas(canvas_frame)
        scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas)

        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        fanpages = self.db.get_fanpages()
        vars = []
        
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
                other_name = "Nhóm khác"
                for g in self.db.get_groups():
                    if g['id'] == page.get('group_id'):
                        other_name = g['name']
                        break
                tk.Label(p_row, text=f"(Đang ở: {other_name})", font=("Segoe UI", 8, "italic"), fg="#888").pack(side="left", padx=5)

        def save_assignment():
            selected_indices = [idx for idx, var in vars if var.get()]
            all_pages = self.db.get_fanpages()
            for i, page in enumerate(all_pages):
                if page.get('group_id') == group_id:
                    if i not in selected_indices:
                        self.db.update_page_group(i, "", save=False)
            
            self.db.update_pages_group_bulk(selected_indices, group_id)
            self.log(f"Đã cập nhật Fanpage cho nhóm '{group_name}'")
            if refresh_callback: refresh_callback()
            self.refresh_ui()
            win.destroy()

        btn_frame = tk.Frame(main_frame)
        btn_frame.pack(side="bottom", pady=10)
        
        btn_cancel = tk.Button(btn_frame, text="Hủy", command=win.destroy, bg="#888", fg="white", width=10, relief="flat")
        btn_cancel.pack(side="right", padx=5)
        
        btn_save = tk.Button(btn_frame, text="Lưu Thay Đổi", command=save_assignment, bg="#3a9a5c", fg="white", width=15, relief="flat", font=self.font_bold)
        btn_save.pack(side="right", padx=5)

    # ─── CORE POSTING CONTROLLER (BACKGROUND THREADS) ─────────
    def _on_mode_change(self, event=None):
        map_mode = {"Đăng + Comment": "post_and_comment", "Chỉ Đăng": "post_only", "Chỉ Comment": "comment_only"}
        choice = self.run_mode_var.get()
        self.db.set_run_mode(map_mode.get(choice, "post_and_comment"))
        self.log(f"Đã chọn chế độ chạy: {choice}")

    def start_posting(self):
        self.stop_flag = False
        self.btn_start.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        self.status_lbl.configure(text="● HỆ THỐNG ĐANG HOẠT ĐỘNG", fg="#27ae60", bg="#d4efdf")
        threading.Thread(target=self._start_posting_thread, daemon=True).start()

    def stop_posting(self):
        self.stop_flag = True
        self.log("Dừng chạy được yêu cầu. Đang dừng sau video hiện tại...")
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

                shopee_mode = self.shopee_mode_var.get()
                shopee_products = []
                if shopee_mode:
                    shopee_file = self.shopee_file_path.get()
                    shopee_products = self.parse_shopee_file(shopee_file)
                    if shopee_products:
                        random.shuffle(shopee_products)
                        self.log(f"[Shopee] Đã tải {len(shopee_products)} sản phẩm từ file. Bắt đầu phân bổ...")
                    else:
                        self.log("[Shopee] ⚠️ Chế độ Rải Link bật nhưng file rỗng / lỗi. Tắt Shopee phiên này.")
                        shopee_mode = False

                enabled_pages = [p for p in fanpages if p.get('enabled', True)]
                if not enabled_pages:
                    self.log("Không có Fanpage nào được chọn để chạy.")
                else:
                    total_en = len(enabled_pages)
                    self.log(f"Quét công việc của {total_en} Fanpage...")
                    
                    global_folders = self.db.get_global_folders()
                    groups = self.db.get_groups()
                    group_map = {g['id']: g for g in groups}
                    
                    # 1. Collect pages that have work
                    work_candidates = []
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
                            
                        # Find original index
                        p_idx = -1
                        for k, p_raw in enumerate(fanpages):
                            if p_raw['link'] == page['link']:
                                p_idx = k
                                break
                                
                        # Get candidate profile ids
                        p_id_str = str(page.get('profile_id', ''))
                        p_ids = [p.strip() for p in p_id_str.split(',') if p.strip()]
                        p_names_str = str(page.get('profile_name', ''))
                        p_names = [p.strip() for p in p_names_str.split(',') if p.strip()]
                        
                        # If page has no profile, check group
                        p_group_id = page.get('group_id', '')
                        if not p_ids and p_group_id and p_group_id in group_map:
                            g = group_map[p_group_id]
                            g_p_id_str = str(g.get('profile_id', ''))
                            p_ids = [p.strip() for p in g_p_id_str.split(',') if p.strip()]
                            g_p_names_str = str(g.get('profile_name', ''))
                            p_names = [p.strip() for p in g_p_names_str.split(',') if p.strip()]
                            
                        if not p_ids:
                            p_ids = [""]
                            p_names = [""]
                            
                        b_id = page.get('browser_id', 'gemlogin_default')
                        if p_idx != -1:
                            b_id = self.db.resolve_page_browser_id(p_idx)
                        if p_group_id and p_group_id in group_map:
                            if not page.get('browser_id'):
                                b_id = group_map[p_group_id].get('browser_id', b_id)
                                
                        work_candidates.append({
                            'page': page,
                            'folders': folders,
                            'unposted_files': unposted_files,
                            'to_comment_historic': to_comment_historic,
                            'b_id': b_id,
                            'p_ids': p_ids,
                            'p_names': p_names,
                            'stt': stt,
                            'page_name': page_name
                        })
                        
                    # --- Profile Conflict Elimination Algorithm ---
                    # Group work_candidates by browser_id
                    candidates_by_browser = {}
                    for item in work_candidates:
                        bid = item['b_id']
                        if bid not in candidates_by_browser:
                            candidates_by_browser[bid] = []
                        candidates_by_browser[bid].append(item)

                    for bid, items in candidates_by_browser.items():
                        # Determine group for each item
                        for item in items:
                            pg = item['page']
                            item['grp_key'] = pg.get('group_id') if pg.get('group_id') else f"link_{pg.get('link')}"

                        # Collect unique groups
                        unique_groups = list(set(item['grp_key'] for item in items))
                        if len(unique_groups) <= 1:
                            continue

                        # Collect profiles list for each group
                        group_profiles = {}
                        group_page_counts = {}
                        for item in items:
                            g = item['grp_key']
                            group_page_counts[g] = group_page_counts.get(g, 0) + 1
                            if g not in group_profiles:
                                group_profiles[g] = set()
                            for pid in item['p_ids']:
                                if pid:
                                    group_profiles[g].add(pid)

                        # Find which groups share each profile
                        groups_for_profile = {}
                        for g, pids in group_profiles.items():
                            for pid in pids:
                                if pid not in groups_for_profile:
                                    groups_for_profile[pid] = set()
                                groups_for_profile[pid].add(g)

                        # Check if any profile has overlap
                        overlapping_pids = [pid for pid, grps in groups_for_profile.items() if len(grps) > 1]
                        if overlapping_pids:
                            self.log("⚠️ Phát hiện dùng chung profile giữa các nhóm. Đang tiến hành phân bổ độc lập...")

                        # Track owned profiles for each group
                        owned_profiles = {g: set() for g in unique_groups}

                        # Step A: Assign unique profiles first
                        for pid, grps in list(groups_for_profile.items()):
                            if len(grps) == 1:
                                g = list(grps)[0]
                                owned_profiles[g].add(pid)
                                del groups_for_profile[pid]

                        # Step B: Assign shared profiles greedily to avoid overlap
                        shared_pids = list(groups_for_profile.keys())
                        for pid in shared_pids:
                            grps = list(groups_for_profile[pid])
                            def group_sort_key(g):
                                return (len(owned_profiles[g]), -group_page_counts.get(g, 0), str(g))
                            grps.sort(key=group_sort_key)
                            best_g = grps[0]
                            owned_profiles[best_g].add(pid)

                        # Log the resolved partition for user visibility
                        if overlapping_pids:
                            for g in unique_groups:
                                allowed_pids = owned_profiles[g]
                                display_names = []
                                for pid in allowed_pids:
                                    found_name = pid
                                    for item in items:
                                        if item['grp_key'] == g:
                                            for cur_id, cur_name in zip(item['p_ids'], item['p_names']):
                                                if cur_id == pid:
                                                    found_name = cur_name
                                                    break
                                    display_names.append(found_name)
                                    
                                grp_name = g
                                if g in group_map:
                                    grp_name = group_map[g]['name']
                                elif g.startswith("link_"):
                                    for item in items:
                                        if item['grp_key'] == g:
                                            grp_name = f"Page {item['page_name']}"
                                            break
                                            
                                if display_names:
                                    self.log(f"🛡️ [Độc lập Profile] Nhóm/Page '{grp_name}' giới hạn chạy trên: {', '.join(display_names)}")

                        # Step C: Filter candidate profiles for each item
                        for item in items:
                            g = item['grp_key']
                            allowed = owned_profiles[g]
                            
                            new_p_ids = []
                            new_p_names = []
                            for pid, pname in zip(item['p_ids'], item['p_names']):
                                if pid in allowed:
                                    new_p_ids.append(pid)
                                    new_p_names.append(pname)
                                    
                            if new_p_ids:
                                item['p_ids'] = new_p_ids
                                item['p_names'] = new_p_names
                    # --- End of Profile Conflict Elimination ---

                    # 2. Sort by number of candidates ascending
                    work_candidates.sort(key=lambda x: len(x['p_ids']))
                    
                    # 3. Load balance and group
                    profile_groups = {}
                    profile_counts = {}
                    
                    for item in work_candidates:
                        page = item['page']
                        b_id = item['b_id']
                        p_ids = item['p_ids']
                        p_names = item['p_names']
                        
                        # Find candidate with minimum load
                        chosen_p_id = p_ids[0]
                        min_load = float('inf')
                        for pid in p_ids:
                            load = profile_counts.get((b_id, pid), 0)
                            if load < min_load:
                                min_load = load
                                chosen_p_id = pid
                                
                        # Increment load
                        profile_counts[(b_id, chosen_p_id)] = profile_counts.get((b_id, chosen_p_id), 0) + 1
                        
                        # Add to group
                        key = (b_id, chosen_p_id)
                        if key not in profile_groups:
                            profile_groups[key] = {
                                'pages': [],
                                'profile_name': page.get('profile_name', str(chosen_p_id))
                            }
                            
                        # If profile_name contains comma-separated names, try to find matching index
                        chosen_name = str(chosen_p_id)
                        if len(p_names) == len(p_ids):
                            try:
                                idx_name = p_ids.index(chosen_p_id)
                                chosen_name = p_names[idx_name]
                            except: pass
                        elif p_names:
                            chosen_name = p_names[0]
                        
                        profile_groups[key]['profile_name'] = chosen_name
                        
                        profile_groups[key]['pages'].append({
                            'name': page.get('name'),
                            'link': page.get('link'),
                            'group_id': page.get('group_id', ''),
                            'folders': item['folders'],
                            'unposted_files': item['unposted_files'],
                            'to_comment_historic': item['to_comment_historic'],
                        })
                    
                    if not profile_groups:
                        self.log("Không có Fanpage nào có việc cần làm trong vòng này.")
                    else:
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
                                        continue

                                    page_pool = shopee_products[:]
                                    random.shuffle(page_pool)

                                    assignment = {}
                                    for idx_v, (folder, vf) in enumerate(unposted):
                                        if idx_v >= len(page_pool):
                                            page_pool_ext = shopee_products[:]
                                            random.shuffle(page_pool_ext)
                                            page_pool = page_pool + page_pool_ext
                                        prod = page_pool[idx_v]
                                        assignment[vf] = prod

                                    pdata['shopee_assignment'] = assignment
                                    names_log = ', '.join(f"#{p['stt']}:{p['name']}" for p in assignment.values())
                                    self.log(f"[Shopee] [{pdata['name']}] Gán {len(assignment)} sản phẩm Shopee: {names_log}")

                        self.active_procs = [p for p in self.active_procs if p.poll() is None]
                        all_profile_keys = list(profile_groups.keys())
                        self.log(f"Phát hiện tổng cộng {len(all_profile_keys)} profile có việc cần chạy.")
                        
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
                                
                                page_names_list = ", ".join([p['name'] for p in pages_for_profile])
                                
                                from db_helper import db as sqlite_db
                                job = {
                                    'run_mode': run_mode,
                                    'skip_commented': skip_commented,
                                    'auto_delete': auto_delete,
                                    'browser_config': b_config,
                                    'profile_id': str(p_id),
                                    'profile_label': str(p_id),
                                    'pages': pages_for_profile,
                                    'shopee_mode': shopee_mode,
                                    'db_file': self.db.file_path,
                                    'sqlite_file': sqlite_db.db_path,
                                }
                                tmp = tempfile.NamedTemporaryFile(
                                    mode='w', suffix='.json', delete=False, encoding='utf-8',
                                    dir=_BASE_DIR, prefix=f'job_{p_id}_')
                                json.dump(job, tmp, ensure_ascii=False)
                                tmp.close()
                                
                                worker_script = os.path.join(_BASE_DIR, 'page_worker.py')
                                proc = subprocess.Popen(
                                    ['python', worker_script, tmp.name],
                                    creationflags=subprocess.CREATE_NEW_CONSOLE
                                )
                                self.active_procs.append(proc)
                                current_chunk_procs.append(proc)
                                self.log(f"🚀 [{p_display_name}] Đã mở CMD chạy {len(pages_for_profile)} Fanpage: {page_names_list}")
                            
                            if current_chunk_procs:
                                self.log(f"Đang chờ {len(current_chunk_procs)} tiến trình CMD của nhóm này hoàn tất...")
                                while not self.stop_flag:
                                    chunk_done = all(p.poll() is not None for p in current_chunk_procs)
                                    if chunk_done: break
                                    time.sleep(2)
                                
                            if self.stop_flag: break
                        self.log(f"===== Đã xử lý xong toàn bộ Fanpage được gán trong lượt này =====")

                if self.stop_flag:
                    break

                if loop_mode == 'once':
                    self.log("Hoàn tất chạy 1 lần.")
                    break
                elif loop_mode == 'count' and run_number >= loop_count:
                    self.log(f"Đã hoàn tất {loop_count} lần chạy theo lịch trình.")
                    break

                rest_seconds = random.randint(rest_min * 60, rest_max * 60)
                self.log(f"Hệ thống nghỉ ngơi {rest_seconds // 60} phút trước lần chạy tiếp theo...")
                elapsed = 0
                while elapsed < rest_seconds and not self.stop_flag:
                    time.sleep(10)
                    elapsed += 10
        except Exception as global_e:
            self.log(f"!!! LỖI NGHIÊM TRỌNG TRONG LUỒNG CHẠY CHÍNH: {global_e}")
            import traceback
            print(traceback.format_exc())
            self.stop_flag = True
        finally:
            self.log("Luồng chạy dừng hoạt động.")
            self.stop_flag = True
            self.btn_start.configure(state="normal")
            self.btn_stop.configure(state="disabled")
            self.status_lbl.configure(text="● HỆ THỐNG ĐANG DỪNG", fg="#c0392b", bg="#fadbd8")

    def _process_single_page(self, page, run_mode, skip_commented, auto_delete, is_last_for_profile=True):
        # Fallback method, not normally executed as tasks are outsourced to page_worker.py
        pass

    def on_app_exit(self):
        self.stop_flag = True
        self.log("Đang đóng ứng dụng. Tiến trình CMD con vẫn được giữ chạy...")
        self.destroy()
        sys.exit(0)

if __name__ == "__main__":
    from tkinter import simpledialog

    class ProfileSelector(tk.Tk):
        def __init__(self):
            super().__init__()
            self.title("Chọn Profile Hoạt Động")
            self.geometry("520x450")
            self.resizable(False, False)
            self.configure(bg="#1e1e2e")
            
            # Load or create config
            self.config_path = "profiles_config.json"
            self.load_config()
            
            # Design Title
            lbl_title = tk.Label(self, text="HỆ THỐNG QUẢN LÝ PROFILE", font=("Arial", 16, "bold"), bg="#1e1e2e", fg="#cba6f7")
            lbl_title.pack(pady=20)
            
            lbl_desc = tk.Label(self, text="Vui lòng chọn Profile để truy cập Dashboard riêng biệt:", font=("Arial", 10), bg="#1e1e2e", fg="#a6adc8")
            lbl_desc.pack(pady=(0, 20))
            
            # Grid frame
            grid_frame = tk.Frame(self, bg="#1e1e2e")
            grid_frame.pack(fill="both", expand=True, padx=40)
            
            self.buttons = []
            for i, prof in enumerate(self.profiles):
                row = i // 2
                col = i % 2
                
                # Subframe for button + edit button
                item_frame = tk.Frame(grid_frame, bg="#1e1e2e", pady=8, padx=8)
                item_frame.grid(row=row, column=col, sticky="nsew")
                
                # Select button
                btn_select = tk.Button(
                    item_frame, text=prof['name'], font=("Arial", 11, "bold"),
                    bg="#313244", fg="#cdd6f4", activebackground="#45475a", activeforeground="#cba6f7",
                    bd=0, height=2, width=15, cursor="hand2",
                    command=lambda p=prof: self.select_profile(p)
                )
                btn_select.pack(side="left", fill="x", expand=True)
                self.buttons.append((btn_select, prof))
                
                # Edit name button
                btn_edit = tk.Button(
                    item_frame, text="✏️", font=("Arial", 10),
                    bg="#1e1e2e", fg="#fab387", activebackground="#1e1e2e", activeforeground="#f38ba8",
                    bd=0, cursor="hand2", padx=5,
                    command=lambda idx=i: self.edit_profile_name(idx)
                )
                btn_edit.pack(side="right", padx=(5, 0))
                
            # Set grid weight
            for r in range(3):
                grid_frame.rowconfigure(r, weight=1)
            for c in range(2):
                grid_frame.columnconfigure(c, weight=1)
                
            self.selected_profile = None

        def load_config(self):
            if os.path.exists(self.config_path):
                try:
                    with open(self.config_path, "r", encoding="utf-8") as f:
                        self.config = json.load(f)
                except:
                    self.config = self.get_default_config()
            else:
                self.config = self.get_default_config()
                self.save_config()
                
            self.profiles = self.config.get("profiles", [])

        def get_default_config(self):
            return {
                "profiles": [
                    {"id": 1, "name": "Profile 1", "db_file": "database.json", "sqlite_file": "system.db"},
                    {"id": 2, "name": "Profile 2", "db_file": "database_2.json", "sqlite_file": "system_2.db"},
                    {"id": 3, "name": "Profile 3", "db_file": "database_3.json", "sqlite_file": "system_3.db"},
                    {"id": 4, "name": "Profile 4", "db_file": "database_4.json", "sqlite_file": "system_4.db"},
                    {"id": 5, "name": "Profile 5", "db_file": "database_5.json", "sqlite_file": "system_5.db"},
                    {"id": 6, "name": "Profile 6", "db_file": "database_6.json", "sqlite_file": "system_6.db"}
                ]
            }

        def save_config(self):
            try:
                with open(self.config_path, "w", encoding="utf-8") as f:
                    json.dump(self.config, f, indent=4, ensure_ascii=False)
            except Exception as e:
                print(f"Error saving profiles config: {e}")

        def edit_profile_name(self, idx):
            current_name = self.profiles[idx]['name']
            new_name = simpledialog.askstring("Đổi tên Profile", f"Nhập tên mới cho {current_name}:", parent=self)
            if new_name and new_name.strip():
                self.profiles[idx]['name'] = new_name.strip()
                self.config['profiles'] = self.profiles
                self.save_config()
                self.buttons[idx][0].configure(text=new_name.strip())

        def select_profile(self, profile):
            self.selected_profile = profile
            self.destroy()

    selector = ProfileSelector()
    selector.mainloop()
    
    if selector.selected_profile:
        prof = selector.selected_profile
        app = App(
            db_file=prof['db_file'],
            sqlite_file=prof['sqlite_file'],
            profile_name=prof['name']
        )
        app.mainloop()

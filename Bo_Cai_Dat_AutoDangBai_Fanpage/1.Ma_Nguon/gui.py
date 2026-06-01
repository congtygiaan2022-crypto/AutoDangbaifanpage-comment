import customtkinter as ctk
from tkinter import filedialog, messagebox
import threading
import os
from database import Database
from gemlogin_api import GemLoginAPI
from facebook_automator import FacebookAutomator
import time
import webbrowser

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Công Cụ Đăng Reels Tự Động")
        
        # Set window size to 65% of screen
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        window_width = int(screen_width * 0.65)
        window_height = int(screen_height * 0.65)
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        self.geometry(f"{window_width}x{window_height}+{x}+{y}")
        
        # Set minimum size to prevent too small window
        self.minsize(900, 600)
        
        self.db = Database()
        self.gem_api = GemLoginAPI()
        self.automator = None
        
        # Load and apply theme AFTER db is initialized
        saved_theme = self.db.get_theme()
        ctk.set_appearance_mode(saved_theme)
        
        # Apple SF-inspired Colors (Light, Dark)
        self.bg_color = ("#F5F5F7", "#121212")
        self.sidebar_color = ("#FFFFFF", "#1E1E1E")
        self.card_color = ("#FFFFFF", "#252525")
        self.text_color_primary = ("#000000", "#FFFFFF")
        self.text_color_secondary = ("#666666", "#AAAAAA")
        
        self.accent_blue = "#007AFF"
        self.accent_green = "#34C759"
        self.accent_red = "#FF3B30"
        self.accent_purple = "#AF52DE"
        
        self.entry_bg = ("#E5E5EA", "#1A1A1A")
        self.border_color = ("#D1D1D6", "#333333")
        
        self.configure(fg_color=self.bg_color)

        # Sidebar Layout
        self.sidebar = ctk.CTkFrame(self, width=220, corner_radius=0, fg_color=self.sidebar_color, border_width=0)
        self.sidebar.pack(side="left", fill="y")
        
        self.logo_label = ctk.CTkLabel(self.sidebar, text="Đăng Bài Tự Động", font=ctk.CTkFont(family="SF Pro Display", size=22, weight="bold"))
        self.logo_label.pack(padx=20, pady=(30, 20))

        # Sidebar Buttons
        self.btn_add_page = ctk.CTkButton(self.sidebar, text="+ Thêm Fanpage", height=40, corner_radius=10,
                                          fg_color=self.accent_blue, hover_color="#0062CC",
                                          command=self.add_fanpage_ui)
        self.btn_add_page.pack(padx=20, pady=(20, 10), fill="x")

        self.btn_clear_all = ctk.CTkButton(self.sidebar, text="Xóa Tất Cả", height=40, corner_radius=10, 
                                           fg_color=("gray85", "#333333"), hover_color=("gray75", "#444444"),
                                           command=self.clear_all_ui)
        self.btn_clear_all.pack(padx=20, pady=10, fill="x")

        self.btn_set_comment = ctk.CTkButton(self.sidebar, text="Cài Đặt Bình Luận", height=40, corner_radius=10, 
                                            fg_color=self.accent_purple, hover_color="#8E44AD",
                                            command=self.set_comment_ui)
        self.btn_set_comment.pack(padx=20, pady=10, fill="x")

        self.btn_scheduling = ctk.CTkButton(self.sidebar, text="⏰ Cài Đặt Lịch Chạy", height=40, corner_radius=10, 
                                           fg_color="#FF6B35", hover_color="#E85D2A",
                                           command=self.scheduling_settings_ui)
        self.btn_scheduling.pack(padx=20, pady=10, fill="x")

        self.btn_theme = ctk.CTkButton(self.sidebar, text="🎨 Đổi Giao Diện", height=40, corner_radius=10, 
                                       fg_color=("gray85", "#6C757D"), hover_color=("gray75", "#5A6268"),
                                       command=self.toggle_theme)
        self.btn_theme.pack(padx=20, pady=10, fill="x")

        self.btn_check_log = ctk.CTkButton(self.sidebar, text="📊 Kiểm Tra Video & Log", height=40, corner_radius=10, 
                                           fg_color=self.accent_green, hover_color="#28A745",
                                           command=self.show_video_log_ui)
        self.btn_check_log.pack(padx=20, pady=10, fill="x")

        # Divider
        ctk.CTkFrame(self.sidebar, height=2, fg_color="#333333").pack(padx=20, pady=15, fill="x")
        
        # Run Mode Selector
        ctk.CTkLabel(self.sidebar, text="Chế Độ Chạy:", font=ctk.CTkFont(size=12, weight="bold"), anchor="w").pack(padx=25, pady=(5, 0), anchor="w")
        self.run_mode_var = ctk.StringVar(value=self.db.get_run_mode())
        
        def on_mode_change(choice):
            map_mode = {"Đăng + Comment": "post_and_comment", "Chỉ Đăng": "post_only", "Chỉ Comment": "comment_only"}
            self.db.set_run_mode(map_mode.get(choice, "post_and_comment"))
            self.log(f"Đã chọn chế độ: {choice}")
            
        mode_names = ["Đăng + Comment", "Chỉ Đăng", "Chỉ Comment"]
        # Reverse map to find current display name
        current_mode_val = self.db.get_run_mode()
        current_display = next((k for k, v in {"post_and_comment": "Đăng + Comment", "post_only": "Chỉ Đăng", "comment_only": "Chỉ Comment"}.items() if v == current_mode_val), "Đăng + Comment")
        
        self.mode_combo = ctk.CTkComboBox(self.sidebar, values=mode_names, command=on_mode_change, state="readonly", height=32)
        self.mode_combo.set(current_display)
        self.mode_combo.pack(padx=20, pady=(5, 5), fill="x")

        # Skip Checkbox (Visible for Comment Only/Mixed)
        self.skip_commented_var = ctk.BooleanVar(value=True) # Default True
        self.skip_commented_check = ctk.CTkCheckBox(self.sidebar, text="Không comment lại bài cũ", 
                                                     variable=self.skip_commented_var,
                                                     font=ctk.CTkFont(size=12))
        self.skip_commented_check.pack(padx=25, pady=(0, 10), anchor="w")

        # Divider
        ctk.CTkFrame(self.sidebar, height=2, fg_color="#333333").pack(padx=20, pady=5, fill="x")


        # Start/Stop buttons frame
        btn_control_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        btn_control_frame.pack(padx=20, pady=(10, 10), fill="x")
        
        self.btn_start_upload = ctk.CTkButton(btn_control_frame, text="Bắt Đầu", height=45, corner_radius=10, 
                                              fg_color=self.accent_green, hover_color="#28A745",
                                              font=ctk.CTkFont(weight="bold"),
                                              command=self.start_posting)
        self.btn_start_upload.pack(side="left", fill="x", expand=True, padx=(0, 5))
        
        self.btn_stop_upload = ctk.CTkButton(btn_control_frame, text="Dừng Lại", height=45, corner_radius=10, 
                                             fg_color=self.accent_red, hover_color="#C82333",
                                             font=ctk.CTkFont(weight="bold"),
                                             command=self.stop_posting,
                                             state="disabled")
        self.btn_stop_upload.pack(side="left", fill="x", expand=True, padx=(5, 0))
        
        # Stop flag
        self.stop_flag = False
        
        # Auto-delete videos checkbox
        self.auto_delete_var = ctk.BooleanVar(value=self.db.get_auto_delete_videos())
        self.auto_delete_check = ctk.CTkCheckBox(self.sidebar, text="Tự động xóa video sau khi đăng", 
                                                  variable=self.auto_delete_var,
                                                  command=self.toggle_auto_delete,
                                                  font=ctk.CTkFont(size=12))
        self.auto_delete_check.pack(padx=20, pady=10, anchor="w")
        
        # Log Display Area
        self.log_text = ctk.CTkTextbox(self.sidebar, height=300, corner_radius=10, font=ctk.CTkFont(size=11), fg_color=self.entry_bg)
        self.log_text.pack(padx=15, pady=20, fill="both", expand=True)

        # Pagination state
        self.current_page_index = 0
        self.items_per_page = 5  # Show 5 items per page to ensure smoothness
        
        # Main Scrollable Area (optimized)
        self.main_container = ctk.CTkFrame(self, fg_color=self.bg_color, corner_radius=0)
        self.main_container.pack(side="right", fill="both", expand=True, padx=20, pady=20)
        
        self.main_frame = ctk.CTkScrollableFrame(self.main_container, fg_color="transparent", 
                                                 label_text="Your Fanpages", 
                                                 label_font=ctk.CTkFont(family="SF Pro Display", size=18, weight="bold"),
                                                 scrollbar_button_color=("gray75", "#333333"),
                                                 scrollbar_button_hover_color=("gray65", "#444444"))
        self.main_frame.pack(fill="both", expand=True)
        
        self.refresh_ui()

    def refresh_ui(self):
        if threading.current_thread() != threading.main_thread():
            self.after(0, self.refresh_ui)
            return

        # Clear Content
        for widget in self.main_frame.winfo_children():
            widget.destroy()

        fanpages = self.db.get_fanpages()
        for i, page in enumerate(fanpages):
            # Page Card - Simplified for performance
            # Reduced corner_radius and removed border from main card to speed up drawing
            card = ctk.CTkFrame(self.main_frame, fg_color=self.card_color, corner_radius=10)
            card.pack(fill="x", padx=5, pady=8)
            
            # Use Grid for efficient layout
            card.grid_columnconfigure(1, weight=1)
            
            # Action Buttons - Single Column Stack (Spanning 4 rows now)
            btn_box = ctk.CTkFrame(card, fg_color="transparent")
            btn_box.grid(row=0, column=2, rowspan=4, padx=10, pady=10, sticky="n")
            
            ctk.CTkButton(btn_box, text="Lịch Sử", width=90, height=28, corner_radius=6, 
                          fg_color=self.accent_purple, hover_color="#8E44AD", command=lambda idx=i: self.view_log_ui(idx)).pack(pady=2)
            ctk.CTkButton(btn_box, text="Thêm Folder", width=90, height=28, corner_radius=6, 
                          fg_color=self.accent_blue, hover_color="#0062CC", command=lambda idx=i: self.browse_folders(idx)).pack(pady=2)
            ctk.CTkButton(btn_box, text="Thêm Path", width=90, height=28, corner_radius=6, 
                          fg_color="#2E7D32", hover_color="#1B5E20", command=lambda idx=i: self.add_folder_manual(idx)).pack(pady=2)
            ctk.CTkButton(btn_box, text="Xóa", width=90, height=28, corner_radius=6, 
                          fg_color=("gray85", "#333333"), hover_color=self.accent_red, command=lambda idx=i: self.remove_page(idx)).pack(pady=2)
            
            # New Log Ngày button for specific filtering
            ctk.CTkButton(btn_box, text="Log Ngày", width=90, height=28, corner_radius=6,
                          fg_color=self.accent_green, hover_color="#218838", 
                          command=lambda name=page.get('name', ''): self.show_video_log_ui(filter_name=name)).pack(pady=2)

            # --- Row 0: ID | Name Entry ---
            row0_frame = ctk.CTkFrame(card, fg_color="transparent")
            row0_frame.grid(row=0, column=0, columnspan=2, sticky="ew", padx=5, pady=(5, 0))
            
            # ID
            ctk.CTkLabel(row0_frame, text=f"#{i+1}", font=ctk.CTkFont(weight="bold", size=14), width=30).pack(side="left", padx=(5, 5))
            
            # Name Entry (Manual Input)
            name_entry = ctk.CTkEntry(row0_frame, height=30, corner_radius=6, border_width=1, 
                                      fg_color=self.entry_bg, border_color=self.border_color, 
                                      placeholder_text="Nhập tên Fanpage...", font=ctk.CTkFont(weight="bold"))
            name_entry.insert(0, page.get('name', ''))
            name_entry.pack(side="left", fill="x", expand=True, padx=5)
            name_entry.bind("<FocusOut>", lambda e, idx=i, ent=name_entry: self.db.update_fanpage_name(idx, ent.get()))

            # --- Row 1: Link Entry ---
            link_frame = ctk.CTkFrame(card, fg_color="transparent")
            link_frame.grid(row=1, column=0, columnspan=2, sticky="ew", padx=5, pady=2)
            
            link_entry = ctk.CTkEntry(link_frame, height=30, corner_radius=6, border_width=1, 
                                      fg_color=self.entry_bg, border_color=self.border_color, placeholder_text="Enter Fanpage Link...")
            link_entry.insert(0, page['link'])
            link_entry.pack(fill="x", expand=True, padx=(45, 5)) # Indent to align with Name (ID width approx 40)
            link_entry.bind("<FocusOut>", lambda e, idx=i, ent=link_entry: self.db.update_link(idx, ent.get()))

            # --- Row 2: Limits ---
            limits_frame = ctk.CTkFrame(card, fg_color="transparent")
            limits_frame.grid(row=2, column=0, columnspan=2, sticky="w", padx=45, pady=2) # Indent to match link
            
            ctk.CTkLabel(limits_frame, text="Video/lần:", font=ctk.CTkFont(size=12)).pack(side="left", padx=(0, 5))
            
            min_entry = ctk.CTkEntry(limits_frame, width=50, height=25, corner_radius=4, border_width=1, fg_color=self.entry_bg, border_color=self.border_color)
            min_entry.insert(0, str(page.get('min_videos', 1)))
            min_entry.pack(side="left", padx=(0, 5))
            
            ctk.CTkLabel(limits_frame, text="-", font=ctk.CTkFont(size=12)).pack(side="left", padx=(0, 5))
            
            max_entry = ctk.CTkEntry(limits_frame, width=50, height=25, corner_radius=4, border_width=1, fg_color=self.entry_bg, border_color=self.border_color)
            max_entry.insert(0, str(page.get('max_videos', 1)))
            max_entry.pack(side="left")

            def update_limits(event, idx=i, min_e=min_entry, max_e=max_entry):
                try:
                    min_val = int(min_e.get())
                    max_val = int(max_e.get())
                    if min_val > 0 and max_val >= min_val:
                        self.db.update_video_limits(idx, min_val, max_val)
                except: pass
            
            min_entry.bind("<FocusOut>", update_limits)
            max_entry.bind("<FocusOut>", update_limits)

            # --- Row 3: Folders ---
            folders_area = ctk.CTkFrame(card, fg_color="transparent")
            folders_area.grid(row=3, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 10))
            folders_area.grid_columnconfigure(1, weight=1)

            if not page['folders']:
                ctk.CTkLabel(folders_area, text="Chưa có thư mục", text_color="gray", font=ctk.CTkFont(size=11, slant="italic")).pack(anchor="w", padx=35)
            else:
                for j, folder in enumerate(page['folders']):
                    ctk.CTkLabel(folders_area, text="📁", width=20, font=ctk.CTkFont(size=10)).grid(row=j, column=0, padx=(5, 5), pady=1)
                    ctk.CTkLabel(folders_area, text=folder, anchor="w", font=ctk.CTkFont(size=11)).grid(row=j, column=1, sticky="ew", padx=5, pady=1)
                    ctk.CTkButton(folders_area, text="x", width=20, height=20, fg_color="transparent", hover_color=self.accent_red, text_color="gray",
                                  command=lambda p_idx=i, f_idx=j: self.remove_folder(p_idx, f_idx)).grid(row=j, column=2, padx=2, pady=1)

    def view_log_ui(self, index):
        page = self.db.get_fanpages()[index]
        link = page['link']
        logs = self.db.get_logs(link)
        
        log_window = ctk.CTkToplevel(self)
        log_window.title(f"Lịch Sử: {page['link']}")
        log_window.geometry("650x450")
        log_window.attributes("-topmost", True)
        log_window.resizable(False, False)
        log_window.configure(fg_color=self.bg_color)
        
        log_frame = ctk.CTkScrollableFrame(log_window, fg_color="transparent", label_text=f"Lịch Sử Đăng Bài", 
                                           label_font=ctk.CTkFont(weight="bold", size=16))
        log_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        if not logs:
            ctk.CTkLabel(log_frame, text="Chưa có lịch sử.", text_color="gray").pack(pady=40)
        else:
            for log in reversed(logs):
                l_card = ctk.CTkFrame(log_frame, fg_color=self.card_color, corner_radius=10, border_width=1, border_color=self.border_color)
                l_card.pack(fill="x", pady=4, padx=5)
                
                ctk.CTkLabel(l_card, text=f"{log['timestamp']}", font=ctk.CTkFont(size=11), text_color="gray", width=130).pack(side="left", padx=10)
                ctk.CTkLabel(l_card, text=log['video'], font=ctk.CTkFont(weight="bold"), anchor="w", width=220).pack(side="left", padx=5)
                
                status_color = self.accent_green if "Success" in log['status'] else self.accent_red
                ctk.CTkLabel(l_card, text=log['status'], text_color=status_color, font=ctk.CTkFont(weight="bold")).pack(side="left", padx=10)
                
                if log['link'] and "Captured" not in log['link']:
                    import webbrowser
                    ctk.CTkButton(l_card, text="Mở Link", width=80, height=25, corner_radius=6, 
                                  fg_color=("gray85", "#333333"), hover_color=self.accent_blue,
                                  font=ctk.CTkFont(size=11), command=lambda l=log['link']: webbrowser.open(l)).pack(side="right", padx=10, pady=5)

    def set_comment_ui(self):
        comment_window = ctk.CTkToplevel(self)
        comment_window.title("Auto Comment Template")
        comment_window.geometry("700x500")
        comment_window.attributes("-topmost", True)
        comment_window.resizable(False, False)
        comment_window.configure(fg_color=self.bg_color)
        
        main_f = ctk.CTkFrame(comment_window, fg_color="transparent")
        main_f.pack(fill="both", expand=True, padx=20, pady=20)
        
        ctk.CTkLabel(main_f, text="Comment Template Editor", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=(0, 10), anchor="w")
        ctk.CTkLabel(main_f, text="Nhập mẫu bình luận (hỗ trợ spin syntax {a|b|c} và nhiều dòng)", 
                     font=ctk.CTkFont(size=14, weight="bold")).pack(pady=(0, 10), anchor="w")
        
        comment_text = ctk.CTkTextbox(main_f, height=300, corner_radius=10, border_width=1, fg_color=self.entry_bg, border_color=self.border_color)
        comment_text.pack(fill="both", expand=True, pady=5)
        
        # Load current
        current_template = self.db.get_comment_template()
        comment_text.insert("1.0", current_template)
        
        btn_frame = ctk.CTkFrame(main_f, fg_color="transparent")
        btn_frame.pack(fill="x", pady=(20, 0))
        
        def save():
            text = comment_text.get("1.0", "end-1c")
            self.db.set_comment_template(text)
            self.log("Comment template saved.")
            comment_window.destroy()
            
        ctk.CTkButton(btn_frame, text="Hủy", width=120, fg_color=("gray85", "#333333"), command=comment_window.destroy).pack(side="right", padx=10)
        ctk.CTkButton(btn_frame, text="Lưu Mẫu", width=150, fg_color=self.accent_purple, hover_color="#8E44AD", command=save).pack(side="right", padx=5)

    def toggle_auto_delete(self):
        self.db.set_auto_delete_videos(self.auto_delete_var.get())
        status = "đã bật" if self.auto_delete_var.get() else "đã tắt"
        self.log(f"Tự động xóa video {status}.")

    def toggle_theme(self):
        current_theme = self.db.get_theme()
        # Cycle through: dark -> light -> gray -> dark
        theme_cycle = {'dark': 'light', 'light': 'gray', 'gray': 'dark'}
        new_theme = theme_cycle.get(current_theme, 'dark')
        
        ctk.set_appearance_mode(new_theme)
        self.db.set_theme(new_theme)
        
        theme_names = {'dark': 'Tối', 'light': 'Sáng', 'gray': 'Xám'}
        self.log(f"Đã chuyển sang giao diện {theme_names[new_theme]}.")
        
        # Refresh UI to apply theme changes
        self.refresh_ui()

    def scheduling_settings_ui(self):
        config = self.db.get_scheduling_config()
        
        settings_window = ctk.CTkToplevel(self)
        settings_window.title("⏰ Cài Đặt Lịch Chạy")
        settings_window.geometry("600x550")
        settings_window.attributes("-topmost", True)
        settings_window.resizable(False, False)
        settings_window.configure(fg_color=self.bg_color)
        
        main_f = ctk.CTkFrame(settings_window, fg_color="transparent")
        main_f.pack(fill="both", expand=True, padx=25, pady=25)
        
        ctk.CTkLabel(main_f, text="Cấu Hình Lịch Chạy", font=ctk.CTkFont(size=20, weight="bold")).pack(pady=(0, 20), anchor="w")
        
        # Loop Mode Section
        loop_frame = ctk.CTkFrame(main_f, fg_color=self.entry_bg, corner_radius=12, border_width=1, border_color=self.border_color)
        loop_frame.pack(fill="x", pady=(0, 15))
        
        ctk.CTkLabel(loop_frame, text="Chế Độ Lặp", font=ctk.CTkFont(size=14, weight="bold")).pack(padx=15, pady=(12, 8), anchor="w")
        
        loop_mode_var = ctk.StringVar(value=config['loop_mode'])
        
        ctk.CTkRadioButton(loop_frame, text="Chạy 1 lần", variable=loop_mode_var, value="once").pack(padx=20, pady=5, anchor="w")
        
        count_frame = ctk.CTkFrame(loop_frame, fg_color="transparent")
        count_frame.pack(fill="x", padx=20, pady=5)
        ctk.CTkRadioButton(count_frame, text="Chạy N lần:", variable=loop_mode_var, value="count").pack(side="left")
        count_entry = ctk.CTkEntry(count_frame, width=80, height=28, fg_color=self.entry_bg, border_color=self.border_color)
        count_entry.insert(0, str(config['loop_count']))
        count_entry.pack(side="left", padx=10)
        
        ctk.CTkRadioButton(loop_frame, text="Vòng lặp vô hạn", variable=loop_mode_var, value="infinite").pack(padx=20, pady=(5, 12), anchor="w")
        
        # Rest Interval Section
        rest_frame = ctk.CTkFrame(main_f, fg_color=self.entry_bg, corner_radius=12, border_width=1, border_color=self.border_color)
        rest_frame.pack(fill="x", pady=(0, 15))
        
        ctk.CTkLabel(rest_frame, text="Nghỉ Giữa Các Lần Chạy (phút)", font=ctk.CTkFont(size=14, weight="bold")).pack(padx=15, pady=(12, 8), anchor="w")
        
        rest_controls = ctk.CTkFrame(rest_frame, fg_color="transparent")
        rest_controls.pack(fill="x", padx=20, pady=(0, 12))
        
        ctk.CTkLabel(rest_controls, text="Min:", font=ctk.CTkFont(size=12)).pack(side="left", padx=(0, 5))
        rest_min_entry = ctk.CTkEntry(rest_controls, width=80, height=28, fg_color=self.entry_bg, border_color=self.border_color)
        rest_min_entry.insert(0, str(config['rest_min']))
        rest_min_entry.pack(side="left", padx=(0, 20))
        
        ctk.CTkLabel(rest_controls, text="Max:", font=ctk.CTkFont(size=12)).pack(side="left", padx=(0, 5))
        rest_max_entry = ctk.CTkEntry(rest_controls, width=80, height=28, fg_color=self.entry_bg, border_color=self.border_color)
        rest_max_entry.insert(0, str(config['rest_max']))
        rest_max_entry.pack(side="left")
        
        # Time Window Section
        time_frame = ctk.CTkFrame(main_f, fg_color=self.entry_bg, corner_radius=12, border_width=1, border_color=self.border_color)
        time_frame.pack(fill="x", pady=(0, 15))
        
        ctk.CTkLabel(time_frame, text="Khung Giờ Hoạt Động (24h)", font=ctk.CTkFont(size=14, weight="bold")).pack(padx=15, pady=(12, 8), anchor="w")
        
        time_controls = ctk.CTkFrame(time_frame, fg_color="transparent")
        time_controls.pack(fill="x", padx=20, pady=(0, 12))
        
        ctk.CTkLabel(time_controls, text="Từ:", font=ctk.CTkFont(size=12)).pack(side="left", padx=(0, 5))
        time_start_entry = ctk.CTkEntry(time_controls, width=80, height=28, placeholder_text="HH:MM", fg_color=self.entry_bg, border_color=self.border_color)
        time_start_entry.insert(0, config['time_start'])
        time_start_entry.pack(side="left", padx=(0, 20))
        
        ctk.CTkLabel(time_controls, text="Đến:", font=ctk.CTkFont(size=12)).pack(side="left", padx=(0, 5))
        time_end_entry = ctk.CTkEntry(time_controls, width=80, height=28, placeholder_text="HH:MM", fg_color=self.entry_bg, border_color=self.border_color)
        time_end_entry.insert(0, config['time_end'])
        time_end_entry.pack(side="left")
        
        # Save Button
        def save_settings():
            try:
                loop_mode = loop_mode_var.get()
                loop_count = int(count_entry.get()) if loop_mode == 'count' else 1
                rest_min = int(rest_min_entry.get())
                rest_max = int(rest_max_entry.get())
                time_start = time_start_entry.get()
                time_end = time_end_entry.get()
                
                self.db.set_scheduling_config(loop_mode, loop_count, rest_min, rest_max, time_start, time_end)
                self.log("Đã lưu cài đặt lịch chạy.")
                settings_window.destroy()
            except Exception as e:
                self.log(f"Error saving settings: {e}")
        
        btn_frame = ctk.CTkFrame(main_f, fg_color="transparent")
        btn_frame.pack(fill="x", pady=(15, 0))
        
        ctk.CTkButton(btn_frame, text="Hủy", width=120, fg_color=("gray85", "#333333"), command=settings_window.destroy).pack(side="right", padx=5)
        ctk.CTkButton(btn_frame, text="Lưu Cài Đặt", width=150, fg_color=self.accent_green, hover_color="#28A745", command=save_settings).pack(side="right", padx=5)

    def browse_folders(self, page_index):
        """Multi-folder selection via dialog"""
        from tkinter import filedialog as fd
        
        folder_window = ctk.CTkToplevel(self)
        folder_window.title("Chọn Nhiều Thư Mục")
        folder_window.geometry("600x400")
        folder_window.attributes("-topmost", True)
        folder_window.resizable(False, False)
        folder_window.configure(fg_color=self.bg_color)
        
        main_f = ctk.CTkFrame(folder_window, fg_color="transparent")
        main_f.pack(fill="both", expand=True, padx=20, pady=20)
        
        ctk.CTkLabel(main_f, text="Thư Mục Đã Chọn", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(0, 10), anchor="w")
        
        selected_list = ctk.CTkScrollableFrame(main_f, height=250, fg_color=self.entry_bg, corner_radius=10, border_width=1, border_color=self.border_color)
        selected_list.pack(fill="both", expand=True, pady=5)
        
        self.temp_folders = []
        
        def render_list():
            for widget in selected_list.winfo_children():
                widget.destroy()
            
            if not self.temp_folders:
                ctk.CTkLabel(selected_list, text="Chưa chọn thư mục nào", text_color="gray").pack(pady=20)
                return
                
            for p in self.temp_folders:
                f_row = ctk.CTkFrame(selected_list, fg_color="transparent")
                f_row.pack(fill="x", pady=2)
                ctk.CTkLabel(f_row, text=f"📁 {p}", anchor="w").pack(side="left", padx=5, fill="x", expand=True)
                ctk.CTkButton(f_row, text="X", width=30, height=30, fg_color="transparent", hover_color=self.accent_red, 
                              command=lambda path=p: remove_one(path)).pack(side="right", padx=5)
        
        def add_one_folder():
            folder = fd.askdirectory()
            if folder and folder not in self.temp_folders:
                self.temp_folders.append(folder)
                render_list()
        
        def remove_one(path):
            self.temp_folders.remove(path)
            render_list()
        
        def save_all():
            for folder in self.temp_folders:
                self.db.add_folder(page_index, folder)
            self.refresh_ui()
            folder_window.destroy()
        
        render_list() # Initial render
        
        btn_frame = ctk.CTkFrame(main_f, fg_color="transparent")
        btn_frame.pack(fill="x", pady=(10, 0))
        
        ctk.CTkButton(btn_frame, text="+ Thêm Thư Mục", width=120, fg_color=self.accent_blue, command=add_one_folder).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="Hủy", width=100, fg_color=("gray85", "#333333"), command=folder_window.destroy).pack(side="right", padx=5)
        ctk.CTkButton(btn_frame, text="Lưu Tất Cả", width=120, fg_color=self.accent_green, command=save_all).pack(side="right", padx=5)

    def add_folder_manual(self, page_index):
        """Manual folder path input"""
        dialog_window = ctk.CTkToplevel(self)
        dialog_window.title("Thêm Đường Dẫn")
        dialog_window.geometry("500x200")
        dialog_window.attributes("-topmost", True)
        dialog_window.resizable(False, False)
        dialog_window.configure(fg_color=self.bg_color)
        
        main_f = ctk.CTkFrame(dialog_window, fg_color="transparent")
        main_f.pack(fill="both", expand=True, padx=20, pady=20)
        
        ctk.CTkLabel(main_f, text="Nhập đường dẫn thư mục:", font=ctk.CTkFont(size=14, weight="bold")).pack(pady=(0, 10), anchor="w")
        
        path_entry = ctk.CTkEntry(main_f, height=35, corner_radius=10, border_width=1, fg_color=self.entry_bg, border_color=self.border_color)
        path_entry.pack(fill="x", pady=5)
        path_entry.focus()
        
        def save_path():
            path = path_entry.get().strip()
            if path:
                self.db.add_folder(page_index, path)
                self.refresh_ui()
                dialog_window.destroy()
        
        btn_frame = ctk.CTkFrame(main_f, fg_color="transparent")
        btn_frame.pack(fill="x", pady=(20, 0))
        
        ctk.CTkButton(btn_frame, text="Hủy", width=100, fg_color=("gray85", "#333333"), command=dialog_window.destroy).pack(side="right", padx=5)
        ctk.CTkButton(btn_frame, text="Thêm", width=100, fg_color=self.accent_green, command=save_path).pack(side="right", padx=5)
        
        # Bind Enter key
        path_entry.bind("<Return>", lambda e: save_path())

    def add_fanpage_ui(self):
        dialog = ctk.CTkInputDialog(text="Nhập số lượng Fanpage muốn thêm:", title="Thêm Fanpage")
        input_str = dialog.get_input()
        
        if not input_str:
            return 
            
        try:
            count = int(input_str)
            if count > 0:
                for _ in range(count):
                    self.db.add_fanpage("https://facebook.com/...")
                self.refresh_ui()
        except ValueError:
            pass # Ignore invalid input

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
        self.refresh_ui()

    def log(self, message):
        timestamp = time.strftime("%H:%M:%S")
        msg = f"[{timestamp}] {message}\n"
        print(f"[LOG] {message}")
        if hasattr(self, 'log_text'):
            self.log_text.insert("1.0", msg)
            self.log_text.see("1.0")

    def show_video_log_ui(self, filter_name=None):
        log_file = "thongke_ngay.txt"
        
        log_window = ctk.CTkToplevel(self)
        title = f"Log Ngày: {filter_name}" if filter_name else "Bảng Thống Kê Log Hệ Thống"
        log_window.title(title)
        log_window.geometry("1100x750")
        log_window.attributes("-topmost", True)
        log_window.configure(fg_color=self.bg_color)
        
        main_f = ctk.CTkFrame(log_window, fg_color="transparent")
        main_f.pack(fill="both", expand=True, padx=25, pady=25)
        
        header_text = f"Lịch Sử Hoạt Động - {filter_name}" if filter_name else "Tổng Hợp Lịch Sử Hoạt Động Trong Ngày"
        ctk.CTkLabel(main_f, text=header_text, font=ctk.CTkFont(family="SF Pro Display", size=24, weight="bold")).pack(pady=(0, 20), anchor="w")
        
        # Basic Text View (High Performance)
        log_textbox = ctk.CTkTextbox(main_f, font=ctk.CTkFont(family="Consolas", size=12))
        log_textbox.pack(fill="both", expand=True)

        def populate_table():
            log_textbox.delete("1.0", "end")
            
            if not os.path.exists(log_file):
                log_textbox.insert("1.0", "Chưa có dữ liệu log cho ngày hôm nay.")
                return

            try:
                with open(log_file, "r", encoding="utf-8") as f:
                    log_lines = f.readlines()
                
                display_text = ""
                for line in reversed(log_lines): # Latest logs first
                    line = line.strip()
                    if not line: continue
                    
                    if filter_name and f"Page: {filter_name}" not in line:
                        continue
                    
                    display_text += line + "\n"
                    
                log_textbox.insert("1.0", display_text)
            except Exception as e:
                log_textbox.insert("1.0", f"Lỗi đọc log: {e}")

        populate_table()
        
        btn_f = ctk.CTkFrame(main_f, fg_color="transparent")
        btn_f.pack(fill="x", pady=(20, 0))
        
        ctk.CTkButton(btn_f, text="Đóng Cửa Sổ", width=150, fg_color=("gray80", "#444444"), text_color=self.text_color_primary,
                      command=log_window.destroy).pack(side="right")
        
        def clear_logs():
            if messagebox.askyesno("Xác nhận", "Bạn có chắc chắn muốn xóa toàn bộ lịch sử log ngày hôm nay?"):
                if os.path.exists(log_file):
                    os.remove(log_file)
                populate_table()

        ctk.CTkButton(btn_f, text="🗑️ Xoá Sạch Log", width=150, fg_color=self.accent_red, command=clear_logs).pack(side="left")
        ctk.CTkButton(btn_f, text="🔄 Làm Mới", width=150, fg_color=self.accent_blue, command=populate_table).pack(side="right", padx=15)

    def write_thongke(self, message):
        log_file = "thongke_ngay.txt"
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {message}\n")

    def view_comment_history(self):
        history_window = ctk.CTkToplevel(self)
        history_window.title("Lịch Sử Comment")
        history_window.geometry("700x500")
        
        # Bring to front
        history_window.lift()
        history_window.focus_force()
        
        content = ctk.CTkTextbox(history_window, font=ctk.CTkFont(size=12))
        content.pack(fill="both", expand=True, padx=10, pady=10)
        
        history = self.db.comment_history
        if not history:
            content.insert("1.0", "Chưa có lịch sử comment nào.")
        else:
            text = ""
            for page, entries in history.items():
                text += f"=== Page: {page} ===\n"
                for entry in entries:
                    text += f"[{entry.get('timestamp')}] Video: {entry.get('video')} -> {entry.get('post_link')}\n"
                text += "\n"
            content.insert("1.0", text)
        
        content.configure(state="disabled")

    def start_posting(self):
        self.stop_flag = False
        self.btn_start_upload.configure(state="disabled")
        self.btn_stop_upload.configure(state="normal")
        threading.Thread(target=self._start_posting_thread, daemon=True).start()

    def stop_posting(self):
        self.stop_flag = True
        self.log("Stop requested. Finishing current video and stopping...")
        self.btn_stop_upload.configure(state="disabled")

    def _start_posting_thread(self):
        # Refresh database from disk before starting to ensure latest paths are used
        self.db.reload()
        
        self.log("Starting GemLogin profile...")
        profile = self.gem_api.find_profile_by_name("Đăng bài Fanpage + comment")
        if not profile:
            self.log("Profile 'Đăng bài Fanpage + comment' not found!")
            self.btn_start_upload.configure(state="normal")
            self.btn_stop_upload.configure(state="disabled")
            return

        max_retries = 3
        launch_data = None
        for i in range(max_retries):
            launch_data = self.gem_api.start_profile(profile['id'])
            if launch_data and launch_data.get('success'):
                break
            
            error_msg = launch_data.get('message', 'Unknown error') if launch_data else 'No response'
            self.log(f"Attempt {i+1} failed: {error_msg}")
            
            if i < max_retries - 1:
                self.log("Đang thử đóng profile (để reset) trước khi thử lại...")
                try:
                    self.gem_api.stop_profile(profile['id'])
                except:
                    pass
                time.sleep(5)

        if not launch_data or not launch_data.get('success'):
            self.log(f"Failed to start profile: {launch_data.get('message') if launch_data else 'No response'}")
            self.btn_start_upload.configure(state="normal")
            self.btn_stop_upload.configure(state="disabled")
            return

        # Store profile_id for cleanup
        self.current_profile_id = profile['id']
        
        data_content = launch_data.get('data', {}) if isinstance(launch_data.get('data'), dict) else {}
        debugger_address = data_content.get('remote_debugging_address') or data_content.get('debugger_address')
        driver_path = data_content.get('driver_path')

        if not debugger_address:
            self.log("Failed to get debugger address from response!")
            self.btn_start_upload.configure(state="normal")
            self.btn_stop_upload.configure(state="disabled")
            return

        self.log(f"Profile started! Connecting to {debugger_address}...")
        
        try:
            from facebook_automator import FacebookAutomator
            self.automator = FacebookAutomator(debugger_address, driver_path)
            self.log("Connected to browser successfully!")
        except Exception as e:
            self.log(f"Failed to connect: {e}")
            self.btn_start_upload.configure(state="normal")
            self.btn_stop_upload.configure(state="disabled")
            return

        # Get scheduling config
        config = self.db.get_scheduling_config()
        loop_mode = config['loop_mode']
        loop_count = config['loop_count']
        rest_min = config['rest_min']
        rest_max = config['rest_max']
        time_start = config['time_start']
        time_end = config['time_end']
        
        run_number = 0
        
        while True:
            # Check stop flag
            if self.stop_flag:
                self.log("Stopped by user.")
                break
            
            # Check time window
            from datetime import datetime
            current_time = datetime.now().strftime("%H:%M")
            if not (time_start <= current_time <= time_end):
                self.log(f"Outside active time window ({time_start}-{time_end}). Current time: {current_time}")
                self.log(f"Waiting until {time_start}...")
                
                # Wait and check every minute
                while not self.stop_flag:
                    current_time = datetime.now().strftime("%H:%M")
                    if time_start <= current_time <= time_end:
                        break
                    time.sleep(60)
                
                if self.stop_flag:
                    break
                    
                self.log(f"Now in active time window. Starting run...")
            
            # Increment run counter
            run_number += 1
            
            # Log run info
            if loop_mode == 'once':
                self.log(f"Starting single run...")
            elif loop_mode == 'count':
                self.log(f"Starting run {run_number}/{loop_count}...")
            else:  # infinite
                self.log(f"Starting run #{run_number}...")
            
            # Perform the upload task
            fanpages = self.db.get_fanpages()
            for i, page in enumerate(fanpages):
                if self.stop_flag:
                    break
                    
                link = page['link']
                if not link or "facebook.com" not in link: 
                    continue
                
                # Check if folders are assigned
                if not page.get('folders'):
                    self.log(f"Page {i+1} ({page.get('name')}) chưa được gán thư mục -> Bỏ qua.")
                    continue

                # Collect ALL videos from all folders recursively
                video_set = set() # Use set to prevent duplicates
                for folder in page['folders']:
                    if self.stop_flag: break
                    if not os.path.exists(folder):
                        continue
                    
                    for root, dirs, files in os.walk(folder):
                        for f in files:
                            if f.lower().endswith(('.mp4', '.mkv', '.mov')):
                                # Normalize path to avoid duplicates like C:\a.mp4 vs C:/a.mp4
                                full_path = os.path.normpath(os.path.abspath(os.path.join(root, f)))
                                # On Windows, we should also handle case-insensitivity for de-duplication
                                # but keep the original case for actual OS operations if possible.
                                # Let's just store the normalized path.
                                video_set.add(full_path)
                
                all_videos = list(video_set)

                if not all_videos:
                    self.log(f"Không tìm thấy video nào tại {link} -> Chuyển sang Page tiếp theo.")
                    continue

                # NEW SELECTION LOGIC
                run_mode = self.db.get_run_mode()
                skip_existing = self.skip_commented_var.get()
                
                selected_videos = []
                
                if run_mode == "comment_only":
                    # For Comment Only: Process ALL eligible videos (filtering out history)
                    eligible_videos = []
                    for v in all_videos:
                        v_name = os.path.basename(v)
                        # Filter if skip enabled
                        if skip_existing and self.db.has_commented(link, v_name):
                            continue
                        eligible_videos.append(v)
                        
                    if not eligible_videos:
                        self.log(f"Không có video nào cần comment (đã comment hết hoặc trống).")
                        continue
                        
                    self.log(f"Đã tìm thấy {len(all_videos)} video. Có {len(eligible_videos)} video chưa comment. Bắt đầu chạy...")
                    selected_videos = eligible_videos
                    
                else:
                     # For Upload modes: Use Min-Max limits & Random Sampling
                    import random
                    min_v = page.get('min_videos', 1)
                    max_v = page.get('max_videos', 10)
                    
                    # Ensure valid range
                    if min_v < 1: min_v = 1
                    if max_v < min_v: max_v = min_v
                    
                    count_to_upload = random.randint(min_v, max_v)
                    if count_to_upload > len(all_videos):
                        count_to_upload = len(all_videos)
                    
                    self.log(f"Đã tìm thấy {len(all_videos)} video. Sẽ đăng ngẫu nhiên {count_to_upload} video...")
                    selected_videos = random.sample(all_videos, count_to_upload)

                for video_path in selected_videos:
                    if self.stop_flag:
                        break
                        
                    video_filename = os.path.basename(video_path)
                    title = os.path.splitext(video_filename)[0]
                    run_mode = self.db.get_run_mode()
                    skip_existing = self.skip_commented_var.get()
                    
                    self.log(f"Đang xử lý {video_filename} (Mode: {run_mode})")
                    
                    # PRE-CHECK: Skip if Comment Only/Mixed and already commented
                    if run_mode in ["comment_only", "post_and_comment"] and skip_existing:
                         if self.db.has_commented(link, video_filename):
                             self.log(f"Đã từng comment bài này -> Bỏ qua.")
                             # If Post Only, we might still want to upload? 
                             # User said "Phát triên thêm tính năng chỉ comment... không chạy những bài từng comment".
                             # So only skip if strictly in Comment Only mode, or if mixed?
                             # Let's assume if "Post & Comment" and we already commented, we probably already uploaded too.
                             # But to be safe and strictly follow "upload new", we might only skip the *comment* part?
                             # Requirements say: "không chạy những bài từng comment rồi".
                             # If we found it in comment history, it means we processed it.
                             continue
                    
                    try:
                        post_link = ""
                        upload_success = False
                        
                        # 1. UPLOAD PHASE (Strictly Post Only OR Post & Comment)
                        if run_mode in ["post_only", "post_and_comment"]:
                            # Upload video and get post link
                            result = self.automator.upload_reel_by_link(link, video_path, title, scrape_name=False)
                            post_link = result if not isinstance(result, tuple) else result[0]
                            self.log(f"Upload thành công: {post_link}")
                            upload_success = True
                            
                            if run_mode == "post_only":
                                self.db.add_log(i, video_filename, "Uploaded", post_link)
                                self.write_thongke(f"Page: {page.get('name')} | Video: {video_filename} | Status: Uploaded | Link: {post_link}")

                        # 2. FIND POST PHASE (Strictly Comment Only)
                        elif run_mode == "comment_only":
                             self.log("Đang tìm bài viết trùng tên file...")
                             asset_id = self.automator.resolve_asset_id(link)
                             if asset_id:
                                 found_link = self.automator.find_and_open_post(asset_id, title)
                                 if found_link:
                                     post_link = found_link
                                     self.log(f"Đã mở bài viết: {post_link}")
                                 else:
                                     raise Exception("Không tìm thấy bài viết nào có tiêu đề trùng khớp.")
                             else:
                                 raise Exception("Không lấy được Asset ID từ Link.")

                        # 3. COMMENT PHASE (Comment Only OR Post & Comment)
                        should_comment = False
                        if run_mode == "comment_only": should_comment = True
                        if run_mode == "post_and_comment" and upload_success: should_comment = True
                        
                        if should_comment and not self.stop_flag:
                            comment_template = self.db.get_comment_template()
                            if comment_template:
                                self.log(f"Đang thực hiện chiến dịch bình luận 2 lớp cho: {video_filename}")
                                asset_id = self.automator.resolve_asset_id(link)
                                if asset_id:
                                    success, real_link = self.automator.comment_with_dual_strategy(asset_id, title, comment_template)
                                    
                                    if success:
                                        if real_link: post_link = real_link
                                        self.log("Đã đăng bình luận thành công (Dual-Strategy)!")
                                        status = "Success" if run_mode == "post_and_comment" else "Commented"
                                        self.db.add_log(i, video_filename, status, post_link)
                                        self.write_thongke(f"Page: {page.get('name')} | Video: {video_filename} | Status: {status} | Link: {post_link}")
                                        self.db.add_comment_history(link, video_filename, post_link)
                                    else:
                                        self.log("Thất bại: Cả hai phương pháp bình luận đều không thành công.")
                                        self.db.add_log(i, video_filename, "Comment Failed", post_link)
                                        self.write_thongke(f"Page: {page.get('name')} | Video: {video_filename} | Status: Comment Failed | Link: {post_link}")
                                else:
                                    self.log("Lỗi: Không lấy được Asset ID để bình luận.")
                            else:
                                self.log("Bỏ qua bình luận (Chưa cài đặt mẫu comment).")
                                if run_mode == "post_and_comment":
                                    self.db.add_log(i, video_filename, "Uploaded (No Comment)", post_link)
                                    self.write_thongke(f"Page: {page.get('name')} | Video: {video_filename} | Status: Uploaded (No Comment) | Link: {post_link}")
                        
                        # 4. CLEANUP (Auto-Delete) - Only if we Uploaded (Run Mode involves posting)
                        if run_mode in ["post_only", "post_and_comment"] and self.db.get_auto_delete_videos():
                            self.log(f"Tiến hành xóa video ngay lập tức: {video_filename}")
                            
                            # Add retries for deletion
                            deleted = False
                            for attempt in range(3):
                                try:
                                    if not os.path.exists(video_path):
                                        self.log(f"Video không tồn tại (có thể đã xóa): {video_filename}")
                                        deleted = True
                                        break
                                        
                                    # Wait a bit
                                    time.sleep(3 * (attempt + 1))
                                    
                                    # TECHNIQUE: Rename before delete to ensure we have the right file and it's not locked
                                    import uuid
                                    temp_name = video_path + "." + str(uuid.uuid4())[:8] + ".trash"
                                    
                                    try:
                                        os.rename(video_path, temp_name)
                                        # If rename succeeded, we definitely have the right file and it's unlocked for us
                                        os.remove(temp_name)
                                        
                                        if not os.path.exists(temp_name) and not os.path.exists(video_path):
                                            self.log(f"Đã xóa video vĩnh viễn: {video_filename}")
                                            self.write_thongke(f"Page: {page.get('name')} | Action: Permanently Deleted | File: {video_path}")
                                            deleted = True
                                            break
                                    except Exception as e:
                                        # If rename fails, try direct delete as fallback
                                        self.log(f"Rename thất bại (lần {attempt+1}), thử xóa trực tiếp: {e}")
                                        try:
                                            os.remove(video_path)
                                        except: pass
                                        
                                        if not os.path.exists(video_path):
                                            self.log(f"Đã xóa video (Direct): {video_filename}")
                                            self.write_thongke(f"Page: {page.get('name')} | Action: Direct Deleted | File: {video_path}")
                                            deleted = True
                                            break
                                        
                                except Exception as del_err:
                                    self.log(f"Lỗi khi xóa video (lần {attempt+1}): {del_err}")
                                    if attempt == 2:
                                        self.write_thongke(f"Page: {page.get('name')} | Action: Delete FAILED | File: {video_path} | Error: {del_err}")
                            
                            # CRITICAL FINAL CHECK
                            if not deleted and os.path.exists(video_path):
                                self.log(f"❌ THẤT BẠI: Video vẫn chưa được xóa khỏi ổ cứng: {video_filename}")
                                self.write_thongke(f"Page: {page.get('name')} | Action: CRITICAL FAIL | File still exists: {video_path}")
                            elif deleted:
                                # One last sanity check to never report fake success
                                if os.path.exists(video_path):
                                    self.log(f"⚠️ Cảnh báo: Tool báo xóa xong nhưng OS vẫn thấy file: {video_filename}")
                                    self.write_thongke(f"Page: {page.get('name')} | Action: ZOMBIE FILE | File: {video_path}")
                                
                    except Exception as e:
                        self.log(f"Lỗi {video_filename}: {e}")
                        self.db.add_log(i, video_filename, "Failed", str(e))
                        self.write_thongke(f"Page: {page.get('name')} | Video: {video_filename} | Status: Failed | Error: {e}")
                    
                    self.refresh_ui()
                    time.sleep(10)
            
            # Check if should continue looping
            if loop_mode == 'once':
                self.log("Đã hoàn thành 1 lần chạy.")
                break
            elif loop_mode == 'count':
                if run_number >= loop_count:
                    self.log(f"Đã hoàn thành tất cả {loop_count} lần chạy.")
                    break
            # For infinite mode, continue
            
            if self.stop_flag:
                break
            
            # Close browser to save RAM before resting
            try:
                if hasattr(self, 'current_profile_id'):
                    self.log("Đóng trình duyệt để tiết kiệm RAM...")
                    stop_result = self.gem_api.stop_profile(self.current_profile_id)
                    if stop_result and stop_result.get('success'):
                        self.log("Đã đóng trình duyệt.")
                    else:
                        self.log(f"Cảnh báo: Không thể đóng trình duyệt: {stop_result.get('message') if stop_result else 'Không có phản hồi'}")
            except Exception as e:
                self.log(f"Lỗi khi đóng trình duyệt: {e}")
            
            # Rest between runs
            import random
            rest_time = random.randint(rest_min, rest_max)
            self.log(f"Nghỉ {rest_time} phút trước lần chạy tiếp...")
            
            # Wait with stop check
            for _ in range(rest_time * 60):  # Convert to seconds
                if self.stop_flag:
                    break
                time.sleep(1)
            
            if self.stop_flag:
                break
            
            # Restart profile for next run
            self.log("Khởi động lại trình duyệt cho lần chạy tiếp...")
            
            restart_success = False
            for attempt in range(3):
                if self.stop_flag:
                    break
                    
                launch_data = self.gem_api.start_profile(profile['id'])
                if launch_data and launch_data.get('success'):
                    data_content = launch_data.get('data', {}) if isinstance(launch_data.get('data'), dict) else {}
                    debugger_address = data_content.get('remote_debugging_address') or data_content.get('debugger_address')
                    driver_path = data_content.get('driver_path')
                    
                    if debugger_address:
                        try:
                            from facebook_automator import FacebookAutomator
                            self.automator = FacebookAutomator(debugger_address, driver_path)
                            self.log("Đã kết nối lại trình duyệt!")
                            restart_success = True
                            break
                        except Exception as e:
                            self.log(f"Không thể kết nối lại (lần {attempt+1}): {e}")
                    else:
                        self.log(f"Không lấy được debugger address (lần {attempt+1})!")
                else:
                    error_msg = launch_data.get('message') if launch_data else 'Không có phản hồi'
                    self.log(f"Không thể khởi động lại profile (lần {attempt+1}): {error_msg}")
                    
                # If we get here, restart failed this attempt. Try to force stop the profile before retrying
                if attempt < 2 and not self.stop_flag:
                    self.log("Stopping GemLogin profile để thử mở lại...")
                    try:
                        self.gem_api.stop_profile(profile['id'])
                    except Exception:
                        pass
                    time.sleep(5)
            
            if not restart_success:
                self.log("Đã thử khởi động lại nhiều lần nhưng thất bại. Dừng hệ thống.")
                break
        
        # Cleanup: Stop GemLogin profile
        try:
            if hasattr(self, 'current_profile_id'):
                self.log("Stopping GemLogin profile...")
                stop_result = self.gem_api.stop_profile(self.current_profile_id)
                if stop_result and stop_result.get('success'):
                    self.log("Browser closed successfully.")
                else:
                    self.log(f"Warning: Failed to stop profile via API: {stop_result.get('message') if stop_result else 'No response'}")
        except Exception as e:
            self.log(f"Error stopping profile: {e}")
        
        self.log("All tasks completed.")
        self.btn_start_upload.configure(state="normal")
        self.btn_stop_upload.configure(state="disabled")

if __name__ == "__main__":
    app = App()
    app.mainloop()

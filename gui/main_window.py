"""Main Window GUI for VIMC Manifest Cleaner v2.0.

Compact design with ship type indicator, based on VOSCO/VINAFCO architecture.
"""

from __future__ import annotations

import configparser
import json
import logging
import os
import subprocess
import sys
import threading
import tkinter as tk
try:
    import winsound
except ImportError:
    winsound = None
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any, Dict, List, Optional

import pandas as pd

from config.constants import (
    APP_TITLE,
    APP_VERSION,
    APP_AUTHOR_VI,
    APP_AUTHOR_EN,
    UI_TEXT,
    COLORS,
)
from core.excel_handler import VimcExcelHandler
from core.ship_detector import (
    ShipType,
    detect_ship_type,
    get_ship_type_display_name,
    get_ship_type_color,
    get_ship_type_description,
)
from utils.helpers import (
    get_application_path,
    get_resource_path,
    setup_logging,
)

try:
    from tkinterdnd2 import DND_FILES  # type: ignore
    HAS_DND = True
except ImportError:
    HAS_DND = False

logger = logging.getLogger(__name__)


class PreviewWindow(tk.Toplevel):
    """Window to preview processed data before saving with filter, sort, and save buttons."""
    
    def __init__(self, parent, df: pd.DataFrame, texts: dict, on_save_callback, handler):
        super().__init__(parent)
        self.df = df
        self.texts = texts
        self.on_save = on_save_callback
        self.handler = handler
        self.filtered_df = df.copy()
        self.sort_reverse = {}  # Track sort direction per column
        
        self.title(texts.get("preview_title", "Xem trước dữ liệu"))
        self.geometry("1000x600")
        self.minsize(800, 500)
        
        self._build_ui()
        self._center_window()
    
    def _center_window(self) -> None:
        """Center window on screen."""
        self.update_idletasks()
        w = self.winfo_width()
        h = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (w // 2)
        y = (self.winfo_screenheight() // 2) - (h // 2)
        self.geometry(f"+{x}+{y}")
    
    def _build_ui(self) -> None:
        """Build preview window UI."""
        # Toolbar
        toolbar = ttk.Frame(self, padding=10)
        toolbar.pack(fill=tk.X)
        
        # Filter
        ttk.Label(toolbar, text=self.texts.get("filter_label", "🔍 Lọc:")).pack(side=tk.LEFT, padx=(0, 5))
        self.filter_var = tk.StringVar()
        self.filter_var.trace("w", self._on_filter_change)
        filter_entry = ttk.Entry(toolbar, textvariable=self.filter_var, width=30)
        filter_entry.pack(side=tk.LEFT, padx=(0, 15))
        
        # Stats
        self.stats_label = ttk.Label(toolbar, text="")
        self.stats_label.pack(side=tk.LEFT, padx=10)
        
        # Buttons
        btn_frame = ttk.Frame(toolbar)
        btn_frame.pack(side=tk.RIGHT)
        
        ttk.Button(
            btn_frame,
            text=self.texts.get("btn_save_excel", "💾 Lưu Excel"),
            style="Success.TButton",
            command=self._save_excel
        ).pack(side=tk.LEFT, padx=2)
        
        ttk.Button(
            btn_frame,
            text=self.texts.get("btn_close", "❌ Đóng"),
            style="Secondary.TButton",
            command=self.destroy
        ).pack(side=tk.LEFT, padx=2)
        
        # Treeview for data
        tree_frame = ttk.Frame(self)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        # Scrollbars
        y_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        x_scroll = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL)
        
        self.tree = ttk.Treeview(
            tree_frame,
            columns=list(self.df.columns),
            show="headings",
            yscrollcommand=y_scroll.set,
            xscrollcommand=x_scroll.set
        )
        
        y_scroll.config(command=self.tree.yview)
        x_scroll.config(command=self.tree.xview)
        
        y_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        x_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        self.tree.pack(fill=tk.BOTH, expand=True)
        
        # Configure columns
        for col in self.df.columns:
            self.tree.heading(col, text=col, command=lambda c=col: self._sort_by(c))
            self.tree.column(col, width=100, minwidth=50)
        
        # Populate data
        self._populate_tree()
        self._update_stats()
    
    def _populate_tree(self) -> None:
        """Populate treeview with data."""
        # Clear existing
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # Add rows
        for _, row in self.filtered_df.iterrows():
            values = [str(v) if pd.notna(v) else "" for v in row]
            self.tree.insert("", tk.END, values=values)
    
    def _on_filter_change(self, *args) -> None:
        """Handle filter text change."""
        filter_text = self.filter_var.get().lower()
        if not filter_text:
            self.filtered_df = self.df.copy()
        else:
            mask = self.df.astype(str).apply(
                lambda x: x.str.lower().str.contains(filter_text, na=False)
            ).any(axis=1)
            self.filtered_df = self.df[mask]
        
        self._populate_tree()
        self._update_stats()
    
    def _sort_by(self, col: str) -> None:
        """Sort data by column with toggle direction."""
        try:
            # Toggle sort direction
            self.sort_reverse[col] = not self.sort_reverse.get(col, False)
            self.filtered_df = self.filtered_df.sort_values(
                by=col, 
                ascending=not self.sort_reverse[col]
            )
            self._populate_tree()
        except Exception:
            pass
    
    def _update_stats(self) -> None:
        """Update statistics label."""
        total = len(self.df)
        shown = len(self.filtered_df)
        
        # Count F/E if column exists
        fe_col = next((c for c in self.df.columns if "F/E" in c or "FE" in c.upper()), None)
        if fe_col:
            full = len(self.df[self.df[fe_col] == "F"])
            empty = len(self.df[self.df[fe_col] == "E"])
            self.stats_label.config(
                text=f"{self.texts.get('stats_total', 'Tổng')}: {total} | "
                     f"{self.texts.get('stats_shown', 'Hiển thị')}: {shown} | "
                     f"Full: {full} | Empty: {empty}"
            )
        else:
            self.stats_label.config(
                text=f"{self.texts.get('stats_total', 'Tổng')}: {total} | "
                     f"{self.texts.get('stats_shown', 'Hiển thị')}: {shown}"
            )
    
    def _save_excel(self) -> None:
        """Save current (filtered) data to Excel."""
        file_path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx")],
            initialfile="Processed_manifest.xlsx"
        )
        
        if not file_path:
            return
        
        try:
            success = self.handler.save_excel(file_path, self.filtered_df)
            
            if success:
                messagebox.showinfo(
                    self.texts.get("dialog_save_result_title", "Kết quả"),
                    f"{self.texts.get('save_success', 'Đã lưu file:')}\n{file_path}"
                )
                # Notify parent
                if self.on_save:
                    self.on_save(file_path)
            else:
                messagebox.showerror(
                    self.texts.get("dialog_error_title", "Lỗi"),
                    self.texts.get("save_error", "Không thể lưu file")
                )
        except Exception as e:
            logger.error(f"Preview save error: {e}")
            messagebox.showerror(
                self.texts.get("dialog_error_title", "Lỗi"),
                f"{self.texts.get('save_error', 'Lỗi khi lưu:')}\n{str(e)}"
            )


class ManifestCleanerApp:
    """Main application window for VIMC Manifest Cleaner."""
    
    def __init__(self, root: tk.Tk):
        """Initialize the application.
        
        Args:
            root: Tkinter root window
        """
        self.root = root
        self.current_file: Optional[str] = None
        self.processed_df: Optional[pd.DataFrame] = None
        self.is_processing = False
        self.current_lang = "vi"
        self.detected_ship_type: ShipType = ShipType.UNKNOWN
        
        # Load app config
        self.app_config = self._load_app_config()
        self.recent_files = self.app_config.get("recent_files", [])
        self.recent_expanded = True
        self.auto_open_after_save = self.app_config.get("auto_open", True)
        
        # Load language
        self.current_lang = self.app_config.get("language", "vi")
        self.texts = self._load_strings()
        
        # Stats variables
        self.stats_vars: Dict[str, tk.StringVar] = {}
        
        # Setup window
        self._setup_window()
        self._setup_styles()
        self._build_ui()
        
        # Bind shortcuts
        self._bind_shortcuts()
        
        logger.info("VIMC Manifest Cleaner initialized")
    
    def _load_app_config(self) -> Dict[str, Any]:
        """Load application configuration from JSON file."""
        config_path = get_application_path() / "app_config.json"
        
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load app config: {e}")
        
        return {
            "recent_files": [],
            "language": "vi",
            "auto_open": True,
        }
    
    def _save_app_config(self) -> None:
        """Save application configuration to JSON file."""
        config_path = get_application_path() / "app_config.json"
        
        config = {
            "recent_files": self.recent_files[:10],  # Keep only 10 recent files
            "language": self.current_lang,
            "auto_open": self.auto_open_after_save,
        }
        
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save app config: {e}")
    
    def _load_strings(self) -> Dict[str, str]:
        """Load UI strings from INI file or fallback to defaults."""
        lang_file = get_resource_path(f"strings_{self.current_lang}.ini")
        
        texts = {}
        if lang_file.exists():
            try:
                config = configparser.ConfigParser(interpolation=None)
                config.read(lang_file, encoding='utf-8')
                
                # Load all sections
                for section in config.sections():
                    for key, value in config[section].items():
                        texts[key] = value
                
                if texts:
                    return texts
            except Exception as e:
                logger.warning(f"Failed to load strings file: {e}")
        
        # Fallback to defaults
        return UI_TEXT.get(self.current_lang, UI_TEXT["vi"])
    
    def _setup_window(self) -> None:
        """Configure the main window."""
        self.root.title(f"{APP_TITLE} v{APP_VERSION}")
        self.root.geometry("640x600")
        self.root.minsize(500, 500)
        self.root.configure(bg=COLORS["bg"])
        
        # Center window
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f"+{x}+{y}")
        
        # Setup Drag and Drop
        if HAS_DND and hasattr(self.root, 'drop_target_register'):
            self.root.drop_target_register(DND_FILES)
            self.root.dnd_bind('<<Drop>>', self._on_drop)
    
    def _setup_styles(self) -> None:
        """Configure ttk styles."""
        style = ttk.Style()
        style.theme_use('clam')
        
        # Frame styles
        style.configure("TFrame", background=COLORS["bg"])
        style.configure("Card.TFrame", background=COLORS["card_bg"])
        
        # Label styles
        style.configure(
            "Title.TLabel",
            font=("Segoe UI", 16, "bold"),
            background=COLORS["card_bg"],
            foreground=COLORS["text"]
        )
        style.configure(
            "Subtitle.TLabel",
            font=("Segoe UI", 10),
            background=COLORS["card_bg"],
            foreground=COLORS["text_light"]
        )
        style.configure(
            "TLabel",
            font=("Segoe UI", 10),
            background=COLORS["card_bg"]
        )
        style.configure(
            "Stats.TLabel",
            font=("Segoe UI", 11, "bold"),
            background=COLORS["card_bg"]
        )
        style.configure(
            "Footer.TLabel",
            font=("Segoe UI", 9),
            foreground=COLORS["text_light"],
            background=COLORS["bg"]
        )
        
        # Button styles
        style.configure(
            "Primary.TButton",
            font=("Segoe UI", 11, "bold"),
            padding=(20, 10),
            background=COLORS["primary"],
            foreground="white",
            bordercolor=COLORS["primary"],
            lightcolor=COLORS["primary"],
            darkcolor=COLORS["primary"]
        )
        style.map(
            "Primary.TButton",
            background=[("active", "#0C4091"), ("disabled", "#E2E8F0")],
            foreground=[("disabled", "#94A3B8")],
            bordercolor=[("active", "#0C4091"), ("disabled", "#E2E8F0")]
        )
        
        style.configure(
            "Action.TButton",
            font=("Segoe UI", 10, "bold"),
            padding=(15, 8),
            background="#475569",
            foreground="white",
            bordercolor="#475569",
            lightcolor="#475569",
            darkcolor="#475569"
        )
        style.map(
            "Action.TButton",
            background=[("active", "#1E293B"), ("disabled", "#E2E8F0")],
            foreground=[("disabled", "#94A3B8")],
            bordercolor=[("active", "#1E293B"), ("disabled", "#CBD5E1")]
        )
        
        # Success.TButton (Solid Emerald Green)
        style.configure(
            "Success.TButton",
            font=("Segoe UI", 10, "bold"),
            padding=(15, 8),
            background="#10B981",
            foreground="white",
            bordercolor="#10B981",
            lightcolor="#10B981",
            darkcolor="#10B981"
        )
        style.map(
            "Success.TButton",
            background=[("active", "#059669"), ("disabled", "#E2E8F0")],
            foreground=[("disabled", "#94A3B8")],
            bordercolor=[("active", "#059669"), ("disabled", "#CBD5E1")]
        )

        # Secondary.TButton (Light gray / outlined style)
        style.configure(
            "Secondary.TButton",
            font=("Segoe UI", 10, "bold"),
            padding=(15, 8),
            background="#F1F5F9",
            foreground="#334155",
            bordercolor="#CBD5E1",
            lightcolor="#F1F5F9",
            darkcolor="#F1F5F9"
        )
        style.map(
            "Secondary.TButton",
            background=[("active", "#E2E8F0"), ("disabled", "#F8FAFC")],
            foreground=[("disabled", "#94A3B8")],
            bordercolor=[("active", "#94A3B8"), ("disabled", "#E2E8F0")]
        )
        
        # Progress bar
        style.configure(
            "Green.Horizontal.TProgressbar",
            troughcolor=COLORS["border"],
            background=COLORS["success"],
            thickness=8
        )
        
        # Entry style
        style.configure(
            "TEntry",
            fieldbackground="#FFFFFF",
            bordercolor=COLORS["border"],
            lightcolor=COLORS["border"],
            darkcolor=COLORS["border"],
            insertcolor=COLORS["text"]
        )
        
        # Treeview style
        style.configure(
            "Treeview",
            font=("Segoe UI", 9),
            background="#FFFFFF",
            foreground=COLORS["text"],
            fieldbackground="#FFFFFF",
            rowheight=24
        )
        style.configure(
            "Treeview.Heading",
            font=("Segoe UI", 9, "bold"),
            background=COLORS["bg"],
            foreground=COLORS["text"],
            bordercolor=COLORS["border"]
        )
        style.map(
            "Treeview",
            background=[("selected", COLORS["primary"])],
            foreground=[("selected", "white")]
        )
    
    def _build_ui(self) -> None:
        """Build the user interface."""
        # Main container
        main_frame = ttk.Frame(self.root, style="TFrame")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=15)
        
        # Card frame
        self.card_frame = tk.Frame(
            main_frame,
            bg=COLORS["card_bg"],
            highlightthickness=1,
            highlightbackground=COLORS["border"]
        )
        self.card_frame.pack(fill=tk.BOTH, expand=True)
        
        # Header with toolbar
        self._build_header()
        
        # File selection
        self._build_file_section()
        
        # Recent files
        self._build_recent_files()
        
        # Action buttons
        self._build_action_buttons()
        
        # Status section
        self._build_status_section()
        
        # Stats section
        self._build_stats_section()
        
        # Footer
        self._build_footer()
    
    def _build_header(self) -> None:
        """Build header with title and settings."""
        header = tk.Frame(self.card_frame, bg=COLORS["card_bg"])
        header.pack(fill=tk.X, padx=15, pady=(15, 5))
        
        # Title
        self.title_label = tk.Label(
            header,
            text=self.texts.get("app_subtitle", "VIMC Manifest Cleaner"),
            font=("Segoe UI", 16, "bold"),
            bg=COLORS["card_bg"],
            fg=COLORS["text"]
        )
        self.title_label.pack(side=tk.LEFT)
        
        # Settings button with dropdown
        self.settings_btn = tk.Menubutton(
            header,
            text="⚙️",
            font=("Segoe UI", 14),
            bg=COLORS["card_bg"],
            relief="flat",
            cursor="hand2"
        )
        self.settings_btn.pack(side=tk.RIGHT)
        
        # Settings menu
        self._build_settings_menu()
    
    def _build_settings_menu(self) -> None:
        """Build settings dropdown menu."""
        self.settings_menu = tk.Menu(self.settings_btn, tearoff=0)
        self.settings_btn["menu"] = self.settings_menu
        
        # Language submenu
        lang_menu = tk.Menu(self.settings_menu, tearoff=0)
        lang_menu.add_command(
            label="🇻🇳 Tiếng Việt",
            command=lambda: self._set_language("vi")
        )
        lang_menu.add_command(
            label="🇬🇧 English",
            command=lambda: self._set_language("en")
        )
        self.settings_menu.add_cascade(
            label=self.texts.get("menu_language", "Ngôn ngữ"),
            menu=lang_menu
        )
        
        # Auto open toggle
        self.auto_open_var = tk.BooleanVar(value=self.auto_open_after_save)
        self.settings_menu.add_checkbutton(
            label=self.texts.get("menu_auto_open", "Tự động mở file"),
            variable=self.auto_open_var,
            command=self._toggle_auto_open
        )
        
        self.settings_menu.add_separator()
        
        # Shortcuts
        self.settings_menu.add_command(
            label=self.texts.get("menu_shortcuts", "Phím tắt"),
            command=self._show_shortcuts
        )
        
        # About
        self.settings_menu.add_command(
            label=self.texts.get("menu_about", "Thông tin"),
            command=self._show_about
        )
    

    def _build_file_section(self) -> None:
        """Build file selection section."""
        file_frame = tk.Frame(self.card_frame, bg=COLORS["card_bg"])
        file_frame.pack(fill=tk.X, padx=15, pady=10)
        
        # Choose file button
        self.btn_choose = ttk.Button(
            file_frame,
            text=self.texts.get("choose_file_button", "📂 Chọn File Manifest"),
            style="Primary.TButton",
            command=self._choose_file
        )
        self.btn_choose.pack(fill=tk.X)
        
        # Selected file display
        self.file_label = tk.Label(
            file_frame,
            text="",
            font=("Segoe UI", 9),
            bg=COLORS["card_bg"],
            fg=COLORS["text_light"],
            wraplength=550
        )
        self.file_label.pack(fill=tk.X, pady=(5, 0))
        
        # Ship type display
        self.ship_type_label = tk.Label(
            file_frame,
            text="",
            font=("Segoe UI", 9, "bold"),
            bg=COLORS["card_bg"],
            fg=COLORS["text_light"],
            wraplength=550
        )
        self.ship_type_label.pack(fill=tk.X, pady=(2, 0))
    
    def _build_recent_files(self) -> None:
        """Build recent files section."""
        recent_frame = tk.Frame(self.card_frame, bg=COLORS["card_bg"])
        recent_frame.pack(fill=tk.X, padx=15, pady=5)
        
        # Header with toggle
        header = tk.Frame(recent_frame, bg=COLORS["card_bg"])
        header.pack(fill=tk.X)
        
        self.recent_toggle = tk.Label(
            header,
            text="▼",
            font=("Segoe UI", 8),
            bg=COLORS["card_bg"],
            fg=COLORS["text_light"],
            cursor="hand2"
        )
        self.recent_toggle.pack(side=tk.LEFT)
        self.recent_toggle.bind("<Button-1>", lambda e: self._toggle_recent())
        
        self.recent_title = tk.Label(
            header,
            text=self.texts.get("recent_files", "📂 Gần đây:"),
            font=("Segoe UI", 9),
            bg=COLORS["card_bg"],
            fg=COLORS["text_light"],
            cursor="hand2"
        )
        self.recent_title.pack(side=tk.LEFT, padx=(3, 0))
        self.recent_title.bind("<Button-1>", lambda e: self._toggle_recent())
        
        # Recent files list
        self.recent_list_frame = tk.Frame(recent_frame, bg=COLORS["card_bg"])
        self.recent_list_frame.pack(fill=tk.X, pady=(3, 0))
        
        self._update_recent_files_display()
    
    def _update_recent_files_display(self) -> None:
        """Update recent files display."""
        for widget in self.recent_list_frame.winfo_children():
            widget.destroy()
        
        if not self.recent_files:
            tk.Label(
                self.recent_list_frame,
                text=self.texts.get("no_recent", "Chưa có file nào"),
                font=("Segoe UI", 9),
                bg=COLORS["card_bg"],
                fg=COLORS["text_light"]
            ).pack(anchor="w")
            return
        
        # Show up to 5 recent files
        for entry in self.recent_files[:5]:
            if isinstance(entry, dict):
                path = entry.get("path", "")
                stats = entry.get("stats", {})
            else:
                path = entry
                stats = {}
            
            if not path:
                continue
            
            file_frame = tk.Frame(self.recent_list_frame, bg=COLORS["card_bg"])
            file_frame.pack(fill=tk.X, pady=1)
            
            filename = Path(path).name if path else ""
            display_name = filename[:40] + "..." if len(filename) > 40 else filename
            
            # File button
            btn = tk.Label(
                file_frame,
                text=f"📄 {display_name}",
                font=("Segoe UI", 9),
                bg=COLORS["card_bg"],
                fg=COLORS["primary"],
                cursor="hand2"
            )
            btn.pack(side=tk.LEFT)
            btn.bind("<Button-1>", lambda e, p=path: self._load_recent_file(p))
            
            # Stats if available
            if stats:
                stats_text = f"({stats.get('containers', '?')} cont)"
                tk.Label(
                    file_frame,
                    text=stats_text,
                    font=("Segoe UI", 8),
                    bg=COLORS["card_bg"],
                    fg=COLORS["text_light"]
                ).pack(side=tk.LEFT, padx=(5, 0))
    
    def _toggle_recent(self) -> None:
        """Toggle recent files section."""
        self.recent_expanded = not self.recent_expanded
        
        if self.recent_expanded:
            self.recent_toggle.config(text="▼")
            self.recent_list_frame.pack(fill=tk.X, pady=(3, 0))
        else:
            self.recent_toggle.config(text="▶")
            self.recent_list_frame.pack_forget()
    
    def _build_action_buttons(self) -> None:
        """Build action buttons."""
        btn_frame = tk.Frame(self.card_frame, bg=COLORS["card_bg"])
        btn_frame.pack(fill=tk.X, padx=15, pady=10)
        
        # Process button
        self.btn_process = ttk.Button(
            btn_frame,
            text=self.texts.get("btn_process", "🔄 Xử lý"),
            style="Action.TButton",
            command=self._start_processing,
            state=tk.DISABLED
        )
        self.btn_process.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 5))
        
        # Preview button
        self.btn_preview = ttk.Button(
            btn_frame,
            text=self.texts.get("btn_preview", "👁️ Xem trước"),
            style="Action.TButton",
            command=self._show_preview,
            state=tk.DISABLED
        )
        self.btn_preview.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)
        
        # Save button
        self.btn_save = ttk.Button(
            btn_frame,
            text=self.texts.get("btn_save", "💾 Lưu file"),
            style="Success.TButton",
            command=self._save_file,
            state=tk.DISABLED
        )
        self.btn_save.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(5, 0))
    
    def _build_status_section(self) -> None:
        """Build status section."""
        status_frame = tk.Frame(self.card_frame, bg=COLORS["card_bg"])
        status_frame.pack(fill=tk.X, padx=15, pady=10)
        
        # Progress bar
        self.progress = ttk.Progressbar(
            status_frame,
            style="Green.Horizontal.TProgressbar",
            mode="indeterminate",
            length=550
        )
        self.progress.pack_forget()  # Hidden initially
        
        # Status label
        self.status_var = tk.StringVar(
            value=self.texts.get("status_ready", "Sẵn sàng")
        )
        self.status_label = tk.Label(
            status_frame,
            textvariable=self.status_var,
            font=("Segoe UI", 10),
            bg=COLORS["card_bg"],
            fg=COLORS["primary"]
        )
        self.status_label.pack()
    
    def _build_stats_section(self) -> None:
        """Build statistics section."""
        self.stats_frame = tk.Frame(self.card_frame, bg=COLORS["card_bg"])
        # Hidden initially, shown after processing
        
        # Stats labels
        stats_grid = tk.Frame(self.stats_frame, bg=COLORS["card_bg"])
        stats_grid.pack(fill=tk.X)
        
        stats_items = [
            ("container_count", "stats_containers", "Container:"),
            ("full_count", "stats_full", "Full:"),
            ("empty_count", "stats_empty", "Empty:"),
            ("soc_count", "stats_soc", "SOC:"),
            ("coc_count", "stats_coc", "COC:"),
        ]
        
        for key, text_key, default_text in stats_items:
            frame = tk.Frame(stats_grid, bg=COLORS["card_bg"])
            frame.pack(side=tk.LEFT, expand=True)
            
            tk.Label(
                frame,
                text=self.texts.get(text_key, default_text),
                font=("Segoe UI", 9),
                bg=COLORS["card_bg"],
                fg=COLORS["text_light"]
            ).pack(side=tk.LEFT)
            
            self.stats_vars[key] = tk.StringVar(value="0")
            tk.Label(
                frame,
                textvariable=self.stats_vars[key],
                font=("Segoe UI", 11, "bold"),
                bg=COLORS["card_bg"],
                fg=COLORS["text"]
            ).pack(side=tk.LEFT, padx=(3, 10))
    
    def _build_footer(self) -> None:
        """Build footer."""
        footer = tk.Frame(self.root, bg=COLORS["bg"])
        footer.pack(side=tk.BOTTOM, fill=tk.X, padx=20, pady=10)
        
        # Version
        tk.Label(
            footer,
            text=f"v{APP_VERSION}",
            font=("Segoe UI", 9),
            bg=COLORS["bg"],
            fg=COLORS["text_light"]
        ).pack(side=tk.LEFT)
        
        # Author
        author = APP_AUTHOR_VI if self.current_lang == "vi" else APP_AUTHOR_EN
        self.author_label = tk.Label(
            footer,
            text=author,
            font=("Segoe UI", 9),
            bg=COLORS["bg"],
            fg=COLORS["text_light"]
        )
        self.author_label.pack(side=tk.RIGHT)
    
    def _bind_shortcuts(self) -> None:
        """Bind keyboard shortcuts."""
        self.root.bind("<Control-o>", lambda e: self._choose_file())
        self.root.bind("<Control-O>", lambda e: self._choose_file())
        self.root.bind("<F5>", lambda e: self._start_processing())
        self.root.bind("<F1>", lambda e: self._show_shortcuts())
    
    # ========== Actions ==========
    
    def _on_drop(self, event) -> None:
        """Handle file drop event."""
        # file_path might be wrapped in curly braces by tkinterdnd2
        file_path = event.data
        if file_path.startswith('{') and file_path.endswith('}'):
            file_path = file_path[1:-1]
        
        if file_path.lower().endswith(('.xlsx', '.xls')):
            self._load_file(file_path)
        else:
            messagebox.showerror("Lỗi", "Vui lòng chọn file Excel (.xlsx, .xls)")
            
    def _choose_file(self) -> None:
        """Open file dialog to choose manifest file."""
        filetypes = [
            ("Excel files", "*.xls *.xlsx *.xlsm"),
            ("All files", "*.*")
        ]
        
        file_path = filedialog.askopenfilename(
            title="Chọn file Manifest",
            filetypes=filetypes
        )
        
        if not file_path:
            return
        
        self._load_file(file_path)
    
    def _load_file(self, file_path: str) -> None:
        """Load selected file."""
        self.current_file = file_path
        
        # Update display
        filename = Path(file_path).name
        self.file_label.config(text=filename)
        
        # Detect ship type
        self.detected_ship_type = detect_ship_type(file_path)
        self._update_ship_type_display()
        
        # Enable process button
        self.btn_process.config(state=tk.NORMAL)
        self.btn_preview.config(state=tk.DISABLED)
        self.btn_save.config(state=tk.DISABLED)
        
        # Reset stats
        self.stats_frame.pack_forget()
        self.processed_df = None
        
        self.status_var.set(self.texts.get("status_ready", "Sẵn sàng"))
        self.status_label.config(fg=COLORS["primary"])
        
        logger.info(f"Loaded file: {file_path}")
    
    def _load_recent_file(self, file_path: str) -> None:
        """Load a recent file."""
        if Path(file_path).exists():
            self._load_file(file_path)
        else:
            messagebox.showwarning("Warning", f"File không tồn tại:\n{file_path}")
            # Remove from recent
            self.recent_files = [
                f for f in self.recent_files
                if (isinstance(f, dict) and f.get("path") != file_path) or
                   (isinstance(f, str) and f != file_path)
            ]
            self._update_recent_files_display()
            self._save_app_config()
    
    def _update_ship_type_display(self) -> None:
        """Update the ship type UI based on the detected type."""
        if not hasattr(self, 'ship_type_label'):
            return
            
        if self.detected_ship_type == ShipType.UNKNOWN and not self.current_file:
            self.ship_type_label.config(text="")
            return
            
        display_name = get_ship_type_display_name(self.detected_ship_type)
        color = get_ship_type_color(self.detected_ship_type)
        desc = get_ship_type_description(self.detected_ship_type)
        
        prefix = self.texts.get("ship_type_prefix", "Loại tàu: ")
        text = f"{prefix}{display_name}"
        if desc:
            text += f" ({desc})"
            
        self.ship_type_label.config(text=text, fg=color)

    def _start_processing(self) -> None:
        """Start processing the file."""
        if not self.current_file:
            messagebox.showwarning("Warning", "Vui lòng chọn file trước")
            return
        
        if self.is_processing:
            return
        
        self.is_processing = True
        self.btn_choose.config(state=tk.DISABLED)
        self.btn_process.config(state=tk.DISABLED)
        self.status_var.set(self.texts.get("status_processing", "Đang xử lý..."))
        self.status_label.config(fg=COLORS["primary"])
        self.progress.pack(pady=(5, 0))
        self.progress.config(mode="determinate", value=0, maximum=100)
        
        # Process in thread
        thread = threading.Thread(target=self._process_file, daemon=True)
        thread.start()
    
    def _process_file(self) -> None:
        """Process file in background thread."""
        try:
            handler = VimcExcelHandler()
            
            # Validate file
            is_valid, error_msg = handler.validate_file(self.current_file)
            if not is_valid:
                raise ValueError(error_msg)
            
            # Read file
            df, header_idx = handler.read_excel(self.current_file)
            
            if df is None or df.empty:
                raise ValueError("Không đọc được dữ liệu từ file")
            
            # Define callback
            def update_progress(current: int, total: int, text: str) -> None:
                percent = int((current / total) * 100) if total > 0 else 0
                self.root.after(0, lambda p=percent, t=text: self._update_progress_ui(p, t))
            
            # Parse manifest data
            self.root.after(0, lambda: self.status_var.set("Đang phân tích cấu trúc..."))
            intermediate_data = handler.parse_manifest_data(df, header_idx, progress_callback=update_progress)
            
            if not intermediate_data:
                raise ValueError("Không tìm thấy dữ liệu container trong file")
            
            # Build output DataFrame
            self.processed_df = handler.build_output_dataframe(intermediate_data, progress_callback=update_progress)
            
            if self.processed_df is None or self.processed_df.empty:
                raise ValueError("Không thể tạo bảng kết quả")
            
            # Update UI
            self.root.after(0, self._on_process_complete)
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Processing error: {error_msg}", exc_info=True)
            self.root.after(0, lambda msg=error_msg: self._on_process_error(msg))
            
    def _update_progress_ui(self, percent: int, text: str) -> None:
        """Update progress bar and status text safely from thread."""
        self.progress["value"] = percent
        self.status_var.set(f"{text} ({percent}%)")
    
    def _play_sound(self, sound_type: str) -> None:
        """Play notification sound."""
        try:
            if sound_type == "success":
                winsound.MessageBeep(winsound.MB_OK)
            elif sound_type == "error":
                winsound.MessageBeep(winsound.MB_ICONHAND)
        except Exception:
            pass
    
    def _on_process_complete(self) -> None:
        """Handle processing complete."""
        self.is_processing = False
        self.progress["value"] = 100
        self.progress.pack_forget()
        
        self.btn_choose.config(state=tk.NORMAL)
        self.btn_process.config(state=tk.NORMAL)
        self.btn_preview.config(state=tk.NORMAL)
        self.btn_save.config(state=tk.NORMAL)
        
        self.status_var.set(self.texts.get("status_done", "Hoàn thành!"))
        self.status_label.config(fg=COLORS["success"])
        
        # Calculate stats
        self._calculate_stats()
        self.stats_frame.pack(fill=tk.X, pady=10)
        
        # Add to recent files
        self._add_to_recent()
        
        # Play success sound
        self._play_sound("success")
        
        logger.info("Processing complete")
    
    def _on_process_error(self, error_msg: str) -> None:
        """Handle processing error."""
        self.is_processing = False
        self.progress["value"] = 0
        self.progress.pack_forget()
        
        self.btn_choose.config(state=tk.NORMAL)
        self.btn_process.config(state=tk.NORMAL)
        
        self.status_var.set(f"{self.texts.get('status_error', 'Lỗi:')} {error_msg}")
        self.status_label.config(fg=COLORS["danger"])
        
        # Play error sound
        self._play_sound("error")
        
        messagebox.showerror("Error", f"Xử lý thất bại:\n{error_msg}")
    
    def _calculate_stats(self) -> None:
        """Calculate and display statistics."""
        if self.processed_df is None:
            return
        
        df = self.processed_df
        
        # Total containers
        total = len(df)
        self.stats_vars["container_count"].set(str(total))
        
        # F/E counts
        fe_col = None
        for col in df.columns:
            if 'F/E' in col.upper() or col.upper() in ['F/E', 'FE']:
                fe_col = col
                break
        
        full_count = 0
        empty_count = 0
        if fe_col:
            full_count = len(df[df[fe_col].astype(str).str.upper() == 'F'])
            empty_count = len(df[df[fe_col].astype(str).str.upper() == 'E'])
        
        self.stats_vars["full_count"].set(str(full_count))
        self.stats_vars["empty_count"].set(str(empty_count))
        
        # SOC/COC counts
        operator_col = None
        for col in df.columns:
            if 'khai thác' in col.lower() or 'operator' in col.lower():
                operator_col = col
                break
        
        soc_count = 0
        coc_count = 0
        if operator_col:
            soc_count = len(df[df[operator_col].astype(str).str.upper() == 'SVM'])
            coc_count = len(df[df[operator_col].astype(str).str.upper() == 'VMC'])
        
        self.stats_vars["soc_count"].set(str(soc_count))
        self.stats_vars["coc_count"].set(str(coc_count))
    
    def _add_to_recent(self) -> None:
        """Add current file to recent files."""
        if not self.current_file:
            return
        
        # Get stats
        stats = {
            "containers": self.stats_vars["container_count"].get(),
            "full": self.stats_vars["full_count"].get(),
            "empty": self.stats_vars["empty_count"].get(),
        }
        
        entry = {
            "path": self.current_file,
            "stats": stats,
        }
        
        # Remove if already exists
        self.recent_files = [
            f for f in self.recent_files
            if not (isinstance(f, dict) and f.get("path") == self.current_file) and
               not (isinstance(f, str) and f == self.current_file)
        ]
        
        # Add to front
        self.recent_files.insert(0, entry)
        self.recent_files = self.recent_files[:10]  # Keep only 10
        
        self._update_recent_files_display()
        self._save_app_config()
    
    def _show_preview(self) -> None:
        """Show preview window with filter, sort, and save options."""
        if self.processed_df is None:
            return
        
        # Create handler for saving
        handler = VimcExcelHandler()
        
        def on_save_callback(file_path: str) -> None:
            """Callback when file is saved from preview window."""
            if self.auto_open_after_save:
                self._open_file(file_path)
        
        # Create preview window
        PreviewWindow(
            self.root,
            self.processed_df,
            self.texts,
            on_save_callback,
            handler
        )
    
    def _save_file(self) -> None:
        """Save processed file."""
        if self.processed_df is None:
            return
        
        # Generate default filename
        original_name = Path(self.current_file).stem if self.current_file else "manifest"
        default_name = f"Processed_{original_name}.xlsx"
        
        file_path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx")],
            initialfile=default_name
        )
        
        if not file_path:
            return
        
        try:
            handler = VimcExcelHandler()
            handler.save_excel(file_path, self.processed_df)
            
            messagebox.showinfo(
                "Thành công",
                f"Đã lưu file:\n{file_path}"
            )
            
            if self.auto_open_after_save:
                self._open_file(file_path)
                
        except Exception as e:
            logger.error(f"Save error: {e}", exc_info=True)
            messagebox.showerror("Lỗi", f"Lỗi khi lưu:\n{str(e)}")
    
    def _open_file(self, file_path: str) -> None:
        """Open file with default application."""
        try:
            if sys.platform == "win32":
                os.startfile(file_path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", file_path])
            else:
                subprocess.Popen(["xdg-open", file_path])
        except Exception as e:
            logger.error(f"Failed to open file: {e}")
    
    # ========== Settings ==========
    
    def _set_language(self, lang: str) -> None:
        """Set application language."""
        if self.current_lang == lang:
            return
        
        self.current_lang = lang
        self.texts = self._load_strings()
        self._refresh_ui_texts()
        self._rebuild_settings_menu()
        self._save_app_config()
    
    def _refresh_ui_texts(self) -> None:
        """Refresh all UI texts with current language."""
        # Title
        self.title_label.config(
            text=self.texts.get("app_subtitle", "VIMC Manifest Cleaner")
        )
        
        # Buttons
        self.btn_choose.config(
            text=self.texts.get("choose_file_button", "📂 Chọn File Manifest")
        )
        self.btn_process.config(
            text=self.texts.get("process_button", "🔄 Xử lý")
        )
        self.btn_preview.config(
            text=self.texts.get("preview_button", "👁️ Xem trước")
        )
        self.btn_save.config(
            text=self.texts.get("save_button", "💾 Lưu file")
        )
        
        # Recent files
        self.recent_title.config(
            text=self.texts.get("recent_files", "📂 Gần đây:")
        )
        self._update_recent_files_display()
        
        # Status
        if not self.is_processing and self.processed_df is None:
            self.status_var.set(self.texts.get("status_ready", "Sẵn sàng"))
        
        # Ship type
        self._update_ship_type_display()
        
        # Author
        author = APP_AUTHOR_VI if self.current_lang == "vi" else APP_AUTHOR_EN
        self.author_label.config(text=author)
    
    def _rebuild_settings_menu(self) -> None:
        """Rebuild settings menu with current language."""
        self.settings_menu.delete(0, tk.END)
        
        # Language submenu
        lang_menu = tk.Menu(self.settings_menu, tearoff=0)
        lang_menu.add_command(
            label="🇻🇳 Tiếng Việt",
            command=lambda: self._set_language("vi")
        )
        lang_menu.add_command(
            label="🇬🇧 English",
            command=lambda: self._set_language("en")
        )
        self.settings_menu.add_cascade(
            label=self.texts.get("menu_language", "Ngôn ngữ"),
            menu=lang_menu
        )
        
        # Auto open
        self.settings_menu.add_checkbutton(
            label=self.texts.get("menu_auto_open", "Tự động mở file"),
            variable=self.auto_open_var,
            command=self._toggle_auto_open
        )
        
        self.settings_menu.add_separator()
        
        # Shortcuts
        self.settings_menu.add_command(
            label=self.texts.get("menu_shortcuts", "Phím tắt"),
            command=self._show_shortcuts
        )
        
        # About
        self.settings_menu.add_command(
            label=self.texts.get("menu_about", "Thông tin"),
            command=self._show_about
        )
    
    def _toggle_auto_open(self) -> None:
        """Toggle auto open setting."""
        self.auto_open_after_save = self.auto_open_var.get()
        self._save_app_config()
    
    def _show_shortcuts(self) -> None:
        """Show keyboard shortcuts dialog."""
        shortcuts = """
Phím tắt / Shortcuts:

Ctrl+O    : Chọn file / Open file
F5        : Xử lý / Process
F1        : Phím tắt / Shortcuts
        """
        messagebox.showinfo("Phím tắt / Shortcuts", shortcuts)
    
    def _show_about(self) -> None:
        """Show about dialog."""
        about_text = f"""
VIMC Manifest Cleaner v{APP_VERSION}

Hỗ trợ các loại tàu:
• MARINER (Mô tả trước, KGS)
• PIONEER (Trọng lượng trước, TẤN)
• NAVIGATOR (Trọng lượng trước, TẤN)
• STAR (Trọng lượng trước, TẤN)

{APP_AUTHOR_VI}
    
© 2026
        """
        messagebox.showinfo("Thông tin", about_text)
    
    def run(self) -> None:
        """Run the application."""
        self.root.mainloop()

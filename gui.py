"""
Shopee Card Checker - Modern GUI Application
A beautiful, user-friendly interface for card validation automation.
"""

import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
import threading
import asyncio
import json
import os
from pathlib import Path
from typing import Optional
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from core.browser_manager import init_browser, close_browser, load_session_cookies, verify_session
from core.checker import process_all_batches
from input.card_processor import build_card_queue, validate_card
from utils.helpers import log_info, log_error
from utils.telegram_sender import send_telegram_notification, send_batch_summary, is_telegram_configured


# Set appearance
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class ShopeeCardCheckerGUI(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        # Window configuration
        self.title("Shopee Card Checker Pro")
        self.geometry("900x750")
        self.minsize(800, 700)
        
        # Load config
        self.config = self.load_config()
        
        # Variables
        self.card_file_path = tk.StringVar()
        self.cookies_file_path = tk.StringVar(value="cookies.txt")
        self.results_file_path = tk.StringVar(value="output/results.txt")
        self.failed_file_path = tk.StringVar(value="output/failed.txt")
        self.three_ds_file_path = tk.StringVar(value="output/3ds.txt")
        self.headless_mode = tk.BooleanVar(value=self.config.get("browser", {}).get("headless", True))
        self.workers_count = tk.IntVar(value=self.config.get("workers", 5))
        
        # Retry configuration
        retry_config = self.config.get("retry", {})
        self.retry_enabled = tk.BooleanVar(value=retry_config.get("enabled", False))
        self.retry_max_retries = tk.IntVar(value=retry_config.get("max_retries", 3))
        
        # Processing state
        self.is_processing = False
        self.processing_thread = None
        self.monitor_thread = None
        self.total_cards_count = 0
        self.current_loop = None
        self.current_task = None
        
        # Setup UI
        self.setup_ui()
        
    def load_config(self):
        """Load configuration from config.json"""
        try:
            config_path = Path(__file__).parent / "config.json"
            with open(config_path, "r") as f:
                return json.load(f)
        except Exception as e:
            log_error(f"Failed to load config: {e}")
            return {}
    
    def setup_ui(self):
        """Setup the user interface"""
        # Configure grid
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        
        # Header
        self.create_header()
        
        # Main content
        self.create_main_content()
        
        # Footer with status
        self.create_footer()
    
    def create_header(self):
        """Create header section"""
        header_frame = ctk.CTkFrame(self, corner_radius=0, fg_color=("gray85", "gray15"))
        header_frame.grid(row=0, column=0, sticky="ew", padx=0, pady=0)
        header_frame.grid_columnconfigure(0, weight=1)
        
        # Settings button (top right)
        settings_button = ctk.CTkButton(
            header_frame,
            text="⚙️ Settings",
            command=self.open_settings,
            width=100,
            height=30,
            font=ctk.CTkFont(size=12)
        )
        settings_button.place(relx=0.98, rely=0.1, anchor="ne")
        
        # Title
        title_label = ctk.CTkLabel(
            header_frame,
            text="🛡️ Shopee Card Checker Pro",
            font=ctk.CTkFont(size=28, weight="bold")
        )
        title_label.pack(pady=20)
        
        subtitle_label = ctk.CTkLabel(
            header_frame,
            text="Fast, Parallel Card Validation System",
            font=ctk.CTkFont(size=14),
            text_color=("gray40", "gray60")
        )
        subtitle_label.pack(pady=(0, 20))
    
    def create_main_content(self):
        """Create main content area"""
        main_frame = ctk.CTkFrame(self, corner_radius=10)
        main_frame.grid(row=1, column=0, sticky="nsew", padx=20, pady=20)
        main_frame.grid_columnconfigure(0, weight=1)
        main_frame.grid_rowconfigure(4, weight=1)
        
        # File selection section
        self.create_file_section(main_frame)
        
        # Settings section
        self.create_settings_section(main_frame)
        
        # Control buttons
        self.create_control_section(main_frame)
        
        # Progress section
        self.create_progress_section(main_frame)
        
        # Log display
        self.create_log_section(main_frame)
    
    def create_file_section(self, parent):
        """Create file selection section"""
        file_frame = ctk.CTkFrame(parent)
        file_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 10))
        file_frame.grid_columnconfigure(1, weight=1)
        
        # Card file
        ctk.CTkLabel(file_frame, text="📄 Card File:", font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=0, column=0, sticky="w", padx=10, pady=10
        )
        self.card_file_entry = ctk.CTkEntry(file_frame, textvariable=self.card_file_path, placeholder_text="Select card file...")
        self.card_file_entry.grid(row=0, column=1, sticky="ew", padx=10, pady=10)
        ctk.CTkButton(file_frame, text="Browse", command=self.browse_card_file, width=100).grid(
            row=0, column=2, padx=10, pady=10
        )
        
        # Cookies file
        ctk.CTkLabel(file_frame, text="🍪 Cookies:", font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=1, column=0, sticky="w", padx=10, pady=10
        )
        self.cookies_entry = ctk.CTkEntry(file_frame, textvariable=self.cookies_file_path)
        self.cookies_entry.grid(row=1, column=1, sticky="ew", padx=10, pady=10)
        ctk.CTkButton(file_frame, text="Browse", command=self.browse_cookies_file, width=100).grid(
            row=1, column=2, padx=10, pady=10
        )
    
    def create_settings_section(self, parent):
        """Create settings section"""
        settings_frame = ctk.CTkFrame(parent)
        settings_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=10)
        settings_frame.grid_columnconfigure((0, 1), weight=1)
        
        # Left column
        left_frame = ctk.CTkFrame(settings_frame, fg_color="transparent")
        left_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        
        # Headless mode
        self.headless_checkbox = ctk.CTkCheckBox(
            left_frame,
            text="🚀 Headless Mode (Faster)",
            variable=self.headless_mode,
            font=ctk.CTkFont(size=13)
        )
        self.headless_checkbox.pack(anchor="w", pady=5)
        
        # Retry on specific errors
        self.retry_checkbox = ctk.CTkCheckBox(
            left_frame,
            text="🔄 Enable Auto-Retry (for [3] errors)",
            variable=self.retry_enabled,
            font=ctk.CTkFont(size=13)
        )
        self.retry_checkbox.pack(anchor="w", pady=5)
        # Explicitly set checkbox state from config
        if self.retry_enabled.get():
            self.retry_checkbox.select()
        else:
            self.retry_checkbox.deselect()
        
        # Workers
        workers_frame = ctk.CTkFrame(left_frame, fg_color="transparent")
        workers_frame.pack(anchor="w", pady=5, fill="x")
        ctk.CTkLabel(workers_frame, text="⚙️ Workers:", font=ctk.CTkFont(size=13)).pack(side="left", padx=(0, 10))
        self.workers_slider = ctk.CTkSlider(
            workers_frame,
            from_=1,
            to=10,
            number_of_steps=9,
            variable=self.workers_count,
            width=150
        )
        self.workers_slider.pack(side="left", padx=5)
        self.workers_label = ctk.CTkLabel(workers_frame, text="5", font=ctk.CTkFont(size=13, weight="bold"))
        self.workers_label.pack(side="left", padx=5)
        self.workers_slider.configure(command=self.update_workers_label)
        
        # Retry max attempts
        retry_frame = ctk.CTkFrame(left_frame, fg_color="transparent")
        retry_frame.pack(anchor="w", pady=5, fill="x")
        ctk.CTkLabel(retry_frame, text="🔁 Max Retries:", font=ctk.CTkFont(size=13)).pack(side="left", padx=(0, 10))
        self.retry_slider = ctk.CTkSlider(
            retry_frame,
            from_=1,
            to=5,
            number_of_steps=4,
            variable=self.retry_max_retries,
            width=150
        )
        self.retry_slider.pack(side="left", padx=5)
        self.retry_label = ctk.CTkLabel(retry_frame, text="3", font=ctk.CTkFont(size=13, weight="bold"))
        self.retry_label.pack(side="left", padx=5)
        self.retry_slider.configure(command=self.update_retry_label)
        
        # Right column - Output files
        right_frame = ctk.CTkFrame(settings_frame, fg_color="transparent")
        right_frame.grid(row=0, column=1, sticky="ew", padx=10, pady=10)
        
        output_label = ctk.CTkLabel(right_frame, text="📊 Output Files:", font=ctk.CTkFont(size=13, weight="bold"))
        output_label.pack(anchor="w", pady=(0, 5))
        
        results_frame = ctk.CTkFrame(right_frame, fg_color="transparent")
        results_frame.pack(anchor="w", fill="x", pady=2)
        ctk.CTkLabel(results_frame, text="✅ Success:", font=ctk.CTkFont(size=12)).pack(side="left", padx=(0, 5))
        ctk.CTkEntry(results_frame, textvariable=self.results_file_path, width=150).pack(side="left")
        
        failed_frame = ctk.CTkFrame(right_frame, fg_color="transparent")
        failed_frame.pack(anchor="w", fill="x", pady=2)
        ctk.CTkLabel(failed_frame, text="❌ Failed:", font=ctk.CTkFont(size=12)).pack(side="left", padx=(0, 10))
        ctk.CTkEntry(failed_frame, textvariable=self.failed_file_path, width=150).pack(side="left")
    
    def create_control_section(self, parent):
        """Create control buttons section"""
        control_frame = ctk.CTkFrame(parent, fg_color="transparent")
        control_frame.grid(row=2, column=0, sticky="ew", padx=20, pady=10)
        control_frame.grid_columnconfigure((0, 1), weight=1)
        
        # Start button
        self.start_button = ctk.CTkButton(
            control_frame,
            text="▶️  Start Processing",
            command=self.start_processing,
            font=ctk.CTkFont(size=16, weight="bold"),
            height=50,
            fg_color=("green", "darkgreen"),
            hover_color=("darkgreen", "green")
        )
        self.start_button.grid(row=0, column=0, padx=10, sticky="ew")
        
        # Stop button
        self.stop_button = ctk.CTkButton(
            control_frame,
            text="⏸️  Stop",
            command=self.stop_processing,
            font=ctk.CTkFont(size=16, weight="bold"),
            height=50,
            fg_color=("red", "darkred"),
            hover_color=("darkred", "red"),
            state="disabled"
        )
        self.stop_button.grid(row=0, column=1, padx=10, sticky="ew")
    
    def create_progress_section(self, parent):
        """Create progress indicators section"""
        progress_frame = ctk.CTkFrame(parent)
        progress_frame.grid(row=3, column=0, sticky="ew", padx=20, pady=10)
        progress_frame.grid_columnconfigure(0, weight=1)
        
        # Progress bar
        self.progress_bar = ctk.CTkProgressBar(progress_frame, mode="determinate")
        self.progress_bar.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 5))
        self.progress_bar.set(0)
        
        # Progress label
        self.progress_label = ctk.CTkLabel(
            progress_frame,
            text="Ready to start",
            font=ctk.CTkFont(size=13)
        )
        self.progress_label.grid(row=1, column=0, padx=20, pady=(0, 10))
        
        # Stats frame
        stats_frame = ctk.CTkFrame(progress_frame, fg_color="transparent")
        stats_frame.grid(row=2, column=0, sticky="ew", padx=20, pady=(0, 20))
        stats_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)
        
        self.total_label = ctk.CTkLabel(stats_frame, text="Total: 0", font=ctk.CTkFont(size=12, weight="bold"))
        self.total_label.grid(row=0, column=0, padx=5)
        
        self.success_label = ctk.CTkLabel(stats_frame, text="✅ Success: 0", font=ctk.CTkFont(size=12, weight="bold"), text_color="green")
        self.success_label.grid(row=0, column=1, padx=5)
        
        self.three_ds_label = ctk.CTkLabel(stats_frame, text="🔵 3DS: 0", font=ctk.CTkFont(size=12, weight="bold"), text_color="cyan")
        self.three_ds_label.grid(row=0, column=2, padx=5)
        
        self.failed_label = ctk.CTkLabel(stats_frame, text="❌ Failed: 0", font=ctk.CTkFont(size=12, weight="bold"), text_color="red")
        self.failed_label.grid(row=0, column=3, padx=5)
    
    def create_log_section(self, parent):
        """Create log display section"""
        log_frame = ctk.CTkFrame(parent)
        log_frame.grid(row=4, column=0, sticky="nsew", padx=20, pady=(10, 20))
        log_frame.grid_rowconfigure(1, weight=1, minsize=200)  # Minimum height for log section
        log_frame.grid_columnconfigure(0, weight=1)
        
        ctk.CTkLabel(log_frame, text="📋 Activity Log", font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=0, column=0, sticky="w", padx=15, pady=(15, 5)
        )
        
        # Log textbox with scrollbar - explicitly set height
        self.log_textbox = ctk.CTkTextbox(
            log_frame, 
            font=ctk.CTkFont(family="Consolas", size=11),
            wrap="word",
            height=200,  # Explicit minimum height
            scrollbar_button_color=("gray70", "gray30"),
            scrollbar_button_hover_color=("gray60", "gray40")
        )
        self.log_textbox.grid(row=1, column=0, sticky="nsew", padx=15, pady=(0, 15))
        
    def create_footer(self):
        """Create footer with status bar"""
        footer_frame = ctk.CTkFrame(self, corner_radius=0, height=30, fg_color=("gray85", "gray15"))
        footer_frame.grid(row=2, column=0, sticky="ew", padx=0, pady=0)
        
        self.status_label = ctk.CTkLabel(
            footer_frame,
            text="Status: Idle",
            font=ctk.CTkFont(size=11),
            text_color=("gray40", "gray60")
        )
        self.status_label.pack(side="left", padx=20, pady=5)
    
    def update_workers_label(self, value):
        """Update workers count label"""
        self.workers_label.configure(text=str(int(value)))
    
    def update_retry_label(self, value):
        """Update retry count label"""
        self.retry_label.configure(text=str(int(value)))
    
    def browse_card_file(self):
        """Browse for card file"""
        filename = filedialog.askopenfilename(
            title="Select Card File",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if filename:
            self.card_file_path.set(filename)
    
    def browse_cookies_file(self):
        """Browse for cookies file"""
        filename = filedialog.askopenfilename(
            title="Select Cookies File",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if filename:
            self.cookies_file_path.set(filename)
    
    def open_settings(self):
        """Open settings dialog for Telegram configuration"""
        settings_window = ctk.CTkToplevel(self)
        settings_window.title("Settings - Telegram Configuration")
        settings_window.geometry("550x550")
        settings_window.minsize(550, 550)
        settings_window.transient(self)
        settings_window.grab_set()
        settings_window.resizable(True, True)
        
        # Load current .env values
        env_path = Path(__file__).parent / ".env"
        current_token = ""
        current_chat_id = ""
        
        if env_path.exists():
            with open(env_path, 'r') as f:
                for line in f:
                    if line.startswith('TELEGRAM_BOT_TOKEN='):
                        current_token = line.split('=', 1)[1].strip()
                    elif line.startswith('TELEGRAM_CHAT_ID='):
                        current_chat_id = line.split('=', 1)[1].strip()
        
        # Title
        title_label = ctk.CTkLabel(
            settings_window,
            text="⚙️ Telegram Bot Configuration",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        title_label.pack(pady=20)
        
        # Info label
        info_label = ctk.CTkLabel(
            settings_window,
            text="Configure your Telegram bot to receive notifications during processing.",
            font=ctk.CTkFont(size=12),
            text_color=("gray40", "gray60")
        )
        info_label.pack(pady=(0, 20))
        
        # Form frame
        form_frame = ctk.CTkFrame(settings_window)
        form_frame.pack(fill="both", expand=True, padx=30, pady=(10, 10))
        
        # Bot Token
        ctk.CTkLabel(
            form_frame,
            text="Bot Token:",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(anchor="w", padx=20, pady=(20, 5))
        
        token_entry = ctk.CTkEntry(
            form_frame,
            placeholder_text="Enter your Telegram bot token...",
            width=450
        )
        token_entry.pack(padx=20, pady=(0, 10))
        if current_token:
            token_entry.insert(0, current_token)
        
        ctk.CTkLabel(
            form_frame,
            text="Get your bot token from @BotFather on Telegram",
            font=ctk.CTkFont(size=11),
            text_color=("gray40", "gray60")
        ).pack(anchor="w", padx=20, pady=(0, 15))
        
        # Chat ID
        ctk.CTkLabel(
            form_frame,
            text="Chat ID:",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(anchor="w", padx=20, pady=(10, 5))
        
        chat_id_entry = ctk.CTkEntry(
            form_frame,
            placeholder_text="Enter your Telegram chat ID...",
            width=450
        )
        chat_id_entry.pack(padx=20, pady=(0, 10))
        if current_chat_id:
            chat_id_entry.insert(0, current_chat_id)
        
        ctk.CTkLabel(
            form_frame,
            text="Get your chat ID from @userinfobot or @getidsbot",
            font=ctk.CTkFont(size=11),
            text_color=("gray40", "gray60")
        ).pack(anchor="w", padx=20, pady=(0, 10))
        
        # Status label
        status_label = ctk.CTkLabel(
            form_frame,
            text="",
            font=ctk.CTkFont(size=12)
        )
        status_label.pack(pady=(10, 20))
        
        # Buttons frame - outside form_frame so it's always visible
        button_frame = ctk.CTkFrame(settings_window, fg_color="transparent")
        button_frame.pack(pady=(0, 20))
        
        def save_settings():
            """Save settings to .env file"""
            token = token_entry.get().strip()
            chat_id = chat_id_entry.get().strip()
            
            # Allow saving empty fields (to disable Telegram)
            if not token and not chat_id:
                # Confirm deletion
                if messagebox.askyesno("Confirm", "This will disable Telegram notifications. Continue?", parent=settings_window):
                    try:
                        env_path_abs = Path(__file__).parent / ".env"
                        if env_path_abs.exists():
                            env_path_abs.unlink()
                        status_label.configure(text="✅ Telegram disabled!", text_color="green")
                        self.log_message("Telegram notifications disabled", "INFO")
                        self.after(1500, settings_window.destroy)
                    except Exception as e:
                        error_msg = f"❌ Error: {str(e)}"
                        status_label.configure(text=error_msg, text_color="red")
                        self.log_message(error_msg, "ERROR")
                return
            
            if not token or not chat_id:
                status_label.configure(text="⚠️ Both fields are required", text_color="orange")
                return
            
            try:
                # Ensure .env file path is absolute
                env_path_abs = Path(__file__).parent / ".env"
                
                # Write to .env file with explicit encoding
                env_content = f"# Telegram Bot Configuration\nTELEGRAM_BOT_TOKEN={token}\nTELEGRAM_CHAT_ID={chat_id}\n"
                
                with open(env_path_abs, 'w', encoding='utf-8') as f:
                    f.write(env_content)
                
                # Log the action
                self.log_message(f"Telegram settings saved to {env_path_abs}", "INFO")
                
                status_label.configure(text="✅ Settings saved! Changes active immediately.", text_color="green")
                self.after(2000, settings_window.destroy)
                
            except Exception as e:
                error_msg = f"❌ Error saving: {str(e)}"
                status_label.configure(text=error_msg, text_color="red")
                self.log_message(error_msg, "ERROR")
        
        def clear_fields():
            """Clear input fields only (doesn't save)"""
            token_entry.delete(0, 'end')
            chat_id_entry.delete(0, 'end')
            status_label.configure(text="Fields cleared. Click Save to disable Telegram.", text_color="orange")
        
        # Buttons
        ctk.CTkButton(
            button_frame,
            text="💾 Save",
            command=save_settings,
            width=120,
            height=35,
            fg_color="green",
            hover_color="darkgreen"
        ).pack(side="left", padx=10)
        
        ctk.CTkButton(
            button_frame,
            text="🗑️ Clear Fields",
            command=clear_fields,
            width=120,
            height=35,
            fg_color="orange",
            hover_color="darkorange"
        ).pack(side="left", padx=10)
        
        ctk.CTkButton(
            button_frame,
            text="❌ Cancel",
            command=settings_window.destroy,
            width=120,
            height=35
        ).pack(side="left", padx=10)
    
    def log_message(self, message: str, level: str = "INFO"):
        """Add message to log textbox"""
        self.log_textbox.insert("end", f"[{level}] {message}\n")
        self.log_textbox.see("end")
    
    def start_processing(self):
        """Start card processing"""
        # Validation
        if not self.card_file_path.get():
            messagebox.showerror("Error", "Please select a card file!")
            return
        
        if not os.path.exists(self.card_file_path.get()):
            messagebox.showerror("Error", "Card file does not exist!")
            return
        
        if not os.path.exists(self.cookies_file_path.get()):
            messagebox.showerror("Error", "Cookies file does not exist!")
            return
        
        # Clear previous results
        for filepath in [self.results_file_path.get(), self.failed_file_path.get()]:
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except:
                    pass
        
        # Update UI state
        self.is_processing = True
        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.progress_bar.set(0)
        self.log_textbox.delete("1.0", "end")
        
        # Reset counters
        self.total_cards_count = 0
        self.total_label.configure(text="Total: 0")
        self.success_label.configure(text="✅ Success: 0")
        self.three_ds_label.configure(text="🔵 3DS: 0")
        self.failed_label.configure(text="❌ Failed: 0")
        
        self.log_message("Starting card processing...", "INFO")
        self.update_status("Processing...")
        
        # Update config with GUI values
        self.config["browser"]["headless"] = self.headless_mode.get()
        self.config["workers"] = self.workers_count.get()
        
        # Update retry configuration
        if "retry" not in self.config:
            self.config["retry"] = {}
        self.config["retry"]["enabled"] = self.retry_enabled.get()
        self.config["retry"]["max_retries"] = self.retry_max_retries.get()
        
        # Start monitoring thread
        self.monitor_thread = threading.Thread(target=self.monitor_progress, daemon=True)
        self.monitor_thread.start()
        
        # Start processing in separate thread
        self.processing_thread = threading.Thread(target=self.run_processing, daemon=True)
        self.processing_thread.start()
    
    def stop_processing(self):
        """Stop card processing"""
        self.is_processing = False
        self.log_message("Stop requested - cleaning up...", "WARNING")
        self.update_status("Stopping...")
        
        # Cancel the current async task if it exists
        if self.current_task and not self.current_task.done():
            self.current_task.cancel()
            self.log_message("Processing task cancelled", "WARNING")
    
    def monitor_progress(self):
        """Monitor progress by watching result files"""
        import time
        
        while self.is_processing:
            try:
                success_count = 0
                failed_count = 0
                three_ds_count = 0
                
                # Count lines in results file (only successes)
                if os.path.exists(self.results_file_path.get()):
                    with open(self.results_file_path.get(), 'r', encoding='utf-8') as f:
                        success_count = sum(1 for line in f if line.strip())
                
                # Count lines in failed file
                if os.path.exists(self.failed_file_path.get()):
                    with open(self.failed_file_path.get(), 'r', encoding='utf-8') as f:
                        failed_count = sum(1 for line in f if line.strip())
                
                # Count lines in 3DS file
                if os.path.exists(self.three_ds_file_path.get()):
                    with open(self.three_ds_file_path.get(), 'r', encoding='utf-8') as f:
                        three_ds_count = sum(1 for line in f if line.strip())
                
                processed = success_count + failed_count + three_ds_count
                
                # Update UI in main thread
                self.after(0, lambda sc=success_count: self.success_label.configure(text=f"✅ Success: {sc}"))
                self.after(0, lambda tds=three_ds_count: self.three_ds_label.configure(text=f"🔵 3DS: {tds}"))
                self.after(0, lambda fc=failed_count: self.failed_label.configure(text=f"❌ Failed: {fc}"))
                
                # Update progress bar if we know total
                if self.total_cards_count > 0:
                    progress = processed / self.total_cards_count
                    self.after(0, lambda p=progress: self.progress_bar.set(p))
                    self.after(0, lambda p=processed, t=self.total_cards_count: 
                              self.progress_label.configure(text=f"Processing: {p}/{t} cards"))
                else:
                    self.after(0, lambda p=processed: 
                              self.progress_label.configure(text=f"Processed: {p} cards"))
                
                time.sleep(0.5)  # Update every 500ms
                
            except Exception as e:
                # Silently continue if files don't exist yet
                time.sleep(0.5)
                continue
    
    def run_processing(self):
        """Run the actual card processing (in separate thread)"""
        loop = None
        try:
            # Create new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self.current_loop = loop
            
            # Create and store the task
            self.current_task = loop.create_task(self.process_cards())
            
            # Run until the task completes or is cancelled
            loop.run_until_complete(self.current_task)
            
        except asyncio.CancelledError:
            self.log_message("Processing cancelled by user", "WARNING")
        except Exception as e:
            self.log_message(f"Error during processing: {e}", "ERROR")
            log_error(f"GUI processing error: {e}")
        finally:
            # Clean up any pending tasks
            if loop and not loop.is_closed():
                try:
                    # Cancel all pending tasks
                    pending = asyncio.all_tasks(loop)
                    for task in pending:
                        task.cancel()
                    # Give tasks a chance to clean up
                    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                except Exception:
                    pass
                finally:
                    loop.close()
            
            # Reset UI state
            self.after(0, self.processing_complete)
    
    async def process_cards(self):
        """Async card processing logic"""
        import time
        from pathlib import Path
        start_time = time.time()
        browsers = []
        try:
            # Create output folder and clean output files
            output_dir = Path("output")
            output_dir.mkdir(exist_ok=True)
            
            # Clear previous results
            results_file = Path(self.results_file_path.get())
            failed_file = Path(self.failed_file_path.get())
            three_ds_file = Path(self.three_ds_file_path.get())
            
            for file_path in [results_file, failed_file, three_ds_file]:
                if file_path.exists():
                    file_path.unlink()
                file_path.touch()
            
            self.log_message("Output folder ready, previous results cleared", "INFO")
            
            # Build card queue
            self.log_message(f"Loading cards from {self.card_file_path.get()}...", "INFO")
            card_list = build_card_queue(self.card_file_path.get())
            
            if not card_list:
                self.log_message("No valid cards found!", "ERROR")
                return
            
            # Check if stopped
            if not self.is_processing:
                return
            
            total_cards = len(card_list)
            self.total_cards_count = total_cards  # Store for progress monitoring
            self.after(0, lambda: self.total_label.configure(text=f"Total: {total_cards}"))
            self.log_message(f"Loaded {total_cards} cards", "INFO")
            
            # Launch browsers in parallel
            self.log_message(f"Launching {self.workers_count.get()} browser instances in parallel...", "INFO")
            
            async def init_single_browser(index):
                """Initialize a single browser with cookies and session verification"""
                if not self.is_processing:
                    return None
                
                try:
                    self.log_message(f"Starting browser {index + 1}/{self.workers_count.get()}", "INFO")
                    browser = await init_browser(self.config)
                    
                    cookies_loaded = await load_session_cookies(browser, self.cookies_file_path.get(), self.config)
                    if not cookies_loaded:
                        self.log_message(f"Unable to load cookies for browser {index + 1}", "ERROR")
                        await close_browser(browser, keep_open=False)
                        return None
                    
                    if not await verify_session(browser, self.config):
                        self.log_message(f"Session verification failed for browser {index + 1}", "ERROR")
                        await close_browser(browser, keep_open=False)
                        return None
                    
                    self.log_message(f"Browser {index + 1} ready", "INFO")
                    return browser
                except Exception as e:
                    self.log_message(f"Error initializing browser {index + 1}: {e}", "ERROR")
                    return None
            
            # Launch all browsers concurrently
            browser_tasks = [init_single_browser(i) for i in range(self.workers_count.get())]
            browser_results = await asyncio.gather(*browser_tasks, return_exceptions=False)
            
            # Filter out None results and collect valid browsers
            browsers = [b for b in browser_results if b is not None]
            
            # Check if we got enough browsers
            if not browsers:
                self.log_message("Failed to initialize any browsers; aborting", "ERROR")
                return
            
            if len(browsers) < self.workers_count.get():
                self.log_message(f"Warning: Only {len(browsers)}/{self.workers_count.get()} browsers initialized successfully", "WARNING")
            
            # Check if stopped before processing
            if not self.is_processing:
                self.log_message("Stopping: Closing browsers...", "WARNING")
                for b in browsers:
                    await close_browser(b, keep_open=False)
                return
            
            self.log_message(f"Successfully initialized {len(browsers)} browser instances", "INFO")
            
            # Process cards
            self.log_message("Starting parallel processing...", "INFO")
            summary = await process_all_batches(
                browsers,
                card_list,
                self.cookies_file_path.get(),
                self.config,
                self.results_file_path.get(),
                self.failed_file_path.get(),
                self.card_file_path.get(),
                self.three_ds_file_path.get()
            )
            
            # Update final stats
            self.after(0, lambda: self.success_label.configure(text=f"✅ Success: {summary['success']}"))
            self.after(0, lambda: self.three_ds_label.configure(text=f"🔵 3DS: {summary.get('three_ds', 0)}"))
            self.after(0, lambda: self.failed_label.configure(text=f"❌ Failed: {summary['failed']}"))
            self.after(0, lambda: self.progress_bar.set(1.0))
            
            # Calculate duration
            duration = time.time() - start_time
            
            self.log_message("=" * 50, "INFO")
            self.log_message("PROCESSING COMPLETE!", "INFO")
            self.log_message(f"Total: {summary['total']}", "INFO")
            self.log_message(f"Success: {summary['success']}", "INFO")
            self.log_message(f"Failed: {summary['failed']}", "INFO")
            self.log_message(f"3DS: {summary.get('three_ds', 0)}", "INFO")
            self.log_message(f"Duration: {duration:.1f}s", "INFO")
            self.log_message("=" * 50, "INFO")
            
            # Send Telegram batch summary
            if is_telegram_configured():
                self.log_message("Sending batch summary to Telegram...", "INFO")
                loop = asyncio.get_event_loop()
                success = await loop.run_in_executor(
                    None,
                    send_batch_summary,
                    summary['total'],
                    summary['success'],
                    summary['failed'],
                    duration
                )
                if success:
                    self.log_message("✅ Batch summary sent to Telegram", "INFO")
                else:
                    self.log_message("❌ Failed to send batch summary", "WARNING")
            
        except asyncio.CancelledError:
            self.log_message("Processing cancelled - cleaning up...", "WARNING")
            raise
        except Exception as e:
            self.log_message(f"Processing error: {e}", "ERROR")
            raise
        finally:
            # Always close browsers
            if browsers:
                self.log_message(f"Closing {len(browsers)} browser instances...", "INFO")
                for browser in browsers:
                    try:
                        await close_browser(browser, keep_open=False)
                    except:
                        pass
    
    def processing_complete(self):
        """Called when processing is complete"""
        self.is_processing = False
        self.current_task = None
        self.current_loop = None
        self.start_button.configure(state="normal")
        self.stop_button.configure(state="disabled")
        self.update_status("Idle")
        
        # Only show completion message if not cancelled
        if self.total_cards_count > 0:
            messagebox.showinfo("Complete", "Card processing finished!")
        else:
            messagebox.showinfo("Stopped", "Processing was stopped.")
    
    def update_status(self, status: str):
        """Update status bar"""
        self.status_label.configure(text=f"Status: {status}")


def main():
    """Main entry point"""
    app = ShopeeCardCheckerGUI()
    app.mainloop()


if __name__ == "__main__":
    main()

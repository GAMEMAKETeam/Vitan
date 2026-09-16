import customtkinter as ctk
from pynput import keyboard as pynput_keyboard
import subprocess
import ctypes
import json
import os
import sys
import io
import logging
import re
import pywinstyles
import threading
import time
import random
import pygame
from tkinter import filedialog as fd
from tkinter import colorchooser

if hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'buffer'):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

os.system('chcp 65001 > nul')

LOG_FILE = "vita.log"
logging.basicConfig(
    level=logging.INFO,
    format='[VITA] %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("VitaLogger")
pygame.mixer.init()

COMMANDS_FILE = "commands.json"
WEBSITES_FILE = "websites.json"
COMMANDS_LIST_FILE = "commands_list.txt"
WEBSITES_LIST_FILE = "websites_list.txt"
CONFIG_FILE = "config.json"
DEFAULT_FILE = "default.json"

def clean_json_data(obj):
    if isinstance(obj, dict):
        return {k.strip(): clean_json_data(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [clean_json_data(item) for item in obj]
    elif isinstance(obj, str):
        return obj.strip()
    return obj

class StyleManager:
    def __init__(self):
        self.default_config = {}
        self.default_config = self.load_default()
        self.config = self.load_config()

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    user_config = json.load(f)
                    user_config = clean_json_data(user_config)
                    return self._merge_configs(self.default_config, user_config)
            except Exception as e:
                logger.error(f"Failed to load config: {e}. Using defaults.")
                return self.default_config.copy()
        return self.default_config.copy()

    def load_default(self):
        if os.path.exists(DEFAULT_FILE):
            try:
                with open(DEFAULT_FILE, "r", encoding="utf-8") as f:
                    default_config_file = json.load(f)
                    default_config_file = clean_json_data(default_config_file)
                    return self._merge_configs(self.default_config, default_config_file)
            except Exception as e:
                logger.error(f"Failed to load default config: {e}.")
        os._exit(0)

    def _merge_configs(self, default, user):
        merged = default.copy()
        for key, value in user.items():
            if isinstance(value, dict) and key in merged and isinstance(merged[key], dict):
                merged[key] = self._merge_configs(merged[key], value)
            else:
                merged[key] = value
        return merged

    def save_config(self):
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(self.config, f, indent=4, ensure_ascii=False)

    def reset_to_defaults(self):
        self.config = self.default_config.copy()
        self.save_config()
        return self.config

    def get(self, *keys):
        val = self.config
        for key in keys:
            if isinstance(val, dict):
                val = val.get(key, {})
            else:
                return None
        return val

    def set(self, *keys, value):
        if not keys:
            return
        val = self.config
        for key in keys[:-1]:
            if key not in val or not isinstance(val[key], dict):
                val[key] = {}
            val = val[key]
        val[keys[-1]] = value
        self.save_config()

style_manager = StyleManager()

def load_commands():
    if os.path.exists(COMMANDS_FILE):
        with open(COMMANDS_FILE, "r", encoding="utf-8") as f:
            return clean_json_data(json.load(f))
    return {}

def save_commands(commands):
    with open(COMMANDS_FILE, "w", encoding="utf-8") as f:
        json.dump(commands, f, indent=4, ensure_ascii=False)

def load_websites():
    if os.path.exists(WEBSITES_FILE):
        with open(WEBSITES_FILE, "r", encoding="utf-8") as f:
            return clean_json_data(json.load(f))
    return {}

def save_websites(websites):
    with open(WEBSITES_FILE, "w", encoding="utf-8") as f:
        json.dump(websites, f, indent=4, ensure_ascii=False)

LOCAL_COMMANDS = load_commands()
LOCAL_WEBSITES = load_websites()

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

DEFAULT_HINT = style_manager.get("ui", "default_hint")
MIN_WIDTH = 600
MIN_HEIGHT = 110
MAX_HINTS = 99

BUILTIN_COMMANDS = {
    "list": "Show all commands in a text file",
    "quit": "Close the application",
    "exit": "Close the application",
    "log": "Show application log in a window",
    "style": "Open settings window to customize colors, sounds and reset to defaults",
    "edit": "Open commands and websites editor"
}

orig_colors = style_manager.get("colors", "original")

root = ctk.CTk(fg_color=style_manager.get("ui", "chromakey_color"))
root.title("Vitan")
root.geometry(f"{MIN_WIDTH}x{MIN_HEIGHT}")
root.overrideredirect(True)
root.attributes('-topmost', True)
root.attributes('-alpha', style_manager.get("ui", "alpha"))
chromakey_color = style_manager.get("ui", "chromakey_color")
root.configure(fg_color=chromakey_color)
pywinstyles.set_opacity(root, color=chromakey_color, value=1)
root.update_idletasks()
x = (root.winfo_screenwidth() // 2) - (MIN_WIDTH // 2)
y = 150
root.geometry(f"+{x}+{y}")

entry_frame = ctk.CTkFrame(root, fg_color=orig_colors["entry_frame"],
                           corner_radius=15, border_width=2, border_color=orig_colors["border"])
entry_frame.pack(pady=(10, 5), padx=15, fill="x")

drag_handle = ctk.CTkFrame(root, fg_color='transparent', 
                           width=20, height=20, corner_radius=100)
drag_handle.pack(side="right", anchor="n", padx=10, pady=0)
drag_handle.pack_propagate(False)

font_main = (style_manager.get("ui", "font_family"), style_manager.get("ui", "font_size_main"))
entry = ctk.CTkEntry(entry_frame, placeholder_text="Enter command...",
                     font=font_main, height=40,
                     fg_color="transparent",
                     text_color=orig_colors["text_main"], placeholder_text_color=orig_colors["text_placeholder"],
                     border_width=0,
                     corner_radius=15)
entry.pack(side="left", fill="both", expand=True, padx=10, pady=5)

drag_data = {"x": 0, "y": 0}



def close(event):
    window = event.widget.winfo_toplevel()
    window.destroy()

drag_data = {"x": 0, "y": 0}

def start_drag(event):
    window = event.widget.winfo_toplevel()
    
    drag_data["x"] = event.x_root - window.winfo_x()
    drag_data["y"] = event.y_root - window.winfo_y()

def do_drag(event):
    window = event.widget.winfo_toplevel()
    
    x = event.x_root - drag_data["x"]
    y = event.y_root - drag_data["y"]
    
    window.geometry(f"+{x}+{y}")

def stop_drag(event):
    drag_data["x"] = 0
    drag_data["y"] = 0

drag_handle.bind("<Button-1>", start_drag)
drag_handle.bind("<B1-Motion>", do_drag)
drag_handle.bind("<ButtonRelease-1>", stop_drag)

hint_border_frame = ctk.CTkFrame(root, fg_color=orig_colors["hint_border_frame"],
                                 border_width=2, border_color=orig_colors["border"], corner_radius=8)
hint_border_frame.pack(anchor="w", padx=15, pady=(0, 5))

hint_frame = ctk.CTkFrame(root, fg_color=orig_colors["hint_frame"],
                                 border_width=3, border_color=orig_colors["border"], corner_radius=15)
hint_frame.pack(pady=(10, 5), padx=15, fill="x")

font_hint = (style_manager.get("ui", "font_family") or "Segoe UI", style_manager.get("ui", "font_size_hint") or 14)
hint_label = ctk.CTkLabel(hint_border_frame, text=DEFAULT_HINT,
                          font=font_hint, text_color=orig_colors["text_main"],
                          fg_color="transparent")
hint_label.pack(padx=10, pady=5)

hint_frames = []
root.withdraw()

last_window_open_time = 0
scheduled_revert_id = None
MATCH_COLOR = orig_colors["text_match"]
FULL_MATCH_COLOR = orig_colors["text_main"]

selected_hint_index = -1
current_matches = []
previous_text = ""

def close_window():
    w = root.winfo_width()
    h = root.winfo_height()
    x = root.winfo_x()
    y = root.winfo_y()
    play_sound("quit")
    
    bottom_y = y + h
    steps = 15
    initial_alpha = float(root.attributes('-alpha'))
    
    def step_hide(step):
        if step <= 0:
            root.destroy()
            root.quit()
            return
        progress = step / steps
        current_h = max(1, int(h * progress))
        new_y = bottom_y - current_h
        root.attributes('-alpha', initial_alpha * progress)
        root.geometry(f"{w}x{current_h}+{x}+{new_y}")
        root.after(15, lambda: step_hide(step - 1))
    
    step_hide(steps)

def smooth_hide():
    play_sound("noth")
    def step_hide(step):
        if step <= 0:
            hide_window()
            root.attributes('-alpha', style_manager.get("ui", "alpha"))
            return
        root.attributes('-alpha', step / 10)
        root.after(15, lambda: step_hide(step - 1))
    step_hide(9)
    
def apply_colors(scheme="original"):
    colors = style_manager.get("colors", scheme)
    if not colors:
        colors = style_manager.get("colors", "original")
    
    entry_frame.configure(fg_color=colors["entry_frame"], border_color=colors["border"])
    hint_border_frame.configure(fg_color=colors["hint_border_frame"], border_color=colors["border"])
    hint_frame.configure(fg_color=colors["hint_frame"], border_color=colors["border"])
    
    entry.configure(text_color=colors["text_main"], placeholder_text_color=colors["text_placeholder"])
    hint_label.configure(text_color=colors["text_main"])
    
    drag_handle.configure(fg_color=colors["drag_handle"])

    
    global MATCH_COLOR, FULL_MATCH_COLOR
    MATCH_COLOR = colors["text_match"]
    FULL_MATCH_COLOR = colors["text_main"]
    
    for frame in hint_frames:
        for child in frame.winfo_children():
            if isinstance(child, ctk.CTkLabel) and hasattr(child, 'role'):
                if child.role == "secondary":
                    child.configure(text_color=colors["text_secondary"])
                elif child.role == "match":
                    child.configure(text_color=colors["text_match"])
                elif child.role == "selected":
                    child.configure(text_color=colors["text_main"])
                else:
                    child.configure(text_color=colors["text_main"])
    
    root.update_idletasks()

def flash_color(scheme, duration=1000):
    global scheduled_revert_id
    if scheduled_revert_id:
        root.after_cancel(scheduled_revert_id)
    apply_colors(scheme)
    scheduled_revert_id = root.after(duration, lambda: apply_colors("original"))

def flash_green():
    flash_color("green", duration=1000)

def flash_red():
    flash_color("red", duration=1000)

def play_sound(action, volume=None):
    if volume is None:
        volume = style_manager.get("ui", "volume") or 0.5
    sound_file = style_manager.get("sounds", action)
    if not sound_file or not os.path.exists(sound_file):
        return
    try:
        sound = pygame.mixer.Sound(sound_file)
        sound.set_volume(volume)
        sound.play()
    except Exception as e:
        logger.error(f"Ошибка pygame для {sound_file}: {e}")

def force_focus():
    global last_window_open_time, previous_text, selected_hint_index
    last_window_open_time = time.time()
    previous_text = ""
    selected_hint_index = -1
    apply_colors("original")
    play_sound("open")
    root.deiconify()
    root.attributes('-alpha', style_manager.get("ui", "alpha"))
    root.update_idletasks()
    root.focus_force()
    entry.focus_force()
    entry.delete(0, ctk.END)
    hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
    ctypes.windll.user32.SetForegroundWindow(hwnd)
    update_hint()

def hide_window():
    global selected_hint_index
    root.withdraw()
    entry.delete(0, ctk.END)
    selected_hint_index = -1
    colors = style_manager.get("colors", "original")
    entry.configure(text_color=colors["text_main"])
    hint_label.configure(text=DEFAULT_HINT)
    for frame in hint_frames:
        frame.destroy()
    hint_frames.clear()
    root.geometry(f"{MIN_WIDTH}x{MIN_HEIGHT}")
    root.attributes('-alpha', style_manager.get("ui", "alpha"))

def quit_app():
    logger.info("Quitting...")
    try:
        hotkey_listener.stop()
    except:
        pass
    close_window()

def shake_window():
    original_x = root.winfo_x()
    original_y = root.winfo_y()
    def shake_step(step):
        if step >= 12:
            root.geometry(f"+{original_x}+{original_y}")
            return
        offset_x = random.randint(-3, 3)
        offset_y = random.randint(-3, 3)
        root.geometry(f"+{original_x + offset_x}+{original_y + offset_y}")
        root.after(25, lambda: shake_step(step + 1))
    shake_step(0)

def show_error_window(message):
    play_sound("error")
    logger.error(message)
    
    error_window = ctk.CTkToplevel(root)
    error_window.title("Error")
    error_window.attributes('-topmost', True)
    error_window.attributes('-alpha', 0.95)
    chromakey = style_manager.get("ui", "chromakey_color")
    error_window.configure(fg_color=chromakey)
    pywinstyles.set_opacity(error_window, color=chromakey, value=1)
    drag_handle = ctk.CTkFrame(error_window, fg_color='transparent', 
                               width=20, height=20, corner_radius=100)
    drag_handle.pack(side="right", anchor="n", padx=10, pady=0)
    drag_handle.pack_propagate(False)

    drag_handle.bind("<Button-1>", start_drag)
    drag_handle.bind("<B1-Motion>", do_drag)
    drag_handle.bind("<ButtonRelease-1>", stop_drag)

    inner = ctk.CTkFrame(
        error_window,
        fg_color=style_manager.get("colors", "red", "hint_frame"),
        corner_radius=12,
        border_width=2,
        border_color=style_manager.get("colors", "red", "text_main")
    )
    inner.pack(fill="both", expand=True, padx=2, pady=2)
    
    font_err = (style_manager.get("ui", "font_family") or "Segoe UI", 13)
    label = ctk.CTkLabel(
        inner, 
        text=f"⚠ {message}",
        font=font_err,
        text_color=style_manager.get("colors", "red", "text_main"),
        wraplength=500,
        justify="left"
    )
    label.pack(padx=20, pady=15)
    
    error_window.update_idletasks()
    content_w = label.winfo_reqwidth() + 70
    content_h = label.winfo_reqheight() + 50
    window_w = max(400, min(content_w, 900))
    window_h = content_h + 4
    
    error_window.geometry(f"{window_w}x{window_h}")
    sx = (error_window.winfo_screenwidth() // 2) - (window_w // 2)
    sy = (error_window.winfo_screenheight() // 2) - (window_h // 2)
    error_window.geometry(f"+{sx}+{sy}")
    error_window.overrideredirect(True)
    error_window.bind("<Escape>", lambda e: error_window.destroy())

def error_feedback(message="Command not found"):
    entry.configure(text_color=style_manager.get("colors", "red", "text_main"))
    shake_window()

def is_url(text):
    return bool(re.match(r'^(https?://)?([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})(/[^\s]*)?$', text))

def create_colored_hint(parent, cmd_name, user_input, full_text, icon="💡", is_selected=False):
    frame = ctk.CTkFrame(parent, fg_color="transparent")
    frame.pack(anchor="w", padx=15, pady=5)
    user_lower = user_input.lower()
    cmd_lower = cmd_name.lower()
    
    colors = style_manager.get("colors", "original")
    font_family = style_manager.get("ui", "font_family") or "Segoe UI"
    font_size_hint = style_manager.get("ui", "font_size_hint") or 14
    
    if is_selected:
        frame.configure(fg_color=colors["entry_frame"])
        
    if cmd_lower == user_lower:
        lbl = ctk.CTkLabel(frame, text=full_text, font=(font_family, font_size_hint), text_color=colors["text_main"])
        lbl.role = "selected" if is_selected else "main"
        lbl.pack(side="left", padx=5, pady=2)
    elif cmd_lower.startswith(user_lower):
        lbl1 = ctk.CTkLabel(frame, text=f"{icon} {cmd_name[:len(user_input)]}", font=(font_family, font_size_hint), text_color=colors["text_match"])
        lbl1.role = "match"
        lbl1.pack(side="left", padx=(5,0), pady=2)
        
        lbl2 = ctk.CTkLabel(frame, text=cmd_name[len(user_input):], font=(font_family, font_size_hint), text_color=colors["text_secondary"])
        lbl2.role = "secondary"
        lbl2.pack(side="left", pady=2)
        
        desc_start = full_text.find(" - ")
        if desc_start != -1:
            lbl3 = ctk.CTkLabel(frame, text=full_text[desc_start:], font=(font_family, font_size_hint), text_color=colors["text_secondary"])
            lbl3.role = "secondary"
            lbl3.pack(side="left", pady=2)
    else:
        lbl = ctk.CTkLabel(frame, text=full_text, font=(font_family, font_size_hint), text_color=colors["text_secondary"])
        lbl.role = "secondary"
        lbl.pack(side="left", padx=5, pady=2)
    return frame

def format_hint(name, data, user_input, icon="💡"):
    if isinstance(data, dict):
        attrs = data.get("attributes", [])
        desc = data.get("description", "")
        attr_str = " {" + ", ".join(attrs) + "}" if attrs else ""
        full_cmd = name + attr_str
        is_full = name.lower() == user_input.lower()
        return f"{icon} {full_cmd} - {desc}" if desc else f"{icon} {full_cmd}", is_full
    is_full = name.lower() == user_input.lower()
    return f"{icon} {name} - {data}", is_full

def show_output_window(command_name, output):
    out_window = ctk.CTkToplevel(root)
    out_window.title("Output")
    out_window.attributes('-topmost', True)
    out_window.attributes('-alpha', 0.95)
    chromakey = style_manager.get("ui", "chromakey_color")
    out_window.configure(fg_color=chromakey)
    pywinstyles.set_opacity(out_window, color=chromakey, value=1)
    drag_handle = ctk.CTkFrame(out_window, fg_color='transparent', 
                               width=20, height=20, corner_radius=100)
    drag_handle.pack(side="right", anchor="n", padx=10, pady=0)
    drag_handle.pack_propagate(False)

    drag_handle.bind("<Button-1>", start_drag)
    drag_handle.bind("<B1-Motion>", do_drag)
    drag_handle.bind("<ButtonRelease-1>", stop_drag)
    
    inner = ctk.CTkFrame(
        out_window,
        fg_color=style_manager.get("colors", "green", "hint_frame"),
        corner_radius=12,
        border_width=2,
        border_color=style_manager.get("colors", "green", "text_main")
    )
    inner.pack(fill="both", expand=True, padx=2, pady=2)
    font_out = (style_manager.get("ui", "font_family") or "Segoe UI", style_manager.get("ui", "font_size_output") or 12)
    text_box = ctk.CTkTextbox(inner, font=font_out, wrap="word", 
                              fg_color='transparent', text_color=style_manager.get("colors", "green", "text_main"))
    text_box.pack(fill="both", expand=True, padx=10, pady=10)
    text_box.insert("1.0", output)
    text_box.configure(state="disabled")
    
    out_window.update_idletasks()
    wx = (out_window.winfo_screenwidth() // 2) - 250
    wy = (out_window.winfo_screenheight() // 2) - 150
    out_window.geometry(f"+{wx}+{wy}")
    out_window.overrideredirect(True)

def run_command_async(command):
    try:
        ps_command = f"[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; {command}"
        result = subprocess.run(
            ['powershell.exe', '-NoProfile', '-Command', ps_command],
            capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW,
            encoding='utf-8', errors='replace'
        )
        output = result.stdout.strip()
        error = result.stderr.strip()
        if output:
            root.after(0, lambda: show_output_window(command, output))
        elif error:
            root.after(0, lambda: show_error_window(error))
        else:
            logger.info(f"Command '{command}' executed successfully (no output).")
    except Exception as e:
        root.after(0, lambda: (play_sound("error"), error_feedback(f"Could not execute: {command}")))

def execute_cmd(command):
    logger.info(f"Executing: {command}")
    try:
        os.startfile(command)
        return
    except Exception:
        pass
    threading.Thread(target=run_command_async, args=(command,), daemon=True).start()

def open_website(url):
    logger.info(f"Opening website: {url}")
    try:
        os.startfile(url)
    except Exception as e:
        play_sound("error")
        error_feedback(f"Could not open: {url}")

def handle_site_command(args_string):
    if not args_string:
        play_sound("error")
        error_feedback("Usage: site <name or url or search>")
        return
    website_input = args_string.strip()
    if website_input in LOCAL_WEBSITES:
        web_data = LOCAL_WEBSITES[website_input]
        open_website(web_data["url"] if isinstance(web_data, dict) else web_data)
    elif is_url(website_input):
        if not website_input.startswith(('http://', 'https://')):
            website_input = 'https://' + website_input
        open_website(website_input)
    else:
        open_website(f"https://www.google.com/search?q={website_input}")

def show_log_window():
    os.startfile('vita.log')

def shake_window_input(offset, turn_off):
    original_x = root.winfo_x()
    original_y = root.winfo_y()
    def shake_step(step):
        if step >= 5:
            root.geometry(f"+{original_x}+{original_y}")
            if turn_off:
                root.after(200, lambda: hide_window())
            return
        offset_x = random.randint(offset * -1, offset)
        offset_y = random.randint(offset * -1, offset)
        root.geometry(f"+{original_x + offset_x}+{original_y + offset_y}")
        root.after(15, lambda: shake_step(step + 1))
    shake_step(0)

def show_welcome_screen():
    welcome = ctk.CTkToplevel(root)
    welcome.title("Welcome")
    welcome.geometry("500x300")
    welcome.attributes('-topmost', True)
    welcome.attributes('-alpha', 0.8)
    welcome.overrideredirect(True)
    
    chromakey = style_manager.get("ui", "chromakey_color")
    welcome.configure(fg_color=chromakey)
    pywinstyles.set_opacity(welcome, color=chromakey, value=1)
    
    welcome.update_idletasks()
    wx = (welcome.winfo_screenwidth() // 2) - 250
    wy = (welcome.winfo_screenheight() // 2) - 150
    welcome.geometry(f"+{wx}+{wy}")
    
    inner_frame = ctk.CTkFrame(
        welcome,
        fg_color=style_manager.get("colors", "original", "entry_frame"),
        corner_radius=20,
        border_width=2,
        border_color=style_manager.get("colors", "original", "border")
    )
    inner_frame.pack(fill="both", expand=True, padx=15, pady=15)
    
    font_welcome_title = (style_manager.get("ui", "font_family") or "Segoe UI", 24, "bold")
    title_label = ctk.CTkLabel(inner_frame, text="Welcome to Vitan!",
                               font=font_welcome_title,
                               text_color=style_manager.get("colors", "original", "text_main"), fg_color="transparent")
    title_label.pack(pady=(40, 20))
    
    font_welcome_desc = (style_manager.get("ui", "font_family") or "Segoe UI", 14)
    desc_label = ctk.CTkLabel(inner_frame, text="Your fast command launcher,\nPress Alt+V to open anytime.",
                              font=font_welcome_desc,
                              text_color=style_manager.get("colors", "original", "text_match"), fg_color="transparent",
                              justify="center")
    desc_label.pack(pady=10, padx=20)
    
    font_btn = (style_manager.get("ui", "font_family") or "Segoe UI", 14)
    close_btn = ctk.CTkButton(inner_frame, text="Close",
                              font=font_btn,
                              fg_color=style_manager.get("colors", "original", "text_main"), text_color=style_manager.get("ui", "chromakey_color"),
                              hover_color=style_manager.get("colors", "original", "text_match"),
                              corner_radius=10,
                              width=120, height=35,
                              command=welcome.destroy)
    close_btn.pack(side="bottom", pady=30)
    
    welcome.bind("<Escape>", lambda e: welcome.destroy())

def show_settings_window():
    settings_window = ctk.CTkToplevel(root)
    settings_window.title("Settings")
    settings_window.geometry("600x700")
    settings_window.attributes('-topmost', True)
    settings_window.attributes('-alpha', 0.95)
    settings_window.overrideredirect(True)
    
    chromakey = style_manager.get("ui", "chromakey_color")
    settings_window.configure(fg_color=chromakey)
    pywinstyles.set_opacity(settings_window, color=chromakey, value=1)

    drag_handle = ctk.CTkFrame(settings_window, fg_color='transparent', 
                                   width=20, height=20, corner_radius=100)
    drag_handle.pack(side="right", anchor="n", padx=10, pady=0)
    drag_handle.pack_propagate(False)

    drag_handle.bind("<Button-1>", start_drag)
    drag_handle.bind("<B1-Motion>", do_drag)
    drag_handle.bind("<ButtonRelease-1>", stop_drag)
    
    inner = ctk.CTkFrame(settings_window, fg_color=style_manager.get("colors", "original", "entry_frame"), corner_radius=12, border_width=2, border_color=style_manager.get("colors", "original", "border"))
    inner.pack(fill="both", expand=True, padx=10, pady=10)
    
    font_title = (style_manager.get("ui", "font_family") or "Segoe UI", 20, "bold")
    title = ctk.CTkLabel(inner, text="⚙ Settings", font=font_title, text_color=style_manager.get("colors", "original", "text_main"))
    title.pack(pady=10)
    
    tabview = ctk.CTkTabview(inner, fg_color="transparent", segmented_button_fg_color=style_manager.get("colors", "original", "hint_frame"), segmented_button_selected_color=style_manager.get("colors", "original", "text_main"), text_color=style_manager.get("colors", "original", "text_main"))
    tabview.pack(fill="both", expand=True, padx=10, pady=10)
    
    tab_ui = tabview.add("UI")
    tab_sounds = tabview.add("Sounds")
    tab_colors = tabview.add("Colors")
    
    scroll_ui = ctk.CTkScrollableFrame(tab_ui, fg_color="transparent")
    scroll_ui.pack(fill="both", expand=True)
    
    ui_keys = ["min_width", "min_height", "max_hints", "window_y", "alpha", "chromakey_color", "font_family", "font_size_main", "font_size_hint", "font_size_output", "font_size_log", "default_hint", "volume"]
    ui_entries = {}
    
    for key in ui_keys:
        row = ctk.CTkFrame(scroll_ui, fg_color="transparent")
        row.pack(fill="x", pady=5)
        
        lbl = ctk.CTkLabel(row, text=f"{key.replace('_', ' ').title()}:", width=120, anchor="w", text_color=style_manager.get("colors", "original", "text_main"))
        lbl.pack(side="left", padx=5)
        
        ent = ctk.CTkEntry(row, width=200)
        current_val = style_manager.get("ui", key)
        ent.insert(0, str(current_val) if current_val is not None else "")
        ent.pack(side="left", padx=5)
        ui_entries[key] = ent

    scroll_sounds = ctk.CTkScrollableFrame(tab_sounds, fg_color="transparent")
    scroll_sounds.pack(fill="both", expand=True)
    
    sound_actions = style_manager.get("sounds")
    sound_entries = {}
    
    for action, current_sound in (sound_actions or {}).items():
        row = ctk.CTkFrame(scroll_sounds, fg_color="transparent")
        row.pack(fill="x", pady=5)
        
        lbl = ctk.CTkLabel(row, text=f"{action.capitalize()}:", width=100, anchor="w", text_color=style_manager.get("colors", "original", "text_main"))
        lbl.pack(side="left", padx=5)
        
        ent = ctk.CTkEntry(row, width=280)
        ent.insert(0, current_sound)
        ent.pack(side="left", padx=5)
        sound_entries[action] = ent
        
        def make_browse(act, entry_widget):
            def browse():
                file = fd.askopenfilename(filetypes=[("Audio files", "*.wav *.mp3 *.ogg")])
                if file:
                    entry_widget.delete(0, ctk.END)
                    entry_widget.insert(0, file)
            return browse
            
        btn = ctk.CTkButton(row, text="...", width=30, command=make_browse(action, ent))
        btn.pack(side="left", padx=5)

    scroll_colors = ctk.CTkScrollableFrame(tab_colors, fg_color="transparent")
    scroll_colors.pack(fill="both", expand=True)
    
    color_entries = {}
    original_colors = style_manager.get("colors", "original")
    
    for color_key, current_hex in (original_colors or {}).items():
        row = ctk.CTkFrame(scroll_colors, fg_color="transparent")
        row.pack(fill="x", pady=5)
        
        display_name = color_key.replace("_", " ").title()
        
        lbl = ctk.CTkLabel(row, text=f"{display_name}:", width=120, anchor="w", text_color=style_manager.get("colors", "original", "text_main"))
        lbl.pack(side="left", padx=5)
        
        ent = ctk.CTkEntry(row, width=100)
        ent.insert(0, current_hex)
        ent.pack(side="left", padx=5)
        color_entries[color_key] = ent
        
        preview = ctk.CTkFrame(row, width=20, height=20, fg_color=current_hex, corner_radius=4)
        preview.pack(side="left", padx=5)
        
        def make_color_picker(key, entry_widget, preview_widget):
            def pick():
                color = colorchooser.askcolor(initialcolor=entry_widget.get(), title=f"Choose {key}")[1]
                if color:
                    entry_widget.delete(0, ctk.END)
                    entry_widget.insert(0, color)
                    preview_widget.configure(fg_color=color)
            return pick
            
        btn = ctk.CTkButton(row, text="🎨", width=40, command=make_color_picker(color_key, ent, preview))
        btn.pack(side="left", padx=5)

    btn_frame = ctk.CTkFrame(inner, fg_color="transparent")
    btn_frame.pack(fill="x", pady=10)
    
    def save_settings():
        for key, ent in ui_entries.items():
            val = ent.get().strip()
            if key in ["min_width", "min_height", "max_hints", "window_y", "font_size_main", "font_size_hint", "font_size_output", "font_size_log"]:
                try:
                    val = int(val)
                except ValueError:
                    pass
            elif key in ["alpha", "volume"]:
                try:
                    val = float(val)
                except ValueError:
                    pass
            style_manager.set("ui", key, value=val)
            
        for action, ent in sound_entries.items():
            style_manager.set("sounds", action, value=ent.get().strip())
        for color_key, ent in color_entries.items():
            style_manager.set("colors", "original", color_key, value=ent.get().strip())
        
        apply_colors("original")
        root.geometry(f"{MIN_WIDTH}x{MIN_HEIGHT}")
        play_sound("enter")
        settings_window.destroy()

    def reset_settings():
        style_manager.reset_to_defaults()
        play_sound("enter")
        apply_colors("original")
        root.geometry(f"{MIN_WIDTH}x{MIN_HEIGHT}")
        settings_window.destroy()
    
    font_btn = (style_manager.get("ui", "font_family") or "Segoe UI", 14)
    save_btn = ctk.CTkButton(btn_frame, text="Save & Apply", font=font_btn, command=save_settings, fg_color=style_manager.get("colors", "original", "text_match"), text_color=style_manager.get("colors", "original", "drag_label"))
    save_btn.pack(side="left", expand=True, padx=10)
    
    reset_btn = ctk.CTkButton(btn_frame, text="Reset to Default", font=font_btn, command=reset_settings, fg_color=style_manager.get("colors", "red", "text_main"), text_color="#ffffff")
    reset_btn.pack(side="right", expand=True, padx=10)
    
    settings_window.update_idletasks()
    wx = (settings_window.winfo_screenwidth() // 2) - 300
    wy = (settings_window.winfo_screenheight() // 2) - 350
    settings_window.geometry(f"+{wx}+{wy}")
    settings_window.bind("<Escape>", lambda e: settings_window.destroy())

def show_editor_window():
    editor_window = ctk.CTkToplevel(root)
    editor_window.title("Editor")
    editor_window.geometry("700x600")
    editor_window.attributes('-topmost', True)
    editor_window.attributes('-alpha', 0.95)
    editor_window.overrideredirect(True)
    
    chromakey = style_manager.get("ui", "chromakey_color")
    editor_window.configure(fg_color=chromakey)
    pywinstyles.set_opacity(editor_window, color=chromakey, value=1)
    
    inner = ctk.CTkFrame(editor_window, fg_color=style_manager.get("colors", "original", "entry_frame"), corner_radius=12, border_width=2, border_color=style_manager.get("colors", "original", "border"))
    inner.pack(fill="both", expand=True, padx=10, pady=10)
    
    font_title = (style_manager.get("ui", "font_family") or "Segoe UI", 20, "bold")
    title = ctk.CTkLabel(inner, text="📝 Editor", font=font_title, text_color=style_manager.get("colors", "original", "text_main"))
    title.pack(pady=10)
    
    tabview = ctk.CTkTabview(inner, fg_color="transparent", segmented_button_fg_color=style_manager.get("colors", "original", "hint_frame"), segmented_button_selected_color=style_manager.get("colors", "original", "text_main"), text_color=style_manager.get("colors", "original", "text_main"))
    tabview.pack(fill="both", expand=True, padx=10, pady=10)
    
    tab_cmds = tabview.add("Commands")
    tab_sites = tabview.add("Websites")
    
    font_editor = (style_manager.get("ui", "font_family") or "Consolas", 12)
    
    txt_cmds = ctk.CTkTextbox(tab_cmds, font=font_editor, wrap="none", fg_color=style_manager.get("ui", "chromakey_color"), text_color=style_manager.get("colors", "original", "text_main"))
    txt_cmds.pack(fill="both", expand=True, padx=5, pady=5)
    txt_cmds.insert("1.0", json.dumps(LOCAL_COMMANDS, indent=4, ensure_ascii=False))
    
    txt_sites = ctk.CTkTextbox(tab_sites, font=font_editor, wrap="none", fg_color=style_manager.get("ui", "chromakey_color"), text_color=style_manager.get("colors", "original", "text_main"))
    txt_sites.pack(fill="both", expand=True, padx=5, pady=5)
    txt_sites.insert("1.0", json.dumps(LOCAL_WEBSITES, indent=4, ensure_ascii=False))
    
    btn_frame = ctk.CTkFrame(inner, fg_color="transparent")
    btn_frame.pack(fill="x", pady=10)
    
    def save_editor():
        try:
            new_cmds = json.loads(txt_cmds.get("1.0", "end"))
            save_commands(new_cmds)
            global LOCAL_COMMANDS
            LOCAL_COMMANDS = new_cmds
        except json.JSONDecodeError as e:
            show_error_window(f"Invalid JSON in Commands:\n{e}")
            return
            
        try:
            new_sites = json.loads(txt_sites.get("1.0", "end"))
            save_websites(new_sites)
            global LOCAL_WEBSITES
            LOCAL_WEBSITES = new_sites
        except json.JSONDecodeError as e:
            show_error_window(f"Invalid JSON in Websites:\n{e}")
            return
            
        play_sound("enter")
        editor_window.destroy()
        update_hint()
    
    font_btn = (style_manager.get("ui", "font_family") or "Segoe UI", 14)
    save_btn = ctk.CTkButton(btn_frame, text="Save & Reload", font=font_btn, command=save_editor, fg_color=style_manager.get("colors", "original", "text_match"), text_color=style_manager.get("colors", "original", "drag_label"))
    save_btn.pack(side="left", expand=True, padx=10)
    
    cancel_btn = ctk.CTkButton(btn_frame, text="Cancel", font=font_btn, command=editor_window.destroy, fg_color=style_manager.get("colors", "red", "text_main"), text_color="#ffffff")
    cancel_btn.pack(side="right", expand=True, padx=10)
    
    editor_window.update_idletasks()
    wx = (editor_window.winfo_screenwidth() // 2) - 350
    wy = (editor_window.winfo_screenheight() // 2) - 300
    editor_window.geometry(f"+{wx}+{wy}")
    editor_window.bind("<Escape>", lambda e: editor_window.destroy())

def navigate_hints(direction):
    global selected_hint_index
    if not current_matches:
        return
    
    if direction == "down":
        selected_hint_index = min(len(current_matches) - 1, selected_hint_index + 1)
    elif direction == "up":
        selected_hint_index = max(-1, selected_hint_index - 1)
        
    update_hint(force_rebuild=True)

def update_hint(event=None, force_rebuild=False):
    global previous_text, current_matches, selected_hint_index
    
    if event and event.keysym in ('Return', 'Escape', 'Tab', 'Up', 'Down'):
        if event.keysym == 'Up':
            navigate_hints("up")
            return "break"
        elif event.keysym == 'Down':
            navigate_hints("down")
            return "break"
        return

    current_text = entry.get()
    if current_text != previous_text or force_rebuild:
        if not force_rebuild:
            shake_window_input(1, False)
            play_sound("input")
        previous_text = current_text
    
    for frame in hint_frames:
        frame.destroy()
    hint_frames.clear()
    
    current_text_stripped = current_text.strip().lower()
    if not current_text_stripped:
        hint_label.configure(text=DEFAULT_HINT)
        selected_hint_index = -1
        current_matches = []
        root.geometry(f"{MIN_WIDTH}x{MIN_HEIGHT}")
        return
        
    parts = current_text_stripped.split(maxsplit=1)
    cmd_name = parts[0]
    args_string = parts[1] if len(parts) > 1 else ""
    
    matches = []
    for name, desc in BUILTIN_COMMANDS.items():
        if name.startswith(cmd_name):
            matches.append((name, f"💡 {name} - {desc}", name == cmd_name))
    for name, data in LOCAL_COMMANDS.items():
        if name.lower().startswith(cmd_name):
            full_text, is_full = format_hint(name, data, cmd_name, icon="💡")
            matches.append((name, full_text, is_full))
    for name, data in LOCAL_WEBSITES.items():
        if name.lower().startswith(cmd_name):
            full_text, is_full = format_hint(name, data, cmd_name, icon="🌐")
            matches.append((name, full_text, is_full))
            
    current_matches = matches
            
    colors = style_manager.get("colors", "original")
    font_family = style_manager.get("ui", "font_family") or "Segoe UI"
    font_size_hint = style_manager.get("ui", "font_size_hint") or 14
            
    if matches:
        if selected_hint_index >= len(matches):
            selected_hint_index = len(matches) - 1
            
        for i, (name, full_text, is_full_match) in enumerate(matches[:MAX_HINTS]):
            is_website = name in LOCAL_WEBSITES
            current_icon = "🌐" if is_website else "💡"
            is_selected = (i == selected_hint_index)
            
            if is_full_match and args_string and not is_selected:
                frame = ctk.CTkFrame(root, fg_color="transparent")
                frame.pack(anchor="w", padx=15, pady=2)
                hint_frames.append(frame)
                lbl1 = ctk.CTkLabel(frame, text=f"{current_icon} {name} {args_string}", font=(font_family, 10), text_color=colors["text_main"])
                lbl1.role = "main"
                lbl1.pack(side="left")
                desc_start = full_text.find(" - ")
                if desc_start != -1:
                    lbl2 = ctk.CTkLabel(frame, text=full_text[desc_start:], font=(font_family, 10), text_color=colors["text_secondary"])
                    lbl2.role = "secondary"
                    lbl2.pack(side="left")
            else:
                frame = create_colored_hint(hint_frame, name, cmd_name, full_text, icon=current_icon, is_selected=is_selected)
                hint_frames.append(frame)
                
        root.update_idletasks()
        req_height = root.winfo_reqheight()
        safe_height = MIN_HEIGHT + (len(hint_frames) * 35)
        new_height = max(MIN_HEIGHT, req_height, safe_height)
        root.geometry(f"{MIN_WIDTH}x{new_height}")
    else:
        hint_label.configure(text="No matches found")
        selected_hint_index = -1
        root.geometry(f"{MIN_WIDTH}x{MIN_HEIGHT}")

def autocomplete(event=None):
    current_text = entry.get().strip().lower()
    if not current_text:
        return
    for name in list(LOCAL_COMMANDS.keys()) + list(LOCAL_WEBSITES.keys()):
        if name.lower().startswith(current_text) and name.lower() != current_text:
            entry.delete(0, ctk.END)
            entry.insert(0, name)
            update_hint()
            return "break"

def process_command(event=None):
    global selected_hint_index
    user_input = entry.get().strip()
    if not user_input:
        smooth_hide()
        return
        
    if selected_hint_index >= 0 and selected_hint_index < len(current_matches):
        cmd_to_execute = current_matches[selected_hint_index][0]
        entry.delete(0, ctk.END)
        entry.insert(0, cmd_to_execute)
        user_input = cmd_to_execute
        
    lower_input = user_input.lower()
    if lower_input in ["quit", "exit"]:
        return quit_app()
    if lower_input == "list":
        play_sound("enter")
        flash_green()
        shake_window_input(10, True)
        with open(COMMANDS_LIST_FILE, "w", encoding="utf-8") as f:
            f.write("=== VITAN COMMANDS ===\n\n")
            for name, data in LOCAL_COMMANDS.items():
                if isinstance(data, dict):
                    attrs = data.get("attributes", [])
                    desc = data.get("description", "No description")
                    attr_str = " {" + ", ".join(attrs) + "}" if attrs else ""
                    f.write(f"{name}{attr_str} - {desc}\n")
                else:
                    f.write(f"{name} - {data}\n")
        os.startfile(COMMANDS_LIST_FILE)
        return
    if lower_input == "log":
        play_sound("enter")
        flash_green()
        shake_window_input(10, True)
        show_log_window()
        return
    if lower_input == "style":
        play_sound("enter")
        flash_green()
        shake_window_input(10, True)
        show_settings_window()
        return
    if lower_input == "edit":
        play_sound("enter")
        flash_green()
        shake_window_input(10, True)
        show_editor_window()
        return
        
    parts = user_input.split(maxsplit=1)
    cmd_name = parts[0].lower()
    args_string = parts[1] if len(parts) > 1 else ""
    
    if cmd_name == "site":
        play_sound("enter")
        flash_green()
        shake_window_input(10, True)
        handle_site_command(args_string)
        return
    if cmd_name in LOCAL_COMMANDS:
        play_sound("enter")
        flash_green()
        shake_window_input(10, True)
        cmd_data = LOCAL_COMMANDS[cmd_name]
        if isinstance(cmd_data, dict):
            command_template = cmd_data["command"]
            attributes = cmd_data.get("attributes", [])
            if not attributes:
                execute_cmd(command_template)
            else:
                user_args = [args_string.strip()] if len(attributes) == 1 else args_string.split()
                if len(user_args) < len(attributes):
                    play_sound("error")
                    error_feedback(f"Usage: {cmd_name} {' '.join([f'<{a}>' for a in attributes])}")
                    return
                final_command = command_template
                for i, attr in enumerate(attributes):
                    final_command = final_command.replace("{" + attr + "}", user_args[i])
                execute_cmd(final_command)
        else:
            execute_cmd(cmd_data)
        return
    if cmd_name in LOCAL_WEBSITES:
        play_sound("enter")
        flash_green()
        shake_window_input(10, True)
        web_data = LOCAL_WEBSITES[cmd_name]
        if isinstance(web_data, dict):
            url_template = web_data["url"]
            attributes = web_data.get("attributes", [])
            if not attributes:
                open_website(url_template)
            else:
                user_args = [args_string.strip()] if len(attributes) == 1 else args_string.split()
                if len(user_args) < len(attributes):
                    play_sound("error")
                    error_feedback(f"Usage: {cmd_name} {' '.join([f'<{a}>' for a in attributes])}")
                    return
                final_url = url_template
                for i, attr in enumerate(attributes):
                    final_url = final_url.replace("{" + attr + "}", user_args[i])
                open_website(final_url)
        else:
            open_website(web_data)
        return
    
    play_sound("unknow_command")
    flash_red()
    error_feedback(f"Unknown command: {user_input}")

entry.bind("<KeyRelease>", update_hint)
entry.bind("<Tab>", autocomplete)
entry.bind("<Return>", process_command)
entry.bind("<Escape>", lambda e: hide_window())

def on_hotkey_triggered():
    root.after(0, force_focus)

hotkey_listener = pynput_keyboard.GlobalHotKeys({
    '<alt>+v': on_hotkey_triggered,
    '<alt>+м': on_hotkey_triggered,
    '<ctrl>+<alt>+q': quit_app,
    '<ctrl>+<alt>+й': quit_app
})
hotkey_listener.daemon = True
hotkey_listener.start()

logger.info("Running. Alt+V to open. Ctrl+Alt+Q to quit.")

show_welcome_screen()

try:
    root.mainloop()
except KeyboardInterrupt:
    hotkey_listener.stop()

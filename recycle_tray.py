import os
import sys
import ctypes
import subprocess
import winsound
import threading
import json
import tkinter.messagebox
import winreg
import time
import requests

import customtkinter as ctk
from pystray import Icon, MenuItem, Menu
from PIL import Image, ImageDraw

APP_NAME = "RecycleBinCleaner"
SETTINGS_PATH = os.path.join(os.getenv("APPDATA"), APP_NAME, "settings.json")
CURRENT_VERSION = "1.0"

def load_settings():
    default = {
        "autostart": True,
        "sound": True,
        "theme": "light",
        "check_updates": True
    }
    try:
        with open(SETTINGS_PATH, "r") as f:
            data = json.load(f)
        return {**default, **data}
    except Exception:
        return default

def save_settings(settings):
    os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
    with open(SETTINGS_PATH, "w") as f:
        json.dump(settings, f, indent=4)

settings = load_settings()

def add_to_startup(enable):
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                             r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE)
        exe_path = os.path.abspath(sys.executable if getattr(sys, 'frozen', False) else __file__)
        if enable:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, exe_path)
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass
        key.Close()
    except Exception as e:
        print(f"Failed to modify startup: {e}")

add_to_startup(settings.get("autostart", True))

def create_image(color_bg, color_fg):
    image = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
    dc = ImageDraw.Draw(image)
    dc.ellipse((4, 4, 60, 60), fill=color_bg)
    dc.text((22, 14), 'R', fill=color_fg)
    return image

def empty_recycle_bin(icon, item):
    SHEmptyRecycleBin = ctypes.windll.shell32.SHEmptyRecycleBinW
    SHEmptyRecycleBin(None, None, 0x00000001 | 0x00000002 | 0x00000004)
    if settings.get("sound", True):
        winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)

def open_recycle_bin(icon, item):
    subprocess.Popen('explorer.exe shell:RecycleBinFolder')

def show_about(icon, item):
    def show():
        ctk.set_appearance_mode(settings.get("theme", "light"))
        root = ctk.CTk()
        root.withdraw()
        tkinter.messagebox.showinfo("About", "Special version 1.0 by SurN\n© 2025 copyright")
        root.destroy()
    threading.Thread(target=show).start()

class UpdateWindow:
    def __init__(self, latest_version, download_url):
        self.latest_version = latest_version
        self.download_url = download_url
        self.root = None

    def show(self):
        ctk.set_appearance_mode(settings.get("theme", "light"))
        self.root = ctk.CTk()
        self.root.title("Update Available")
        self.root.geometry("400x180")
        self.root.resizable(False, False)

        frame = ctk.CTkFrame(self.root, corner_radius=10)
        frame.pack(padx=20, pady=20, fill="both", expand=True)

        label = ctk.CTkLabel(frame, text=f"New version {self.latest_version} is available!", font=ctk.CTkFont(size=16, weight="bold"))
        label.pack(pady=(0,10))

        desc = ctk.CTkLabel(frame, text="Do you want to open the download page to update?", wraplength=360)
        desc.pack(pady=(0,20))

        btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btn_frame.pack(fill="x", pady=(0,10))

        def on_ok():
            import webbrowser
            webbrowser.open(self.download_url)
            self.root.destroy()

        def on_cancel():
            self.root.destroy()

        btn_ok = ctk.CTkButton(btn_frame, text="OK", width=80, command=on_ok)
        btn_ok.pack(side="left", padx=(0,10))

        btn_cancel = ctk.CTkButton(btn_frame, text="Cancel", width=80, command=on_cancel)
        btn_cancel.pack(side="left")

        self.root.mainloop()

def check_for_updates(show_window_if_update=True):
    if not settings.get("check_updates", True):
        return
    try:
        url = "https://api.github.com/repos/Artur8-00/RecycleBinCleaner/releases/latest"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            latest_version = data["tag_name"].lstrip("v")
            download_url = data["assets"][0]["browser_download_url"] if data["assets"] else data["html_url"]
            if latest_version > CURRENT_VERSION:
                if show_window_if_update:
                    update_win = UpdateWindow(latest_version, download_url)
                    update_win.show()
                else:
                    
                    pass
    except Exception as e:
        print(f"Update check failed: {e}")

class SettingsWindow:
    def __init__(self, icon_wrapper):
        self.root = None
        self.icon_wrapper = icon_wrapper
        self.opening_lock = threading.Lock()

    def open(self):
        if self.root and self.root.winfo_exists():
            self.root.deiconify()
            self.root.lift()
            return
        if not self.opening_lock.acquire(blocking=False):
            return
        try:
            ctk.set_appearance_mode(settings.get("theme", "light"))
            self.root = ctk.CTk()
            self.root.title("Settings")
            self.root.geometry("360x360")
            self.root.resizable(False, False)

            self.autostart_var = ctk.BooleanVar(value=settings.get("autostart", True))
            self.sound_var = ctk.BooleanVar(value=settings.get("sound", True))
            self.theme_var = ctk.StringVar(value=settings.get("theme", "light"))
            self.check_updates_var = ctk.BooleanVar(value=settings.get("check_updates", True))

            def make_checkbox_row(parent, label_text, var):
                frame = ctk.CTkFrame(parent, fg_color="transparent")
                frame.pack(fill="x", padx=20, pady=8)
                lbl = ctk.CTkLabel(frame, text=label_text)
                lbl.pack(side="left")
                on_off = ctk.CTkLabel(frame, text="ON" if var.get() else "OFF", width=40, anchor="e")
                on_off.pack(side="right")
                def on_var_change(*args):
                    on_off.configure(text="ON" if var.get() else "OFF")
                var.trace_add("write", on_var_change)
                cbox = ctk.CTkCheckBox(frame, variable=var, text="")
                cbox.pack(side="right", padx=5)
                return frame

            self.autostart_row = make_checkbox_row(self.root, "Autostart with Windows", self.autostart_var)
            self.sound_row = make_checkbox_row(self.root, "Sound on Empty Recycle Bin", self.sound_var)
            self.check_updates_row = make_checkbox_row(self.root, "Check for updates automatically", self.check_updates_var)

            ctk.CTkLabel(self.root, text="Theme").pack(anchor="w", padx=20, pady=(15,5))
            ctk.CTkRadioButton(self.root, text="Light", variable=self.theme_var, value="light").pack(anchor="w", padx=40)
            ctk.CTkRadioButton(self.root, text="Dark", variable=self.theme_var, value="dark").pack(anchor="w", padx=40)

            btn_check = ctk.CTkButton(self.root, text="Check for updates now", command=self.check_updates_now)
            btn_check.pack(pady=(20, 5))

            btn_restore = ctk.CTkButton(self.root, text="Restore Defaults", command=self.restore_defaults)
            btn_restore.pack(pady=5)

            btn_save = ctk.CTkButton(self.root, text="Save Changes", command=self.save)
            btn_save.pack(pady=10)

            self.root.protocol("WM_DELETE_WINDOW", self.on_close)
            self.root.mainloop()
        finally:
            self.opening_lock.release()

    def restore_defaults(self):
        self.autostart_var.set(True)
        self.sound_var.set(True)
        self.theme_var.set("light")
        self.check_updates_var.set(True)

    def save(self):
        global settings
        settings = {
            "autostart": self.autostart_var.get(),
            "sound": self.sound_var.get(),
            "theme": self.theme_var.get(),
            "check_updates": self.check_updates_var.get()
        }
        save_settings(settings)
        add_to_startup(settings["autostart"])
        tkinter.messagebox.showinfo("Settings", "Settings saved successfully.\nPlease restart the app to apply changes.")
        self.root.withdraw()

    def on_close(self):
        self.root.withdraw()

    def check_updates_now(self):
        threading.Thread(target=lambda: check_for_updates(show_window_if_update=True), daemon=True).start()

class TrayIcon:
    def __init__(self):
        self.icon = None
        self.menu = Menu(
            MenuItem("Empty Recycle Bin", empty_recycle_bin),
            MenuItem("Open Recycle Bin", open_recycle_bin),
            MenuItem("Settings", self.open_settings),
            MenuItem("About", show_about),
            MenuItem("Exit", self.quit_app)
        )
        self.current_theme = settings.get("theme", "light")
        self.create_icon(self.current_theme)
        self.settings_window = SettingsWindow(self)
        self.icon_thread = None

    def create_icon(self, theme):
        if theme == "dark":
            img = create_image("#212121", "white")
        else:
            img = create_image("#2196F3", "white")
        self.icon = Icon(APP_NAME, img, APP_NAME, menu=self.menu)

    def open_settings(self, icon=None, item=None):
        threading.Thread(target=self.settings_window.open, daemon=True).start()

    def quit_app(self, icon=None, item=None):
        if self.icon:
            try:
                self.icon.visible = False
                self.icon.stop()
            except:
                pass
        os._exit(0)

    def run(self):
        self.icon_thread = threading.Thread(target=self.icon.run, daemon=True)
        self.icon_thread.start()
        try:
            while True:
                time.sleep(0.5)
        except KeyboardInterrupt:
            self.quit_app()

def main():
    ctk.set_appearance_mode(settings.get("theme", "light"))
    
    threading.Thread(target=lambda: check_for_updates(show_window_if_update=True), daemon=True).start()
    tray = TrayIcon()
    tray.run()

if __name__ == '__main__':
    main()

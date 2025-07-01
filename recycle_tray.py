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

import customtkinter as ctk
from pystray import Icon, MenuItem, Menu
from PIL import Image, ImageDraw

APP_NAME = "RecycleBinCleaner"
SETTINGS_PATH = os.path.join(os.getenv("APPDATA"), APP_NAME, "settings.json")

# --- Работа с настройками ---
def load_settings():
    default = {
        "autostart": True,
        "sound": True,
        "theme": "light"
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

# Применяем автозапуск при старте
add_to_startup(settings.get("autostart", True))

# --- Создание иконок для трея ---
def create_image(color_bg, color_fg):
    image = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
    dc = ImageDraw.Draw(image)
    dc.ellipse((4, 4, 60, 60), fill=color_bg)
    dc.text((22, 14), 'R', fill=color_fg)
    return image

# --- Функции трея ---
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

# --- Окно настроек ---
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
            self.root.geometry("350x320")
            self.root.resizable(False, False)

            self.autostart_var = ctk.BooleanVar(value=settings.get("autostart", True))
            self.sound_var = ctk.BooleanVar(value=settings.get("sound", True))
            self.theme_var = ctk.StringVar(value=settings.get("theme", "light"))

            ctk.CTkLabel(self.root, text="Autostart with Windows").pack(anchor="w", padx=20, pady=(20,5))
            ctk.CTkCheckBox(self.root, variable=self.autostart_var).pack(anchor="w", padx=40)

            ctk.CTkLabel(self.root, text="Sound on Empty Recycle Bin").pack(anchor="w", padx=20, pady=5)
            ctk.CTkCheckBox(self.root, variable=self.sound_var).pack(anchor="w", padx=40)

            ctk.CTkLabel(self.root, text="Theme").pack(anchor="w", padx=20, pady=5)
            ctk.CTkRadioButton(self.root, text="Light", variable=self.theme_var, value="light").pack(anchor="w", padx=40)
            ctk.CTkRadioButton(self.root, text="Dark", variable=self.theme_var, value="dark").pack(anchor="w", padx=40)

            ctk.CTkButton(self.root, text="Restore Defaults", command=self.restore_defaults).pack(pady=(10, 5))
            ctk.CTkButton(self.root, text="Save Settings", command=self.save).pack(pady=(5, 20))

            self.root.protocol("WM_DELETE_WINDOW", self.on_close)

            self.root.mainloop()
        finally:
            self.opening_lock.release()

    def restore_defaults(self):
        self.autostart_var.set(True)
        self.sound_var.set(True)
        self.theme_var.set("light")

    def save(self):
        global settings
        settings = {
            "autostart": self.autostart_var.get(),
            "sound": self.sound_var.get(),
            "theme": self.theme_var.get()
        }
        save_settings(settings)
        add_to_startup(settings["autostart"])
        tkinter.messagebox.showinfo("Settings", "Settings saved successfully.\nPlease restart the app to apply changes.")
        self.root.withdraw()

    def on_close(self):
        self.root.withdraw()

# --- Управление tray-иконкой ---
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
    ctk.set_appearance_mode(settings.get("theme", "light"))  # применяем тему при старте
    tray = TrayIcon()
    tray.run()

if __name__ == '__main__':
    main()

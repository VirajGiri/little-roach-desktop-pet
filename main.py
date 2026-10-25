"""A tiny, offline-first Windows desktop cockroach pet."""

from __future__ import annotations

import json
import math
import os
import random
import sys
import tkinter as tk
from dataclasses import asdict
from pathlib import Path
from tkinter import messagebox, ttk

from pet_core import PetSettings, choose_target, settings_path

try:
    import winreg
except ImportError:  # pragma: no cover - Windows-only integration
    winreg = None


KEY_COLOR = "#ff00ff"
PET_W, PET_H = 171, 114
SPRITE_SOURCE_SUBSAMPLE = 9
SPRITE_SUBSAMPLE = 10
APP_NAME = "Little Roach"


def load_settings() -> PetSettings:
    path = settings_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return PetSettings.from_dict(data)
    except (OSError, ValueError, TypeError):
        return PetSettings()


def save_settings(settings: PetSettings) -> None:
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(settings), indent=2), encoding="utf-8")


def set_startup(enabled: bool) -> None:
    if winreg is None:
        raise OSError("Windows startup settings are only available on Windows.")
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            executable = sys.executable
            if not getattr(sys, "frozen", False):
                pythonw = str(Path(executable).with_name("pythonw.exe"))
                if Path(pythonw).exists():
                    executable = pythonw
            command = f'"{executable}"' if getattr(sys, "frozen", False) else f'"{executable}" "{Path(__file__).resolve()}"'
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, command)
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass


class CockroachPet:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.settings = load_settings()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg=KEY_COLOR)
        try:
            self.root.wm_attributes("-transparentcolor", KEY_COLOR)
        except tk.TclError:
            # On unusual Windows themes, retain a clean magenta key background.
            pass
        self.canvas = tk.Canvas(self.root, width=PET_W, height=PET_H, bg=KEY_COLOR,
                                highlightthickness=0, bd=0)
        self.canvas.pack()
        bundle_dir = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
        asset_dir = bundle_dir / "assets"
        self.sprite_sources = {
            "right": tk.PhotoImage(file=str(asset_dir / "roach_nymph_right.png")).subsample(
                SPRITE_SOURCE_SUBSAMPLE, SPRITE_SOURCE_SUBSAMPLE
            ),
            "left": tk.PhotoImage(file=str(asset_dir / "roach_nymph_left.png")).subsample(
                SPRITE_SOURCE_SUBSAMPLE, SPRITE_SOURCE_SUBSAMPLE
            ),
        }
        self.sprite_cache: dict[tuple[str, int], tk.PhotoImage] = {}
        self.facing = "right"
        self.root.geometry(self._geometry(int(PET_W*self.settings.scale), int(PET_H*self.settings.scale), self._start_x(), self._start_y()))
        # Keep the entire drawing visible even if the window manager reports a
        # smaller default size for this borderless top-level window.
        self.root.minsize(int(PET_W*self.settings.scale), int(PET_H*self.settings.scale))
        self.root.lift()
        self.root.attributes("-topmost", True)
        self.root.bind("<Button-1>", self._press)
        self.root.bind("<B1-Motion>", self._drag)
        self.root.bind("<ButtonRelease-1>", self._release)
        self.root.bind("<Double-Button-1>", self._startle)
        self.root.bind("<Button-3>", self._show_menu)
        self.root.bind("<Escape>", lambda _event: self.root.destroy())
        self.menu = tk.Menu(self.root, tearoff=False)
        self.menu.add_command(label="Startle (make it scurry)", command=self._startle)
        self.menu.add_command(label="Settings…", command=self._open_settings)
        self.menu.add_command(label="Pause wandering", command=self._toggle_pause)
        self.menu.add_separator()
        self.menu.add_command(label="Quit", command=self.root.destroy)
        self.paused = False
        self.dragging = False
        self.drag_offset = (0, 0)
        self.target = (self.root.winfo_x(), self.root.winfo_y())
        self.rest_until: int | None = None
        self.move_speed = self.settings.speed * 1.6
        self.burst_steps = 0
        self.moving = False
        self.frame = 0
        self.root.after(80, self._tick)

    def _start_x(self) -> int:
        if sys.platform == "win32":
            import ctypes
            width = ctypes.windll.user32.GetSystemMetrics(0)
        else:
            width = 1920
        return (width - int(PET_W*self.settings.scale)) // 2

    def _start_y(self) -> int:
        if sys.platform == "win32":
            import ctypes
            height = ctypes.windll.user32.GetSystemMetrics(1)
        else:
            height = 1080
        return (height - int(PET_H*self.settings.scale)) // 2

    @staticmethod
    def _geometry(width: int, height: int, x: int, y: int) -> str:
        return f"{width}x{height}{x:+d}{y:+d}"

    @staticmethod
    def _virtual_screen() -> tuple[int, int, int, int]:
        if sys.platform == "win32":
            import ctypes
            user32 = ctypes.windll.user32
            return (user32.GetSystemMetrics(76), user32.GetSystemMetrics(77),
                    user32.GetSystemMetrics(78), user32.GetSystemMetrics(79))
        return (0, 0, 1920, 1080)

    def _press(self, event: tk.Event) -> None:
        self.dragging = False
        self.drag_offset = (event.x_root - self.root.winfo_x(), event.y_root - self.root.winfo_y())

    def _drag(self, event: tk.Event) -> None:
        self.dragging = True
        x, y = event.x_root - self.drag_offset[0], event.y_root - self.drag_offset[1]
        self.root.geometry(self._geometry(int(PET_W*self.settings.scale), int(PET_H*self.settings.scale), x, y))
        self.target = (x, y)

    def _release(self, _event: tk.Event) -> None:
        self.dragging = False
        self.rest_until = None

    def _show_menu(self, event: tk.Event) -> None:
        self.menu.tk_popup(event.x_root, event.y_root)

    def _toggle_pause(self) -> None:
        self.paused = not self.paused
        self.menu.entryconfigure(2, label="Resume wandering" if self.paused else "Pause wandering")

    def _startle(self, _event: tk.Event | None = None) -> None:
        x, y = self.root.winfo_x(), self.root.winfo_y()
        self.target = choose_target(
            x, y, self._virtual_screen(), int(PET_W*self.settings.scale),
            int(PET_H*self.settings.scale), self.settings.speed * 2.2, random,
        )
        self.move_speed = self.settings.speed * random.uniform(4.5, 6.0)
        self.burst_steps = random.randint(18, 30)
        self.rest_until = None
        self.moving = True

    def _open_settings(self) -> None:
        if getattr(self, "settings_window", None) and self.settings_window.winfo_exists():
            self.settings_window.lift()
            return
        win = tk.Toplevel(self.root)
        self.settings_window = win
        win.title("Little Roach settings")
        win.resizable(False, False)
        win.attributes("-topmost", True)
        panel = ttk.Frame(win, padding=16)
        panel.grid()
        ttk.Label(panel, text="Wandering speed").grid(row=0, column=0, sticky="w")
        speed = tk.DoubleVar(value=self.settings.speed)
        ttk.Scale(panel, from_=0.4, to=2.4, variable=speed, orient="horizontal", length=210).grid(row=0, column=1, padx=10)
        ttk.Label(panel, text="Pet size").grid(row=1, column=0, sticky="w", pady=(12, 0))
        size = tk.DoubleVar(value=self.settings.scale)
        ttk.Scale(panel, from_=0.7, to=2.0, variable=size, orient="horizontal", length=210).grid(row=1, column=1, padx=10, pady=(12, 0))
        startup = tk.BooleanVar(value=self.settings.start_with_windows)
        ttk.Checkbutton(panel, text="Start with Windows", variable=startup).grid(row=2, column=0, columnspan=2, sticky="w", pady=(12, 0))
        ttk.Label(panel, text="Right-click the pet for actions. Double-click to say hello.", wraplength=300).grid(row=3, column=0, columnspan=2, sticky="w", pady=(12, 0))

        def apply() -> None:
            old_startup = self.settings.start_with_windows
            self.settings = PetSettings(speed=float(speed.get()), scale=float(size.get()), start_with_windows=startup.get())
            try:
                if old_startup != self.settings.start_with_windows:
                    set_startup(self.settings.start_with_windows)
                save_settings(self.settings)
                self.root.geometry(self._geometry(int(PET_W*self.settings.scale), int(PET_H*self.settings.scale), self.root.winfo_x(), self.root.winfo_y()))
                win.destroy()
            except OSError as exc:
                messagebox.showerror("Could not save settings", str(exc), parent=win)
        ttk.Button(panel, text="Save", command=apply).grid(row=4, column=0, sticky="w", pady=(14, 0))
        ttk.Button(panel, text="Cancel", command=win.destroy).grid(row=4, column=1, sticky="e", pady=(14, 0))

    def _draw(self) -> None:
        c = self.canvas
        c.delete("all")
        s = self.settings.scale
        c.configure(width=int(PET_W*s), height=int(PET_H*s))
        zoom = max(1, round(s * SPRITE_SUBSAMPLE))
        key = (self.facing, zoom)
        sprite = self.sprite_cache.get(key)
        if sprite is None:
            sprite = self.sprite_sources[self.facing].zoom(zoom, zoom).subsample(
                SPRITE_SUBSAMPLE, SPRITE_SUBSAMPLE
            )
            self.sprite_cache[key] = sprite
        bob = math.sin(self.frame * (0.75 if self.moving else 0.22)) * (1.4 if self.moving else 0.45)
        c.create_image(int(PET_W*s)/2, int(PET_H*s)/2 + bob, image=sprite)

    def _tick(self) -> None:
        self.frame += 1
        if not self.paused and not self.dragging:
            x, y = self.root.winfo_x(), self.root.winfo_y()
            dx, dy = self.target[0]-x, self.target[1]-y
            distance = math.hypot(dx, dy)
            if self.rest_until is not None:
                self.moving = False
                if self.frame >= self.rest_until:
                    self.target = choose_target(
                        x, y, self._virtual_screen(), int(PET_W*self.settings.scale),
                        int(PET_H*self.settings.scale), self.settings.speed, random,
                    )
                    self.rest_until = None
                    if random.random() < 0.24:
                        self.burst_steps = random.randint(8, 17)
                        self.move_speed = self.settings.speed * random.uniform(2.8, 4.2)
                    else:
                        self.burst_steps = 0
                        self.move_speed = self.settings.speed * random.uniform(1.2, 2.0)
                    self.moving = True
            elif distance < 7:
                self.moving = False
                self.rest_until = self.frame + random.randint(9, 28)
            else:
                self.moving = True
                self.facing = "left" if dx < 0 else "right"
                step = min(distance, max(1.0, self.move_speed * 1.4))
                self.root.geometry(self._geometry(int(PET_W*self.settings.scale), int(PET_H*self.settings.scale), int(x+dx/distance*step), int(y+dy/distance*step)))
                if self.burst_steps > 0:
                    self.burst_steps -= 1
                    if self.burst_steps == 0:
                        self.move_speed = self.settings.speed * random.uniform(1.2, 2.0)
        self._draw()
        self.root.after(80, self._tick)

    def run(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    if getattr(sys, "frozen", False):
        # The Tcl/Tk libraries are bundled beside the executable's unpacked
        # files. Set these explicitly so Tcl 8.6 can find its startup scripts.
        bundle_dir = Path(sys._MEIPASS)
        os.environ["TCL_LIBRARY"] = str(bundle_dir / "_tcl_data")
        os.environ["TK_LIBRARY"] = str(bundle_dir / "_tk_data")
    CockroachPet().run()

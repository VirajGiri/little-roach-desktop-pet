"""A tiny, offline-first Windows desktop cockroach pet."""

from __future__ import annotations

import json
import math
import os
import random
import sys
import time
import tkinter as tk
from collections import OrderedDict
from dataclasses import asdict
from pathlib import Path
from tkinter import messagebox, ttk

from pet_core import (
    PetSettings,
    approach_angle,
    choose_target,
    forward_crawl_step,
    movement_step,
    settings_path,
)

try:
    import winreg
except ImportError:  # pragma: no cover - Windows-only integration
    winreg = None


KEY_COLOR = "#010203"
PET_W, PET_H = 192, 192
DIRECTION_COUNT = 32
STRIDE_DISTANCE = 72.0
FRAME_INTERVAL_MS = 16
MAX_CACHED_SPRITES = 96
APP_NAME = "Little Roach"


def load_settings() -> PetSettings:
    path = settings_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        settings = PetSettings.from_dict(data)
        settings.scale = round(settings.scale * 10) / 10
        return settings
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
        self.root.title(APP_NAME)
        self.settings = load_settings()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg=KEY_COLOR)
        try:
            self.root.wm_attributes("-transparentcolor", KEY_COLOR)
        except tk.TclError:
            # On unusual Windows themes, retain a clean magenta key background.
            pass
        initial_width = int(PET_W * self.settings.scale)
        initial_height = int(PET_H * self.settings.scale)
        self.canvas = tk.Canvas(self.root, width=initial_width, height=initial_height, bg=KEY_COLOR,
                                highlightthickness=0, bd=0)
        self.canvas.pack()
        bundle_dir = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
        self.asset_dir = bundle_dir / "assets"
        # Load sprites on demand and keep a small LRU cache. This avoids a long
        # startup delay and hundreds of megabytes of decoded Tk images.
        self.sprite_cache: OrderedDict[tuple[int, int, int], tk.PhotoImage] = OrderedDict()
        self.sprite_item: int | None = None
        self.current_sprite_key: tuple[int, int, int] | None = None
        self.direction = 0
        self.direction_angle = 0.0
        start_x, start_y = self._start_x(), self._start_y()
        self.position_x, self.position_y = float(start_x), float(start_y)
        self.window_position = (start_x, start_y)
        self.root.geometry(self._geometry(initial_width, initial_height, start_x, start_y))
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
        # Tk can report (0, 0) until the borderless window is mapped. Keep the
        # initial target tied to the explicit geometry so the first crawl
        # starts where the pet was placed instead of darting to the corner.
        self.target = (start_x, start_y)
        self.rest_until: float | None = None
        self.move_speed = self.settings.speed * 2.6
        self.burst_until: float | None = None
        self.moving = False
        self.turning = False
        self.gait_distance = 0.0
        self.frame = 0
        self.last_tick = time.perf_counter()
        self.root.after(FRAME_INTERVAL_MS, self._tick)

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
        self.position_x, self.position_y = float(x), float(y)
        self.window_position = (x, y)
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
        x, y = round(self.position_x), round(self.position_y)
        self.target = choose_target(
            x, y, self._virtual_screen(), int(PET_W*self.settings.scale),
            int(PET_H*self.settings.scale), self.settings.speed * 2.2, random,
        )
        self.move_speed = self.settings.speed * random.uniform(4.5, 6.0)
        self.burst_until = time.perf_counter() + random.uniform(0.72, 1.2)
        self.rest_until = None
        self.moving = True
        self.turning = False

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
        ttk.Scale(panel, from_=0.4, to=3.0, variable=speed, orient="horizontal", length=210).grid(row=0, column=1, padx=10)
        ttk.Label(panel, text="Pet size").grid(row=1, column=0, sticky="w", pady=(12, 0))
        size = tk.DoubleVar(value=self.settings.scale)
        ttk.Scale(panel, from_=0.7, to=2.0, variable=size, orient="horizontal", length=210).grid(row=1, column=1, padx=10, pady=(12, 0))
        startup = tk.BooleanVar(value=self.settings.start_with_windows)
        ttk.Checkbutton(panel, text="Start with Windows", variable=startup).grid(row=2, column=0, columnspan=2, sticky="w", pady=(12, 0))
        ttk.Label(panel, text="Right-click the pet for actions. Double-click to say hello.", wraplength=300).grid(row=3, column=0, columnspan=2, sticky="w", pady=(12, 0))

        def apply() -> None:
            old_startup = self.settings.start_with_windows
            selected_scale = round(float(size.get()) * 10) / 10
            self.settings = PetSettings(speed=float(speed.get()), scale=selected_scale, start_with_windows=startup.get())
            try:
                if old_startup != self.settings.start_with_windows:
                    set_startup(self.settings.start_with_windows)
                save_settings(self.settings)
                width, height = int(PET_W*self.settings.scale), int(PET_H*self.settings.scale)
                self.root.minsize(width, height)
                self.canvas.configure(width=width, height=height)
                x, y = self.root.winfo_x(), self.root.winfo_y()
                self.position_x, self.position_y = float(x), float(y)
                self.window_position = (x, y)
                self.root.geometry(self._geometry(width, height, x, y))
                win.destroy()
            except OSError as exc:
                messagebox.showerror("Could not save settings", str(exc), parent=win)
        ttk.Button(panel, text="Save", command=apply).grid(row=4, column=0, sticky="w", pady=(14, 0))
        ttk.Button(panel, text="Cancel", command=win.destroy).grid(row=4, column=1, sticky="e", pady=(14, 0))

    def _draw(self) -> None:
        c = self.canvas
        s = self.settings.scale
        scale_step = min(20, max(7, round(s * 10)))
        # The reference is a side view, so show it facing the travel direction
        # and avoid fake perspective rotations that alter the cockroach.
        facing = "left" if 8 < self.direction < 24 else "right"
        key = (0 if facing == "right" else 1, scale_step, 0)
        sprite = self.sprite_cache.get(key)
        if sprite is None:
            sprite_path = self.asset_dir / f"roach_photo_{facing}_scale_{scale_step}.png"
            sprite = tk.PhotoImage(file=str(sprite_path))
            self.sprite_cache[key] = sprite
            if len(self.sprite_cache) > MAX_CACHED_SPRITES:
                self.sprite_cache.popitem(last=False)
        else:
            self.sprite_cache.move_to_end(key)
        bob = (
            math.sin(self.gait_distance * (2 * math.pi / STRIDE_DISTANCE)) * 1.7
            if self.moving or self.turning else math.sin(self.frame * 0.04) * 0.55
        )
        position = (int(PET_W*s)/2, int(PET_H*s)/2 + bob)
        if self.sprite_item is None:
            self.sprite_item = c.create_image(*position, image=sprite)
            self.current_sprite_key = key
        else:
            c.coords(self.sprite_item, *position)
            if self.current_sprite_key != key:
                c.itemconfigure(self.sprite_item, image=sprite)
                self.current_sprite_key = key

    def _tick(self) -> None:
        now = time.perf_counter()
        dt = max(1.0 / 240.0, min(now - self.last_tick, 0.08))
        self.last_tick = now
        self.frame += 1
        if not self.paused and not self.dragging:
            x, y = self.position_x, self.position_y
            dx, dy = self.target[0]-x, self.target[1]-y
            distance = math.hypot(dx, dy)
            if self.rest_until is not None:
                self.moving = False
                self.turning = False
                if now >= self.rest_until:
                    self.target = choose_target(
                        round(x), round(y), self._virtual_screen(), int(PET_W*self.settings.scale),
                        int(PET_H*self.settings.scale), self.settings.speed, random,
                    )
                    self.rest_until = None
                    if random.random() < 0.24:
                        self.burst_until = now + random.uniform(0.32, 0.68)
                        self.move_speed = self.settings.speed * random.uniform(3.0, 4.5)
                    else:
                        self.burst_until = None
                        self.move_speed = self.settings.speed * random.uniform(2.1, 3.0)
                    self.moving = True
            elif distance < 7:
                self.moving = False
                self.turning = False
                self.rest_until = now + random.uniform(0.72, 2.24)
                self.burst_until = None
            else:
                desired = math.degrees(math.atan2(dy, dx)) % 360.0
                # Turn first, then let the body advance only along its heading.
                previous_angle = self.direction_angle
                self.direction_angle = approach_angle(
                    self.direction_angle, desired, 240.0 * dt
                )
                turn_step = (self.direction_angle - previous_angle + 180.0) % 360.0 - 180.0
                self.direction = int(round(self.direction_angle / (360.0 / DIRECTION_COUNT))) % DIRECTION_COUNT
                if self.burst_until is not None and now >= self.burst_until:
                    self.burst_until = None
                    self.move_speed = self.settings.speed * random.uniform(2.1, 3.0)
                step_x, step_y, self.moving = forward_crawl_step(
                    dx, dy, self.direction_angle,
                    movement_step(self.move_speed, dt),
                )
                self.turning = not self.moving and abs(turn_step) > 0.01
                if self.turning:
                    # Let the legs step during a pivot rather than rotating a
                    # frozen insect; the small cycle is tied to turn angle.
                    self.gait_distance += abs(turn_step) * 0.28
                step = math.hypot(step_x, step_y)
                if step > 0.0:
                    self.position_x = x + step_x
                    self.position_y = y + step_y
                    self.gait_distance += step
                next_window_position = (round(self.position_x), round(self.position_y))
                if next_window_position != self.window_position:
                    self.root.geometry(self._geometry(
                        int(PET_W*self.settings.scale), int(PET_H*self.settings.scale),
                        *next_window_position,
                    ))
                    self.window_position = next_window_position
        self._draw()
        self.root.after(FRAME_INTERVAL_MS, self._tick)

    def run(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    if getattr(sys, "frozen", False):
        # The Tcl/Tk libraries are bundled beside the executable's unpacked
        # files. Set these explicitly so Tcl 8.6 can find its startup scripts.
        bundle_dir = Path(sys._MEIPASS)
        os.environ["TCL_LIBRARY"] = os.environ.get(
            "LITTLE_ROACH_TCL_LIBRARY", str(bundle_dir / "_tcl_data")
        )
        os.environ["TK_LIBRARY"] = os.environ.get(
            "LITTLE_ROACH_TK_LIBRARY", str(bundle_dir / "_tk_data")
        )
    try:
        CockroachPet().run()
    except Exception as exc:
        import traceback

        details = traceback.format_exc()
        try:
            log_dir = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "LittleRoach"
            log_dir.mkdir(parents=True, exist_ok=True)
            (log_dir / "startup.log").write_text(details, encoding="utf-8")
        except OSError:
            pass
        # Windowed PyInstaller builds otherwise fail silently. Use the native
        # Windows dialog so startup errors are visible even if Tk failed.
        if sys.platform == "win32":
            try:
                import ctypes
                log_path = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "LittleRoach" / "startup.log"
                ctypes.windll.user32.MessageBoxW(
                    None,
                    f"Little Roach could not start. Details were saved to:\n{log_path}\n\n{exc}",
                    APP_NAME,
                    0x10,
                )
            except Exception:
                pass
        raise

# Little Roach

A small, offline-first Windows desktop pet: one young cockroach that stays above other windows, wanders around the virtual desktop, and responds to simple interactions.

## Run from source

Requirements: Windows 10/11 and Python 3.10 or newer with Tkinter. There are no third-party runtime packages.

1. Open PowerShell in this folder.
2. Run `py main.py` (or `python main.py`).
3. Right-click the pet for **Settings**, **Pause/Resume**, and **Quit**. Drag it with the left mouse button, and double-click to greet it.

Settings are saved under `%APPDATA%\LittleRoach\settings.json`. “Start with Windows” adds or removes a per-user Run entry in the Windows registry. No administrator access is required.

## Build a shareable Windows app

On a Windows machine with Python 3.10+ including Tcl/Tk support and internet access for the one-time build-tool install:

```powershell
python -m pip install pyinstaller
.\build_windows.ps1
```

The build creates a portable app folder and a ZIP file. Share `dist\LittleRoach-portable.zip`; the recipient extracts it and opens `LittleRoach\LittleRoach.exe`. They do not need Python installed. Keep the executable beside its `_internal` folder; the executable alone is not enough because the app uses bundled Tcl/Tk files. For startup registration, open the executable and enable **Start with Windows** in Settings.

## Behavior and limitations

- The pet is a frameless, color-key transparent Tk window marked always-on-top. It uses Windows virtual-screen bounds, including monitors positioned left of or above the primary display.
- Wander targets are chosen randomly, with mostly nearby steps and occasional longer trips. It can be paused or repositioned by dragging.
- Right-click opens pet actions and settings; double-click or **Pet me** shows a greeting. Speed, size, and startup preference persist locally.
- It has no model/API dependency and does not access the network. `local_ai.py` defines a tiny optional assistant interface; a later local adapter can connect to a model installed on the user's machine. No model is bundled in this initial version.
- Some exclusive full-screen games may hide ordinary desktop-topmost windows. Transparency relies on Windows' Tk color-key support, and behavior can vary with unusual desktop compositors.

## Verify

```powershell
py -m unittest -v
py -m py_compile main.py pet_core.py local_ai.py
```


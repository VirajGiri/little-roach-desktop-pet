# Little Roach

A small, offline-first Windows desktop pet: one young cockroach that stays above other windows, wanders around the virtual desktop, and responds to simple interactions.

## Run from source

Requirements: Windows 10/11 and Python 3.10 or newer with Tkinter. There are no third-party runtime packages.

1. Open PowerShell in this folder.
2. Run `py main.py` (or `python main.py`).
3. Right-click the pet for **Settings**, **Pause/Resume**, **Startle**, and **Quit**. Drag it with the left mouse button; double-click makes it dart away.

Settings are saved under `%APPDATA%\LittleRoach\settings.json`. “Start with Windows” adds or removes a per-user Run entry in the Windows registry. No administrator access is required.

## Build a shareable Windows app

On a Windows machine with Python 3.10+ including Tcl/Tk support and internet access for the one-time build-tool install:

```powershell
python -m pip install pyinstaller
.\build_windows.ps1
```

The build creates a portable app folder and a ZIP file. Share `dist\LittleRoach-portable.zip`; the recipient extracts it and opens `LittleRoach\LittleRoach.exe`. They do not need Python installed. Keep the executable beside its `_internal` folder and the bundled `assets` folder; the executable alone is not enough. For startup registration, open the executable and enable **Start with Windows** in Settings.

## Behavior and limitations

- The pet is a frameless, color-key transparent Tk window marked always-on-top. It uses Windows virtual-screen bounds, including monitors positioned left of or above the primary display.
- It wanders in short bursts with natural pauses and occasional quick dashes. Sixteen gait poses animate the legs in step with distance traveled, including small steps during pivots. Eight distinct side, three-quarter, front, and rear body views give it real perspective changes; 32 headings fill the turns between those views. It turns before advancing, walks along its facing direction, and curves as it corrects toward a target instead of sliding sideways. Eased turns and an update rate of up to 60 FPS keep movement smooth. Double-click or **Startle** triggers a longer sprint; it can be paused or repositioned by dragging.
- Right-click opens pet actions and settings. Speed, size, and startup preference persist locally. The default size is compact, and the crawl poses advance according to distance traveled so the legs stay in step with body movement.
- It loads artwork only as the current pose and nearby recent poses are needed, keeping startup fast and decoded image memory bounded. The two eight-view animation sheets in `artwork/roach_views_gait_01.png` and `artwork/roach_views_gait_02.png` preserve the natural chestnut-and-amber colors and provide real body-angle changes. Rebuild the 512 direction/pose sprites with `python tools/generate_sprites.py` after installing Pillow and NumPy. Neither package is needed to run or build the pet.
- `artwork/roach_appearance_reference.png` preserves the earlier cockroach artwork used to guide the current shell colors and markings. `artwork/roach_animation_preview.png` shows the generated movement views and gait frames.
- It has no model/API dependency and does not access the network. `local_ai.py` defines a tiny optional assistant interface; a later local adapter can connect to a model installed on the user's machine. No model is bundled in this initial version.
- Some exclusive full-screen games may hide ordinary desktop-topmost windows. Transparency relies on Windows' Tk color-key support. The animation uses a crisp alpha silhouette because Tk color-key windows cannot blend soft alpha edges; some jaggedness may be visible at larger sizes. Behavior can vary with unusual desktop compositors.

## Verify

```powershell
py -m unittest -v
py -m py_compile main.py pet_core.py local_ai.py
```

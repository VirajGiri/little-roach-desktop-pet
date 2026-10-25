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
- It wanders in short bursts with natural pauses and occasional quick dashes. It turns before advancing and moves along its facing direction instead of sliding sideways. Eased turns and an update rate of up to 60 FPS keep movement smooth. Double-click or **Startle** triggers a longer sprint; it can be paused or repositioned by dragging.
- Right-click opens pet actions and settings. Speed, size, and startup preference persist locally. The default size is compact.
- The pet uses an editable, reference-guided 3D nymph model in `artwork/LittleRoach_3D.blend`. Its abdomen and pronotum use texture sampled from the supplied image; six articulated legs, spines, antennae, eyes, mouthparts, and tail cerci are modeled separately. The app displays eight looping walking poses across 32 headings (256 transparent sprites), so the gait changes with travel and the body turns through intermediate angles. The included sprite PNGs are runtime assets; the `.blend` and `tools/build_roach_3d.py` are authoring sources.
- To regenerate the model and sprite set, install Blender 5.2 and run `blender --background --python tools/build_roach_3d.py`. This renders 384×384 transparent frames and embeds the sampled textures in the saved Blender project. Run `tools\create_animation_preview.ps1` to create the contact sheet. The model is a 3D reconstruction guided by one side-view reference: its visible shell markings are sampled from that image, while unseen surfaces and other angles are inferred. A single reference cannot establish exact anatomy or 100% matching views from every direction.
- It has no model/API dependency and does not access the network. `local_ai.py` defines a tiny optional assistant interface; a later local adapter can connect to a model installed on the user's machine. No model is bundled in this initial version.
- Some exclusive full-screen games may hide ordinary desktop-topmost windows. Transparency relies on Windows' Tk color-key support. Behavior can vary with unusual desktop compositors.

## Verify

```powershell
py -m unittest -v
py -m py_compile main.py pet_core.py local_ai.py
```

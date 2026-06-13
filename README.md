# Prompt Architect

A multi-platform AI prompt builder that helps you create stronger prompts with built-in effectiveness scoring, reusable project presets, and platform-aware guidance for PC, Raspberry Pi, and Android workflows.

![Python](https://img.shields.io/badge/Python-3.11+-blue) ![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20Pi%20%7C%20Android-green) ![License](https://img.shields.io/badge/License-MIT-yellow)

## What It Does

Instead of typing raw English into an AI and hoping for the best, Prompt Architect lets you:

1. **Pick your project type** (PC app, Pi app, game, website, Android, etc.)
2. **Select enhancements** (modern GUI, security, diagnostics, etc.)
3. **Choose a thinking framework** (Chain of Thought, Tree of Thought, etc.)
4. **Set quality rules** (PEP 8, security, robustness, conciseness)
5. **Load your project conventions** so the AI already knows your patterns
6. **Hit Generate** — get a structured, optimized prompt with role, context, constraints, and quality gates

Then copy it or send it directly to your open Claude/ChatGPT/Gemini window.

## Features

- **4 prompt categories**: Code, Conversation, Image generation, Video generation
- **My Projects presets**: Auto-inject your project-specific conventions (build commands, patterns, project context) so you never re-explain them
- **Rolling Update Chain**: Build follow-up prompts that carry forward context from previous changes
- **Effectiveness Scoring**: detailed multi-point analysis grades your prompt A+ through F with actionable suggestions
- **Send to AI**: One-click paste into Claude, ChatGPT, or Gemini browser windows
- **Templates**: Save/load your favorite configurations
- **History**: Every prompt you generate is searchable and reusable
- **Diagnostics**: Built-in health report for troubleshooting
- **Dark/Light theme toggle**
- **Launches maximized by default** — fills your screen immediately; resize or restore as needed (F11 or View menu)
- **Full copy/paste support**: Ctrl+C/X/V/A on every text field; right-click context menus; explicit Copy buttons on the output area

## Install + Run by Platform

### PC (Windows / Linux / macOS desktop app)

From the repository root:

```bash
python -m pip install -r requirements.txt
python prompt_architect.py
```

Notes:
- Python 3.11+ recommended.
- `tkinter` is required for the desktop UI:
  - Linux/Raspberry Pi OS: `sudo apt install python3-tk`
  - Windows/macOS: usually bundled with the standard Python installer.
- Optional desktop integrations (already in `requirements.txt`): `pyautogui`, `pyperclip`.

Windows launcher options:
- `PromptArchitect.bat` (runs the app)
- `launch.bat` (installs `requirements.txt` first, then runs the app)

### Build your own .exe
```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name PromptArchitect prompt_architect.py
```

### Raspberry Pi (GUI + optional headless CLI)

Install dependencies:

```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-tk
python3 -m pip install -r requirements.txt
```

Run GUI mode:

```bash
python3 prompt_architect_pi.py
```

Run CLI mode (headless over SSH):

```bash
python3 prompt_architect_pi.py --cli --target "Raspberry Pi App" --task "Build a temperature logger"
```

### Android (Kivy mobile edition)

Desktop preview:

```bash
pip install kivy
python prompt_architect_android.py
```

APK build (via Buildozer on Linux):

```bash
pip install buildozer
buildozer android debug
```

`buildozer.spec` includes Android package requirements (`python3,kivy,plyer`) for APK builds.

## Platform Notes (PC / Pi / Android)

- **PC**: Full desktop UI (`prompt_architect.py`) with templates, history, diagnostics, and Send to AI integrations.
- **Raspberry Pi**: Pi-optimized desktop UI plus optional headless CLI mode (`--cli`) for SSH-driven workflows.
- **Android**: Mobile-focused Kivy frontend (`prompt_architect_android.py`) using shared prompt logic from `prompt_engine.py`.

## Usage Walkthrough (short example)

1. Open the app for your platform (`prompt_architect.py`, `prompt_architect_pi.py`, or `prompt_architect_android.py`).
2. Choose a prompt category (for example, **Code**).
3. Select a build target (for example, **Raspberry Pi App** or **PC Desktop App**).
4. Pick enhancements and a reasoning framework.
5. Enter your task (example: `Build a temperature logger with CSV export and error handling`).
6. Click **Generate** to produce a structured prompt.
7. Review the **Effectiveness Analysis** score/grade and apply quick-win suggestions if needed.
8. Copy the prompt (or send it to your AI tool) and iterate with Update Chain follow-ups.

## Testing

- At the time of writing, there is no configured automated unit/integration test suite in this repository.
- `benchmark_prompt_architect.py` can be used for prompt quality/performance benchmarking.
- Use the manual checklist below for UI and behavior verification.

## File Structure

| File | Description |
|------|-------------|
| `prompt_architect.py` | Main desktop app (tkinter) |
| `prompt_architect_pi.py` | Raspberry Pi edition (lighter UI, Pi fonts) |
| `prompt_architect_android.py` | Android/mobile edition (Kivy) |
| `prompt_engine.py` | Shared prompt generation logic (no UI deps) |
| `PromptArchitect.bat` | Windows launcher |
| `launch.bat` | Windows launcher that installs requirements then starts app |
| `buildozer.spec` | Android APK build config |

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+Enter` | Generate prompt |
| `Ctrl+Shift+C` | Copy output to clipboard |
| `Ctrl+S` | Save output to file |
| `Ctrl+N` | New session |
| `Ctrl+T` | Toggle dark/light theme |
| `Ctrl+D` | Run diagnostics |
| `Ctrl+Z / Ctrl+Y` | Undo / Redo in text fields |
| `Ctrl+A` | Select all in focused text field |
| `F11` | Toggle maximize / restore window |

### Manual Test Checklist

Use this checklist when verifying a new build:

### Startup & Window
- [ ] App opens **maximized** on first launch (no saved geometry)
- [ ] Window state is persisted — re-opening after closing maximized restores maximized state
- [ ] Re-opening after restoring a normal window size restores that size
- [ ] **F11** toggles between maximized and normal
- [ ] View → **Maximize Window** maximizes the window
- [ ] View → **Restore Window Size** un-maximizes the window
- [ ] Window can be manually resized when not maximized
- [ ] `minsize` prevents shrinking below usable dimensions

### Copy / Paste (Desktop app)
- [ ] **Ctrl+C** copies selected text in Task, Context, Custom Constraints, Result fields
- [ ] **Ctrl+V** pastes into Task, Context, Custom Constraints, Result fields
- [ ] **Ctrl+X** cuts selected text from input fields
- [ ] **Ctrl+A** selects all text in any focused text field (including Result area)
- [ ] **Right-click** shows context menu with Cut / Copy / Paste / Select All / Clear
- [ ] **Copy Prompt Only** button copies just the generated prompt (no review section)
- [ ] **Copy All** button copies prompt + review section
- [ ] **Copy Selection** button copies highlighted text from the result area

### Copy / Paste (Pi app)
- [ ] **Ctrl+C / Ctrl+V / Ctrl+X / Ctrl+A** work in Task, Context, Custom Constraints fields
- [ ] **Right-click** shows context menu on all text fields

### Theme
- [ ] Dark theme is default on first launch
- [ ] **Ctrl+T** or View → Toggle Theme switches dark ↔ light
- [ ] All widgets (buttons, text areas, menus) update color when theme changes

### Cross-Platform Notes
- On **Windows**: maximized state uses `root.state("zoomed")`
- On **Linux**: maximized state uses `root.attributes("-zoomed", True)`
- On **Raspberry Pi (800×480 touchscreen)**: app fills the screen natively without forcing maximize; larger displays maximize
- On **macOS**: maximize approximated via `-zoomed`; full-screen behavior depends on OS version

## License

MIT

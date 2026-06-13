# Prompt Architect

A desktop tool that builds optimized, structured prompts for AI models — so you stop wasting tokens on bad prompts and start getting better results from Claude, ChatGPT, Gemini, and image/video generators.

![Python](https://img.shields.io/badge/Python-3.11+-blue) ![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20Pi-green) ![License](https://img.shields.io/badge/License-MIT-yellow)

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
- **My Projects presets**: Auto-inject your project-specific conventions (struct formats, widget patterns, build commands) so you never re-explain them
- **Rolling Update Chain**: Build follow-up prompts that carry forward context from previous changes
- **Effectiveness Scoring**: 13-point analysis grades your prompt A+ through F with actionable suggestions
- **Send to AI**: One-click paste into Claude, ChatGPT, or Gemini browser windows
- **Templates**: Save/load your favorite configurations
- **History**: Every prompt you generate is searchable and reusable
- **Diagnostics**: Built-in health report for troubleshooting
- **Dark/Light theme toggle**
- **Launches maximized by default** — fills your screen immediately; resize or restore as needed (F11 or View menu)
- **Full copy/paste support**: Ctrl+C/X/V/A on every text field; right-click context menus; explicit Copy buttons on the output area

## Quick Start

### Windows (Python)
```bash
cd prompt_architect
python prompt_architect.py
```

### Windows (Batch file)
Double-click `PromptArchitect.bat`

### Build your own .exe
```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name PromptArchitect prompt_architect.py
```

### Raspberry Pi
```bash
python3 prompt_architect_pi.py
```

### Android (Kivy)
```bash
pip install kivy
python prompt_architect_android.py   # Preview on desktop
# Or build APK: pip install buildozer && buildozer android debug
```

## File Structure

| File | Description |
|------|-------------|
| `prompt_architect.py` | Main desktop app (tkinter) |
| `prompt_architect_pi.py` | Raspberry Pi edition (lighter UI, Pi fonts) |
| `prompt_architect_android.py` | Android/mobile edition (Kivy) |
| `prompt_engine.py` | Shared prompt generation logic (no UI deps) |
| `PromptArchitect.bat` | Windows launcher |
| `buildozer.spec` | Android APK build config |

## Requirements

- Python 3.11+
- tkinter (included with Python)
- Optional: `pyautogui`, `pyperclip` (for Send to AI feature)
- Optional: `kivy`, `plyer` (for Android edition)

## Automated Tests

Run unit tests with:

```bash
python -m unittest discover -s tests
```

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

## Manual Test Checklist

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

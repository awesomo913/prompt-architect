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
- **Right-click context menus** on every text field (cut, copy, paste, select all)

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

## License

MIT

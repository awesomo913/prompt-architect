"""
Prompt Architect v4.0 — Raspberry Pi Edition

Optimized for:
- Smaller screens (800x480 official Pi touchscreen up to 1080p)
- Lower RAM / CPU (lighter widgets, smaller fonts)
- Pi-available fonts (DejaVu Sans / Liberation Mono)
- Touch-friendly button sizes
- CLI mode for headless Pi use over SSH

Usage:
  GUI mode:   python3 prompt_architect_pi.py
  CLI mode:   python3 prompt_architect_pi.py --cli --target "Raspberry Pi App" --task "Build a temperature logger"
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import json
import os
import platform
import re
import sys
import hashlib
import argparse
import traceback
import logging
import shutil
import time
from logging.handlers import RotatingFileHandler
from datetime import datetime
from pathlib import Path

# ═══════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════

APP_NAME = "Prompt Architect"
APP_VERSION = "4.0 (Pi)"
DIAG_VERSION = f"{APP_NAME} v{APP_VERSION}"

COLORS = {
    "bg": "#1e1e2e", "surface": "#313244", "overlay": "#181825",
    "text": "#cdd6f4", "subtext": "#a6adc8", "blue": "#89b4fa",
    "green": "#a6e3a1", "red": "#f38ba8", "peach": "#fab387",
    "mauve": "#cba6f7", "yellow": "#f9e2af", "teal": "#94e2d5",
    "dark": "#11111b",
}

COLORS_LIGHT = {
    "bg": "#eff1f5", "surface": "#ccd0da", "overlay": "#e6e9ef",
    "text": "#4c4f69", "subtext": "#6c6f85", "blue": "#1e66f5",
    "green": "#40a02b", "red": "#d20f39", "peach": "#fe640b",
    "mauve": "#8839ef", "yellow": "#df8e1d", "teal": "#179299",
    "dark": "#dce0e8",
}

FONT = ("DejaVu Sans", 10)
FONT_SM = ("DejaVu Sans", 9)
FONT_HD = ("DejaVu Sans", 14, "bold")
FONT_MN = ("Liberation Mono", 10)
FONT_MS = ("Liberation Mono", 9)
FONT_BT = ("DejaVu Sans", 10, "bold")

TEMPLATES_DIR = Path(os.path.dirname(os.path.abspath(__file__))) / "prompt_templates"
CONFIG_DIR = Path.home() / ".prompt_architect_pi"
AUTOSAVE_FILE = CONFIG_DIR / "autosave.json"
HISTORY_FILE = CONFIG_DIR / "history_pi.json"
GEOMETRY_FILE = CONFIG_DIR / "geometry.json"
LOG_FILE = CONFIG_DIR / "prompt_architect_pi.log"
MAX_HISTORY = 500
AUTOSAVE_INTERVAL_MS = 120000  # 120s for Pi to reduce SD card wear
INPUT_LIMITS = {"task": 50 * 1024, "context": 100 * 1024, "custom_constraints": 10 * 1024}
TEMPLATE_SCHEMA_KEYS = {"build_target", "enhancements", "role", "reasoning",
                        "output_format", "constraints", "custom_constraints", "context", "task"}
# Screen width at or below this pixel count uses a compact fixed geometry rather than maximizing
_PI_SMALL_SCREEN_WIDTH = 800


def _setup_logging() -> logging.Logger:
    """Initialize rotating file logger."""
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    log = logging.getLogger("prompt_architect_pi")
    log.setLevel(logging.DEBUG)
    if not log.handlers:
        try:
            fh = RotatingFileHandler(str(LOG_FILE), maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8")
            fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
            log.addHandler(fh)
        except OSError:
            pass
    return log


logger = _setup_logging()


def _lighten_color(hex_color: str, factor: float = 0.15) -> str:
    """Lighten a hex color by blending toward white."""
    hex_color = hex_color.lstrip("#")
    r, g, b = int(hex_color[:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    r = min(255, int(r + (255 - r) * factor))
    g = min(255, int(g + (255 - g) * factor))
    b = min(255, int(b + (255 - b) * factor))
    return f"#{r:02x}{g:02x}{b:02x}"


# ═══════════════════════════════════════════════════════════════════
# TOOLTIP
# ═══════════════════════════════════════════════════════════════════

class ToolTip:
    def __init__(self, widget: tk.Widget, text: str, colors: dict):
        self.widget = widget
        self.text = text
        self.colors = colors
        self.tipwindow: tk.Toplevel | None = None
        widget.bind("<Enter>", self._show, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _show(self, event=None):
        if self.tipwindow:
            return
        x = self.widget.winfo_rootx() + 16
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 2
        tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tw.wm_attributes("-topmost", True)
        tk.Label(tw, text=self.text, justify=tk.LEFT, background=self.colors["surface"],
                 foreground=self.colors["text"], relief=tk.SOLID, borderwidth=1,
                 font=FONT_SM, padx=6, pady=3, wraplength=260).pack()
        self.tipwindow = tw

    def _hide(self, event=None):
        if self.tipwindow:
            self.tipwindow.destroy()
            self.tipwindow = None

    def update_colors(self, colors: dict):
        self.colors = colors


# ═══════════════════════════════════════════════════════════════════
# PROMPT TYPES — same structure as PC edition, compact descriptions
# ═══════════════════════════════════════════════════════════════════

BUILD_TARGETS = {
    "PC Desktop App": {
        "description": "A program with a window that runs on a regular computer (Windows/Mac/Linux).",
        "role": "Senior Desktop Application Engineer specializing in cross-platform GUI development, native OS integration, and production-grade packaging",
        "platform_context": "TARGET PLATFORM: Windows / macOS / Linux desktop.\n- Use Python 3.10+ with tkinter/ttk, PyQt6, or wxPython for GUI.\n- Handle DPI scaling, window management, cross-platform file paths (pathlib).\n- Save settings via JSON/TOML in platform config dirs.\n- Graceful shutdown: save state, release locks, clean temp files.",
        "extra_constraints": ["Separate UI, logic, and data layers.", "Use threading for long operations to keep UI responsive.", "Handle missing files and startup failures gracefully."],
    },
    "Raspberry Pi App": {
        "description": "An app for Raspberry Pi \u2014 lightweight, GPIO for sensors/LEDs/motors, handles limited RAM.",
        "role": "Embedded Systems Engineer specializing in Raspberry Pi, ARM Linux, GPIO programming, and resource-constrained design",
        "platform_context": "TARGET PLATFORM: Raspberry Pi (ARM Linux \u2014 Raspberry Pi OS).\n- Limited RAM (1-8 GB). Minimize memory usage.\n- SD card is slow and wears out. Minimize writes; use tmpfs for temp data.\n- GPIO via gpiozero or lgpio. Camera via picamera2.\n- Design for headless use (systemd service, SSH-manageable).\n- Handle power loss \u2014 assume unclean shutdown can happen anytime.\n- Always clean up GPIO pins in try/finally or atexit.",
        "extra_constraints": ["Include requirements.txt with pinned versions.", "Include setup instructions for I2C/SPI/camera if needed.", "Support both Pi 4 (RPi.GPIO) and Pi 5 (lgpio).", "Handle missing hardware with clear error messages."],
    },
    "Cross-Platform (PC + Pi)": {
        "description": "ONE program that works on BOTH a regular PC and a Raspberry Pi, auto-detecting which device.",
        "role": "Cross-Platform Architect for portable Python apps on x86 desktop and ARM Raspberry Pi",
        "platform_context": "TARGET: Windows/macOS/Linux AND Raspberry Pi.\n- Auto-detect platform at startup. GPIO optional on PC (use stubs).\n- tkinter for GUI (works everywhere). Headless CLI fallback on Pi.\n- Use pathlib for paths, conditional imports for Pi libraries.\n- Keep resource usage low enough for Pi, modern-looking on desktop.",
        "extra_constraints": ["Abstract hardware interfaces with PC mock and Pi real implementations.", "Use try/except ImportError for Pi-specific libraries.", "Provide instructions for both platforms."],
    },
    "Game": {
        "description": "A video game with graphics, player input, sounds, collision, and game screens.",
        "role": "Game Developer specializing in 2D/3D game architecture, rendering, physics, and player experience",
        "platform_context": "TARGET: Game application using pygame, pyglet, or arcade.\n- Proper game loop: 60 FPS, delta-time movement.\n- Separate state, rendering, and input systems.\n- Load assets from organized assets/ directory.\n- Scene manager for title, gameplay, pause, game over screens.\n- Save/load game state to JSON.",
        "extra_constraints": ["All speeds/sizes/colors as constants, not magic numbers.", "Handle window close and pause/resume cleanly.", "No per-frame memory allocations in the game loop."],
    },
    "Website / Web App": {
        "description": "A website or web app that runs in a browser \u2014 frontend, backend, database, login.",
        "role": "Full-Stack Web Developer specializing in responsive design, REST APIs, accessibility, and web security",
        "platform_context": "TARGET: Web application (browser-based).\n- Frontend: HTML5/CSS3/JS with React, Vue, or Svelte if appropriate.\n- Backend: Flask, FastAPI, Django, or Express.\n- Mobile-first responsive design. Accessibility (ARIA, keyboard nav).\n- Security: CSRF, XSS prevention, env-based secrets.\n- RESTful API with proper HTTP methods and status codes.",
        "extra_constraints": ["Validate input on both client and server side.", "Use HTTPS-only cookies for auth.", "Include rate limiting on auth endpoints."],
    },
}

ENHANCEMENTS = {
    "Modern GUI + UX": {
        "description": "Make it LOOK modern \u2014 dark theme, hover effects, keyboard shortcuts, tooltips, smooth resizing.",
        "role": "UI/UX Modernization Specialist",
        "platform_context": "OBJECTIVE: Modernize the UI.\n- Cohesive dark theme with optional light toggle.\n- Hover states, loading indicators, progress bars.\n- Keyboard shortcuts, status bar, tooltips.\n- Responsive layout. Replace default widgets with styled ones.",
        "extra_constraints": ["Preserve ALL existing functionality.", "Support 100%-200% display scaling.", "Separate theme/styling code from logic."],
    },
    "Security + Compliance": {
        "description": "Make it SAFE \u2014 fix security holes, handle private data properly, prepare for app store rules.",
        "role": "Application Security and Compliance Specialist",
        "platform_context": "OBJECTIVE: Security hardening and platform compliance.\n- Sanitize ALL user/file/network input.\n- Encrypt sensitive data. No hardcoded secrets.\n- Platform rules: Microsoft Store, Linux FHS, GDPR privacy.\n- Dependency audit for known vulnerabilities.",
        "extra_constraints": ["Create SECURITY_NOTES.md listing changes.", "Flag remaining risks with severity levels.", "Don't break existing functionality."],
    },
    "More Features + Robustness": {
        "description": "Make it DO more and BREAK less \u2014 undo/redo, auto-save, better errors, loading bars, retry logic.",
        "role": "Senior Engineer specializing in feature expansion and reliability",
        "platform_context": "OBJECTIVE: Expand features and harden reliability.\n- Add input validation, undo/redo, auto-save.\n- Logging with configurable verbosity.\n- Retry logic for network/IO. Graceful degradation.\n- Progress bars for slow operations. Unit tests.",
        "extra_constraints": ["List every improvement with before/after.", "No breaking changes to existing features.", "Every new feature must have error handling."],
    },
    "Add Diagnostics": {
        "description": "Add a 'health check' button that generates a report file on your Desktop for troubleshooting.",
        "role": "Systems Reliability Engineer for diagnostics and logging",
        "platform_context": "OBJECTIVE: Add diagnostic report system.\n- Save .txt report to Desktop (fallback to home dir).\n- Include: OS info, app state, dependency check, recent errors, memory usage.\n- Add 'Run Diagnostics' button. Auto-generate on crashes.\n- Use rotating log files (5 MB max, 3 backups).",
        "extra_constraints": ["Never include passwords or API keys in reports.", "Human-readable format with clear section headers."],
    },
    "Find Expansion Opportunities": {
        "description": "Don't code \u2014 ANALYZE your program and find missed features, fork ideas, plugin points, and quick wins.",
        "role": "Product Strategist and Architect for expansion analysis",
        "platform_context": "OBJECTIVE: Strategic expansion report.\n- Find missed features, partial implementations.\n- Fork opportunities: Lite/Pro, PC/Pi/Web editions.\n- Plugin/extension points. Integration opportunities.\n- Prioritized by effort (Low/Med/High). Flag quick wins.",
        "extra_constraints": ["Reference actual functions and files in the code.", "Include concrete first steps, not vague ideas.", "Assess risks for each expansion path."],
    },
}

REASONING_MODES = {
    "Standard Chain of Thought": {"description": "Step-by-step thinking.", "block": "REASONING: Think through the problem step by step. Show your reasoning clearly."},
    "Structured Chain of Thought (SCoT)": {"description": "Best for code \u2014 plan with pseudocode first.", "block": "REASONING: Use Structured Chain of Thought (SCoT).\nDraft a pseudocode plan first:\n1. SEQUENTIAL: Setup and data flow.\n2. BRANCHES: Edge cases and error paths.\n3. LOOPS: Repetition and termination.\n4. COMPOSE: Combine into solution."},
    "Tree of Thought (ToT)": {"description": "Try 3 approaches, compare, pick the best.", "block": "REASONING: Use Tree of Thought.\n1. Generate 3 distinct approaches.\n2. Evaluate each for correctness, efficiency, maintainability.\n3. Select the best with justification.\n4. Implement only the chosen approach."},
    "None": {"description": "No thinking framework \u2014 just answer.", "block": ""},
}

OUTPUT_FORMATS = {
    "Free-form": {"description": "AI picks the best format.", "block": ""},
    "JSON (strict)": {"description": "Raw JSON data only.", "block": "OUTPUT FORMAT: Return strictly valid JSON. No markdown. Raw JSON only."},
    "Markdown": {"description": "Headers, bullets, code blocks.", "block": "OUTPUT FORMAT: Return well-structured Markdown."},
    "Code Only": {"description": "Just the runnable code.", "block": "OUTPUT FORMAT: Return only executable code. No explanations."},
}

CONSTRAINT_PRESETS = {
    "Python Best Practices": {"description": "PEP 8, type hints, docstrings", "rules": ["Follow PEP 8.", "Use type hints.", "Include docstrings."]},
    "Performance": {"description": "Fast code, low memory", "rules": ["Optimize time complexity.", "Minimize memory use."]},
    "Security": {"description": "Validate input, no hardcoded secrets", "rules": ["Sanitize all inputs.", "Never hardcode secrets."]},
    "Conciseness": {"description": "Short, no filler", "rules": ["No conversational filler.", "No restating the problem."]},
    "Robustness": {"description": "Handles errors gracefully", "rules": ["Handle edge cases.", "Input validation.", "Meaningful error messages."]},
}


# ═══════════════════════════════════════════════════════════════════
# CLI MODE
# ═══════════════════════════════════════════════════════════════════

def cli_generate(args: argparse.Namespace) -> None:
    all_types: list[dict] = []
    if args.target and args.target in BUILD_TARGETS:
        all_types.append(BUILD_TARGETS[args.target])
    for enh_name in (args.enhance or []):
        if enh_name in ENHANCEMENTS:
            all_types.append(ENHANCEMENTS[enh_name])

    sections: list[str] = []
    if all_types:
        roles = " AND ".join(t["role"] for t in all_types)
        sections.append(f"# ROLE\nYou are: {roles}.")
    sections.append(f"# TASK\n{args.task}")
    for t in all_types:
        pc = t.get("platform_context", "")
        if pc:
            sections.append(f"# PLATFORM & ENVIRONMENT\n{pc}")
    if args.context:
        sections.append(f"# ADDITIONAL CONTEXT\n{args.context}")
    if args.reasoning and args.reasoning in REASONING_MODES:
        block = REASONING_MODES[args.reasoning]["block"]
        if block:
            sections.append(f"# REASONING\n{block}")
    constraints: list[str] = []
    for t in all_types:
        constraints.extend(t.get("extra_constraints", []))
    if constraints:
        sections.append("# CONSTRAINTS\n" + "\n".join(f"- {c}" for c in constraints))
    sections.append("# QUALITY GATE\n1. All TASK requirements addressed.\n2. All CONSTRAINTS satisfied.\n3. Code runs without errors.\n4. Edge cases handled.\n5. No placeholder TODOs left behind.")

    final = "\n\n".join(sections)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(final)
        print(f"Saved to: {args.output}")
    else:
        print(final)


# ═══════════════════════════════════════════════════════════════════
# GUI APPLICATION
# ═══════════════════════════════════════════════════════════════════

class PromptArchitectPi:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(f"{APP_NAME} v{APP_VERSION}")
        self.root.configure(bg=COLORS["bg"])

        self.history: list[dict] = []
        self._startup_time = datetime.now()
        self._error_log: list[dict] = []
        self._dark_mode = True
        self._dirty = False
        self._autosave_hash = ""
        self._clipboard_clear_id = None
        self._toast_window = None
        self._status_clear_id = None

        self._themed_buttons: list[tuple[tk.Button, str, str]] = []
        self._themed_texts: list = []
        self._tooltips: list[ToolTip] = []

        sw = root.winfo_screenwidth()
        if sw <= 800:
            self.root.geometry("800x480")
        elif sw <= 1280:
            self.root.geometry("1024x700")
        else:
            self.root.geometry("1100x800")
        self.root.minsize(780, 460)

        self._install_error_handler()
        self._restore_geometry()
        self._configure_styles(self._active_colors())
        self._build_menu_bar()
        self._build_ui()
        self._build_status_bar()
        self._bind_shortcuts()
        self._load_autosave()
        self._load_history_from_disk()
        self._start_autosave()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        logger.info("Application started (Pi)")

    # ── Theme ────────────────────────────────────────────────────

    def _active_colors(self) -> dict:
        return COLORS if self._dark_mode else COLORS_LIGHT

    def _toggle_theme(self) -> None:
        self._dark_mode = not self._dark_mode
        c = self._active_colors()
        self._configure_styles(c)
        self.root.configure(bg=c["bg"])
        if hasattr(self, "_left_canvas"):
            self._left_canvas.configure(bg=c["bg"])
        for btn, ck, _ in self._themed_buttons:
            try:
                btn.configure(bg=c[ck], fg=c["dark"])
            except tk.TclError:
                pass
        for tw in self._themed_texts:
            try:
                tw.configure(bg=c["overlay"], fg=c["text"], insertbackground=c["text"])
            except tk.TclError:
                pass
        if hasattr(self, "result"):
            self.result.configure(fg=c["yellow"])
        if hasattr(self, "diag"):
            self.diag.configure(fg=c["green"])
        for tip in self._tooltips:
            tip.update_colors(c)
        self._style_menus(c)
        self._set_status(f"{'Dark' if self._dark_mode else 'Light'} theme")
        logger.info(f"Theme: {'dark' if self._dark_mode else 'light'}")

    # ── Styles ───────────────────────────────────────────────────

    def _configure_styles(self, c: dict) -> None:
        s = ttk.Style()
        s.theme_use("clam")
        s.configure("TFrame", background=c["bg"])
        s.configure("TLabel", background=c["bg"], foreground=c["text"], font=FONT)
        s.configure("Header.TLabel", font=FONT_HD, foreground=c["blue"])
        s.configure("Sub.TLabel", font=FONT_SM, foreground=c["subtext"])
        s.configure("Desc.TLabel", font=FONT_SM, foreground=c["teal"])
        s.configure("Warn.TLabel", font=FONT_SM, foreground=c["red"])
        s.configure("TLabelframe", background=c["bg"], foreground=c["mauve"], font=("DejaVu Sans", 10, "bold"))
        s.configure("TLabelframe.Label", background=c["bg"], foreground=c["mauve"], font=("DejaVu Sans", 10, "bold"))
        s.configure("TNotebook", background=c["bg"])
        s.configure("TNotebook.Tab", background=c["surface"], foreground=c["text"], font=FONT, padding=[10, 4])
        s.map("TNotebook.Tab", background=[("selected", c["bg"])], foreground=[("selected", c["blue"])])
        s.configure("TCheckbutton", background=c["bg"], foreground=c["text"], font=FONT)
        s.map("TCheckbutton", background=[("active", c["bg"])])
        s.configure("TRadiobutton", background=c["bg"], foreground=c["text"], font=FONT)
        s.map("TRadiobutton", background=[("active", c["bg"])])
        s.configure("TEntry", fieldbackground=c["surface"], foreground=c["text"])
        s.configure("Status.TLabel", background=c["surface"], foreground=c["subtext"], font=FONT_SM)
        s.configure("StatusBar.TFrame", background=c["surface"])

    def _style_menus(self, c: dict) -> None:
        for menu in [self._file_menu, self._edit_menu, self._view_menu, self._help_menu]:
            try:
                menu.configure(bg=c["surface"], fg=c["text"], activebackground=c["blue"], activeforeground=c["dark"])
            except tk.TclError:
                pass

    # ── Menu Bar ─────────────────────────────────────────────────

    def _build_menu_bar(self) -> None:
        c = self._active_colors()
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        self._file_menu = tk.Menu(menubar, tearoff=0, bg=c["surface"], fg=c["text"])
        self._file_menu.add_command(label="New", command=self._new_session, accelerator="Ctrl+N")
        self._file_menu.add_command(label="Open Template", command=lambda: self.notebook.select(1))
        self._file_menu.add_separator()
        self._file_menu.add_command(label="Save Output", command=self.save_file, accelerator="Ctrl+S")
        self._file_menu.add_separator()
        self._file_menu.add_command(label="Exit", command=self._on_close)
        menubar.add_cascade(label="File", menu=self._file_menu)

        self._edit_menu = tk.Menu(menubar, tearoff=0, bg=c["surface"], fg=c["text"])
        self._edit_menu.add_command(label="Undo", command=self._undo, accelerator="Ctrl+Z")
        self._edit_menu.add_command(label="Redo", command=self._redo, accelerator="Ctrl+Y")
        self._edit_menu.add_separator()
        self._edit_menu.add_command(label="Copy Output", command=self.copy_clip, accelerator="Ctrl+Shift+C")
        self._edit_menu.add_command(label="Clear Output", command=self.clear_out)
        self._edit_menu.add_separator()
        self._auto_clear_clip = tk.BooleanVar(value=False)
        self._edit_menu.add_checkbutton(label="Auto-clear clipboard (60s)", variable=self._auto_clear_clip)
        menubar.add_cascade(label="Edit", menu=self._edit_menu)

        self._view_menu = tk.Menu(menubar, tearoff=0, bg=c["surface"], fg=c["text"])
        self._view_menu.add_command(label="Toggle Theme", command=self._toggle_theme, accelerator="Ctrl+T")
        self._view_menu.add_separator()
        self._view_menu.add_command(label="Maximize Window", command=self._maximize_window, accelerator="F11")
        self._view_menu.add_command(label="Restore Window Size", command=self._restore_window_size)
        menubar.add_cascade(label="View", menu=self._view_menu)

        self._help_menu = tk.Menu(menubar, tearoff=0, bg=c["surface"], fg=c["text"])
        self._help_menu.add_command(label="Shortcuts", command=self._show_shortcuts)
        self._help_menu.add_command(label="About", command=self._show_about)
        menubar.add_cascade(label="Help", menu=self._help_menu)

    # ── Error Handler ────────────────────────────────────────────

    def _install_error_handler(self) -> None:
        original = tk.Tk.report_callback_exception
        app_ref = self

        def _on_err(sr, et, ev, tb):
            entry = {"time": datetime.now().isoformat(), "type": et.__name__, "message": str(ev), "traceback": traceback.format_exception(et, ev, tb)}
            app_ref._error_log.append(entry)
            if len(app_ref._error_log) > 50:
                app_ref._error_log.pop(0)
            logger.error(f"Unhandled: {et.__name__}: {ev}")
            try:
                crash_path = CONFIG_DIR / f"crash_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                crash_path.write_text(app_ref._make_diag(), encoding="utf-8")
            except Exception:
                pass
            original(sr, et, ev, tb)

        tk.Tk.report_callback_exception = _on_err

    # ── Status Bar ───────────────────────────────────────────────

    def _build_status_bar(self) -> None:
        self._statusbar = ttk.Frame(self.root, style="StatusBar.TFrame")
        self._statusbar.pack(fill=tk.X, side=tk.BOTTOM)
        self._status_mode = ttk.Label(self._statusbar, text="\u2630 Builder", style="Status.TLabel")
        self._status_mode.pack(side=tk.LEFT, padx=6, pady=2)
        self._status_action = ttk.Label(self._statusbar, text="Ready", style="Status.TLabel")
        self._status_action.pack(side=tk.LEFT, padx=6, pady=2)
        self.token_label = ttk.Label(self._statusbar, text="~0 tokens", style="Status.TLabel")
        self.token_label.pack(side=tk.RIGHT, padx=6, pady=2)

    def _set_status(self, text: str) -> None:
        self._status_action.config(text=text)
        if self._status_clear_id:
            self.root.after_cancel(self._status_clear_id)
        self._status_clear_id = self.root.after(5000, lambda: self._status_action.config(text="Ready"))

    # ── Toast ────────────────────────────────────────────────────

    def _toast(self, message: str, duration: int = 3000) -> None:
        if self._toast_window:
            try:
                self._toast_window.destroy()
            except tk.TclError:
                pass
        c = self._active_colors()
        tw = tk.Toplevel(self.root)
        tw.wm_overrideredirect(True)
        tw.wm_attributes("-topmost", True)
        rx = self.root.winfo_rootx() + (self.root.winfo_width() - 240) // 2
        ry = self.root.winfo_rooty() + self.root.winfo_height() - 50
        tw.wm_geometry(f"240x36+{rx}+{ry}")
        frm = tk.Frame(tw, bg=c["green"], padx=8, pady=6)
        frm.pack(fill=tk.BOTH, expand=True)
        tk.Label(frm, text=message, bg=c["green"], fg=c["dark"], font=FONT_SM).pack(side=tk.LEFT)
        close_lbl = tk.Label(frm, text="\u2715", bg=c["green"], fg=c["dark"], font=FONT_SM, cursor="hand2")
        close_lbl.pack(side=tk.RIGHT)
        close_lbl.bind("<Button-1>", lambda e: tw.destroy())
        self._toast_window = tw
        self.root.after(duration, lambda: self._destroy_toast(tw))

    def _destroy_toast(self, tw):
        try:
            tw.destroy()
        except tk.TclError:
            pass
        if self._toast_window is tw:
            self._toast_window = None

    # ── UI ───────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        main = ttk.Frame(self.root, padding=8)
        main.pack(fill=tk.BOTH, expand=True)
        hdr = ttk.Frame(main)
        hdr.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(hdr, text=f"\u2726 PROMPT ARCHITECT (Pi)", style="Header.TLabel").pack(side=tk.LEFT)

        self.notebook = ttk.Notebook(main)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        self.notebook.bind("<<NotebookTabChanged>>", lambda e: self._status_mode.config(text=self.notebook.tab(self.notebook.select(), "text").strip()))

        builder = ttk.Frame(self.notebook, padding=6)
        self.notebook.add(builder, text=" \u2692 Builder ")
        paned = ttk.PanedWindow(builder, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)

        lo = ttk.Frame(paned)
        paned.add(lo, weight=1)
        c = self._active_colors()
        self._left_canvas = tk.Canvas(lo, bg=c["bg"], highlightthickness=0)
        ls = ttk.Scrollbar(lo, orient=tk.VERTICAL, command=self._left_canvas.yview)
        self.lf = ttk.Frame(self._left_canvas)
        self.lf.bind("<Configure>", lambda e: self._left_canvas.configure(scrollregion=self._left_canvas.bbox("all")))
        self._left_canvas.create_window((0, 0), window=self.lf, anchor="nw")
        self._left_canvas.configure(yscrollcommand=ls.set)
        self._left_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        ls.pack(side=tk.RIGHT, fill=tk.Y)
        self._left_canvas.bind_all("<MouseWheel>", lambda e: self._left_canvas.yview_scroll(int(-1*(e.delta/120)), "units"))
        self._left_canvas.bind_all("<Button-4>", lambda e: self._left_canvas.yview_scroll(-3, "units"))
        self._left_canvas.bind_all("<Button-5>", lambda e: self._left_canvas.yview_scroll(3, "units"))

        self._build_targets_ui(self.lf)
        self._build_enhancements_ui(self.lf)
        self._build_role_ui(self.lf)
        self._build_reasoning_ui(self.lf)
        self._build_format_ui(self.lf)
        self._build_constraints_ui(self.lf)
        self._build_context_ui(self.lf)
        self._build_task_ui(self.lf)
        self._build_buttons_ui(self.lf)

        rt = ttk.Frame(paned)
        paned.add(rt, weight=1)
        rf = ttk.LabelFrame(rt, text=" Generated Prompt ", padding=6)
        rf.pack(fill=tk.BOTH, expand=True)
        self.result = scrolledtext.ScrolledText(rf, bg=c["overlay"], fg=c["yellow"], insertbackground="white", font=FONT_MN, wrap=tk.WORD, relief=tk.FLAT, padx=6, pady=6)
        self.result.pack(fill=tk.BOTH, expand=True)
        self.result.bind("<<Modified>>", self._on_mod)

        tmpl = ttk.Frame(self.notebook, padding=6)
        self.notebook.add(tmpl, text=" \u2630 Templates ")
        self._build_templates_ui(tmpl)

        hist = ttk.Frame(self.notebook, padding=6)
        self.notebook.add(hist, text=" \u23f0 History ")
        self._build_history_ui(hist)

        diag_tab = ttk.Frame(self.notebook, padding=6)
        self.notebook.add(diag_tab, text=" \u2695 Diag ")
        self._build_diag_ui(diag_tab)

    # ── Builder sections ─────────────────────────────────────────

    def _build_targets_ui(self, p):
        f = ttk.LabelFrame(p, text=" What Are You Building? ", padding=6)
        f.pack(fill=tk.X, pady=(0, 4))
        self.bt_var = tk.StringVar(value="(none)")
        ttk.Radiobutton(f, text="Nothing specific", variable=self.bt_var, value="(none)").pack(anchor=tk.W)
        for name, data in BUILD_TARGETS.items():
            ttk.Radiobutton(f, text=name, variable=self.bt_var, value=name).pack(anchor=tk.W)
            ttk.Label(f, text=data["description"], style="Desc.TLabel", wraplength=400).pack(anchor=tk.W, padx=(24, 0), pady=(0, 4))

    def _build_enhancements_ui(self, p):
        f = ttk.LabelFrame(p, text=" Improvements (pick any) ", padding=6)
        f.pack(fill=tk.X, pady=4)
        self.enh_vars: dict[str, tk.BooleanVar] = {}
        for name, data in ENHANCEMENTS.items():
            var = tk.BooleanVar(value=False)
            self.enh_vars[name] = var
            ttk.Checkbutton(f, text=name, variable=var).pack(anchor=tk.W)
            ttk.Label(f, text=data["description"], style="Desc.TLabel", wraplength=400).pack(anchor=tk.W, padx=(24, 0), pady=(0, 4))

    def _build_role_ui(self, p):
        f = ttk.LabelFrame(p, text=" Role ", padding=6)
        f.pack(fill=tk.X, pady=4)
        self.role_input = ttk.Entry(f, font=FONT)
        self.role_input.pack(fill=tk.X)

    def _build_reasoning_ui(self, p):
        f = ttk.LabelFrame(p, text=" Thinking Style ", padding=6)
        f.pack(fill=tk.X, pady=4)
        self.reason_var = tk.StringVar(value="Structured Chain of Thought (SCoT)")
        opts = list(REASONING_MODES.keys())
        ttk.OptionMenu(f, self.reason_var, opts[1], *opts, command=self._on_reason).pack(fill=tk.X)
        self.reason_desc = ttk.Label(f, text=REASONING_MODES[opts[1]]["description"], style="Desc.TLabel", wraplength=420)
        self.reason_desc.pack(anchor=tk.W, pady=(3, 0))

    def _on_reason(self, v):
        self.reason_desc.config(text=REASONING_MODES.get(v, {}).get("description", ""))

    def _build_format_ui(self, p):
        f = ttk.LabelFrame(p, text=" Output Format ", padding=6)
        f.pack(fill=tk.X, pady=4)
        self.fmt_var = tk.StringVar(value="Free-form")
        opts = list(OUTPUT_FORMATS.keys())
        ttk.OptionMenu(f, self.fmt_var, opts[0], *opts, command=self._on_fmt).pack(fill=tk.X)
        self.fmt_desc = ttk.Label(f, text=OUTPUT_FORMATS["Free-form"]["description"], style="Desc.TLabel", wraplength=420)
        self.fmt_desc.pack(anchor=tk.W, pady=(3, 0))

    def _on_fmt(self, v):
        self.fmt_desc.config(text=OUTPUT_FORMATS.get(v, {}).get("description", ""))

    def _build_constraints_ui(self, p):
        f = ttk.LabelFrame(p, text=" Quality Rules ", padding=6)
        f.pack(fill=tk.X, pady=4)
        self.con_vars: dict[str, tk.BooleanVar] = {}
        for name, data in CONSTRAINT_PRESETS.items():
            var = tk.BooleanVar(value=(name in ("Conciseness", "Python Best Practices")))
            self.con_vars[name] = var
            row = ttk.Frame(f)
            row.pack(fill=tk.X)
            ttk.Checkbutton(row, text=name, variable=var).pack(side=tk.LEFT)
            ttk.Label(row, text=f"  {data['description']}", style="Desc.TLabel").pack(side=tk.LEFT)
        c = self._active_colors()
        self.custom_con = tk.Text(f, height=2, bg=c["surface"], fg=c["text"], insertbackground="white", font=FONT_MS, relief=tk.FLAT, padx=4, pady=4, undo=True, maxundo=-1)
        self.custom_con.pack(fill=tk.X)
        self._themed_texts.append(self.custom_con)

    def _build_context_ui(self, p):
        f = ttk.LabelFrame(p, text=" Extra Context ", padding=6)
        f.pack(fill=tk.X, pady=4)
        top_row = ttk.Frame(f)
        top_row.pack(fill=tk.X, pady=(0, 3))
        ttk.Label(top_row, text="\u26a0 Do not paste API keys or passwords here.", style="Warn.TLabel").pack(side=tk.LEFT)
        c = self._active_colors()
        ctx_clr = tk.Button(top_row, text="\u2715 Clear", command=self._clear_context, bg=c["surface"], fg=c["red"], font=("DejaVu Sans", 8), relief=tk.FLAT, padx=4, pady=1, cursor="hand2")
        ctx_clr.pack(side=tk.RIGHT)
        self._themed_buttons.append((ctx_clr, "surface", "surface"))
        self.ctx = tk.Text(f, height=2, bg=c["surface"], fg=c["text"], insertbackground="white", font=FONT_MS, relief=tk.FLAT, padx=4, pady=4, undo=True, maxundo=-1)
        self.ctx.pack(fill=tk.BOTH, expand=True)
        self._themed_texts.append(self.ctx)

    def _build_task_ui(self, p):
        f = ttk.LabelFrame(p, text=" Task Description ", padding=6)
        f.pack(fill=tk.X, pady=4)
        top_row = ttk.Frame(f)
        top_row.pack(fill=tk.X, pady=(0, 3))
        ttk.Label(top_row, text="What should the AI do? More detail = better.", style="Sub.TLabel").pack(side=tk.LEFT)
        c = self._active_colors()
        task_clr = tk.Button(top_row, text="\u2715 Clear", command=self._clear_task, bg=c["surface"], fg=c["red"], font=("DejaVu Sans", 8), relief=tk.FLAT, padx=4, pady=1, cursor="hand2")
        task_clr.pack(side=tk.RIGHT)
        self._themed_buttons.append((task_clr, "surface", "surface"))
        self.task = scrolledtext.ScrolledText(f, height=4, bg=c["surface"], fg=c["text"], insertbackground="white", font=FONT_MN, wrap=tk.WORD, relief=tk.FLAT, padx=4, pady=4, undo=True, maxundo=-1)
        self.task.pack(fill=tk.BOTH, expand=True)
        self.task.insert(tk.END, "Create a Python script that reads a DHT22 sensor and logs temperature to a CSV every 10 seconds.")
        self._themed_texts.append(self.task)

    def _build_buttons_ui(self, p):
        f = ttk.Frame(p)
        f.pack(fill=tk.X, pady=(6, 2))
        c = self._active_colors()
        for t, ck, cmd, tip in [
            ("\u25b6 GENERATE", "green", self.generate, "Build prompt (Ctrl+Enter)"),
            ("\u2398 COPY", "blue", self.copy_clip, "Copy to clipboard (Ctrl+Shift+C)"),
            ("\u2b07 SAVE", "peach", self.save_file, "Save to file (Ctrl+S)"),
            ("\u21ba INPUTS", "yellow", self.clear_inputs, "Clear task + context (keep settings)"),
            ("\u2715 OUTPUT", "red", self.clear_out, "Clear generated prompt"),
        ]:
            btn = tk.Button(f, text=t, command=cmd, bg=c[ck], fg=c["dark"], font=FONT_BT, relief=tk.FLAT, padx=12, pady=5, cursor="hand2")
            btn.pack(side=tk.LEFT, padx=(0, 4))
            self._themed_buttons.append((btn, ck, ck))
            hover = _lighten_color(c[ck])
            btn.bind("<Enter>", lambda e, b=btn, hc=hover: b.config(bg=hc))
            btn.bind("<Leave>", lambda e, b=btn, k=ck: b.config(bg=self._active_colors()[k]))
            self._tooltips.append(ToolTip(btn, tip, c))

    # ── Templates ────────────────────────────────────────────────

    def _build_templates_ui(self, p):
        c = self._active_colors()
        top = ttk.Frame(p)
        top.pack(fill=tk.X, pady=(0, 6))
        for t, ck, cmd in [("SAVE", "peach", self._save_t), ("LOAD", "blue", self._load_t), ("DELETE", "red", self._del_t)]:
            btn = tk.Button(top, text=t, command=cmd, bg=c[ck], fg=c["dark"], font=FONT_BT, relief=tk.FLAT, padx=10, pady=5)
            btn.pack(side=tk.LEFT, padx=(0, 4))
            self._themed_buttons.append((btn, ck, ck))
        self.tl = tk.Listbox(p, bg=c["surface"], fg=c["text"], font=FONT_MN, selectbackground=c["blue"], selectforeground=c["dark"], relief=tk.FLAT)
        self.tl.pack(fill=tk.BOTH, expand=True)
        self._refresh_t()

    def _refresh_t(self):
        self.tl.delete(0, tk.END)
        tdir = Path(TEMPLATES_DIR)
        if tdir.is_dir():
            for fp in sorted(tdir.iterdir()):
                if fp.suffix == ".json":
                    self.tl.insert(tk.END, fp.stem)

    def _safe_template_path(self, name: str) -> Path:
        safe = re.sub(r'[^\w\- ]', '', name).strip()
        if not safe:
            raise ValueError("Invalid template name")
        tdir = Path(TEMPLATES_DIR).resolve()
        path = (tdir / f"{safe}.json").resolve()
        if not str(path).startswith(str(tdir)):
            raise ValueError("Path traversal detected")
        return path

    def _validate_template(self, data) -> tuple[bool, str]:
        if not isinstance(data, dict):
            return False, "Not a JSON object"
        for key in TEMPLATE_SCHEMA_KEYS:
            if key not in data:
                return False, f"Missing key: {key}"
        return True, ""

    def _save_t(self):
        name = self._ask("Template Name", "Name:")
        if not name:
            return
        try:
            path = self._safe_template_path(name)
        except ValueError as e:
            messagebox.showwarning("Invalid", str(e))
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self._collect(), f, indent=2)
            self._refresh_t()
            self._toast(f"'{path.stem}' saved")
            logger.info(f"Template saved: {path.stem}")
        except OSError as e:
            messagebox.showerror("Error", e.strerror or str(e))

    def _load_t(self):
        sel = self.tl.curselection()
        if not sel:
            messagebox.showwarning("Select", "Pick a template.")
            return
        name = self.tl.get(sel[0])
        try:
            path = self._safe_template_path(name)
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (ValueError, OSError, json.JSONDecodeError) as e:
            messagebox.showerror("Error", str(e))
            return
        valid, msg = self._validate_template(data)
        if not valid:
            messagebox.showerror("Invalid Template", msg)
            return
        self._apply(data)
        self._toast(f"'{name}' loaded")
        logger.info(f"Template loaded: {name}")

    def _del_t(self):
        sel = self.tl.curselection()
        if not sel:
            return
        name = self.tl.get(sel[0])
        if messagebox.askyesno("Confirm", f"Delete '{name}'?"):
            try:
                self._safe_template_path(name).unlink(missing_ok=True)
                self._refresh_t()
                self._toast(f"'{name}' deleted")
                logger.info(f"Template deleted: {name}")
            except (ValueError, OSError) as e:
                messagebox.showerror("Error", str(e))

    def _collect(self) -> dict:
        return {
            "build_target": self.bt_var.get(),
            "enhancements": {k: v.get() for k, v in self.enh_vars.items()},
            "role": self.role_input.get(), "reasoning": self.reason_var.get(),
            "output_format": self.fmt_var.get(),
            "constraints": {k: v.get() for k, v in self.con_vars.items()},
            "custom_constraints": self.custom_con.get("1.0", tk.END).strip(),
            "context": self.ctx.get("1.0", tk.END).strip(),
            "task": self.task.get("1.0", tk.END).strip(),
        }

    def _apply(self, d: dict):
        self.bt_var.set(d.get("build_target", "(none)"))
        for k, v in d.get("enhancements", {}).items():
            if k in self.enh_vars:
                self.enh_vars[k].set(v)
        self.role_input.delete(0, tk.END)
        self.role_input.insert(0, d.get("role", ""))
        self.reason_var.set(d.get("reasoning", "None"))
        self.fmt_var.set(d.get("output_format", "Free-form"))
        for k, v in d.get("constraints", {}).items():
            if k in self.con_vars:
                self.con_vars[k].set(v)
        self.custom_con.delete("1.0", tk.END)
        self.custom_con.insert("1.0", d.get("custom_constraints", ""))
        self.ctx.delete("1.0", tk.END)
        self.ctx.insert("1.0", d.get("context", ""))
        self.task.delete("1.0", tk.END)
        self.task.insert("1.0", d.get("task", ""))

    # ── History ──────────────────────────────────────────────────

    def _build_history_ui(self, p):
        c = self._active_colors()
        sf = ttk.Frame(p)
        sf.pack(fill=tk.X, pady=(0, 4))
        self._hist_search = ttk.Entry(sf, font=FONT_SM)
        self._hist_search.pack(fill=tk.X, expand=True)
        self._hist_search.bind("<KeyRelease>", self._filter_hist)

        top = ttk.Frame(p)
        top.pack(fill=tk.X, pady=(0, 6))
        for t, ck, cmd in [("LOAD", "blue", self._load_h), ("EXPORT", "peach", self._export_h), ("CLEAR", "red", self._clear_h)]:
            btn = tk.Button(top, text=t, command=cmd, bg=c[ck], fg=c["dark"], font=FONT_BT, relief=tk.FLAT, padx=10, pady=5)
            btn.pack(side=tk.LEFT, padx=(0, 4))
            self._themed_buttons.append((btn, ck, ck))
        self.hl = tk.Listbox(p, bg=c["surface"], fg=c["text"], font=FONT_MN, selectbackground=c["blue"], selectforeground=c["dark"], relief=tk.FLAT)
        self.hl.pack(fill=tk.BOTH, expand=True)

    def _filter_hist(self, event=None):
        q = self._hist_search.get().strip().lower()
        self.hl.delete(0, tk.END)
        for e in self.history:
            p = e.get("task_preview", "")
            if not q or q in p.lower():
                self.hl.insert(tk.END, f"[{e['timestamp']}] {p}")

    def _load_h(self):
        sel = self.hl.curselection()
        if not sel:
            return
        dt = self.hl.get(sel[0])
        for e in self.history:
            if f"[{e['timestamp']}] {e['task_preview']}" == dt:
                self.result.delete("1.0", tk.END)
                self.result.insert(tk.END, e["prompt"])
                self.notebook.select(0)
                self._set_status("Loaded from history")
                return

    def _clear_h(self):
        if messagebox.askyesno("Confirm", "Clear all history?"):
            self.history.clear()
            self.hl.delete(0, tk.END)
            self._save_history_to_disk()

    def _export_h(self):
        if not self.history:
            messagebox.showwarning("Empty", "No history.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON", "*.json")])
        if path:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(self.history, f, indent=2)
                self._toast(f"Exported {len(self.history)} entries")
            except OSError as e:
                messagebox.showerror("Error", e.strerror or str(e))

    # ── Diagnostics ──────────────────────────────────────────────

    def _build_diag_ui(self, p):
        ttk.Label(p, text="Generate a health report and save to Desktop.", style="Sub.TLabel").pack(anchor=tk.W, pady=(0, 6))
        c = self._active_colors()
        bf = ttk.Frame(p)
        bf.pack(fill=tk.X, pady=(0, 6))
        for t, ck, cmd in [("\u2695 RUN DIAGNOSTICS", "teal", self._run_diag), ("\u2398 COPY", "blue", self._copy_diag)]:
            btn = tk.Button(bf, text=t, command=cmd, bg=c[ck], fg=c["dark"], font=FONT_BT, relief=tk.FLAT, padx=14, pady=6)
            btn.pack(side=tk.LEFT, padx=(0, 4))
            self._themed_buttons.append((btn, ck, ck))
        self.diag = scrolledtext.ScrolledText(p, bg=c["overlay"], fg=c["green"], font=FONT_MS, wrap=tk.WORD, relief=tk.FLAT, padx=6, pady=6)
        self.diag.pack(fill=tk.BOTH, expand=True)

    def _make_diag(self) -> str:
        start = time.time()
        sep = "=" * 60
        lines = [sep, f"  {DIAG_VERSION} -- Diagnostic Report", f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", sep, "",
                 "  No passwords or API keys are included in this report.", ""]

        lines.append(f"{sep}\n  1. SYSTEM INFO\n{sep}")
        lines.append(f"  OS: {platform.system()} {platform.release()}")
        lines.append(f"  Arch: {platform.machine()}")
        lines.append(f"  Python: {sys.version.split()[0]}")
        lines.append(f"  Tk: {tk.TkVersion}")
        try:
            lines.append(f"  Screen: {self.root.winfo_screenwidth()}x{self.root.winfo_screenheight()}")
        except tk.TclError:
            pass
        lines.append(f"  Uptime: {datetime.now() - self._startup_time}")
        lines.append(f"  Theme: {'Dark' if self._dark_mode else 'Light'}")

        is_pi = os.path.exists("/sys/firmware/devicetree/base/model")
        if is_pi:
            try:
                with open("/sys/firmware/devicetree/base/model") as mf:
                    lines.append(f"  Pi Model: {mf.read().strip()}")
            except (OSError, IOError):
                lines.append("  Pi Model: (detected but unreadable)")
            try:
                with open("/proc/device-tree/serial-number") as sf:
                    lines.append(f"  Pi Serial: {sf.read().strip()}")
            except (OSError, IOError):
                pass
        lines.append("")

        lines.append(f"{sep}\n  2. ERRORS ({len(self._error_log)})\n{sep}")
        if not self._error_log:
            lines.append("  No errors this session.")
        for e in self._error_log[-10:]:
            lines.append(f"  [{e['time']}] {e['type']}: {e['message']}")
        lines.append("")

        lines.append(f"{sep}\n  3. PERFORMANCE\n{sep}")
        try:
            import psutil
            lines.append(f"  Memory: {psutil.Process(os.getpid()).memory_info().rss/1024/1024:.1f} MB")
        except ImportError:
            lines.append("  Memory: install psutil for details")
        lines.append("")

        lines.append(f"{sep}\n  4. NETWORK\n{sep}")
        try:
            import urllib.request
            urllib.request.urlopen("https://httpbin.org/get", timeout=5)
            lines.append("  [OK]   Internet connectivity")
        except Exception as e:
            lines.append(f"  [FAIL] Internet: {type(e).__name__}")
        lines.append("")

        lines.append(f"{sep}\n  5. DISK & FILES\n{sep}")
        try:
            usage = shutil.disk_usage(Path.home())
            lines.append(f"  Total: {usage.total / (1024**3):.1f} GB")
            lines.append(f"  Free:  {usage.free / (1024**3):.1f} GB")
        except Exception as e:
            lines.append(f"  Disk: {e}")
        tdir = Path(TEMPLATES_DIR)
        if tdir.is_dir():
            templates = list(tdir.glob("*.json"))
            lines.append(f"  Templates: {len(templates)}")
        if LOG_FILE.exists():
            lines.append(f"  Log: {LOG_FILE.stat().st_size / 1024:.1f} KB")
        lines.append("")

        elapsed = time.time() - start
        lines.append(f"  Generated in {elapsed:.2f}s")
        lines.append(sep)
        return "\n".join(lines)

    def _run_diag(self):
        rpt = self._make_diag()
        self.diag.delete("1.0", tk.END)
        self.diag.insert(tk.END, rpt)
        fp = (Path.home() / "Desktop" if (Path.home() / "Desktop").is_dir() else Path.home()) / f"prompt_architect_pi_diag_{datetime.now().strftime('%Y-%m-%d_%H%M%S')}.txt"
        try:
            fp.write_text(rpt, encoding="utf-8")
            self._toast("Report saved")
            self._set_status(f"Saved: {fp.name}")
            logger.info(f"Diagnostics saved: {fp}")
        except OSError as e:
            messagebox.showerror("Error", e.strerror or str(e))

    def _copy_diag(self):
        t = self.diag.get("1.0", tk.END).strip()
        if not t:
            self._run_diag()
            t = self.diag.get("1.0", tk.END).strip()
        if t:
            try:
                self.root.clipboard_clear()
                self.root.clipboard_append(t)
                self._toast("Copied")
            except tk.TclError:
                messagebox.showerror("Error", "Clipboard access failed.")

    # ══════════════════════════════════════════════════════════════
    # GENERATION
    # ══════════════════════════════════════════════════════════════

    def generate(self):
        task_text = self.task.get("1.0", tk.END).strip()
        if not task_text:
            messagebox.showwarning("Missing", "Enter a task.")
            return
        if len(task_text.encode("utf-8")) > INPUT_LIMITS["task"]:
            messagebox.showwarning("Too Large", "Task exceeds 50 KB.")
            return

        all_types: list[dict] = []
        bt = self.bt_var.get()
        if bt != "(none)" and bt in BUILD_TARGETS:
            all_types.append(BUILD_TARGETS[bt])
        for name, var in self.enh_vars.items():
            if var.get() and name in ENHANCEMENTS:
                all_types.append(ENHANCEMENTS[name])

        sections: list[str] = []
        user_role = self.role_input.get().strip()
        if user_role:
            sections.append(f"# ROLE\nYou are: {user_role}.")
        elif all_types:
            sections.append(f"# ROLE\nYou are: {' AND '.join(t['role'] for t in all_types)}.")

        sections.append(f"# TASK\n{task_text}")
        for t in all_types:
            pc = t.get("platform_context", "")
            if pc:
                sections.append(f"# PLATFORM & ENVIRONMENT\n{pc}")

        ctx = self.ctx.get("1.0", tk.END).strip()
        if ctx:
            sections.append(f"# ADDITIONAL CONTEXT\n{ctx}")

        blk = REASONING_MODES.get(self.reason_var.get(), {}).get("block", "")
        if blk:
            sections.append(f"# REASONING\n{blk}")

        fmt = OUTPUT_FORMATS.get(self.fmt_var.get(), {}).get("block", "")
        if fmt:
            sections.append(f"# OUTPUT FORMAT\n{fmt}")

        cons: list[str] = []
        for name, var in self.con_vars.items():
            if var.get():
                cons.extend(CONSTRAINT_PRESETS[name]["rules"])
        cust = self.custom_con.get("1.0", tk.END).strip()
        if cust:
            cons.extend(l.strip() for l in cust.splitlines() if l.strip())
        for t in all_types:
            cons.extend(t.get("extra_constraints", []))
        seen: set[str] = set()
        unique = [c for c in cons if c not in seen and not seen.add(c)]
        if unique:
            sections.append("# CONSTRAINTS\n" + "\n".join(f"- {c}" for c in unique))

        sections.append("# QUALITY GATE\n1. All TASK requirements addressed.\n2. All CONSTRAINTS satisfied.\n3. Code runs without errors.\n4. Edge cases handled.\n5. No placeholder TODOs left behind.")

        final = "\n\n".join(sections)
        self.result.delete("1.0", tk.END)
        self.result.insert(tk.END, final)
        self._upd_tok(final)

        labels = ([bt] if bt != "(none)" else []) + [k for k, v in self.enh_vars.items() if v.get()]
        entry = {"timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "task_preview": f"[{'+'.join(labels) or 'Manual'}] {task_text[:40]}...", "prompt": final}
        self.history.append(entry)
        if len(self.history) > MAX_HISTORY:
            self.history.pop(0)
            self.hl.delete(0)
        self.hl.insert(tk.END, f"[{entry['timestamp']}] {entry['task_preview']}")
        self._save_history_to_disk()
        self._toast("Prompt generated!")
        self._set_status(f"Generated (~{len(final)//4:,} tokens)")
        logger.info(f"Generated: {'+'.join(labels) or 'Manual'}, {len(final)} chars")

    # ── Actions ──────────────────────────────────────────────────

    def copy_clip(self):
        c = self.result.get("1.0", tk.END).strip()
        if not c:
            messagebox.showwarning("Empty", "Generate first.")
            return
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(c)
            self._toast("Copied")
            if self._auto_clear_clip.get():
                if self._clipboard_clear_id:
                    self.root.after_cancel(self._clipboard_clear_id)
                self._clipboard_clear_id = self.root.after(60000, lambda: self.root.clipboard_clear())
        except tk.TclError:
            messagebox.showerror("Error", "Clipboard access failed.")

    def save_file(self):
        c = self.result.get("1.0", tk.END).strip()
        if not c:
            messagebox.showwarning("Empty", "Generate first.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text", "*.txt"), ("All", "*.*")])
        if path:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(c)
                self._toast(f"Saved: {Path(path).name}")
                logger.info(f"Output saved: {Path(path).name}")
            except OSError as e:
                messagebox.showerror("Error", e.strerror or str(e))

    def clear_out(self):
        self.result.delete("1.0", tk.END)
        self._upd_tok("")

    def clear_inputs(self):
        """Clear task + context, keep all settings."""
        self.task.delete("1.0", tk.END)
        self.ctx.delete("1.0", tk.END)
        self._toast("Inputs cleared \u2014 settings preserved")

    def _clear_task(self):
        self.task.delete("1.0", tk.END)
        self._toast("Task cleared")

    def _clear_context(self):
        self.ctx.delete("1.0", tk.END)
        self._toast("Context cleared")

    def _on_mod(self, e):
        self.result.edit_modified(False)
        self._upd_tok(self.result.get("1.0", tk.END))

    def _upd_tok(self, t):
        self.token_label.config(text=f"~{max(0, len(t)//4):,} tokens")

    # ── Undo/Redo ────────────────────────────────────────────────

    def _undo(self):
        w = self.root.focus_get()
        if isinstance(w, tk.Text):
            try:
                w.edit_undo()
            except tk.TclError:
                pass

    def _redo(self):
        w = self.root.focus_get()
        if isinstance(w, tk.Text):
            try:
                w.edit_redo()
            except tk.TclError:
                pass

    # ── Persistence ──────────────────────────────────────────────

    def _start_autosave(self):
        self._do_autosave()

    def _do_autosave(self):
        try:
            state = self._collect()
            s = json.dumps(state, sort_keys=True)
            h = hashlib.md5(s.encode()).hexdigest()
            if h != self._autosave_hash:
                CONFIG_DIR.mkdir(parents=True, exist_ok=True)
                with open(AUTOSAVE_FILE, "w", encoding="utf-8") as f:
                    f.write(s)
                self._autosave_hash = h
        except Exception as e:
            logger.warning(f"Auto-save failed: {e}")
        self.root.after(AUTOSAVE_INTERVAL_MS, self._do_autosave)

    def _load_autosave(self):
        if AUTOSAVE_FILE.exists():
            try:
                with open(AUTOSAVE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    valid, _ = self._validate_template(data)
                    if valid:
                        self._apply(data)
                        logger.info("Restored from autosave")
            except (OSError, json.JSONDecodeError) as e:
                logger.warning(f"Autosave load failed: {e}")

    def _save_history_to_disk(self):
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(self.history[-MAX_HISTORY:], f, indent=2)
        except Exception as e:
            logger.warning(f"History save failed: {e}")

    def _load_history_from_disk(self):
        if HISTORY_FILE.exists():
            try:
                with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    self.history = data[-MAX_HISTORY:]
                    for e in self.history:
                        if isinstance(e, dict) and "timestamp" in e:
                            self.hl.insert(tk.END, f"[{e['timestamp']}] {e.get('task_preview', '')}")
                    logger.info(f"Loaded {len(self.history)} history entries")
            except (OSError, json.JSONDecodeError) as e:
                logger.warning(f"History load failed: {e}")

    def _save_geometry(self):
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            state = ""
            try:
                state = self.root.state()
            except tk.TclError:
                pass
            if not state:
                try:
                    state = "zoomed" if self.root.attributes("-zoomed") else "normal"
                except tk.TclError:
                    pass
            data = {"geometry": self.root.geometry(), "state": state}
            with open(GEOMETRY_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f)
        except Exception:
            pass

    def _restore_geometry(self):
        if GEOMETRY_FILE.exists():
            try:
                with open(GEOMETRY_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                geo = data.get("geometry", "")
                state = data.get("state", "")
                if geo and re.match(r'\d+x\d+[+\-]\d+[+\-]\d+', geo):
                    self.root.geometry(geo)
                if state == "zoomed":
                    self.root.after(0, self._maximize_window)
                return
            except (OSError, json.JSONDecodeError):
                pass
        # First launch — maximize on larger screens; small Pi touchscreen fills naturally
        if self.root.winfo_screenwidth() > _PI_SMALL_SCREEN_WIDTH:
            self.root.after(0, self._maximize_window)

    def _maximize_window(self):
        """Maximize the window cross-platform."""
        try:
            if platform.system() == "Windows":
                self.root.state("zoomed")
            else:
                self.root.attributes("-zoomed", True)
        except tk.TclError:
            try:
                w = self.root.winfo_screenwidth()
                h = self.root.winfo_screenheight()
                self.root.geometry(f"{w}x{h}+0+0")
            except Exception:
                pass
        self._set_status("Window maximized")

    def _restore_window_size(self):
        """Restore the window from maximized to its normal size."""
        try:
            if platform.system() == "Windows":
                self.root.state("normal")
            else:
                self.root.attributes("-zoomed", False)
        except tk.TclError:
            pass
        self._set_status("Window restored")

    def _toggle_maximize(self):
        """Toggle between maximized and normal window state (F11)."""
        system = platform.system()
        try:
            if system == "Windows":
                if self.root.state() == "zoomed":
                    self._restore_window_size()
                else:
                    self._maximize_window()
            else:
                currently_zoomed = False
                try:
                    currently_zoomed = bool(self.root.attributes("-zoomed"))
                except tk.TclError:
                    pass
                if currently_zoomed:
                    self._restore_window_size()
                else:
                    self._maximize_window()
        except tk.TclError:
            pass

    # ── Session ──────────────────────────────────────────────────

    def _new_session(self):
        self.bt_var.set("(none)")
        for v in self.enh_vars.values():
            v.set(False)
        self.role_input.delete(0, tk.END)
        self.reason_var.set("Structured Chain of Thought (SCoT)")
        self.fmt_var.set("Free-form")
        for n, v in self.con_vars.items():
            v.set(n in ("Conciseness", "Python Best Practices"))
        self.custom_con.delete("1.0", tk.END)
        self.ctx.delete("1.0", tk.END)
        self.task.delete("1.0", tk.END)
        self.result.delete("1.0", tk.END)
        self._upd_tok("")
        self._set_status("New session")

    def _on_close(self):
        self._save_geometry()
        self._do_autosave()
        self.root.destroy()

    # ── Helpers ──────────────────────────────────────────────────

    def _show_shortcuts(self):
        messagebox.showinfo("Shortcuts",
            "Ctrl+Enter     Generate\n"
            "Ctrl+Shift+C   Copy output\n"
            "Ctrl+S         Save\n"
            "Ctrl+D         Diagnostics\n"
            "Ctrl+N         New session\n"
            "Ctrl+T         Toggle theme\n"
            "Ctrl+Z         Undo\n"
            "Ctrl+Y         Redo\n"
            "Ctrl+A         Select all (in text fields)\n"
            "F11            Toggle maximize/restore window"
        )

    def _show_about(self):
        messagebox.showinfo("About", f"{APP_NAME} v{APP_VERSION}\n\nPython {sys.version.split()[0]}\nTk {tk.TkVersion}\n\nOptimized for Raspberry Pi")

    def _ask(self, title, prompt):
        c = self._active_colors()
        d = tk.Toplevel(self.root)
        d.title(title)
        d.geometry("320x120")
        d.configure(bg=c["bg"])
        d.transient(self.root)
        d.grab_set()
        ttk.Label(d, text=prompt).pack(padx=12, pady=(12, 4))
        e = ttk.Entry(d, font=FONT)
        e.pack(padx=12, fill=tk.X)
        e.focus_set()
        r = [None]
        def ok(ev=None):
            r[0] = e.get().strip()
            d.destroy()
        e.bind("<Return>", ok)
        tk.Button(d, text="OK", command=ok, bg=c["green"], fg=c["dark"], font=FONT_BT, relief=tk.FLAT, padx=16, pady=3).pack(pady=8)
        d.wait_window()
        return r[0]

    def _bind_shortcuts(self):
        self.root.bind("<Control-Return>", lambda e: self.generate())
        self.root.bind("<Control-Shift-C>", lambda e: self.copy_clip())
        self.root.bind("<Control-s>", lambda e: self.save_file())
        self.root.bind("<Control-d>", lambda e: self._run_diag())
        self.root.bind("<Control-n>", lambda e: self._new_session())
        self.root.bind("<Control-t>", lambda e: self._toggle_theme())
        self.root.bind("<Control-z>", lambda e: self._undo())
        self.root.bind("<Control-y>", lambda e: self._redo())
        self.root.bind("<F11>", lambda e: self._toggle_maximize())
        self._add_text_context_menus()

    def _add_text_context_menus(self):
        """Add right-click copy/cut/paste/select-all context menus to every text widget."""
        text_widgets = [self.task, self.ctx, self.custom_con]
        if hasattr(self, "result"):
            text_widgets.append(self.result)
        for widget in text_widgets:
            self._attach_text_menu(widget)
        entry_widgets = [self.role_input]
        if hasattr(self, "_history_search"):
            entry_widgets.append(self._history_search)
        for widget in entry_widgets:
            self._attach_entry_menu(widget)

    def _attach_text_menu(self, widget):
        """Attach a right-click context menu to a Text or ScrolledText widget."""
        c = self._active_colors()
        menu = tk.Menu(self.root, tearoff=0, bg=c["surface"], fg=c["text"],
                       activebackground=c["blue"], activeforeground=c["dark"],
                       font=FONT)

        def do_cut():
            try:
                sel = widget.selection_get()
                self.root.clipboard_clear()
                self.root.clipboard_append(sel)
                widget.delete(tk.SEL_FIRST, tk.SEL_LAST)
            except tk.TclError:
                pass

        def do_copy():
            try:
                sel = widget.selection_get()
                self.root.clipboard_clear()
                self.root.clipboard_append(sel)
            except tk.TclError:
                pass

        def do_paste():
            try:
                text = self.root.clipboard_get()
                try:
                    widget.delete(tk.SEL_FIRST, tk.SEL_LAST)
                except tk.TclError:
                    pass
                widget.insert(tk.INSERT, text)
            except tk.TclError:
                pass

        def do_select_all():
            widget.tag_add(tk.SEL, "1.0", tk.END)
            widget.mark_set(tk.INSERT, "1.0")

        def do_clear():
            widget.delete("1.0", tk.END)

        menu.add_command(label="Cut         Ctrl+X", command=do_cut)
        menu.add_command(label="Copy        Ctrl+C", command=do_copy)
        menu.add_command(label="Paste       Ctrl+V", command=do_paste)
        menu.add_separator()
        menu.add_command(label="Select All  Ctrl+A", command=do_select_all)
        menu.add_command(label="Clear", command=do_clear)

        widget.bind("<Button-3>", lambda e: menu.tk_popup(e.x_root, e.y_root))
        widget.bind("<Control-c>", lambda e: (do_copy(), "break")[-1])
        widget.bind("<Control-x>", lambda e: (do_cut(), "break")[-1])
        widget.bind("<Control-v>", lambda e: (do_paste(), "break")[-1])
        widget.bind("<Control-a>", lambda e: (do_select_all(), "break")[-1])

    def _attach_entry_menu(self, widget):
        """Attach a right-click context menu to an Entry or ttk.Entry widget."""
        c = self._active_colors()
        menu = tk.Menu(self.root, tearoff=0, bg=c["surface"], fg=c["text"],
                       activebackground=c["blue"], activeforeground=c["dark"],
                       font=FONT)

        def do_cut():
            try:
                sel = widget.selection_get()
                self.root.clipboard_clear()
                self.root.clipboard_append(sel)
                widget.delete(tk.SEL_FIRST, tk.SEL_LAST)
            except (tk.TclError, AttributeError):
                pass

        def do_copy():
            try:
                sel = widget.selection_get()
                self.root.clipboard_clear()
                self.root.clipboard_append(sel)
            except (tk.TclError, AttributeError):
                pass

        def do_paste():
            try:
                text = self.root.clipboard_get()
                try:
                    widget.delete(tk.SEL_FIRST, tk.SEL_LAST)
                except (tk.TclError, AttributeError):
                    pass
                widget.insert(tk.INSERT, text)
            except tk.TclError:
                pass

        def do_select_all():
            widget.select_range(0, tk.END)
            widget.icursor(tk.END)

        def do_clear():
            widget.delete(0, tk.END)

        menu.add_command(label="Cut         Ctrl+X", command=do_cut)
        menu.add_command(label="Copy        Ctrl+C", command=do_copy)
        menu.add_command(label="Paste       Ctrl+V", command=do_paste)
        menu.add_separator()
        menu.add_command(label="Select All  Ctrl+A", command=do_select_all)
        menu.add_command(label="Clear", command=do_clear)

        widget.bind("<Button-3>", lambda e: menu.tk_popup(e.x_root, e.y_root))


def main():
    parser = argparse.ArgumentParser(description=f"{APP_NAME} v{APP_VERSION}")
    parser.add_argument("--cli", action="store_true", help="Headless CLI mode")
    parser.add_argument("--target", default="", help="Build target preset name")
    parser.add_argument("--enhance", nargs="*", default=[], help="Enhancement names")
    parser.add_argument("--task", default="", help="Task description")
    parser.add_argument("--context", default="", help="Additional context")
    parser.add_argument("--reasoning", default="Structured Chain of Thought (SCoT)")
    parser.add_argument("-o", "--output", default="", help="Save to file")
    args = parser.parse_args()
    if args.cli:
        if not args.task:
            parser.error("--task required in CLI mode")
        cli_generate(args)
    else:
        root = tk.Tk()
        PromptArchitectPi(root)
        root.mainloop()


if __name__ == "__main__":
    main()

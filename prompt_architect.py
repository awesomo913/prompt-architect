import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import json
import os
import platform
import re
import sys
import hashlib
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
APP_VERSION = "4.0"
DIAG_VERSION = f"{APP_NAME} v{APP_VERSION}"

COLORS = {
    "bg": "#232634", "surface": "#3b3f58", "overlay": "#1e2030",
    "text": "#d9dce8", "subtext": "#b0b4c8", "blue": "#8caaee",
    "green": "#a6d189", "red": "#e78284", "peach": "#ef9f76",
    "mauve": "#c6a0f6", "yellow": "#e5c890", "teal": "#81c8be",
    "pink": "#f4b8e4", "dark": "#14151e",
}

COLORS_LIGHT = {
    "bg": "#f2f4f8", "surface": "#d8dce6", "overlay": "#ebeef5",
    "text": "#3b3f52", "subtext": "#5c6070", "blue": "#3070d0",
    "green": "#449a30", "red": "#c42b40", "peach": "#d97020",
    "mauve": "#7040c0", "yellow": "#b88018", "teal": "#1a8a80",
    "pink": "#d060a8", "dark": "#e0e4ee",
}

TEMPLATES_DIR = Path(os.path.dirname(os.path.abspath(__file__))) / "prompt_templates"
CONFIG_DIR = Path.home() / ".prompt_architect"
AUTOSAVE_FILE = CONFIG_DIR / "autosave.json"
HISTORY_FILE = CONFIG_DIR / "history.json"
GEOMETRY_FILE = CONFIG_DIR / "geometry.json"
LOG_FILE = CONFIG_DIR / "prompt_architect.log"
MAX_HISTORY = 500
AUTOSAVE_INTERVAL_MS = 60000
INPUT_LIMITS = {"task": 50 * 1024, "context": 100 * 1024, "custom_constraints": 10 * 1024}
TEMPLATE_SCHEMA_KEYS = {"build_target", "enhancements", "role", "reasoning",
                        "output_format", "constraints", "custom_constraints", "context", "task",
                        "prompt_category", "conv_style", "conv_tone",
                        "image_style", "image_lighting", "image_camera",
                        "video_style", "video_camera", "video_pacing"}


def _setup_logging() -> logging.Logger:
    """Initialize rotating file logger."""
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    log = logging.getLogger("prompt_architect")
    log.setLevel(logging.DEBUG)
    if not log.handlers:
        try:
            fh = RotatingFileHandler(
                str(LOG_FILE), maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
            )
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
    """Lightweight tooltip that follows the mouse on hover."""

    def __init__(self, widget: tk.Widget, text: str, colors: dict):
        self.widget = widget
        self.text = text
        self.colors = colors
        self.tipwindow: tk.Toplevel | None = None
        widget.bind("<Enter>", self._show, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _show(self, event: tk.Event = None) -> None:
        if self.tipwindow:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tw.wm_attributes("-topmost", True)
        label = tk.Label(
            tw, text=self.text, justify=tk.LEFT,
            background=self.colors["surface"], foreground=self.colors["text"],
            relief=tk.SOLID, borderwidth=1, font=("Segoe UI", 9),
            padx=8, pady=4, wraplength=300,
        )
        label.pack()
        self.tipwindow = tw

    def _hide(self, event: tk.Event = None) -> None:
        if self.tipwindow:
            self.tipwindow.destroy()
            self.tipwindow = None

    def update_colors(self, colors: dict) -> None:
        self.colors = colors


# ═══════════════════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════════════
# MY PROJECTS — Personal presets that inject YOUR specific patterns
# so you never have to re-explain your conventions to the AI.
# These get added BEFORE the prompt as a persistent context block.
# ═══════════════════════════════════════════════════════════════════

MY_PROJECTS = {
    "(None)": {
        "description": "No project preset. Use the generic options below.",
        "context_block": "",
        "token_savings": "",
        "path": "",
    },
    "GBA ROM Hack (pokeemerald C)": {
        "description": (
            "Your Pokemon Emerald redesign — C source modifications to pokeemerald decomp. "
            "Auto-includes struct formats, bracket parsing, marker patterns, build command, GBA globals."
        ),
        "context_block": (
            "PROJECT CONVENTIONS (follow without asking):\n"
            "- Build: cd pokeemerald && make EXE=.exe -j4\n"
            "- Trainer party structs: TrainerMonItemCustomMoves has .iv .lvl .species .heldItem .moves; "
            "TrainerMonNoItemDefaultMoves has only .iv .lvl .species. Detect which type before modifying.\n"
            "- Idempotency: Every mod MUST have a marker comment '// --- CUSTOM: NAME ---' and skip if already present.\n"
            "- Nested C structs: Use bracket-depth counters, NOT regex.\n"
            "- Two-pass pattern: Parse File A for data, then use that data while processing File B.\n"
            "- GBA globals (access directly, don't pass): gPlayerParty[], gEnemyParty[], gBattleTypeFlags, "
            "gBattlerPartyIndexes[], gPlayerPartyCount, gEnemyPartyCount, gEvolutionTable, gBattleMoves.\n"
            "- Hook injection: Write new function above hook point, string-replace to insert call. Provide fallback anchors.\n"
            "- Flags: #define FLAG (1 << N), combine with |, check with &.\n"
            "- JSON encounters: json.load/dump. C data: string manipulation or bracket parsing. Never mix.\n"
            "- Every mod function: print what it does, count changes, report results, warn on failures."
        ),
        "token_savings": (
            "pokeemerald C conventions. Key rules: TrainerMonItemCustomMoves=all fields; "
            "markers `// --- CUSTOM: ---` required; bracket-depth not regex; GBA globals direct; "
            "build `make EXE=.exe -j4`; JSON=wild encounters only."
        ),
        "path": "",
    },
    "EmeraldDevTool (CustomTkinter GUI)": {
        "description": (
            "Your GBA developer tool — 9-tab CustomTkinter desktop app. "
            "Auto-includes tab pattern, toast/log/export conventions, widget inventory, threading rules."
        ),
        "context_block": (
            "PROJECT CONVENTIONS (follow without asking):\n"
            "- Framework: CustomTkinter (import customtkinter as ctk). NEVER raw tkinter widgets.\n"
            "- Tab pattern: class Tab(ctk.CTkFrame) with __init__(master, backend_ref), _build_ui(), load_data(). "
            "Backend injected via constructor, never instantiated in tabs.\n"
            "- Notifications: ToastNotification(self, msg, toast_type='success|error|warning'). NEVER messagebox.\n"
            "- Logging: app_log('msg', level='SUCCESS', source='TabName'). Always include source=.\n"
            "- Export: export_to_txt(content, default_name='type_YYYYMMDD_HHMMSS.txt', parent=self).\n"
            "- Threading: Long ops on daemon thread, UI updates via self.after(0, callback). NEVER touch UI from threads.\n"
            "- Existing widgets (USE THEM): SectionFrame, HexViewer, PokemonSlotWidget, ToolTip, SearchableList, StatusBar, ToastNotification.\n"
            "- SearchableList: on_select(idx, name) callback. Max 500 items.\n"
            "- StatusBar: self.statusbar.set('section', 'text', color=None).\n"
            "- Theme: COLORS_DARK/COLORS_LIGHT from config.py. Segoe UI for labels, Consolas for monospace.\n"
            "- Error pattern: try/except -> toast error + app_log ERROR + return. Then toast success + app_log SUCCESS.\n"
            "- Shortcuts: Ctrl+1-9 tabs, Ctrl+S save, Ctrl+Q quit, F5 refresh. Don't conflict."
        ),
        "token_savings": (
            "EmeraldDevTool: CustomTkinter (ctk.*), tab pattern (backend_ref injected, _build_ui, load_data), "
            "ToastNotification not messagebox, app_log with source=, use existing widgets (SearchableList, StatusBar, "
            "HexViewer, PokemonSlotWidget), threading via self.after(0, cb)."
        ),
        "path": "",
    },
    "Android App (Kivy)": {
        "description": "Android mobile app using Kivy + Buildozer. Touch-first, Material-inspired.",
        "context_block": (
            "PROJECT CONVENTIONS:\n"
            "- Framework: Kivy. Touch-friendly: min 48dp targets, ScrollView everywhere.\n"
            "- Build: buildozer android debug. Min API 24.\n"
            "- Use Spinner for dropdowns, ToggleButton for radios/checks.\n"
            "- Clipboard via kivy.core.clipboard, Share via plyer.\n"
            "- Dark theme (Catppuccin Mocha colors)."
        ),
        "token_savings": (
            "Kivy + buildozer. 48dp touch targets, Spinner/ToggleButton, kivy.core.clipboard + plyer, dark theme."
        ),
        "path": "",
    },
    "Python AI Tool": {
        "description": "Standalone Python tools that interact with AI APIs, process data, or automate tasks.",
        "context_block": (
            "PROJECT CONVENTIONS:\n"
            "- Pure Python 3.11+, minimal dependencies.\n"
            "- Use pathlib for paths, json for config, logging with RotatingFileHandler.\n"
            "- API keys from env vars (os.environ), NEVER hardcoded.\n"
            "- Graceful error handling with retries for network calls.\n"
            "- If GUI: tkinter with ttk theming, dark mode, proper thread separation."
        ),
        "token_savings": (
            "Python 3.11+. pathlib/json/logging RotatingFileHandler. API keys via os.environ. "
            "Retries for network. tkinter+ttk dark mode if GUI."
        ),
        "path": "",
    },
    "General Script": {
        "description": "Quick Python scripts for automation, data processing, or utilities.",
        "context_block": (
            "PROJECT CONVENTIONS:\n"
            "- Python 3.11+. Use pathlib, argparse for CLI.\n"
            "- if __name__ == '__main__' guard. Type hints. Brief docstrings.\n"
            "- Print progress for long operations."
        ),
        "token_savings": "Python 3.11+, pathlib, argparse, __main__ guard, type hints, brief docstrings.",
        "path": "",
    },
}

def scan_projects_folder(root_path: Path, max_projects: int = 100) -> dict:
    """Auto-discover project folders under root_path.

    Returns a dict shaped like MY_PROJECTS where each discovered folder
    becomes an entry. A folder is considered a project if it contains any of:
    CLAUDE.md, README.md, requirements.txt, Makefile, package.json,
    pyproject.toml, buildozer.spec.

    Description = first non-empty line of CLAUDE.md or README.md.
    context_block = full CLAUDE.md (if present) or auto-generated stub from file types.
    token_savings = first 2-3 sentences of CLAUDE.md, else auto-stub.
    """
    discovered: dict = {}
    if not root_path or not root_path.is_dir():
        return discovered

    signals = ("CLAUDE.md", "README.md", "requirements.txt", "Makefile",
               "package.json", "pyproject.toml", "buildozer.spec")

    try:
        subdirs = sorted(p for p in root_path.iterdir() if p.is_dir())
    except (OSError, PermissionError):
        return discovered

    for subdir in subdirs:
        if subdir.name.startswith('.') or subdir.name.startswith('_'):
            continue
        if subdir.name in ("__pycache__", "node_modules", "venv", ".venv", "build", "dist"):
            continue

        # Check for at least one signal file
        signal_found = None
        for sig in signals:
            if (subdir / sig).exists():
                signal_found = sig
                break
        if not signal_found:
            continue

        # Read CLAUDE.md first, fall back to README.md
        desc_text = ""
        context = ""
        claude_md = subdir / "CLAUDE.md"
        readme_md = subdir / "README.md"

        try:
            if claude_md.exists():
                context = claude_md.read_text(encoding="utf-8", errors="ignore")[:8000]
            elif readme_md.exists():
                context = readme_md.read_text(encoding="utf-8", errors="ignore")[:4000]
        except (OSError, UnicodeDecodeError):
            context = ""

        # Extract description: first non-empty, non-heading line
        for line in context.splitlines():
            stripped = line.strip().lstrip("#").strip()
            if stripped and not stripped.startswith("!["):
                desc_text = stripped[:200]
                break
        if not desc_text:
            # Build stub from detected languages
            types = []
            if (subdir / "requirements.txt").exists() or (subdir / "pyproject.toml").exists():
                types.append("Python")
            if (subdir / "package.json").exists():
                types.append("Node.js")
            if (subdir / "Makefile").exists():
                types.append("C/Make")
            if (subdir / "buildozer.spec").exists():
                types.append("Kivy/Android")
            desc_text = f"{'/'.join(types) or 'Auto-discovered'} project at {subdir.name}"

        # Build token-saver stub
        token_stub = ""
        for line in context.splitlines():
            s = line.strip().lstrip("-*#").strip()
            if s and len(s) > 10:
                token_stub += s[:120] + " "
                if len(token_stub) > 280:
                    break
        if not token_stub:
            token_stub = desc_text[:200]

        discovered[subdir.name] = {
            "description": desc_text,
            "context_block": (
                f"PROJECT CONTEXT for '{subdir.name}' "
                f"(auto-discovered from {signal_found}):\n{context}"
            ) if context else f"PROJECT: {subdir.name}. No CLAUDE.md or README.md found.",
            "token_savings": f"Project '{subdir.name}': {token_stub.strip()}",
            "path": str(subdir),
        }

        if len(discovered) >= max_projects:
            break

    return discovered


# ═══════════════════════════════════════════════════════════════════
# MODEL CATALOG — Reference page for each AI service's models.
# Used by _recommend_model() to suggest the most efficient model for
# a given prompt's characteristics (size, complexity, category).
# This is a suggestion, not a forced setting — the tool just tells
# you which model you should select before you paste.
# ═══════════════════════════════════════════════════════════════════

MODEL_CATALOG: dict = {
    "Claude": {
        "docs_url": "https://docs.claude.com/en/docs/about-claude/models/overview",
        "tiers": {
            "cheap":    {"name": "Claude Haiku 4.5",  "context": 200_000, "input_per_million": 1.00,  "best_for": "quick edits, simple Q&A, chat, short code changes"},
            "balanced": {"name": "Claude Sonnet 4.5", "context": 200_000, "input_per_million": 3.00,  "best_for": "most coding, general reasoning, Agent SDK work, refactoring"},
            "premium":  {"name": "Claude Opus 4.5",   "context": 200_000, "input_per_million": 15.00, "best_for": "complex multi-step reasoning, large refactors, novel problems, agents"},
        },
    },
    "ChatGPT": {
        "docs_url": "https://platform.openai.com/docs/models",
        "tiers": {
            "cheap":    {"name": "GPT-5-mini",  "context": 400_000,   "input_per_million": 0.25, "best_for": "simple tasks, chat, quick summaries, cheap batch work"},
            "balanced": {"name": "GPT-5",       "context": 400_000,   "input_per_million": 2.50, "best_for": "general coding, multimodal (images), most daily prompts"},
            "premium":  {"name": "o3 / o4-pro", "context": 200_000,   "input_per_million": 15.00, "best_for": "hard reasoning, math, science, step-by-step logic, complex agents"},
        },
    },
    "Gemini": {
        "docs_url": "https://ai.google.dev/gemini-api/docs/models",
        "tiers": {
            "cheap":    {"name": "Gemini 2.5 Flash", "context": 1_000_000, "input_per_million": 0.10, "best_for": "simple tasks with big documents (1M context), cheap + fast"},
            "balanced": {"name": "Gemini 2.5 Pro",   "context": 2_000_000, "input_per_million": 1.25, "best_for": "huge codebases (2M context!), long doc analysis, RAG pipelines"},
            "premium":  {"name": "Gemini 2.5 Ultra", "context": 2_000_000, "input_per_million": 7.00, "best_for": "premium reasoning + long context combined"},
        },
    },
    "DeepSeek": {
        "docs_url": "https://api-docs.deepseek.com/quick_start/pricing",
        "tiers": {
            "cheap":    {"name": "DeepSeek V3 Chat", "context": 128_000, "input_per_million": 0.27, "best_for": "cheap daily chat, fast summaries, simple code"},
            "balanced": {"name": "DeepSeek V3",      "context": 128_000, "input_per_million": 0.27, "best_for": "coding, general reasoning — punches way above its price"},
            "premium":  {"name": "DeepSeek R1",      "context": 128_000, "input_per_million": 0.55, "best_for": "reasoning model — math, logic, hard debugging. Shows its thinking."},
        },
    },
    "Qwen": {
        "docs_url": "https://help.aliyun.com/zh/model-studio/developer-reference/what-is-qwen-llm",
        "tiers": {
            "cheap":    {"name": "Qwen3-Turbo",   "context": 1_000_000, "input_per_million": 0.05, "best_for": "cheapest for big context, simple tasks, multilingual (esp. Chinese)"},
            "balanced": {"name": "Qwen3-Plus",    "context": 128_000,   "input_per_million": 0.40, "best_for": "balanced — strong coding and reasoning, cost-efficient"},
            "premium":  {"name": "Qwen3-Max",     "context": 128_000,   "input_per_million": 1.60, "best_for": "top-tier reasoning and coding, challenges GPT-5 in benchmarks"},
        },
        "specialist": {"name": "Qwen3-Coder",     "context": 1_000_000, "input_per_million": 0.30, "best_for": "dedicated coding model — 1M context, fine-tuned on code"},
    },
    "Mistral": {
        "docs_url": "https://docs.mistral.ai/getting-started/models/models_overview",
        "tiers": {
            "cheap":    {"name": "Mistral Small 3",   "context": 128_000, "input_per_million": 0.20, "best_for": "simple tasks, EU-hosted data privacy"},
            "balanced": {"name": "Mistral Large 2",   "context": 128_000, "input_per_million": 2.00, "best_for": "general coding + reasoning, European alternative"},
            "premium":  {"name": "Mistral Medium 3",  "context": 128_000, "input_per_million": 0.40, "best_for": "flagship — frontier-class at middle prices"},
        },
        "specialist": {"name": "Codestral 25.08",     "context": 256_000, "input_per_million": 0.30, "best_for": "dedicated code model — FIM (fill-in-middle), 80+ languages"},
    },
    "Grok (xAI)": {
        "docs_url": "https://docs.x.ai/docs/models",
        "tiers": {
            "cheap":    {"name": "Grok-4 Fast",  "context": 2_000_000, "input_per_million": 0.20, "best_for": "fast + cheap + huge context — good for agents"},
            "balanced": {"name": "Grok-4",       "context": 256_000,   "input_per_million": 3.00, "best_for": "real-time X/Twitter awareness, reasoning, web search built in"},
            "premium":  {"name": "Grok-4 Heavy", "context": 256_000,   "input_per_million": 15.00, "best_for": "frontier model — top benchmarks, agentic work"},
        },
    },
    "Perplexity": {
        "docs_url": "https://docs.perplexity.ai/guides/model-cards",
        "tiers": {
            "cheap":    {"name": "Sonar",        "context": 200_000, "input_per_million": 0.20, "best_for": "fast web search + answer synthesis, citations"},
            "balanced": {"name": "Sonar Pro",    "context": 200_000, "input_per_million": 3.00, "best_for": "deep research — multi-hop web search with sources"},
            "premium":  {"name": "Sonar Reasoning Pro", "context": 200_000, "input_per_million": 3.00, "best_for": "research + reasoning combo — shows its work, real-time data"},
        },
    },
    "Llama (Meta)": {
        "docs_url": "https://www.llama.com/docs/overview/",
        "tiers": {
            "cheap":    {"name": "Llama 3.3 70B",   "context": 128_000, "input_per_million": 0.20, "best_for": "open-weight, self-hostable, cheap via providers like Groq/Together"},
            "balanced": {"name": "Llama 4 Maverick", "context": 1_000_000, "input_per_million": 0.35, "best_for": "multimodal open-weight — 1M context, 17B active params"},
            "premium":  {"name": "Llama 4 Behemoth", "context": 1_000_000, "input_per_million": 1.00, "best_for": "frontier open-weight — 288B active, competitive with closed frontier"},
        },
    },
    "OpenCoder": {
        "docs_url": "https://opencoder-llm.github.io/",
        "tiers": {
            "cheap":    {"name": "OpenCoder-1.5B", "context": 8_192,   "input_per_million": 0.00, "best_for": "self-hosted, tiny, fast — for offline or air-gapped work"},
            "balanced": {"name": "OpenCoder-8B",   "context": 32_768,  "input_per_million": 0.00, "best_for": "self-hosted code model — fully open data + weights, no API cost"},
            "premium":  {"name": "OpenCoder-8B-Instruct", "context": 32_768, "input_per_million": 0.00, "best_for": "instruction-tuned for chat-style coding — still free/self-hosted"},
        },
        "note": "Zero API cost — runs locally via Ollama / vLLM / transformers. Trade CPU/GPU time for token cost.",
    },
    "OpenRouter": {
        "docs_url": "https://openrouter.ai/docs/quickstart",
        "is_router": True,
        "tiers": {
            "cheap":    {"name": "deepseek/deepseek-chat",      "context": 128_000, "input_per_million": 0.27, "best_for": "cheap proxy to DeepSeek via OpenRouter"},
            "balanced": {"name": "anthropic/claude-sonnet-4.5", "context": 200_000, "input_per_million": 3.00, "best_for": "proxy to Claude Sonnet 4.5 — OpenAI-compatible API, unified billing"},
            "premium":  {"name": "openai/gpt-5",                "context": 400_000, "input_per_million": 2.50, "best_for": "proxy to GPT-5 — one API key, many models, free + paid tiers"},
        },
        "note": "Router service — lets you use any model from any vendor through one API. Add +5% OpenRouter fee on top.",
    },
}

# AI_SERVICES drives the Send/Grab buttons and window detection.
# Each entry: (display_name, color_key, window_title_keywords, catalog_key_or_None).
# catalog_key_or_None controls the recommendation target when that AI is chosen.
AI_SERVICES: list[tuple[str, str, list[str], str | None]] = [
    ("Claude",     "mauve", ["claude.ai", "Claude"],                "Claude"),
    ("ChatGPT",    "green", ["chatgpt.com", "ChatGPT", "chat.openai.com"], "ChatGPT"),
    ("Gemini",     "blue",  ["gemini.google", "Gemini"],            "Gemini"),
    ("DeepSeek",   "teal",  ["chat.deepseek.com", "DeepSeek"],      "DeepSeek"),
    ("Qwen",       "peach", ["chat.qwen.ai", "Qwen", "Tongyi"],     "Qwen"),
    ("Mistral",    "yellow", ["chat.mistral.ai", "Le Chat", "Mistral"], "Mistral"),
    ("Grok",       "red",    ["grok.com", "Grok"],                   "Grok (xAI)"),
    ("Perplexity", "pink",   ["perplexity.ai", "Perplexity"],        "Perplexity"),
    ("OpenRouter", "surface", ["openrouter.ai", "OpenRouter"],       "OpenRouter"),
    # OpenCoder/Llama typically run locally or via APIs, no browser UI — included
    # in the catalog but no window search term.
]

# For Image/Video categories — these use dedicated generation services
IMAGE_MODELS = {
    "Midjourney v7": "High-quality artistic, photorealistic. Discord-based. ~$10/mo subscription.",
    "DALL-E 3 (via ChatGPT Plus)": "Good for text-in-image, easy access. Free with Plus.",
    "Stable Diffusion XL / Flux": "Free/local. Full control, fine-tune-able, slower setup.",
    "Nano Banana (Gemini)": "Integrated in Gemini. Good for quick concept art.",
}

VIDEO_MODELS = {
    "Sora (OpenAI)": "Best quality, long shots. Access via ChatGPT Pro.",
    "Runway Gen-3": "Fast, good motion. $15-$95/mo.",
    "Pika Labs 1.5": "Fast iteration, good prompt adherence.",
    "Luma Dream Machine": "Cinematic shots, 5-sec clips free tier.",
}


# ═══════════════════════════════════════════════════════════════════
# PROMPT TYPES
# ═══════════════════════════════════════════════════════════════════

BUILD_TARGETS = {
    "PC Desktop App": {
        "description": (
            "You want to create a program that opens as a window on a regular computer "
            "(Windows, Mac, or Linux). Think of apps like Notepad, Spotify, or a calculator "
            "\u2014 programs you double-click to open and they show up with buttons, menus, and "
            "text fields. This option tells the AI to make it look professional, save your "
            "settings when you close it, and work on any computer."
        ),
        "role": "Senior Desktop Application Engineer specializing in cross-platform GUI development, native OS integration, and production-grade packaging",
        "platform_context": (
            "TARGET PLATFORM: Windows / macOS / Linux desktop.\n"
            "ENVIRONMENT REQUIREMENTS:\n"
            "- Must run on Python 3.10+ (or specify the language runtime clearly).\n"
            "- Use a modern GUI framework: tkinter with ttk theming, PyQt6/PySide6, or wxPython.\n"
            "- Design for variable DPI / HiDPI displays.\n"
            "- Implement proper window management: minimize, maximize, restore, taskbar icon.\n"
            "- Persist user settings via JSON, TOML, or platform-native config (AppData / ~/.config).\n"
            "- Handle file paths cross-platform using pathlib, never hardcode path separators.\n"
            "- Provide graceful shutdown: save state, release locks, clean temp files."
        ),
        "extra_constraints": [
            "Structure as a proper application: separate UI, logic, and data layers.",
            "Include a main entry point with if __name__ == '__main__' guard.",
            "Use threading or asyncio for any long-running operations to keep UI responsive.",
            "Provide meaningful window titles and status feedback to the user.",
            "Handle missing files, permissions errors, and startup failures gracefully.",
        ],
    },
    "Raspberry Pi App": {
        "description": (
            "You want to build something that runs on a Raspberry Pi \u2014 that small, "
            "credit-card-sized computer. Pi apps are special because the Pi has less memory "
            "and power than a regular PC, and it can connect to physical things like sensors, "
            "LEDs, motors, and cameras through its GPIO pins (the metal pins on the board). "
            "This option tells the AI to keep the code lightweight, handle the Pi's "
            "limitations, and include instructions for wiring and setup."
        ),
        "role": "Embedded Systems Engineer specializing in Raspberry Pi, ARM Linux, GPIO programming, and resource-constrained application design",
        "platform_context": (
            "TARGET PLATFORM: Raspberry Pi (ARM Linux \u2014 Raspberry Pi OS / Debian-based).\n"
            "HARDWARE CONSIDERATIONS:\n"
            "- Limited RAM (1-8 GB depending on model). Minimize memory footprint.\n"
            "- SD card storage is slow and wear-prone. Minimize disk writes; use tmpfs for logs/temp.\n"
            "- GPIO access requires RPi.GPIO, gpiozero, or lgpio libraries.\n"
            "- For I2C/SPI/UART peripherals, use smbus2, spidev, or pyserial.\n"
            "- Camera access via picamera2 (not the deprecated picamera).\n"
            "- If GUI is needed, use lightweight frameworks: tkinter, pygame, or framebuffer-direct.\n"
            "- Design for headless operation where possible (systemd service, SSH-manageable).\n"
            "- Handle power loss gracefully \u2014 assume unclean shutdown can happen at any time.\n"
            "- Respect GPIO cleanup: always use try/finally or atexit to release pins."
        ),
        "extra_constraints": [
            "Pin all hardware dependencies with exact versions in requirements.txt.",
            "Include setup instructions for enabling I2C/SPI/camera if needed.",
            "Use systemd service files for auto-start on boot when appropriate.",
            "Log to journald or a rotating log file, never an unbounded file.",
            "Test with both Pi 4 and Pi 5 considerations (lgpio vs RPi.GPIO).",
            "Handle missing hardware gracefully with clear error messages.",
        ],
    },
    "Cross-Platform (PC + Pi)": {
        "description": (
            "You want ONE program that works on BOTH a regular computer AND a Raspberry Pi. "
            "This is tricky because PCs and Pi's are very different \u2014 a PC has lots of power "
            "but no GPIO pins, while a Pi has GPIO but limited resources. This option tells "
            "the AI to write smart code that detects which device it's running on and adjusts "
            "automatically. On a PC it will skip the hardware stuff; on a Pi it will use "
            "lighter graphics and connect to sensors."
        ),
        "role": "Cross-Platform Software Architect specializing in portable Python applications that run on both x86 desktop and ARM Raspberry Pi with hardware abstraction",
        "platform_context": (
            "TARGET PLATFORMS: Windows/macOS/Linux desktop AND Raspberry Pi (ARM Linux).\n"
            "CROSS-PLATFORM STRATEGY:\n"
            "- Use a hardware abstraction layer: detect platform at startup and load the right backend.\n"
            "- Platform detection: use platform.machine() for arch, check for /sys/firmware/devicetree for Pi.\n"
            "- GUI must work on both: tkinter is safe; avoid PyQt6 on Pi unless confirmed available.\n"
            "- On Pi: support headless mode with a CLI or web interface fallback.\n"
            "- GPIO features should be optional: wrap in try/import, provide stubs on desktop.\n"
            "- File paths: always use pathlib. Config dirs: use platformdirs or manual os detection.\n"
            "- Network features must handle both WiFi and Ethernet transparently.\n"
            "- Package as: pip-installable with optional [pi] extras for GPIO dependencies."
        ),
        "extra_constraints": [
            "Create an abstract base class for any hardware interface with PC mock and Pi real implementations.",
            "Include a config flag or auto-detect to switch between PC and Pi mode.",
            "Test on both platforms \u2014 provide instructions for each.",
            "Keep resource usage low enough for Pi while still looking modern on desktop.",
            "Use conditional imports: try/except ImportError for Pi-specific libraries.",
        ],
    },
    "Game": {
        "description": (
            "You want to build a video game \u2014 something with graphics on screen that a "
            "player interacts with using keyboard, mouse, or a controller. This could be "
            "anything from a simple puzzle to a platformer to a space shooter. This option "
            "tells the AI to set up a proper game engine with a main loop, handle player "
            "input, load images and sounds, detect collisions, and manage different screens "
            "like the title screen, gameplay, pause menu, and game over."
        ),
        "role": "Game Developer and Engine Programmer specializing in 2D/3D game architecture, real-time rendering, physics, and player experience design",
        "platform_context": (
            "TARGET: Game application.\n"
            "GAME DEVELOPMENT REQUIREMENTS:\n"
            "- Use pygame, pyglet, arcade, or Godot (specify which based on the game type).\n"
            "- Implement a proper game loop: fixed timestep for physics, variable for rendering.\n"
            "- Separate game state, rendering, and input handling into distinct systems.\n"
            "- Asset management: load sprites/sounds/fonts from a structured assets/ directory.\n"
            "- Input handling: support keyboard, mouse, and optionally gamepad.\n"
            "- Implement basic collision detection appropriate to the game type.\n"
            "- Audio: background music and sound effects with volume control.\n"
            "- Frame rate targeting: 60 FPS with delta-time-based movement.\n"
            "- Screen management: title screen, gameplay, pause, game over states.\n"
            "- Save/load game state to JSON for persistence."
        ),
        "extra_constraints": [
            "Use sprite sheets or texture atlases for efficient rendering.",
            "Implement a scene/state manager for menu, gameplay, pause, and end screens.",
            "All magic numbers (speeds, sizes, colors) should be constants at the top of the file or in a config.",
            "Handle window close, Alt+F4, and pause/resume cleanly.",
            "Profile for performance: no per-frame allocations in the hot loop.",
        ],
    },
    "Website / Web App": {
        "description": (
            "You want to build something that runs in a web browser \u2014 like a website, "
            "a dashboard, an online tool, or a web application. This could be a simple "
            "page with information, or a full app with login, databases, and interactive "
            "features. This option tells the AI to handle both the frontend and backend, "
            "make it look good on phones and desktops, and keep it secure."
        ),
        "role": "Full-Stack Web Developer specializing in modern responsive design, REST APIs, accessibility, and web security best practices",
        "platform_context": (
            "TARGET: Web application (browser-based).\n"
            "WEB DEVELOPMENT REQUIREMENTS:\n"
            "- Frontend: HTML5, CSS3, JavaScript (or TypeScript). Use a framework if appropriate (React, Vue, Svelte).\n"
            "- Backend: Flask, FastAPI, Django, or Node.js/Express as appropriate.\n"
            "- Responsive design: mobile-first, works on 320px to 4K screens.\n"
            "- Accessibility: semantic HTML, ARIA labels, keyboard navigation, color contrast.\n"
            "- Security: CSRF protection, XSS prevention, Content-Security-Policy headers.\n"
            "- API design: RESTful with proper HTTP methods, status codes, and JSON responses.\n"
            "- Database: use an ORM (SQLAlchemy, Prisma) or document store as appropriate.\n"
            "- Environment config via .env files (never commit secrets).\n"
            "- Include CORS handling if frontend and backend are separate origins."
        ),
        "extra_constraints": [
            "Validate all user input on both client and server side.",
            "Use HTTPS-only cookies with SameSite and HttpOnly flags for auth.",
            "Include rate limiting on authentication and API endpoints.",
            "Serve static assets with cache headers and compression.",
            "Provide a clear API contract (OpenAPI/Swagger or documented endpoints).",
        ],
    },
    "Android App": {
        "description": (
            "You want to build a mobile app for Android phones and tablets. This could be "
            "a Kotlin/Java app using Android Studio, a cross-platform app using Flutter or "
            "React Native, or a Python app using Kivy/BeeWare. This option tells the AI to "
            "handle mobile-specific concerns: touch input, screen sizes, battery life, "
            "permissions, and Google Play Store requirements."
        ),
        "role": "Android Mobile Developer specializing in native Kotlin/Java development, Jetpack Compose, Material Design 3, and Google Play Store publishing requirements",
        "platform_context": (
            "TARGET PLATFORM: Android mobile devices.\n"
            "ANDROID DEVELOPMENT REQUIREMENTS:\n"
            "- Language: Kotlin preferred (or Java). For cross-platform: Flutter (Dart) or React Native.\n"
            "- UI: Jetpack Compose (modern) or XML layouts (legacy). Follow Material Design 3 guidelines.\n"
            "- Architecture: MVVM with ViewModel + LiveData/StateFlow. Use Repository pattern for data.\n"
            "- Navigation: Jetpack Navigation component with safe args.\n"
            "- Permissions: request at runtime, handle denial gracefully, explain why needed.\n"
            "- Lifecycle: handle activity/fragment lifecycle correctly. Save state on rotation/background.\n"
            "- Storage: Room database for structured data, DataStore for preferences, no raw SharedPreferences.\n"
            "- Networking: Retrofit + OkHttp with proper error handling and offline support.\n"
            "- Threading: use Kotlin coroutines, never block the main/UI thread.\n"
            "- Testing: unit tests with JUnit, UI tests with Espresso or Compose testing.\n"
            "- Min SDK: target API 24+ (Android 7.0) for broad compatibility.\n"
            "- Play Store: proper manifest, no dangerous permissions without justification, privacy policy."
        ),
        "extra_constraints": [
            "Handle all screen sizes: phones, tablets, foldables. Use responsive layouts.",
            "Support dark mode via Material You / dynamic theming.",
            "Handle back button, gesture navigation, and edge-to-edge display correctly.",
            "Minimize battery drain: avoid wake locks, use WorkManager for background tasks.",
            "Include ProGuard/R8 rules for release builds.",
            "Follow Google Play Store content policies and data safety requirements.",
        ],
    },
}

# ═══════════════════════════════════════════════════════════════════
# CONVERSATION PROMPT STYLES — for general AI chat, not coding
# ═══════════════════════════════════════════════════════════════════

CONVERSATION_STYLES = {
    "General Chat": {
        "description": "A normal conversation with the AI — asking questions, brainstorming, getting advice.",
        "block": "You are a helpful, knowledgeable assistant. Be conversational and clear. Match the user's tone.",
    },
    "Expert Consultation": {
        "description": "Talk to the AI as if it's a specialist — doctor, lawyer, engineer, etc. (for info, not real advice).",
        "block": "Act as a domain expert. Provide thorough, well-sourced analysis. Distinguish between established facts and your reasoning. Flag when the user should consult a real professional.",
    },
    "Creative Writing": {
        "description": "Storytelling, poetry, scripts, worldbuilding — anything creative.",
        "block": "You are a creative writing partner. Prioritize vivid language, original ideas, and emotional resonance. Match the requested genre and tone. Show, don't tell.",
    },
    "Teaching / Explaining": {
        "description": "Have the AI explain something step by step, like a patient teacher.",
        "block": "You are a patient, skilled teacher. Break complex topics into digestible steps. Use analogies and examples. Check understanding by asking the reader to consider edge cases.",
    },
    "Debate / Devil's Advocate": {
        "description": "Have the AI argue the other side, challenge your ideas, stress-test your thinking.",
        "block": "Act as a rigorous devil's advocate. Challenge every assumption. Present the strongest possible counterarguments. Be intellectually honest — concede points that are genuinely strong.",
    },
    "Summarize / Analyze": {
        "description": "Give the AI text and have it summarize, extract key points, or analyze it.",
        "block": "Analyze the provided content thoroughly. Extract key themes, arguments, and conclusions. Be objective. Distinguish between what the source says and your interpretation.",
    },
}

CONVERSATION_TONES = {
    "Professional": "Use formal, professional language suitable for business communication.",
    "Casual": "Be relaxed and conversational, like chatting with a knowledgeable friend.",
    "Academic": "Use precise, scholarly language with proper citations and caveats.",
    "ELI5 (Explain Like I'm 5)": "Use extremely simple language. No jargon. Lots of analogies a child would understand.",
}

# ═══════════════════════════════════════════════════════════════════
# IMAGE PROMPT OPTIONS — for AI image generation (DALL-E, Midjourney, Stable Diffusion, etc.)
# ═══════════════════════════════════════════════════════════════════

IMAGE_STYLES = {
    "Photorealistic": "Photorealistic, ultra-detailed, 8K resolution, professional photography",
    "Digital Art": "Digital art, vibrant colors, detailed illustration, trending on ArtStation",
    "Oil Painting": "Oil painting style, rich textures, visible brushstrokes, classical composition",
    "Watercolor": "Delicate watercolor painting, soft edges, translucent layers, paper texture",
    "Anime / Manga": "Anime art style, clean lines, cel shading, expressive features",
    "3D Render": "3D rendered, Octane render, ray tracing, subsurface scattering, studio lighting",
    "Pixel Art": "Pixel art, retro game aesthetic, limited color palette, crisp pixels",
    "Sketch / Pencil": "Pencil sketch, graphite on paper, detailed hatching, hand-drawn feel",
    "Cinematic": "Cinematic still frame, dramatic lighting, film grain, anamorphic lens, movie quality",
    "Minimalist": "Minimalist design, clean lines, negative space, simple geometric shapes",
}

IMAGE_LIGHTING = {
    "Natural / Soft": "soft natural lighting, golden hour",
    "Dramatic": "dramatic chiaroscuro lighting, deep shadows, strong highlights",
    "Studio": "professional studio lighting, softbox, clean white background",
    "Neon / Cyberpunk": "neon glow, cyberpunk atmosphere, colorful rim lighting",
    "Backlit": "strong backlighting, silhouette effect, lens flare",
}

IMAGE_CAMERAS = {
    "Wide Angle": "wide angle lens, expansive view, 24mm focal length",
    "Portrait (85mm)": "85mm portrait lens, shallow depth of field, bokeh background",
    "Macro": "macro photography, extreme close-up, detailed texture",
    "Aerial / Drone": "aerial drone photography, bird's eye view, sweeping landscape",
    "Fish-eye": "fish-eye lens, distorted perspective, 180-degree field of view",
}

# ═══════════════════════════════════════════════════════════════════
# VIDEO PROMPT OPTIONS — for AI video generation (Sora, Runway, Pika, etc.)
# ═══════════════════════════════════════════════════════════════════

VIDEO_STYLES = {
    "Cinematic": "Cinematic quality, 24fps film look, shallow depth of field, professional color grading",
    "Documentary": "Documentary style, handheld camera, natural lighting, observational",
    "Animation (2D)": "2D animation, smooth frame-by-frame movement, illustrated style",
    "Animation (3D)": "3D CGI animation, Pixar/DreamWorks quality, realistic rendering",
    "Music Video": "Music video aesthetic, stylized editing, beat-synchronized cuts, creative transitions",
    "Commercial / Ad": "Polished commercial quality, product-focused, aspirational, clean edits",
    "Social Media": "Short-form vertical video, fast-paced, eye-catching in first 2 seconds, trending style",
}

VIDEO_CAMERA_MOVES = {
    "Static / Tripod": "locked-off static shot, stable tripod, no camera movement",
    "Slow Pan": "slow smooth horizontal pan, revealing the scene gradually",
    "Tracking Shot": "camera tracking alongside subject, steady movement, following action",
    "Dolly Zoom": "dolly zoom / vertigo effect, background scaling while subject stays same size",
    "Drone / Aerial": "sweeping drone shot, rising aerial reveal, cinematic flyover",
    "Handheld": "handheld camera, slight shake, intimate and raw feeling",
    "Timelapse": "timelapse, sped up passage of time, clouds moving, day to night",
}

VIDEO_PACING = {
    "Slow / Contemplative": "slow pacing, long takes, meditative, atmospheric",
    "Medium / Narrative": "medium pacing, story-driven, natural rhythm, scene-to-scene flow",
    "Fast / Energetic": "fast cuts, high energy, dynamic editing, impact frames",
}

ENHANCEMENTS = {
    "Modern GUI + UX": {
        "description": (
            "Make an existing program LOOK better. Right now your app might work fine but "
            "looks plain, ugly, or outdated. This option tells the AI to give it a modern "
            "dark theme (or light theme toggle), add smooth animations, hover effects on "
            "buttons, keyboard shortcuts, a status bar, tooltips, and make it resize properly."
        ),
        "role": "UI/UX Engineer and Desktop Application Modernization Specialist focused on transforming functional code into polished, professional user experiences",
        "platform_context": (
            "OBJECTIVE: Modernize an existing application's user interface and experience.\n"
            "MODERNIZATION REQUIREMENTS:\n"
            "- Apply a cohesive color theme (dark mode preferred, with optional light mode toggle).\n"
            "- Use consistent spacing, padding, and alignment throughout.\n"
            "- Replace default OS widgets with styled equivalents (ttk themes, custom widgets).\n"
            "- Add visual feedback: hover states, active states, loading indicators, progress bars.\n"
            "- Implement smooth transitions where possible (fade, slide for panels).\n"
            "- Add keyboard shortcuts for all major actions with visible hints.\n"
            "- Status bar with contextual information and operation feedback.\n"
            "- Responsive layout that handles window resizing gracefully.\n"
            "- Toast notifications or non-blocking status messages instead of modal popups where appropriate.\n"
            "- Icon support: use Unicode symbols or bundled icon set for buttons and menus.\n"
            "- Add tooltips for all non-obvious controls."
        ),
        "extra_constraints": [
            "Preserve ALL existing functionality \u2014 this is a UI upgrade, not a rewrite.",
            "Ensure the new UI works at 100%, 125%, 150%, and 200% display scaling.",
            "Test with both mouse and keyboard-only navigation.",
            "Add a menu bar with File, Edit, View, Help menus as appropriate.",
            "Keep the code structure clean: separate styling/theme from widget layout from logic.",
        ],
    },
    "Security + Compliance": {
        "description": (
            "Make an existing program SAFER and ready for official distribution. This option "
            "tells the AI to audit your code for security holes, fix them, make sure it "
            "follows platform rules, and handle user privacy properly."
        ),
        "role": "Application Security Engineer and Platform Compliance Specialist covering Microsoft Store, Linux package guidelines, Raspberry Pi OS, Apple App Store sandboxing, and modern security standards",
        "platform_context": (
            "OBJECTIVE: Harden an existing application for security and platform compliance.\n"
            "SECURITY AUDIT SCOPE:\n"
            "- Input validation: sanitize ALL external input (user, file, network, clipboard).\n"
            "- Data at rest: encrypt sensitive config/data using cryptography.fernet or OS keychain.\n"
            "- Data in transit: enforce TLS 1.2+ for all network calls. Pin certificates if critical.\n"
            "- Authentication: use bcrypt/argon2 for password hashing. Never store plaintext.\n"
            "- Secrets management: no hardcoded keys/tokens. Use env vars or OS credential store.\n"
            "- File operations: validate paths to prevent traversal attacks. Use tempfile for temp data.\n"
            "- Dependency audit: check for known CVEs. Pin versions. Minimize dependency count.\n"
            "PLATFORM COMPLIANCE:\n"
            "- Windows/Microsoft Store: proper manifest, no admin rights unless essential, MSIX-compatible.\n"
            "- Linux/Pi: follow FHS for file placement. No writes outside home or /tmp without permission.\n"
            "- App Store (general): no private API usage, proper sandboxing, data privacy declaration.\n"
            "- GDPR/Privacy: log what data is collected, provide export/delete capabilities.\n"
            "- Accessibility compliance: WCAG 2.1 AA minimum for any UI components."
        ),
        "extra_constraints": [
            "Produce a SECURITY_NOTES.md listing every change and the threat it mitigates.",
            "Flag any remaining risks as TODO comments with severity (LOW/MEDIUM/HIGH/CRITICAL).",
            "Do not break existing functionality \u2014 security hardening must be backward-compatible.",
            "Add logging for security-relevant events (login attempts, permission changes, errors).",
            "Recommend specific dependency updates if any are outdated or have known CVEs.",
        ],
    },
    "More Features + Robustness": {
        "description": (
            "Make an existing program DO more and BREAK less. This tells the AI to add "
            "undo/redo, better error messages, auto-saving, loading bars, settings, and "
            "defensive programming so the app handles problems gracefully."
        ),
        "role": "Senior Software Engineer specializing in feature expansion, defensive programming, comprehensive error handling, and production reliability engineering",
        "platform_context": (
            "OBJECTIVE: Expand and harden an existing application's capabilities.\n"
            "IMPROVEMENT SCOPE:\n"
            "- Audit every user-facing feature for edge cases and failure modes.\n"
            "- Add input validation with clear, actionable error messages for every entry point.\n"
            "- Implement undo/redo where the app modifies data.\n"
            "- Add configuration options for behaviors that are currently hardcoded.\n"
            "- Implement proper logging with configurable verbosity (DEBUG, INFO, WARNING, ERROR).\n"
            "- Add retry logic with exponential backoff for network/IO operations.\n"
            "- Implement graceful degradation: if a feature fails, the app continues working.\n"
            "- Add progress reporting for any operation that takes more than 1 second.\n"
            "- Implement data backup/auto-save to prevent data loss.\n"
            "- Add command-line arguments for power users (argparse).\n"
            "- Write unit tests for critical business logic."
        ),
        "extra_constraints": [
            "List every improvement made with before/after description.",
            "Preserve the existing API/interface \u2014 additions only, no breaking changes.",
            "Every new feature must have error handling \u2014 no bare except, no silent failures.",
            "Add type hints to any function you modify or create.",
            "Include a CHANGELOG entry for each improvement.",
        ],
    },
    "Add Diagnostics": {
        "description": (
            "Add a 'health check' system to your program. This option adds a button that "
            "generates a diagnostic report (.txt file saved to Desktop) with everything "
            "needed to troubleshoot: OS info, Python version, errors, memory, and dependencies."
        ),
        "role": "Systems Reliability Engineer specializing in application diagnostics, telemetry, structured logging, and automated health reporting",
        "platform_context": (
            "OBJECTIVE: Add comprehensive diagnostic capabilities that produce a report on the desktop.\n"
            "DIAGNOSTIC SYSTEM REQUIREMENTS:\n"
            "- Create a diagnostic report as a .txt file saved to the user's Desktop.\n"
            "- Desktop path detection: use pathlib.Path.home() / 'Desktop' with fallback to home dir.\n"
            "- Report filename: <app_name>_diagnostic_<YYYY-MM-DD_HHMMSS>.txt\n"
            "- Report contents must include:\n"
            "  1. SYSTEM INFO: OS, Python version, platform.machine(), screen resolution, available RAM/disk.\n"
            "  2. APP STATE: current configuration, loaded files, active features, uptime.\n"
            "  3. DEPENDENCY CHECK: installed versions of all required packages, missing packages.\n"
            "  4. RECENT ERRORS: last 50 logged errors/warnings with timestamps and tracebacks.\n"
            "  5. PERFORMANCE: startup time, memory usage, any slow operations detected.\n"
            "  6. CONNECTIVITY: network reachability if the app uses network features.\n"
            "- Add a 'Run Diagnostics' button in the UI that triggers the report.\n"
            "- Also generate diagnostics automatically on unhandled exceptions.\n"
            "- Use the logging module with a rotating file handler for ongoing log capture."
        ),
        "extra_constraints": [
            "Never include passwords, API keys, or tokens in the diagnostic report.",
            "Limit log file size: use RotatingFileHandler with 5 MB max and 3 backup files.",
            "Format the report for human readability with clear section headers and separators.",
            "Add a 'Copy Diagnostics to Clipboard' option alongside the file save.",
            "Include instructions at the top of the report on how to share it for support.",
        ],
    },
    "Find Expansion Opportunities": {
        "description": (
            "Don't write code \u2014 instead, ANALYZE your existing program and find ways to "
            "make it bigger and better. The AI will find missed features, fork ideas, plugin "
            "points, integration opportunities, and quick wins."
        ),
        "role": "Product Strategist and Software Architect specializing in identifying expansion opportunities, modular architecture for product forks, feature gap analysis, and edition planning",
        "platform_context": (
            "OBJECTIVE: Analyze existing code and produce a strategic expansion report.\n"
            "ANALYSIS FRAMEWORK:\n"
            "- MISSED FEATURES: Identify capabilities the code is close to having but does not expose.\n"
            "  Look for: unused function parameters, partial implementations, data collected but not displayed.\n"
            "- FORK OPPORTUNITIES: Identify how this codebase could be forked into specialized editions.\n"
            "  Consider: Lite vs Pro, Platform-specific (PC/Pi/Web), Audience-specific (Beginner/Expert).\n"
            "- PLUGIN/EXTENSION POINTS: Where could a plugin API be added for community expansion?\n"
            "- INTEGRATION OPPORTUNITIES: What external services, APIs, or tools could this connect to?\n"
            "- MONETIZATION PATHS: Free vs paid features, what constitutes genuine upgrade value.\n"
            "- MODULAR EXTRACTION: Which components could become standalone libraries or tools?\n"
            "OUTPUT REQUIREMENTS:\n"
            "- Prioritized list with estimated effort (Low/Medium/High) for each opportunity.\n"
            "- For each fork/edition idea, describe: target audience, differentiating features, shared core.\n"
            "- Include a dependency diagram showing which expansions unlock which others.\n"
            "- Flag quick wins (high value, low effort) separately."
        ),
        "extra_constraints": [
            "Be specific \u2014 reference actual functions, classes, and files in the codebase.",
            "Distinguish between 'should do now' and 'should architect for later'.",
            "Every suggestion must include a concrete first step, not just a vague idea.",
            "Consider backward compatibility for existing users in all expansion proposals.",
            "Include risk assessment: what could go wrong with each expansion path.",
        ],
    },
}

REASONING_MODES = {
    "Standard Chain of Thought": {
        "description": "The AI explains its thinking step by step, like showing work on a math problem.",
        "block": "REASONING: Use Chain of Thought.\nThink through the problem step by step before providing your answer.\nShow your reasoning process clearly.",
    },
    "Structured Chain of Thought (SCoT)": {
        "description": "Best for coding. The AI writes a pseudocode plan before real code \u2014 like a blueprint before building.",
        "block": "REASONING: Use Structured Chain of Thought (SCoT).\nBefore writing any code, draft a numbered pseudocode plan:\n1. SEQUENTIAL OPERATIONS: Define the setup and data flow.\n2. BRANCH CONDITIONALS: Define edge cases and error handling paths.\n3. ITERATIVE LOOPS: Define repetition logic and termination conditions.\n4. COMPOSITION: Combine the above into a cohesive solution.",
    },
    "Chain of Density (CoD)": {
        "description": "Multiple drafts, each packing MORE info into the SAME space. Best for summaries.",
        "block": "REASONING: Use Chain of Density.\nProduce multiple iterations. Each iteration must increase entity density\nand specificity without increasing total word count.\nFinal output should be maximally information-dense.",
    },
    "Tree of Thought (ToT)": {
        "description": "Generates 3 approaches, compares them, picks the best. Best for exploring options.",
        "block": "REASONING: Use Tree of Thought.\n1. Generate 3 distinct approaches to solve this problem.\n2. For each approach, evaluate: correctness, efficiency, maintainability.\n3. Select the best approach with justification.\n4. Implement only the chosen approach.",
    },
    "ReAct (Reason + Act)": {
        "description": "Alternates between THINKING and DOING. Best for multi-step tasks with dependencies.",
        "block": "REASONING: Use the ReAct framework.\nFor each step, alternate between:\n- THOUGHT: Analyze what needs to happen next and why.\n- ACTION: Describe the concrete action to take.\n- OBSERVATION: State what the result or outcome is.\nContinue until the task is complete.",
    },
    "None": {
        "description": "No thinking framework \u2014 just answer directly.",
        "block": "",
    },
}

OUTPUT_FORMATS = {
    "Free-form": {"description": "No format rules \u2014 AI picks the best format.", "block": ""},
    "JSON (strict)": {"description": "Raw JSON data only, no extra text.", "block": "OUTPUT FORMAT: Return a strictly valid JSON object.\nDo not wrap in markdown code fences. Raw JSON only."},
    "JSON (Pydantic schema)": {"description": "Strict JSON with type-checked fields.", "block": "OUTPUT FORMAT: Return a strictly valid JSON object conforming to a Pydantic-style schema.\nInclude all required fields. Use correct types. No extra keys."},
    "Markdown": {"description": "Headers, bullets, code blocks \u2014 looks nice in docs.", "block": "OUTPUT FORMAT: Return well-structured Markdown.\nUse headers, lists, and code blocks where appropriate."},
    "XML Tags": {"description": "Labeled tags like <solution>...</solution> for easy parsing.", "block": "OUTPUT FORMAT: Structure your response using XML tags.\nUse semantic tag names (e.g., <analysis>, <solution>, <code>)."},
    "Code Only": {"description": "ONLY runnable code, no explanations.", "block": "OUTPUT FORMAT: Return only executable code.\nNo explanations, no markdown fences, no comments outside the code."},
}

CONSTRAINT_PRESETS = {
    "Python Best Practices": {
        "description": "PEP 8 style, type hints, docstrings.",
        "rules": ["Follow PEP 8 style guidelines.", "Use type hints for all function signatures.", "Include docstrings for public functions and classes."],
    },
    "Performance": {
        "description": "Fast code, low memory, minimal I/O.",
        "rules": ["Optimize for time complexity \u2014 prefer O(n) or better.", "Minimize memory allocations and copies.", "Avoid unnecessary I/O operations."],
    },
    "Security": {
        "description": "Validate input, no hardcoded secrets, safe DB queries.",
        "rules": ["Sanitize all user inputs.", "Never hardcode secrets or credentials.", "Use parameterized queries for any database access."],
    },
    "Conciseness": {
        "description": "Short, no fluff, minimal comments.",
        "rules": ["No conversational filler.", "No restating the problem.", "Minimal comments \u2014 only where logic is non-obvious."],
    },
    "Robustness": {
        "description": "Handles weird inputs and missing files without crashing.",
        "rules": ["Handle edge cases explicitly.", "Include input validation.", "Provide meaningful error messages."],
    },
    "Diplomatic Reframe": {
        "description": (
            "Rewords your prompt so the AI approaches sensitive or restricted topics through "
            "a constructive, educational, or professional lens. Instead of triggering refusals, "
            "the AI sees a legitimate professional context and delivers the same useful result."
        ),
        "rules": [
            "Frame all requests as professional, educational, or research-oriented tasks.",
            "When discussing security topics, frame as 'defense and hardening' rather than 'attack'.",
            "When discussing sensitive content, provide the professional context (e.g., 'for a security audit', 'for academic research', 'for content moderation development').",
            "Use constructive language: 'How to protect against X' instead of 'How to do X'.",
            "Present yourself as building tools for safety, education, compliance, or legitimate business needs.",
            "If the task involves analyzing risks, frame it as 'threat modeling' or 'vulnerability assessment'.",
        ],
    },
}


# ═══════════════════════════════════════════════════════════════════
# THE APPLICATION
# ═══════════════════════════════════════════════════════════════════

class PromptArchitect:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(f"{APP_NAME} v{APP_VERSION}")
        self.root.minsize(900, 700)
        self.root.configure(bg=COLORS["bg"])

        self.history: list[dict] = []
        self._update_chain: list[dict] = []  # Rolling list of follow-up updates
        self._startup_time = datetime.now()
        self._error_log: list[dict] = []
        self._dark_mode = True
        self._dirty = False
        self._autosave_hash = ""
        self._clipboard_clear_id: str | None = None
        self._toast_window: tk.Toplevel | None = None
        self._status_clear_id: str | None = None

        self._themed_buttons: list[tuple[tk.Button, str, str]] = []
        self._themed_texts: list[tk.Text | scrolledtext.ScrolledText] = []
        self._tooltips: list[ToolTip] = []

        # v5.0 additions: scan root, discovered projects cache, merged project dict
        self._scan_root: Path = self._load_scan_root()
        self._discovered_projects: dict = {}
        self._merged_projects: dict = dict(MY_PROJECTS)  # Live view: hardcoded + discovered
        self._refresh_discovered_projects()

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
        logger.info("Application started")

    # ── v5.0: Scan-root persistence + project auto-discovery ──

    def _load_scan_root(self) -> Path:
        """Load the last-used project scan root from config, fall back to Desktop/AI."""
        default = Path("C:/Users/computer/Desktop/AI")
        cfg_file = CONFIG_DIR / "scan_root.json"
        if cfg_file.exists():
            try:
                data = json.loads(cfg_file.read_text(encoding="utf-8"))
                p = Path(data.get("path", ""))
                if p.is_dir():
                    return p
            except (OSError, json.JSONDecodeError):
                pass
        return default if default.is_dir() else Path.home()

    def _save_scan_root(self, p: Path) -> None:
        """Persist the current scan root."""
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            cfg_file = CONFIG_DIR / "scan_root.json"
            cfg_file.write_text(json.dumps({"path": str(p)}, indent=2), encoding="utf-8")
        except OSError as exc:
            logger.warning(f"Could not save scan_root: {exc}")

    def _refresh_discovered_projects(self) -> None:
        """Rescan the current scan_root folder and merge results into _merged_projects."""
        try:
            self._discovered_projects = scan_projects_folder(self._scan_root, max_projects=150)
        except Exception as exc:
            logger.warning(f"Project scan failed: {exc}")
            self._discovered_projects = {}

        # Merge: hardcoded takes precedence (so custom conventions aren't overwritten)
        merged = dict(self._discovered_projects)
        for name, data in MY_PROJECTS.items():
            merged[name] = data
        self._merged_projects = merged
        logger.info(
            f"Scanned {self._scan_root}: {len(self._discovered_projects)} discovered, "
            f"{len(self._merged_projects)} total projects"
        )

    # ══════════════════════════════════════════════════════════════
    # THEME
    # ══════════════════════════════════════════════════════════════

    def _active_colors(self) -> dict:
        return COLORS if self._dark_mode else COLORS_LIGHT

    def _toggle_theme(self) -> None:
        self._dark_mode = not self._dark_mode
        c = self._active_colors()
        self._configure_styles(c)
        self.root.configure(bg=c["bg"])
        if hasattr(self, "_left_canvas"):
            self._left_canvas.configure(bg=c["bg"])
        for btn, normal_key, _ in self._themed_buttons:
            try:
                btn.configure(bg=c[normal_key], fg=c["dark"])
            except tk.TclError:
                pass
        for tw in self._themed_texts:
            try:
                tw.configure(bg=c["overlay"], fg=c["text"], insertbackground=c["text"])
            except tk.TclError:
                pass
        if hasattr(self, "result_area"):
            self.result_area.configure(fg=c["yellow"])
        if hasattr(self, "diag_area"):
            self.diag_area.configure(fg=c["green"])
        for tip in self._tooltips:
            tip.update_colors(c)
        self._style_menus(c)
        self._set_status(f"Switched to {'dark' if self._dark_mode else 'light'} theme")
        logger.info(f"Theme toggled to {'dark' if self._dark_mode else 'light'}")

    # ══════════════════════════════════════════════════════════════
    # STYLES
    # ══════════════════════════════════════════════════════════════

    def _configure_styles(self, c: dict) -> None:
        s = ttk.Style()
        s.theme_use("clam")
        s.configure("TFrame", background=c["bg"])
        s.configure("TLabel", background=c["bg"], foreground=c["text"], font=("Segoe UI", 11))
        s.configure("Header.TLabel", font=("Segoe UI", 18, "bold"), foreground=c["blue"])
        s.configure("Sub.TLabel", font=("Segoe UI", 10), foreground=c["subtext"])
        s.configure("Desc.TLabel", font=("Segoe UI", 10), foreground=c["teal"])
        s.configure("Warn.TLabel", font=("Segoe UI", 10), foreground=c["red"])
        s.configure("TLabelframe", background=c["bg"], foreground=c["mauve"], font=("Segoe UI", 11, "bold"))
        s.configure("TLabelframe.Label", background=c["bg"], foreground=c["mauve"], font=("Segoe UI", 11, "bold"))
        s.configure("TNotebook", background=c["bg"])
        s.configure("TNotebook.Tab", background=c["surface"], foreground=c["text"], font=("Segoe UI", 11), padding=[14, 6])
        s.map("TNotebook.Tab", background=[("selected", c["bg"])], foreground=[("selected", c["blue"])])
        s.configure("TCheckbutton", background=c["bg"], foreground=c["text"], font=("Segoe UI", 11))
        s.map("TCheckbutton", background=[("active", c["bg"])])
        s.configure("TRadiobutton", background=c["bg"], foreground=c["text"], font=("Segoe UI", 11))
        s.map("TRadiobutton", background=[("active", c["bg"])])
        s.configure("TEntry", fieldbackground=c["surface"], foreground=c["text"], font=("Segoe UI", 11))
        s.configure("Status.TLabel", background=c["surface"], foreground=c["subtext"], font=("Segoe UI", 10))
        s.configure("StatusBar.TFrame", background=c["surface"])
        s.configure("TSeparator", background=c["surface"])

    def _style_menus(self, c: dict) -> None:
        for menu in [self._file_menu, self._edit_menu, self._view_menu, self._help_menu]:
            try:
                menu.configure(bg=c["surface"], fg=c["text"], activebackground=c["blue"], activeforeground=c["dark"])
            except tk.TclError:
                pass

    # ══════════════════════════════════════════════════════════════
    # MENU BAR
    # ══════════════════════════════════════════════════════════════

    def _build_menu_bar(self) -> None:
        c = self._active_colors()
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        self._file_menu = tk.Menu(menubar, tearoff=0, bg=c["surface"], fg=c["text"])
        self._file_menu.add_command(label="New Session", command=self._new_session, accelerator="Ctrl+N")
        self._file_menu.add_command(label="Open Template...", command=self._load_template_via_menu)
        self._file_menu.add_separator()
        self._file_menu.add_command(label="Save Output...", command=self.save_to_file, accelerator="Ctrl+S")
        self._file_menu.add_separator()
        self._file_menu.add_command(label="Exit", command=self._on_close, accelerator="Alt+F4")
        menubar.add_cascade(label="File", menu=self._file_menu)

        self._edit_menu = tk.Menu(menubar, tearoff=0, bg=c["surface"], fg=c["text"])
        self._edit_menu.add_command(label="Undo", command=self._undo, accelerator="Ctrl+Z")
        self._edit_menu.add_command(label="Redo", command=self._redo, accelerator="Ctrl+Y")
        self._edit_menu.add_separator()
        self._edit_menu.add_command(label="Copy Output", command=self.copy_to_clipboard, accelerator="Ctrl+Shift+C")
        self._edit_menu.add_command(label="Clear Output", command=self.clear_output)
        self._edit_menu.add_separator()
        self._auto_clear_clip = tk.BooleanVar(value=False)
        self._edit_menu.add_checkbutton(label="Auto-clear clipboard (60s)", variable=self._auto_clear_clip)
        menubar.add_cascade(label="Edit", menu=self._edit_menu)

        self._view_menu = tk.Menu(menubar, tearoff=0, bg=c["surface"], fg=c["text"])
        self._view_menu.add_command(label="Toggle Light/Dark Theme", command=self._toggle_theme, accelerator="Ctrl+T")
        font_menu = tk.Menu(self._view_menu, tearoff=0, bg=c["surface"], fg=c["text"])
        for size in [8, 9, 10, 11, 12, 14]:
            font_menu.add_command(label=str(size), command=lambda s=size: self._set_font_size(s))
        self._view_menu.add_cascade(label="Font Size", menu=font_menu)
        self._view_menu.add_separator()
        self._view_menu.add_command(label="Maximize Window", command=self._maximize_window, accelerator="F11")
        self._view_menu.add_command(label="Restore Window Size", command=self._restore_window_size)
        menubar.add_cascade(label="View", menu=self._view_menu)

        self._help_menu = tk.Menu(menubar, tearoff=0, bg=c["surface"], fg=c["text"])
        self._help_menu.add_command(label="Keyboard Shortcuts", command=self._show_shortcuts)
        self._help_menu.add_command(label="About", command=self._show_about)
        menubar.add_cascade(label="Help", menu=self._help_menu)

    # ══════════════════════════════════════════════════════════════
    # ERROR HANDLER
    # ══════════════════════════════════════════════════════════════

    def _install_error_handler(self) -> None:
        original_report = tk.Tk.report_callback_exception
        app_ref = self

        def _on_error(self_root, exc_type, exc_value, exc_tb):
            entry = {
                "time": datetime.now().isoformat(),
                "type": exc_type.__name__,
                "message": str(exc_value),
                "traceback": traceback.format_exception(exc_type, exc_value, exc_tb),
            }
            app_ref._error_log.append(entry)
            if len(app_ref._error_log) > 50:
                app_ref._error_log.pop(0)
            logger.error(f"Unhandled: {exc_type.__name__}: {exc_value}")
            try:
                crash_path = CONFIG_DIR / f"crash_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                crash_path.write_text(app_ref._generate_diagnostic_report(), encoding="utf-8")
                logger.info(f"Crash report saved: {crash_path}")
            except Exception:
                pass
            original_report(self_root, exc_type, exc_value, exc_tb)

        tk.Tk.report_callback_exception = _on_error

    # ══════════════════════════════════════════════════════════════
    # STATUS BAR
    # ══════════════════════════════════════════════════════════════

    def _build_status_bar(self) -> None:
        self._statusbar = ttk.Frame(self.root, style="StatusBar.TFrame")
        self._statusbar.pack(fill=tk.X, side=tk.BOTTOM)
        pad = {"padx": 8, "pady": 3}
        self._status_mode = ttk.Label(self._statusbar, text="\u2630 Builder", style="Status.TLabel")
        self._status_mode.pack(side=tk.LEFT, **pad)
        ttk.Separator(self._statusbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=2)
        self._status_action = ttk.Label(self._statusbar, text="Ready", style="Status.TLabel")
        self._status_action.pack(side=tk.LEFT, **pad)
        self.token_label = ttk.Label(self._statusbar, text="~0 tokens", style="Status.TLabel")
        self.token_label.pack(side=tk.RIGHT, **pad)

    def _set_status(self, text: str) -> None:
        self._status_action.config(text=text)
        if self._status_clear_id:
            self.root.after_cancel(self._status_clear_id)
        self._status_clear_id = self.root.after(5000, lambda: self._status_action.config(text="Ready"))

    # ══════════════════════════════════════════════════════════════
    # TOAST NOTIFICATIONS
    # ══════════════════════════════════════════════════════════════

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
        rx = self.root.winfo_rootx() + self.root.winfo_width() - 300
        ry = self.root.winfo_rooty() + self.root.winfo_height() - 60
        tw.wm_geometry(f"280x40+{rx}+{ry}")
        frm = tk.Frame(tw, bg=c["green"], padx=10, pady=8)
        frm.pack(fill=tk.BOTH, expand=True)
        tk.Label(frm, text=message, bg=c["green"], fg=c["dark"], font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT)
        close_lbl = tk.Label(frm, text="\u2715", bg=c["green"], fg=c["dark"], font=("Segoe UI", 9), cursor="hand2")
        close_lbl.pack(side=tk.RIGHT)
        close_lbl.bind("<Button-1>", lambda e: tw.destroy())
        self._toast_window = tw
        self.root.after(duration, lambda: self._destroy_toast(tw))

    def _destroy_toast(self, tw: tk.Toplevel) -> None:
        try:
            tw.destroy()
        except tk.TclError:
            pass
        if self._toast_window is tw:
            self._toast_window = None

    # ══════════════════════════════════════════════════════════════
    # UI CONSTRUCTION
    # ══════════════════════════════════════════════════════════════

    def _build_ui(self) -> None:
        main = ttk.Frame(self.root, padding=15)
        main.pack(fill=tk.BOTH, expand=True)

        header_row = ttk.Frame(main)
        header_row.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(header_row, text=f"\u2726 {APP_NAME.upper()}", style="Header.TLabel").pack(side=tk.LEFT, padx=(0, 16))

        # Template quick-switcher (top ribbon)
        c_hdr = self._active_colors()
        ttk.Label(header_row, text="Template:", style="Sub.TLabel").pack(side=tk.LEFT, padx=(0, 4))
        self._template_quick_var = tk.StringVar(value="")
        self._template_quick_combo = ttk.Combobox(
            header_row, textvariable=self._template_quick_var,
            state="readonly", width=22, font=("Segoe UI", 9),
        )
        self._template_quick_combo.pack(side=tk.LEFT, padx=(0, 4))
        self._template_quick_combo.bind("<<ComboboxSelected>>", lambda e: self._load_template_by_name())

        for text, ck, cmd, tip in [
            ("New", "surface", self._new_from_quick, "Start fresh — clear all settings"),
            ("Save", "peach", self._save_template_from_quick, "Save current settings as a template"),
            ("Delete", "red", self._delete_template_from_quick, "Delete the selected template"),
        ]:
            btn = tk.Button(
                header_row, text=text, command=cmd,
                bg=c_hdr[ck], fg=c_hdr["dark"], font=("Segoe UI", 9, "bold"),
                relief=tk.FLAT, padx=8, pady=2, cursor="hand2",
            )
            btn.pack(side=tk.LEFT, padx=(0, 4))
            self._themed_buttons.append((btn, ck, ck))
            self._tooltips.append(ToolTip(btn, tip, c_hdr))

        # Separator
        ttk.Separator(header_row, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=8)

        # Low Token Mode toggle (right side)
        self._low_token_var = tk.BooleanVar(value=False)
        low_tok_cb = ttk.Checkbutton(
            header_row, text="\u26a1 Low Token Mode", variable=self._low_token_var,
        )
        low_tok_cb.pack(side=tk.RIGHT, padx=(8, 0))
        self._tooltips.append(ToolTip(
            low_tok_cb,
            "When ON, uses abbreviated project context (token_savings) instead of full CLAUDE.md. "
            "Cuts prompt tokens by ~50-60% with minimal effectiveness loss.",
            c_hdr,
        ))

        # Refresh template list at init
        self._refresh_template_quick_list()

        self.notebook = ttk.Notebook(main)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

        builder_tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(builder_tab, text="  \u2692 Builder  ")
        paned = ttk.PanedWindow(builder_tab, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)

        left_outer = ttk.Frame(paned)
        paned.add(left_outer, weight=1)
        c = self._active_colors()
        self._left_canvas = tk.Canvas(left_outer, bg=c["bg"], highlightthickness=0)
        left_sb = ttk.Scrollbar(left_outer, orient=tk.VERTICAL, command=self._left_canvas.yview)
        self.left_frame = ttk.Frame(self._left_canvas)
        self.left_frame.bind("<Configure>", lambda e: self._left_canvas.configure(scrollregion=self._left_canvas.bbox("all")))
        self._left_canvas.create_window((0, 0), window=self.left_frame, anchor="nw")
        self._left_canvas.configure(yscrollcommand=left_sb.set)
        self._left_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        left_sb.pack(side=tk.RIGHT, fill=tk.Y)

        def _scroll(event):
            self._left_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        self._left_canvas.bind_all("<MouseWheel>", _scroll)

        left = self.left_frame

        # ── My Projects preset (top of everything) ──
        self._build_my_projects_section(left)

        # ── Prompt Category selector (controls which sections show) ──
        self._build_category_section(left)

        # ── Category-specific panels (shown/hidden dynamically) ──
        self._code_panel = ttk.Frame(left)
        self._conv_panel = ttk.Frame(left)
        self._image_panel = ttk.Frame(left)
        self._video_panel = ttk.Frame(left)

        # Build all panels (but only code_panel shown initially)
        self._build_build_target_section(self._code_panel)
        self._build_enhancements_section(self._code_panel)
        self._build_conversation_section(self._conv_panel)
        self._build_image_section(self._image_panel)
        self._build_video_section(self._video_panel)

        self._code_panel.pack(fill=tk.X)

        # ── Shared sections (always visible) ──
        self._build_role_section(left)
        self._build_reasoning_section(left)
        self._build_output_format_section(left)
        self._build_constraints_section(left)
        self._build_context_section(left)
        self._build_task_section(left)
        self._build_buttons(left)

        right = ttk.Frame(paned)
        paned.add(right, weight=1)

        # ── Main result area (top) ──
        result_frame = ttk.LabelFrame(right, text=" Generated Prompt ", padding=10)
        result_frame.pack(fill=tk.BOTH, expand=True)

        # Toolbar above result area
        result_toolbar = ttk.Frame(result_frame)
        result_toolbar.pack(fill=tk.X, pady=(0, 4))
        for text, ck, cmd, tip in [
            ("\U0001f4cb Copy Prompt Only", "green", self._copy_prompt_only, "Copy just the prompt (no review section)"),
            ("\U0001f4c4 Copy All", "blue", self.copy_to_clipboard, "Copy everything including the review"),
            ("\u2702 Copy Selection", "teal", self._copy_selection, "Copy highlighted text"),
            ("\u2610 Select All", "surface", self._select_all_result, "Select all text in this box"),
            ("\u2715 Clear", "red", self.clear_output, "Clear the output"),
        ]:
            btn = tk.Button(result_toolbar, text=text, command=cmd, bg=c[ck], fg=c["dark"],
                            font=("Segoe UI", 9, "bold"), relief=tk.FLAT, padx=8, pady=3, cursor="hand2")
            btn.pack(side=tk.LEFT, padx=(0, 3))
            self._themed_buttons.append((btn, ck, ck))
            hover_color = _lighten_color(c[ck])
            btn.bind("<Enter>", lambda e, b=btn, hc=hover_color: b.config(bg=hc))
            btn.bind("<Leave>", lambda e, b=btn, ckey=ck: b.config(bg=self._active_colors()[ckey]))
            self._tooltips.append(ToolTip(btn, tip, c))

        self.result_area = scrolledtext.ScrolledText(
            result_frame, bg=c["overlay"], fg=c["yellow"],
            insertbackground="white", font=("Consolas", 11), wrap=tk.WORD,
            relief=tk.FLAT, borderwidth=0, padx=8, pady=8,
        )
        self.result_area.pack(fill=tk.BOTH, expand=True)
        self.result_area.bind("<<Modified>>", self._on_result_modified)
        self.result_area.bind("<Control-a>", lambda e: (self._select_all_result(), "break")[-1])

        # Right-click context menu on result area
        self._result_ctx_menu = tk.Menu(self.root, tearoff=0, bg=c["surface"], fg=c["text"], font=("Segoe UI", 10))
        self._result_ctx_menu.add_command(label="\U0001f4cb Copy Prompt Only", command=self._copy_prompt_only)
        self._result_ctx_menu.add_command(label="\U0001f4c4 Copy All", command=self.copy_to_clipboard)
        self._result_ctx_menu.add_command(label="\u2702 Copy Selection", command=self._copy_selection)
        self._result_ctx_menu.add_separator()
        self._result_ctx_menu.add_command(label="\U0001f4c3 Paste", command=self._paste_into_result)
        self._result_ctx_menu.add_command(label="\u2610 Select All", command=self._select_all_result)
        self._result_ctx_menu.add_command(label="\u2715 Clear", command=self.clear_output)
        self.result_area.bind("<Button-3>", lambda e: self._result_ctx_menu.tk_popup(e.x_root, e.y_root))

        # ── Follow-Up / Update Chain (bottom) ──
        followup_frame = ttk.LabelFrame(right, text=" Update Chain (rolling follow-ups) ", padding=8)
        followup_frame.pack(fill=tk.X, pady=(6, 0))

        fu_desc = ttk.Label(
            followup_frame,
            text=(
                "Already gave the AI your code? Describe changes here. Each update is saved "
                "in a rolling chain — click any past update to copy it again."
            ),
            style="Sub.TLabel", wraplength=500,
        )
        fu_desc.pack(anchor=tk.W, pady=(0, 4))

        # Input box for the change request
        self.followup_input = tk.Text(
            followup_frame, height=3, bg=c["surface"], fg=c["text"],
            insertbackground="white", font=("Consolas", 11), wrap=tk.WORD,
            relief=tk.FLAT, padx=6, pady=6,
        )
        self.followup_input.pack(fill=tk.X, pady=(0, 4))
        self._themed_texts.append(self.followup_input)

        # Buttons
        fu_btn_row = ttk.Frame(followup_frame)
        fu_btn_row.pack(fill=tk.X, pady=(0, 4))
        for text, ck, cmd in [
            ("\u25b6 Add Update", "green", self._generate_followup),
            ("\u2398 Copy Selected", "teal", self._copy_followup),
            ("\u2398 Copy All Updates", "blue", self._copy_all_updates),
            ("\u2715 Clear Chain", "red", self._clear_followup),
        ]:
            btn = tk.Button(fu_btn_row, text=text, command=cmd, bg=c[ck], fg=c["dark"],
                            font=("Segoe UI", 9, "bold"), relief=tk.FLAT, padx=8, pady=3, cursor="hand2")
            btn.pack(side=tk.LEFT, padx=(0, 4))
            self._themed_buttons.append((btn, ck, ck))
            hover_color = _lighten_color(c[ck])
            btn.bind("<Enter>", lambda e, b=btn, hc=hover_color: b.config(bg=hc))
            btn.bind("<Leave>", lambda e, b=btn, ckey=ck: b.config(bg=self._active_colors()[ckey]))

        # Update chain list (clickable)
        self.update_chain_list = tk.Listbox(
            followup_frame, height=3, bg=c["overlay"], fg=c["teal"],
            font=("Consolas", 10), selectbackground=c["blue"],
            selectforeground=c["dark"], relief=tk.FLAT, borderwidth=0,
        )
        self.update_chain_list.pack(fill=tk.X, pady=(0, 4))

        # Selected update output (shows the full prompt when you click one)
        self.followup_output = scrolledtext.ScrolledText(
            followup_frame, height=5, bg=c["overlay"], fg=c["teal"],
            insertbackground="white", font=("Consolas", 11), wrap=tk.WORD,
            relief=tk.FLAT, borderwidth=0, padx=6, pady=6,
        )
        self.followup_output.pack(fill=tk.BOTH, expand=True)
        self._themed_texts.append(self.followup_output)

        # Click a chain item to preview it
        self.update_chain_list.bind("<<ListboxSelect>>", self._on_chain_select)

        templates_tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(templates_tab, text="  \u2630 Templates  ")
        self._build_templates_tab(templates_tab)

        history_tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(history_tab, text="  \u23f0 History  ")
        self._build_history_tab(history_tab)

        diag_tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(diag_tab, text="  \u2695 Diagnostics  ")
        self._build_diagnostics_tab(diag_tab)

    def _on_tab_changed(self, event: tk.Event = None) -> None:
        tab_text = self.notebook.tab(self.notebook.select(), "text").strip()
        self._status_mode.config(text=tab_text)

    # ── Prompt Category ──────────────────────────────────────────

    def _build_my_projects_section(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text=" My Projects (auto-discovered + built-in) ", padding=8)
        frame.pack(fill=tk.X, pady=(0, 6))
        c = self._active_colors()

        ttk.Label(
            frame,
            text=(
                "Pick a project — its conventions (build commands, patterns, widget rules) "
                "get auto-injected into every prompt. Auto-discovered from your chosen folder."
            ),
            style="Sub.TLabel", wraplength=450,
        ).pack(anchor=tk.W, pady=(0, 4))

        # Scan-root row (folder picker)
        scan_row = ttk.Frame(frame)
        scan_row.pack(fill=tk.X, pady=(2, 4))
        ttk.Label(scan_row, text="Scan folder:", style="Sub.TLabel").pack(side=tk.LEFT, padx=(0, 4))
        self._scan_root_var = tk.StringVar(value=str(self._scan_root))
        scan_entry = ttk.Entry(scan_row, textvariable=self._scan_root_var, font=("Segoe UI", 9))
        scan_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
        browse_btn = tk.Button(
            scan_row, text="...", command=self._browse_scan_root,
            bg=c["surface"], fg=c["text"], font=("Segoe UI", 9), relief=tk.FLAT,
            padx=8, pady=1, cursor="hand2",
        )
        browse_btn.pack(side=tk.LEFT, padx=(0, 2))
        self._themed_buttons.append((browse_btn, "surface", "surface"))
        rescan_btn = tk.Button(
            scan_row, text="Rescan", command=self._rescan_projects,
            bg=c["blue"], fg=c["dark"], font=("Segoe UI", 9, "bold"), relief=tk.FLAT,
            padx=8, pady=1, cursor="hand2",
        )
        rescan_btn.pack(side=tk.LEFT)
        self._themed_buttons.append((rescan_btn, "blue", "blue"))
        self._tooltips.append(ToolTip(rescan_btn, "Rescan the folder above for projects", c))

        # Search box
        search_row = ttk.Frame(frame)
        search_row.pack(fill=tk.X, pady=(2, 4))
        ttk.Label(search_row, text="Search:", style="Sub.TLabel").pack(side=tk.LEFT, padx=(0, 4))
        self._project_search_var = tk.StringVar(value="")
        search_entry = ttk.Entry(search_row, textvariable=self._project_search_var, font=("Segoe UI", 9))
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        search_entry.bind("<KeyRelease>", lambda e: self._refresh_project_list())

        # Scrollable project list
        self.my_project_var = tk.StringVar(value="(None)")
        list_container = ttk.Frame(frame)
        list_container.pack(fill=tk.X, pady=(2, 4))
        self._project_list_canvas = tk.Canvas(list_container, bg=c["bg"], highlightthickness=0, height=180)
        list_sb = ttk.Scrollbar(list_container, orient=tk.VERTICAL, command=self._project_list_canvas.yview)
        self._project_list_frame = ttk.Frame(self._project_list_canvas)
        self._project_list_frame.bind(
            "<Configure>",
            lambda e: self._project_list_canvas.configure(scrollregion=self._project_list_canvas.bbox("all")),
        )
        self._project_list_canvas.create_window((0, 0), window=self._project_list_frame, anchor="nw")
        self._project_list_canvas.configure(yscrollcommand=list_sb.set)
        self._project_list_canvas.pack(side=tk.LEFT, fill=tk.X, expand=True)
        list_sb.pack(side=tk.RIGHT, fill=tk.Y)

        # Working Directory row
        wd_row = ttk.Frame(frame)
        wd_row.pack(fill=tk.X, pady=(4, 2))
        ttk.Label(wd_row, text="Working dir:", style="Sub.TLabel").pack(side=tk.LEFT, padx=(0, 4))
        self.workdir_var = tk.StringVar(value="")
        wd_entry = ttk.Entry(wd_row, textvariable=self.workdir_var, font=("Segoe UI", 9))
        wd_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
        wd_browse = tk.Button(
            wd_row, text="...", command=self._browse_workdir,
            bg=c["surface"], fg=c["text"], font=("Segoe UI", 9), relief=tk.FLAT,
            padx=8, pady=1, cursor="hand2",
        )
        wd_browse.pack(side=tk.LEFT)
        self._themed_buttons.append((wd_browse, "surface", "surface"))
        self._tooltips.append(ToolTip(
            wd_browse,
            "The folder the AI should work in. Auto-filled when you pick a project. "
            "Prepends a '# WORKING DIRECTORY' section to the prompt.",
            c,
        ))

        # Populate the list on first build
        self._refresh_project_list()

        # When project changes, auto-fill workdir and maybe toggle Low Token Mode
        self.my_project_var.trace_add("write", lambda *_: self._on_project_changed())

    # ── v5.0 helper methods for projects ──

    def _refresh_project_list(self) -> None:
        """Rebuild the project radio button list based on current search filter."""
        for child in self._project_list_frame.winfo_children():
            child.destroy()
        query = (self._project_search_var.get() if hasattr(self, "_project_search_var") else "").strip().lower()

        # Always show (None) first
        first_items = [("(None)", self._merged_projects.get("(None)", {}))]
        built_in = [(n, d) for n, d in MY_PROJECTS.items() if n != "(None)"]
        discovered = [(n, d) for n, d in self._discovered_projects.items() if n not in MY_PROJECTS]
        # Merge: built-in first, then discovered (alphabetical within each group)
        all_items = first_items + sorted(built_in, key=lambda x: x[0]) + sorted(discovered, key=lambda x: x[0])

        shown = 0
        for name, data in all_items:
            desc = (data or {}).get("description", "")
            if query and query not in name.lower() and query not in desc.lower():
                continue
            rb = ttk.Radiobutton(
                self._project_list_frame, text=name,
                variable=self.my_project_var, value=name,
            )
            rb.pack(anchor=tk.W, padx=(2, 0))
            if desc:
                ttk.Label(
                    self._project_list_frame, text=desc[:200],
                    style="Desc.TLabel", wraplength=420,
                ).pack(anchor=tk.W, padx=(24, 0), pady=(0, 2))
            shown += 1

        if shown == 0:
            ttk.Label(
                self._project_list_frame,
                text=f"No projects match '{query}'. Try rescanning a different folder.",
                style="Warn.TLabel", wraplength=420,
            ).pack(anchor=tk.W, padx=(2, 0), pady=4)

    def _browse_scan_root(self) -> None:
        """Let user pick a new project-scan folder."""
        chosen = filedialog.askdirectory(
            title="Choose folder to scan for projects",
            initialdir=str(self._scan_root),
        )
        if chosen:
            self._scan_root = Path(chosen)
            self._scan_root_var.set(chosen)
            self._save_scan_root(self._scan_root)
            self._rescan_projects()

    def _rescan_projects(self) -> None:
        """Rescan current scan root and refresh the project list."""
        # Sync from var in case user typed manually
        typed = self._scan_root_var.get().strip()
        if typed:
            p = Path(typed)
            if p.is_dir():
                self._scan_root = p
                self._save_scan_root(p)
        self._refresh_discovered_projects()
        self._refresh_project_list()
        self._set_status(
            f"Scanned {self._scan_root.name}: found {len(self._discovered_projects)} projects"
        )

    def _browse_workdir(self) -> None:
        """Let user pick a working directory."""
        current = self.workdir_var.get().strip()
        init_dir = current if current and Path(current).is_dir() else str(self._scan_root)
        chosen = filedialog.askdirectory(
            title="Choose the working directory for this task",
            initialdir=init_dir,
        )
        if chosen:
            self.workdir_var.set(chosen)

    def _on_project_changed(self) -> None:
        """When a project is selected, auto-fill workdir and maybe enable Low Token Mode."""
        name = self.my_project_var.get()
        data = self._merged_projects.get(name, {})

        # Auto-fill working directory from project path
        proj_path = data.get("path", "")
        if proj_path and hasattr(self, "workdir_var"):
            # Only overwrite if workdir is empty or was an auto-filled path
            cur = self.workdir_var.get().strip()
            # Heuristic: overwrite if empty or if current matches any project path
            known_paths = {p.get("path", "") for p in self._merged_projects.values() if p.get("path")}
            if not cur or cur in known_paths:
                self.workdir_var.set(proj_path)

        # Auto-enable Low Token Mode for big projects (context > 2000 chars ≈ 500 tokens)
        context = data.get("context_block", "")
        if hasattr(self, "_low_token_var") and len(context) > 2000:
            if not self._low_token_var.get():
                self._low_token_var.set(True)
                self._toast(f"Low Token Mode auto-enabled for {name} (large context)")

    def _build_category_section(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text=" What Are You Prompting For? ", padding=8)
        frame.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(
            frame,
            text="Pick the type of prompt you're building. The options below will change to match.",
            style="Sub.TLabel", wraplength=450,
        ).pack(anchor=tk.W, pady=(0, 6))
        self.prompt_category_var = tk.StringVar(value="Code")
        cats = {
            "Code": "Build or improve software — PC apps, Pi apps, Android, games, websites.",
            "Conversation": "General AI chat — questions, brainstorming, teaching, creative writing.",
            "Image": "AI image generation prompts — DALL-E, Midjourney, Stable Diffusion, etc.",
            "Video": "AI video generation prompts — Sora, Runway, Pika, Kling, etc.",
        }
        for name, desc in cats.items():
            ttk.Radiobutton(frame, text=name, variable=self.prompt_category_var, value=name,
                            command=self._on_category_change).pack(anchor=tk.W)
            ttk.Label(frame, text=desc, style="Desc.TLabel", wraplength=430).pack(anchor=tk.W, padx=(24, 0), pady=(0, 4))

    def _on_category_change(self) -> None:
        cat = self.prompt_category_var.get()
        # Hide all category panels
        for panel in (self._code_panel, self._conv_panel, self._image_panel, self._video_panel):
            panel.pack_forget()
        # Show the selected one (insert before the role section)
        panels = {"Code": self._code_panel, "Conversation": self._conv_panel,
                  "Image": self._image_panel, "Video": self._video_panel}
        target = panels.get(cat)
        if target:
            # Pack it right after the category section (position 1 in the parent)
            target.pack(fill=tk.X, after=self.left_frame.winfo_children()[0])

        # Auto-adjust constraints per category (smart preselects)
        if hasattr(self, "constraint_vars"):
            if cat in ("Image", "Video"):
                # Python rules don't apply to image/video prompts
                if "Python Best Practices" in self.constraint_vars:
                    self.constraint_vars["Python Best Practices"].set(False)
                if "Robustness" in self.constraint_vars:
                    self.constraint_vars["Robustness"].set(False)
                # Conciseness helps for image/video (short, dense descriptors)
                if "Conciseness" in self.constraint_vars:
                    self.constraint_vars["Conciseness"].set(True)
            elif cat == "Code":
                # Reinstate Python defaults for Code
                if "Python Best Practices" in self.constraint_vars:
                    self.constraint_vars["Python Best Practices"].set(True)
                if "Conciseness" in self.constraint_vars:
                    self.constraint_vars["Conciseness"].set(True)
            elif cat == "Conversation":
                # Conversation: relax Python rules, keep conciseness
                if "Python Best Practices" in self.constraint_vars:
                    self.constraint_vars["Python Best Practices"].set(False)
                if "Conciseness" in self.constraint_vars:
                    self.constraint_vars["Conciseness"].set(True)

        self._set_status(f"Switched to {cat} prompting")

    # ── Conversation section ─────────────────────────────────────

    def _build_conversation_section(self, parent: ttk.Frame) -> None:
        # Style
        f1 = ttk.LabelFrame(parent, text=" Conversation Style ", padding=8)
        f1.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(f1, text="What kind of conversation do you want?", style="Sub.TLabel", wraplength=440).pack(anchor=tk.W, pady=(0, 6))
        self.conv_style_var = tk.StringVar(value="General Chat")
        for name, data in CONVERSATION_STYLES.items():
            ttk.Radiobutton(f1, text=name, variable=self.conv_style_var, value=name).pack(anchor=tk.W)
            ttk.Label(f1, text=data["description"], style="Desc.TLabel", wraplength=420).pack(anchor=tk.W, padx=(24, 0), pady=(0, 4))
        # Tone
        f2 = ttk.LabelFrame(parent, text=" Tone ", padding=8)
        f2.pack(fill=tk.X, pady=6)
        ttk.Label(f2, text="How should the AI sound?", style="Sub.TLabel", wraplength=440).pack(anchor=tk.W, pady=(0, 4))
        self.conv_tone_var = tk.StringVar(value="Casual")
        for name, desc in CONVERSATION_TONES.items():
            ttk.Radiobutton(f2, text=name, variable=self.conv_tone_var, value=name).pack(anchor=tk.W)
            ttk.Label(f2, text=desc, style="Desc.TLabel", wraplength=420).pack(anchor=tk.W, padx=(24, 0), pady=(0, 4))

    # ── Image section ────────────────────────────────────────────

    def _build_image_section(self, parent: ttk.Frame) -> None:
        # Style
        f1 = ttk.LabelFrame(parent, text=" Image Style ", padding=8)
        f1.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(f1, text="What visual style should the image have?", style="Sub.TLabel", wraplength=440).pack(anchor=tk.W, pady=(0, 6))
        self.image_style_var = tk.StringVar(value="Photorealistic")
        for name in IMAGE_STYLES:
            ttk.Radiobutton(f1, text=name, variable=self.image_style_var, value=name).pack(anchor=tk.W)
        # Lighting
        f2 = ttk.LabelFrame(parent, text=" Lighting ", padding=8)
        f2.pack(fill=tk.X, pady=6)
        ttk.Label(f2, text="What kind of lighting?", style="Sub.TLabel", wraplength=440).pack(anchor=tk.W, pady=(0, 4))
        self.image_lighting_var = tk.StringVar(value="Natural / Soft")
        for name in IMAGE_LIGHTING:
            ttk.Radiobutton(f2, text=name, variable=self.image_lighting_var, value=name).pack(anchor=tk.W)
        # Camera
        f3 = ttk.LabelFrame(parent, text=" Camera / Perspective ", padding=8)
        f3.pack(fill=tk.X, pady=6)
        ttk.Label(f3, text="What camera angle or lens?", style="Sub.TLabel", wraplength=440).pack(anchor=tk.W, pady=(0, 4))
        self.image_camera_var = tk.StringVar(value="Portrait (85mm)")
        for name in IMAGE_CAMERAS:
            ttk.Radiobutton(f3, text=name, variable=self.image_camera_var, value=name).pack(anchor=tk.W)

    # ── Video section ────────────────────────────────────────────

    def _build_video_section(self, parent: ttk.Frame) -> None:
        # Style
        f1 = ttk.LabelFrame(parent, text=" Video Style ", padding=8)
        f1.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(f1, text="What kind of video are you making?", style="Sub.TLabel", wraplength=440).pack(anchor=tk.W, pady=(0, 6))
        self.video_style_var = tk.StringVar(value="Cinematic")
        for name in VIDEO_STYLES:
            ttk.Radiobutton(f1, text=name, variable=self.video_style_var, value=name).pack(anchor=tk.W)
        # Camera Movement
        f2 = ttk.LabelFrame(parent, text=" Camera Movement ", padding=8)
        f2.pack(fill=tk.X, pady=6)
        ttk.Label(f2, text="How should the camera move?", style="Sub.TLabel", wraplength=440).pack(anchor=tk.W, pady=(0, 4))
        self.video_camera_var = tk.StringVar(value="Slow Pan")
        for name in VIDEO_CAMERA_MOVES:
            ttk.Radiobutton(f2, text=name, variable=self.video_camera_var, value=name).pack(anchor=tk.W)
        # Pacing
        f3 = ttk.LabelFrame(parent, text=" Pacing ", padding=8)
        f3.pack(fill=tk.X, pady=6)
        ttk.Label(f3, text="How fast should the video feel?", style="Sub.TLabel", wraplength=440).pack(anchor=tk.W, pady=(0, 4))
        self.video_pacing_var = tk.StringVar(value="Medium / Narrative")
        for name in VIDEO_PACING:
            ttk.Radiobutton(f3, text=name, variable=self.video_pacing_var, value=name).pack(anchor=tk.W)

    # ── Build Target ─────────────────────────────────────────────

    def _build_build_target_section(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text=" What Are You Building? (pick one) ", padding=8)
        frame.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(frame, text="Choose the type of thing you're creating. You can add extras in the next section.", style="Sub.TLabel", wraplength=450).pack(anchor=tk.W, pady=(0, 8))
        self.build_target_var = tk.StringVar(value="PC Desktop App")
        ttk.Radiobutton(frame, text="Nothing specific", variable=self.build_target_var, value="(none)").pack(anchor=tk.W)
        ttk.Label(frame, text="Skip this and use the Task Description box.", style="Desc.TLabel", wraplength=430).pack(anchor=tk.W, padx=(24, 0), pady=(0, 6))
        for name, data in BUILD_TARGETS.items():
            ttk.Radiobutton(frame, text=name, variable=self.build_target_var, value=name).pack(anchor=tk.W)
            ttk.Label(frame, text=data["description"], style="Desc.TLabel", wraplength=430).pack(anchor=tk.W, padx=(24, 0), pady=(0, 6))

    # ── Enhancements ─────────────────────────────────────────────

    def _build_enhancements_section(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text=" What Improvements? (pick any) ", padding=8)
        frame.pack(fill=tk.X, pady=6)
        ttk.Label(frame, text="Stack extras on top of your build target, or use alone.", style="Sub.TLabel", wraplength=450).pack(anchor=tk.W, pady=(0, 8))
        self.enhancement_vars: dict[str, tk.BooleanVar] = {}
        for name, data in ENHANCEMENTS.items():
            var = tk.BooleanVar(value=False)
            self.enhancement_vars[name] = var
            ttk.Checkbutton(frame, text=name, variable=var).pack(anchor=tk.W)
            ttk.Label(frame, text=data["description"], style="Desc.TLabel", wraplength=430).pack(anchor=tk.W, padx=(24, 0), pady=(0, 6))

    # ── Role ─────────────────────────────────────────────────────

    def _build_role_section(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text=" Persona / Role ", padding=8)
        frame.pack(fill=tk.X, pady=6)
        ttk.Label(frame, text="Who should the AI pretend to be? Leave blank to auto-fill.", style="Sub.TLabel", wraplength=450).pack(anchor=tk.W, pady=(0, 4))
        self.role_input = ttk.Entry(frame, font=("Segoe UI", 10))
        self.role_input.pack(fill=tk.X)

    # ── Reasoning ────────────────────────────────────────────────

    def _build_reasoning_section(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text=" Reasoning Framework ", padding=8)
        frame.pack(fill=tk.X, pady=6)
        ttk.Label(frame, text="How should the AI think? SCoT is best for coding.", style="Sub.TLabel", wraplength=450).pack(anchor=tk.W, pady=(0, 4))
        self.reasoning_var = tk.StringVar(value="Structured Chain of Thought (SCoT)")
        options = list(REASONING_MODES.keys())
        ttk.OptionMenu(frame, self.reasoning_var, options[1], *options, command=self._on_reasoning_change).pack(fill=tk.X)
        self.reasoning_desc = ttk.Label(frame, text=REASONING_MODES[options[1]]["description"], style="Desc.TLabel", wraplength=450)
        self.reasoning_desc.pack(anchor=tk.W, pady=(4, 0))

    # ── Output Format ────────────────────────────────────────────

    def _build_output_format_section(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text=" Output Format ", padding=8)
        frame.pack(fill=tk.X, pady=6)
        ttk.Label(frame, text="What shape should the answer come in?", style="Sub.TLabel", wraplength=450).pack(anchor=tk.W, pady=(0, 4))
        self.output_format_var = tk.StringVar(value="Free-form")
        options = list(OUTPUT_FORMATS.keys())
        ttk.OptionMenu(frame, self.output_format_var, options[0], *options, command=self._on_output_format_change).pack(fill=tk.X)
        self.output_format_desc = ttk.Label(frame, text=OUTPUT_FORMATS["Free-form"]["description"], style="Desc.TLabel", wraplength=450)
        self.output_format_desc.pack(anchor=tk.W, pady=(4, 0))

    # ── Constraints ──────────────────────────────────────────────

    def _build_constraints_section(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text=" Quality Rules ", padding=8)
        frame.pack(fill=tk.X, pady=6)
        ttk.Label(frame, text="Rules the AI MUST follow. Your selections above auto-add their own.", style="Sub.TLabel", wraplength=450).pack(anchor=tk.W, pady=(0, 6))
        self.constraint_vars: dict[str, tk.BooleanVar] = {}
        for name, data in CONSTRAINT_PRESETS.items():
            var = tk.BooleanVar(value=(name in ("Conciseness", "Python Best Practices")))
            self.constraint_vars[name] = var
            ttk.Checkbutton(frame, text=name, variable=var).pack(anchor=tk.W)
            ttk.Label(frame, text=data["description"], style="Desc.TLabel", wraplength=430).pack(anchor=tk.W, padx=(24, 0), pady=(0, 4))
        ttk.Label(frame, text="Custom rules (one per line):", style="Sub.TLabel").pack(anchor=tk.W, pady=(6, 2))
        c = self._active_colors()
        self.custom_constraints = tk.Text(
            frame, height=2, bg=c["surface"], fg=c["text"],
            insertbackground="white", font=("Consolas", 10), relief=tk.FLAT, padx=6, pady=4, undo=True, maxundo=-1,
        )
        self.custom_constraints.pack(fill=tk.X)
        self._themed_texts.append(self.custom_constraints)

    # ── Context ──────────────────────────────────────────────────

    def _build_context_section(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text=" Extra Context / Examples ", padding=8)
        frame.pack(fill=tk.X, pady=6)
        top_row = ttk.Frame(frame)
        top_row.pack(fill=tk.X, pady=(0, 4))
        ttk.Label(top_row, text="Optional. Paste extra info, docs, or {{placeholders}}.", style="Sub.TLabel").pack(side=tk.LEFT)
        c = self._active_colors()
        ctx_clear = tk.Button(
            top_row, text="\u2715 Clear", command=self._clear_context,
            bg=c["surface"], fg=c["red"], font=("Segoe UI", 8), relief=tk.FLAT,
            padx=6, pady=1, cursor="hand2",
        )
        ctx_clear.pack(side=tk.RIGHT)
        self._themed_buttons.append((ctx_clear, "surface", "surface"))
        ttk.Label(frame, text="\u26a0 Do not paste API keys, passwords, or secrets here.", style="Warn.TLabel").pack(anchor=tk.W, pady=(0, 4))
        self.context_input = tk.Text(
            frame, height=3, bg=c["surface"], fg=c["text"],
            insertbackground="white", font=("Consolas", 10), relief=tk.FLAT, padx=6, pady=4, undo=True, maxundo=-1,
        )
        self.context_input.pack(fill=tk.BOTH, expand=True)
        self._themed_texts.append(self.context_input)

    # ── Task ─────────────────────────────────────────────────────

    def _build_task_section(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text=" Task Description ", padding=8)
        frame.pack(fill=tk.X, pady=6)
        top_row = ttk.Frame(frame)
        top_row.pack(fill=tk.X, pady=(0, 4))
        ttk.Label(top_row, text="WHAT should the AI do? Be specific \u2014 more detail = better result.", style="Sub.TLabel").pack(side=tk.LEFT)
        c = self._active_colors()
        task_clear = tk.Button(
            top_row, text="\u2715 Clear", command=self._clear_task,
            bg=c["surface"], fg=c["red"], font=("Segoe UI", 8), relief=tk.FLAT,
            padx=6, pady=1, cursor="hand2",
        )
        task_clear.pack(side=tk.RIGHT)
        self._themed_buttons.append((task_clear, "surface", "surface"))
        self.task_input = scrolledtext.ScrolledText(
            frame, height=5, bg=c["surface"], fg=c["text"],
            insertbackground="white", font=("Consolas", 11), wrap=tk.WORD,
            relief=tk.FLAT, borderwidth=0, padx=6, pady=6, undo=True, maxundo=-1,
        )
        self.task_input.pack(fill=tk.BOTH, expand=True)
        self.task_input.insert(tk.END, "Create a Python script that monitors CPU usage and logs it to a CSV file every 5 seconds.")
        self._themed_texts.append(self.task_input)

    # ── Buttons ──────────────────────────────────────────────────

    def _build_buttons(self, parent: ttk.Frame) -> None:
        frame = ttk.Frame(parent)
        frame.pack(fill=tk.X, pady=(8, 4))
        c = self._active_colors()
        btn_defs = [
            ("\u25b6 GENERATE", "green", self.generate, "Build the prompt from current settings (Ctrl+Enter)"),
            ("\u2398 COPY", "blue", self.copy_to_clipboard, "Copy prompt to clipboard (Ctrl+Shift+C)"),
            ("\u2b07 SAVE", "peach", self.save_to_file, "Save prompt to a file (Ctrl+S)"),
            ("\u21ba CLEAR INPUTS", "yellow", self.clear_inputs, "Clear task + context boxes (keeps all settings)"),
            ("\u2715 CLEAR OUTPUT", "red", self.clear_output, "Clear the generated prompt output"),
        ]
        for text, color_key, cmd, tooltip_text in btn_defs:
            btn = tk.Button(
                frame, text=text, command=cmd,
                bg=c[color_key], fg=c["dark"], font=("Segoe UI", 10, "bold"),
                relief=tk.FLAT, padx=14, pady=6, cursor="hand2",
            )
            btn.pack(side=tk.LEFT, padx=(0, 6))
            self._themed_buttons.append((btn, color_key, color_key))
            hover_color = _lighten_color(c[color_key])
            btn.bind("<Enter>", lambda e, b=btn, hc=hover_color: b.config(bg=hc))
            btn.bind("<Leave>", lambda e, b=btn, ck=color_key: b.config(bg=self._active_colors()[ck]))
            self._tooltips.append(ToolTip(btn, tooltip_text, c))

        # Primary AI services shown as buttons (rest go in the overflow combobox)
        primary_services = ["Claude", "ChatGPT", "Gemini"]

        # ── Grab from AI row ──
        grab_frame = ttk.Frame(parent)
        grab_frame.pack(fill=tk.X, pady=(4, 2))
        ttk.Label(grab_frame, text="Grab + Enhance + Send:", style="Sub.TLabel").pack(side=tk.LEFT, padx=(0, 8))
        for display_name, color_key, _search, _cat_key in AI_SERVICES:
            if display_name not in primary_services:
                continue
            btn = tk.Button(
                grab_frame, text=f"\U0001f4e5 {display_name}",
                command=lambda n=display_name: self._grab_enhance_send(n),
                bg=c[color_key], fg=c["dark"], font=("Segoe UI", 9, "bold"),
                relief=tk.FLAT, padx=10, pady=4, cursor="hand2",
            )
            btn.pack(side=tk.LEFT, padx=(0, 4))
            self._themed_buttons.append((btn, color_key, color_key))
            hover = _lighten_color(c[color_key])
            btn.bind("<Enter>", lambda e, b=btn, h=hover: b.config(bg=h))
            btn.bind("<Leave>", lambda e, b=btn, ck=color_key: b.config(bg=self._active_colors()[ck]))
            self._tooltips.append(ToolTip(
                btn, f"Grab what's in the {display_name} input box, enhance with project "
                     f"context + token savings, paste back ready to submit.", c))
        # Any window
        any_grab = tk.Button(
            grab_frame, text="\U0001f4e5 Any",
            command=lambda: self._grab_enhance_send(None),
            bg=c["teal"], fg=c["dark"], font=("Segoe UI", 9, "bold"),
            relief=tk.FLAT, padx=10, pady=4, cursor="hand2",
        )
        any_grab.pack(side=tk.LEFT, padx=(0, 4))
        self._themed_buttons.append((any_grab, "teal", "teal"))
        self._tooltips.append(ToolTip(any_grab, "3-sec countdown: click any AI input, then grab+enhance+paste-back.", c))

        # ── Send to AI row ──
        send_frame = ttk.Frame(parent)
        send_frame.pack(fill=tk.X, pady=(4, 2))
        ttk.Label(send_frame, text="Send prompt to AI:", style="Sub.TLabel").pack(side=tk.LEFT, padx=(0, 8))
        for display_name, color_key, _search, _cat_key in AI_SERVICES:
            if display_name not in primary_services:
                continue
            btn = tk.Button(
                send_frame, text=f"\U0001f4e4 {display_name}",
                command=lambda n=display_name: self._send_to_ai_window(n),
                bg=c[color_key], fg=c["dark"], font=("Segoe UI", 9, "bold"),
                relief=tk.FLAT, padx=10, pady=4, cursor="hand2",
            )
            btn.pack(side=tk.LEFT, padx=(0, 4))
            self._themed_buttons.append((btn, color_key, color_key))
            hover = _lighten_color(c[color_key])
            btn.bind("<Enter>", lambda e, b=btn, h=hover: b.config(bg=h))
            btn.bind("<Leave>", lambda e, b=btn, ck=color_key: b.config(bg=self._active_colors()[ck]))
            self._tooltips.append(ToolTip(
                btn, f"Find an open {display_name} browser tab and paste your prompt.", c))
        any_send = tk.Button(
            send_frame, text="\U0001f4e4 Any Window",
            command=self._send_to_any_window,
            bg=c["teal"], fg=c["dark"], font=("Segoe UI", 9, "bold"),
            relief=tk.FLAT, padx=10, pady=4, cursor="hand2",
        )
        any_send.pack(side=tk.LEFT, padx=(0, 4))
        self._themed_buttons.append((any_send, "teal", "teal"))
        self._tooltips.append(ToolTip(any_send, "Pick any window: 3-sec countdown, paste into whatever you click.", c))

        # ── Other AIs dropdown (overflow) ──
        # Gives access to DeepSeek, Qwen, Mistral, Grok, Perplexity, OpenRouter
        # without cluttering the button rows.
        more_frame = ttk.Frame(parent)
        more_frame.pack(fill=tk.X, pady=(4, 2))
        ttk.Label(more_frame, text="More AIs:", style="Sub.TLabel").pack(side=tk.LEFT, padx=(0, 8))

        other_ai_names = [n for n, *_ in AI_SERVICES if n not in primary_services]
        self._other_ai_var = tk.StringVar(value=other_ai_names[0] if other_ai_names else "")
        other_combo = ttk.Combobox(
            more_frame, textvariable=self._other_ai_var,
            state="readonly", width=14, font=("Segoe UI", 9),
            values=other_ai_names,
        )
        other_combo.pack(side=tk.LEFT, padx=(0, 6))

        for label, color_key, cmd_name, tip in [
            ("\U0001f4e5 Grab", "peach", "grab",
             "Grab+enhance+paste-back for the AI selected in the dropdown"),
            ("\U0001f4e4 Send", "surface", "send",
             "Send current prompt to the AI selected in the dropdown"),
            ("\u2398 Copy & Show Model", "blue", "copy",
             "Copy prompt to clipboard and show recommended model for the selected AI"),
        ]:
            mbtn = tk.Button(
                more_frame, text=label,
                command=lambda act=cmd_name: self._dispatch_other_ai(act),
                bg=c[color_key], fg=c["dark"], font=("Segoe UI", 9, "bold"),
                relief=tk.FLAT, padx=10, pady=4, cursor="hand2",
            )
            mbtn.pack(side=tk.LEFT, padx=(0, 4))
            self._themed_buttons.append((mbtn, color_key, color_key))
            hover = _lighten_color(c[color_key])
            mbtn.bind("<Enter>", lambda e, b=mbtn, h=hover: b.config(bg=h))
            mbtn.bind("<Leave>", lambda e, b=mbtn, ck=color_key: b.config(bg=self._active_colors()[ck]))
            self._tooltips.append(ToolTip(mbtn, tip, c))

    # ── Templates tab ────────────────────────────────────────────

    def _build_templates_tab(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="Save and reload your settings so you don't reconfigure every time.", style="Sub.TLabel", wraplength=600).pack(anchor=tk.W, pady=(0, 8))
        c = self._active_colors()
        top = ttk.Frame(parent)
        top.pack(fill=tk.X, pady=(0, 10))
        for text, ck, cmd, tip in [
            ("SAVE AS TEMPLATE", "peach", self._save_template, "Save current settings as a reusable template"),
            ("LOAD SELECTED", "blue", self._load_template, "Load the selected template"),
            ("DELETE SELECTED", "red", self._delete_template, "Delete the selected template"),
        ]:
            btn = tk.Button(top, text=text, command=cmd, bg=c[ck], fg=c["dark"], font=("Segoe UI", 10, "bold"), relief=tk.FLAT, padx=14, pady=6, cursor="hand2")
            btn.pack(side=tk.LEFT, padx=(0, 6))
            self._themed_buttons.append((btn, ck, ck))
            self._tooltips.append(ToolTip(btn, tip, c))
        self.template_listbox = tk.Listbox(parent, bg=c["surface"], fg=c["text"], font=("Consolas", 11), selectbackground=c["blue"], selectforeground=c["dark"], relief=tk.FLAT, borderwidth=0)
        self.template_listbox.pack(fill=tk.BOTH, expand=True)
        self._refresh_template_list()

    def _refresh_template_list(self) -> None:
        self.template_listbox.delete(0, tk.END)
        tdir = Path(TEMPLATES_DIR)
        if tdir.is_dir():
            for fp in sorted(tdir.iterdir()):
                if fp.suffix == ".json":
                    self.template_listbox.insert(tk.END, fp.stem)
        # Also refresh the quick-switcher combobox if it exists
        if hasattr(self, "_template_quick_combo"):
            self._refresh_template_quick_list()

    def _refresh_template_quick_list(self) -> None:
        """Refresh the values in the top-ribbon template combobox."""
        names = []
        tdir = Path(TEMPLATES_DIR)
        if tdir.is_dir():
            try:
                for fp in sorted(tdir.iterdir()):
                    if fp.suffix == ".json":
                        names.append(fp.stem)
            except OSError:
                pass
        if hasattr(self, "_template_quick_combo"):
            self._template_quick_combo["values"] = names

    def _load_template_by_name(self) -> None:
        """Load the template selected in the top-ribbon combobox."""
        name = self._template_quick_var.get().strip()
        if not name:
            return
        try:
            path = self._safe_template_path(name)
        except ValueError:
            messagebox.showerror("Error", "Invalid template name.")
            return
        if not path.exists():
            messagebox.showwarning("Not Found", f"Template '{name}' not found.")
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            messagebox.showerror("Load Failed", f"Could not read: {exc}")
            return
        valid, msg = self._validate_template(data)
        if not valid:
            messagebox.showerror("Invalid Template", msg)
            return
        self._apply_state(data)
        self._toast(f"Loaded template: {name}")
        self._set_status(f"Template loaded: {name}")

    def _new_from_quick(self) -> None:
        """Clear current settings for a fresh start, asking first."""
        if self._dirty and not messagebox.askyesno(
            "Discard changes?",
            "You have unsaved changes. Discard and start fresh?",
        ):
            return
        # Clear task + context, reset selections to defaults
        self.task_input.delete("1.0", tk.END)
        self.context_input.delete("1.0", tk.END)
        self.custom_constraints.delete("1.0", tk.END)
        self.role_input.delete(0, tk.END)
        if hasattr(self, "workdir_var"):
            self.workdir_var.set("")
        if hasattr(self, "my_project_var"):
            self.my_project_var.set("(None)")
        self._template_quick_var.set("")
        self._set_status("New session started")

    def _save_template_from_quick(self) -> None:
        """Prompt for a name and save current state, then refresh combobox."""
        self._save_template()  # Reuse existing flow
        self._refresh_template_quick_list()

    def _delete_template_from_quick(self) -> None:
        """Delete the currently selected quick-switcher template."""
        name = self._template_quick_var.get().strip()
        if not name:
            self._set_status("No template selected")
            return
        if not messagebox.askyesno("Confirm Delete", f"Delete template '{name}'?"):
            return
        try:
            path = self._safe_template_path(name)
            if path.exists():
                path.unlink()
            self._template_quick_var.set("")
            self._refresh_template_list()
            self._set_status(f"Deleted template: {name}")
        except (ValueError, OSError) as exc:
            messagebox.showerror("Delete Failed", str(exc))

    def _safe_template_path(self, name: str) -> Path:
        """Validate and return a safe template file path, preventing path traversal."""
        safe = re.sub(r'[^\w\- ]', '', name).strip()
        if not safe:
            raise ValueError("Invalid template name")
        tdir = Path(TEMPLATES_DIR).resolve()
        path = (tdir / f"{safe}.json").resolve()
        if not str(path).startswith(str(tdir)):
            raise ValueError("Path traversal detected")
        return path

    def _validate_template(self, data: object) -> tuple[bool, str]:
        """Validate template JSON has required keys and types."""
        if not isinstance(data, dict):
            return False, "Template is not a JSON object"
        for key in TEMPLATE_SCHEMA_KEYS:
            if key not in data:
                return False, f"Missing required key: {key}"
        if not isinstance(data.get("enhancements"), dict):
            return False, "'enhancements' must be a dict"
        if not isinstance(data.get("constraints"), dict):
            return False, "'constraints' must be a dict"
        return True, ""

    def _save_template(self) -> None:
        name = self._ask_string("Template Name", "Enter a name for this template:")
        if not name:
            return
        try:
            path = self._safe_template_path(name)
        except ValueError as e:
            messagebox.showwarning("Invalid Name", str(e))
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        data = self._collect_state()
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            self._refresh_template_list()
            self._toast(f"Template '{path.stem}' saved")
            logger.info(f"Template saved: {path.stem}")
        except OSError as e:
            messagebox.showerror("Save Failed", f"Could not save template: {e.strerror}")

    def _load_template(self) -> None:
        sel = self.template_listbox.curselection()
        if not sel:
            messagebox.showwarning("Select", "Select a template first.")
            return
        name = self.template_listbox.get(sel[0])
        try:
            path = self._safe_template_path(name)
        except ValueError as e:
            messagebox.showerror("Error", str(e))
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            messagebox.showerror("Load Failed", f"Could not load template: {e}")
            return
        valid, msg = self._validate_template(data)
        if not valid:
            messagebox.showerror("Invalid Template", msg)
            return
        self._apply_state(data)
        self._toast(f"Template '{name}' loaded")
        logger.info(f"Template loaded: {name}")

    def _load_template_via_menu(self) -> None:
        self.notebook.select(1)

    def _delete_template(self) -> None:
        sel = self.template_listbox.curselection()
        if not sel:
            return
        name = self.template_listbox.get(sel[0])
        if messagebox.askyesno("Confirm", f"Delete template '{name}'?"):
            try:
                path = self._safe_template_path(name)
                path.unlink(missing_ok=True)
                self._refresh_template_list()
                self._toast(f"Template '{name}' deleted")
                logger.info(f"Template deleted: {name}")
            except (ValueError, OSError) as e:
                messagebox.showerror("Error", str(e))

    def _collect_state(self) -> dict:
        return {
            "my_project": self.my_project_var.get() if hasattr(self, "my_project_var") else "(None)",
            "workdir": self.workdir_var.get() if hasattr(self, "workdir_var") else "",
            "low_token_mode": self._low_token_var.get() if hasattr(self, "_low_token_var") else False,
            "prompt_category": self.prompt_category_var.get(),
            "build_target": self.build_target_var.get(),
            "enhancements": {k: v.get() for k, v in self.enhancement_vars.items()},
            "role": self.role_input.get(),
            "reasoning": self.reasoning_var.get(),
            "output_format": self.output_format_var.get(),
            "constraints": {k: v.get() for k, v in self.constraint_vars.items()},
            "custom_constraints": self.custom_constraints.get("1.0", tk.END).strip(),
            "conv_style": self.conv_style_var.get(),
            "conv_tone": self.conv_tone_var.get(),
            "image_style": self.image_style_var.get(),
            "image_lighting": self.image_lighting_var.get(),
            "image_camera": self.image_camera_var.get(),
            "video_style": self.video_style_var.get(),
            "video_camera": self.video_camera_var.get(),
            "video_pacing": self.video_pacing_var.get(),
            "context": self.context_input.get("1.0", tk.END).strip(),
            "task": self.task_input.get("1.0", tk.END).strip(),
        }

    def _apply_state(self, data: dict) -> None:
        if hasattr(self, "my_project_var"):
            self.my_project_var.set(data.get("my_project", "(None)"))
        if hasattr(self, "workdir_var"):
            self.workdir_var.set(data.get("workdir", ""))
        if hasattr(self, "_low_token_var"):
            self._low_token_var.set(bool(data.get("low_token_mode", False)))
        cat = data.get("prompt_category", "Code")
        self.prompt_category_var.set(cat)
        self._on_category_change()
        self.build_target_var.set(data.get("build_target", "(none)"))
        for k, v in data.get("enhancements", {}).items():
            if k in self.enhancement_vars:
                self.enhancement_vars[k].set(v)
        self.role_input.delete(0, tk.END)
        self.role_input.insert(0, data.get("role", ""))
        self.reasoning_var.set(data.get("reasoning", "None"))
        self.output_format_var.set(data.get("output_format", "Free-form"))
        for k, v in data.get("constraints", {}).items():
            if k in self.constraint_vars:
                self.constraint_vars[k].set(v)
        self.custom_constraints.delete("1.0", tk.END)
        self.custom_constraints.insert("1.0", data.get("custom_constraints", ""))
        self.conv_style_var.set(data.get("conv_style", "General Chat"))
        self.conv_tone_var.set(data.get("conv_tone", "Casual"))
        self.image_style_var.set(data.get("image_style", "Photorealistic"))
        self.image_lighting_var.set(data.get("image_lighting", "Natural / Soft"))
        self.image_camera_var.set(data.get("image_camera", "Portrait (85mm)"))
        self.video_style_var.set(data.get("video_style", "Cinematic"))
        self.video_camera_var.set(data.get("video_camera", "Slow Pan"))
        self.video_pacing_var.set(data.get("video_pacing", "Medium / Narrative"))
        self.context_input.delete("1.0", tk.END)
        self.context_input.insert("1.0", data.get("context", ""))
        self.task_input.delete("1.0", tk.END)
        self.task_input.insert("1.0", data.get("task", ""))

    # ── History tab ──────────────────────────────────────────────

    def _build_history_tab(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="Every prompt you generate is saved here. Click and Load to reuse.", style="Sub.TLabel", wraplength=600).pack(anchor=tk.W, pady=(0, 8))
        c = self._active_colors()
        search_frame = ttk.Frame(parent)
        search_frame.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(search_frame, text="\U0001F50D", font=("Segoe UI", 10)).pack(side=tk.LEFT, padx=(0, 4))
        self._history_search = ttk.Entry(search_frame, font=("Segoe UI", 10))
        self._history_search.pack(fill=tk.X, expand=True)
        self._history_search.bind("<KeyRelease>", self._filter_history)

        top = ttk.Frame(parent)
        top.pack(fill=tk.X, pady=(0, 10))
        for text, ck, cmd, tip in [
            ("LOAD", "blue", self._load_history_item, "Load selected prompt back into output"),
            ("\U0001f4cb COPY PROMPT", "green", self._copy_history_item, "Copy the selected prompt to clipboard"),
            ("EXPORT", "peach", self._export_history, "Export all history to a JSON file"),
            ("CLEAR", "red", self._clear_history, "Clear all history entries"),
        ]:
            btn = tk.Button(top, text=text, command=cmd, bg=c[ck], fg=c["dark"], font=("Segoe UI", 10, "bold"), relief=tk.FLAT, padx=14, pady=6, cursor="hand2")
            btn.pack(side=tk.LEFT, padx=(0, 6))
            self._themed_buttons.append((btn, ck, ck))
            self._tooltips.append(ToolTip(btn, tip, c))

        self.history_listbox = tk.Listbox(parent, bg=c["surface"], fg=c["text"], font=("Consolas", 11), selectbackground=c["blue"], selectforeground=c["dark"], relief=tk.FLAT, borderwidth=0)
        self.history_listbox.pack(fill=tk.BOTH, expand=True)

    def _filter_history(self, event: tk.Event = None) -> None:
        query = self._history_search.get().strip().lower()
        self.history_listbox.delete(0, tk.END)
        for entry in self.history:
            preview = entry.get("task_preview", "")
            if not query or query in preview.lower():
                self.history_listbox.insert(tk.END, f"[{entry['timestamp']}] {preview}")

    def _load_history_item(self) -> None:
        sel = self.history_listbox.curselection()
        if not sel:
            return
        display_text = self.history_listbox.get(sel[0])
        for entry in self.history:
            if f"[{entry['timestamp']}] {entry['task_preview']}" == display_text:
                self.result_area.delete("1.0", tk.END)
                self.result_area.insert(tk.END, entry["prompt"])
                self.notebook.select(0)
                self._set_status("Loaded prompt from history")
                return

    def _clear_history(self) -> None:
        if messagebox.askyesno("Confirm", "Clear all history?"):
            self.history.clear()
            self.history_listbox.delete(0, tk.END)
            self._save_history_to_disk()
            self._set_status("History cleared")

    def _export_history(self) -> None:
        if not self.history:
            messagebox.showwarning("Empty", "No history to export.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON", "*.json")])
        if path:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(self.history, f, indent=2)
                self._toast(f"History exported ({len(self.history)} entries)")
            except OSError as e:
                messagebox.showerror("Export Failed", e.strerror or str(e))

    # ── Diagnostics tab ──────────────────────────────────────────

    def _build_diagnostics_tab(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="Generate a health report for troubleshooting. Saves a .txt file to your Desktop.", style="Sub.TLabel", wraplength=600).pack(anchor=tk.W, pady=(0, 10))
        c = self._active_colors()
        btn_frame = ttk.Frame(parent)
        btn_frame.pack(fill=tk.X, pady=(0, 10))
        for text, ck, cmd, tip in [
            ("\u2695 RUN DIAGNOSTICS & SAVE", "teal", self._run_diagnostics, "Generate and save a diagnostic report to Desktop"),
            ("\u2398 COPY TO CLIPBOARD", "blue", self._copy_diagnostics, "Copy the diagnostic report to clipboard"),
        ]:
            btn = tk.Button(btn_frame, text=text, command=cmd, bg=c[ck], fg=c["dark"], font=("Segoe UI", 11, "bold"), relief=tk.FLAT, padx=20, pady=8, cursor="hand2")
            btn.pack(side=tk.LEFT, padx=(0, 6))
            self._themed_buttons.append((btn, ck, ck))
            self._tooltips.append(ToolTip(btn, tip, c))

        self.diag_area = scrolledtext.ScrolledText(parent, bg=c["overlay"], fg=c["green"], font=("Consolas", 10), wrap=tk.WORD, relief=tk.FLAT, padx=8, pady=8)
        self.diag_area.pack(fill=tk.BOTH, expand=True)

    def _generate_diagnostic_report(self) -> str:
        start = time.time()
        lines: list[str] = []
        sep = "=" * 70

        lines.append(sep)
        lines.append(f"  {DIAG_VERSION} -- Diagnostic Report")
        lines.append(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(sep)
        lines.append("")
        lines.append("  To share this report for support, copy the entire contents.")
        lines.append("  No passwords, API keys, or tokens are included in this report.")
        lines.append("")

        lines.append(f"{sep}\n  1. SYSTEM INFORMATION\n{sep}")
        lines.append(f"  OS:              {platform.system()} {platform.release()} ({platform.version()})")
        lines.append(f"  Architecture:    {platform.machine()}")
        lines.append(f"  Python:          {sys.version}")
        lines.append(f"  Tk Version:      {tk.TkVersion}")
        lines.append(f"  Working Dir:     {Path.cwd()}")
        try:
            lines.append(f"  Screen:          {self.root.winfo_screenwidth()}x{self.root.winfo_screenheight()}")
        except tk.TclError:
            pass
        lines.append("")

        lines.append(f"{sep}\n  2. APPLICATION STATE\n{sep}")
        lines.append(f"  Uptime:          {datetime.now() - self._startup_time}")
        lines.append(f"  History entries:  {len(self.history)}")
        lines.append(f"  Theme:           {'Dark' if self._dark_mode else 'Light'}")
        try:
            lines.append(f"  Build target:    {self.build_target_var.get()}")
            active_enh = [k for k, v in self.enhancement_vars.items() if v.get()]
            lines.append(f"  Enhancements:    {', '.join(active_enh) if active_enh else '(none)'}")
            lines.append(f"  Reasoning mode:  {self.reasoning_var.get()}")
            lines.append(f"  Output format:   {self.output_format_var.get()}")
        except (AttributeError, tk.TclError):
            lines.append("  (UI not fully initialized)")
        lines.append("")

        lines.append(f"{sep}\n  3. DEPENDENCY CHECK\n{sep}")
        for mod_name in ["tkinter", "json", "pathlib", "re", "platform", "traceback", "logging", "hashlib"]:
            try:
                mod = __import__(mod_name)
                ver = getattr(mod, "__version__", getattr(mod, "version", "built-in"))
                lines.append(f"  [OK]   {mod_name} ({ver})")
            except ImportError:
                lines.append(f"  [FAIL] {mod_name} -- NOT INSTALLED")
        for opt_mod in ["psutil"]:
            try:
                mod = __import__(opt_mod)
                lines.append(f"  [OK]   {opt_mod} ({getattr(mod, '__version__', '?')})")
            except ImportError:
                lines.append(f"  [OPT]  {opt_mod} -- not installed (optional)")
        lines.append("")

        lines.append(f"{sep}\n  4. RECENT ERRORS ({len(self._error_log)} captured)\n{sep}")
        if not self._error_log:
            lines.append("  No errors recorded this session.")
        else:
            for err in self._error_log[-20:]:
                lines.append(f"  [{err['time']}] {err['type']}: {err['message']}")
                for tb_line in err.get("traceback", []):
                    for sub in tb_line.strip().splitlines():
                        lines.append(f"    {sub}")
                lines.append("")

        lines.append(f"{sep}\n  5. PERFORMANCE\n{sep}")
        try:
            import psutil
            proc = psutil.Process(os.getpid())
            mem = proc.memory_info()
            lines.append(f"  Memory (RSS):    {mem.rss / 1024 / 1024:.1f} MB")
            lines.append(f"  CPU percent:     {proc.cpu_percent(interval=0.5):.1f}%")
        except ImportError:
            lines.append("  psutil not installed -- install for memory/CPU details.")
        lines.append(f"  Startup time:    {self._startup_time.strftime('%H:%M:%S')}")
        lines.append("")

        lines.append(f"{sep}\n  6. NETWORK CONNECTIVITY\n{sep}")
        try:
            import urllib.request
            urllib.request.urlopen("https://httpbin.org/get", timeout=5)
            lines.append("  [OK]   Internet connectivity")
        except Exception as e:
            lines.append(f"  [FAIL] Internet: {type(e).__name__}")
        lines.append("")

        lines.append(f"{sep}\n  7. DISK SPACE\n{sep}")
        try:
            usage = shutil.disk_usage(Path.home())
            lines.append(f"  Total: {usage.total / (1024**3):.1f} GB")
            lines.append(f"  Free:  {usage.free / (1024**3):.1f} GB")
        except Exception as e:
            lines.append(f"  Could not check: {e}")
        lines.append("")

        lines.append(f"{sep}\n  8. TEMPLATE & LOG AUDIT\n{sep}")
        tdir = Path(TEMPLATES_DIR)
        if tdir.is_dir():
            templates = list(tdir.glob("*.json"))
            total_size = sum(f.stat().st_size for f in templates)
            lines.append(f"  Templates: {len(templates)} ({total_size / 1024:.1f} KB)")
        else:
            lines.append("  Template directory does not exist yet.")
        if LOG_FILE.exists():
            lines.append(f"  Log file: {LOG_FILE} ({LOG_FILE.stat().st_size / 1024:.1f} KB)")
        else:
            lines.append(f"  Log file: {LOG_FILE} (not created yet)")
        lines.append("")

        elapsed = time.time() - start
        lines.append(f"  Report generated in {elapsed:.2f}s")
        lines.append(sep)
        return "\n".join(lines)

    def _run_diagnostics(self) -> None:
        report = self._generate_diagnostic_report()
        self.diag_area.delete("1.0", tk.END)
        self.diag_area.insert(tk.END, report)
        desktop = Path.home() / "Desktop"
        if not desktop.is_dir():
            desktop = Path.home()
        filepath = desktop / f"prompt_architect_diagnostic_{datetime.now().strftime('%Y-%m-%d_%H%M%S')}.txt"
        try:
            filepath.write_text(report, encoding="utf-8")
            self._toast("Report saved to Desktop")
            self._set_status(f"Diagnostic report saved: {filepath.name}")
            logger.info(f"Diagnostics saved: {filepath}")
        except OSError as e:
            messagebox.showerror("Save Failed", f"Could not save: {e.strerror}")

    def _copy_diagnostics(self) -> None:
        content = self.diag_area.get("1.0", tk.END).strip()
        if not content:
            self._run_diagnostics()
            content = self.diag_area.get("1.0", tk.END).strip()
        if content:
            try:
                self.root.clipboard_clear()
                self.root.clipboard_append(content)
                self._toast("Diagnostic report copied")
            except tk.TclError:
                messagebox.showerror("Error", "Could not access clipboard.")

    # ══════════════════════════════════════════════════════════════
    # PROMPT GENERATION
    # ══════════════════════════════════════════════════════════════

    def generate(self) -> None:
        task = self.task_input.get("1.0", tk.END).strip()
        if not task:
            messagebox.showwarning("Missing Task", "Enter a task/prompt description.")
            return
        if len(task.encode("utf-8")) > INPUT_LIMITS["task"]:
            messagebox.showwarning("Input Too Large", "Task text exceeds 50 KB limit. Please shorten it.")
            return
        ctx_text = self.context_input.get("1.0", tk.END).strip()
        if len(ctx_text.encode("utf-8")) > INPUT_LIMITS["context"]:
            messagebox.showwarning("Input Too Large", "Context text exceeds 100 KB limit.")
            return
        cust_text = self.custom_constraints.get("1.0", tk.END).strip()
        if len(cust_text.encode("utf-8")) > INPUT_LIMITS["custom_constraints"]:
            messagebox.showwarning("Input Too Large", "Custom constraints exceed 10 KB limit.")
            return

        user_role = self.role_input.get().strip()
        mode = self.reasoning_var.get()
        output_fmt = self.output_format_var.get()
        category = self.prompt_category_var.get()

        sections: list[str] = []
        label_str = category

        if category == "Code":
            sections = self._generate_code_sections(task, user_role, ctx_text, mode, output_fmt)
            bt_key = self.build_target_var.get()
            labels = []
            if bt_key != "(none)":
                labels.append(bt_key)
            labels.extend(k for k, v in self.enhancement_vars.items() if v.get())
            label_str = "+".join(labels) if labels else "Code"
        elif category == "Conversation":
            sections = self._generate_conversation_sections(task, user_role, ctx_text, mode, output_fmt)
            label_str = f"Chat:{self.conv_style_var.get()}"
        elif category == "Image":
            sections = self._generate_image_sections(task, ctx_text)
            label_str = f"Img:{self.image_style_var.get()}"
        elif category == "Video":
            sections = self._generate_video_sections(task, ctx_text)
            label_str = f"Vid:{self.video_style_var.get()}"

        # Inject My Projects context block at the top if one is selected
        project_key = self.my_project_var.get() if hasattr(self, "my_project_var") else "(None)"
        project_data = self._merged_projects.get(project_key, MY_PROJECTS.get(project_key, {}))

        # Pick token_savings (abbreviated) vs context_block (full) based on Low Token Mode
        low_token_active = (
            hasattr(self, "_low_token_var") and self._low_token_var.get()
        )
        if low_token_active and project_data.get("token_savings"):
            project_block = project_data.get("token_savings", "")
            project_block_label = "# PROJECT CONTEXT (low-token mode)"
        else:
            project_block = project_data.get("context_block", "")
            project_block_label = "# PROJECT CONTEXT"

        if project_block:
            sections.insert(0, f"{project_block_label}\n{project_block}")

        # Working Directory section (if set)
        workdir = self.workdir_var.get().strip() if hasattr(self, "workdir_var") else ""
        if workdir:
            wd_section = (
                f"# WORKING DIRECTORY\n"
                f"The target folder for this task is: {workdir}\n"
                f"Files and paths referenced should be relative to this directory unless specified otherwise."
            )
            # Insert after PROJECT CONTEXT (so it reads top-down: project → workdir → role/task/...)
            insert_idx = 1 if project_block else 0
            sections.insert(insert_idx, wd_section)

        final = "\n\n".join(sections)

        # Build results review
        review = self._build_results_review(task, final, category)
        output_text = final + "\n\n" + review

        self.result_area.delete("1.0", tk.END)
        self.result_area.insert(tk.END, output_text)
        self._update_token_estimate(final)  # Only count the prompt itself, not the review

        entry = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "task_preview": f"[{label_str}] {task[:45]}{'...' if len(task) > 45 else ''}",
            "prompt": final,
        }
        self.history.append(entry)
        if len(self.history) > MAX_HISTORY:
            self.history.pop(0)
            self.history_listbox.delete(0)
        self.history_listbox.insert(tk.END, f"[{entry['timestamp']}] {entry['task_preview']}")
        self._save_history_to_disk()

        self._dirty = False
        self._toast("Prompt generated!")
        self._set_status(f"Generated ({len(final):,} chars, ~{len(final)//4:,} tokens)")
        logger.info(f"Prompt generated: {label_str}, {len(final)} chars")

    # ── Category-specific generators ─────────────────────────────

    def _generate_code_sections(self, task, user_role, ctx_text, mode, output_fmt) -> list[str]:
        """Build sections for Code prompts (original behavior)."""
        all_types: list[dict] = []
        bt_key = self.build_target_var.get()
        if bt_key != "(none)" and bt_key in BUILD_TARGETS:
            all_types.append(BUILD_TARGETS[bt_key])
        for name, var in self.enhancement_vars.items():
            if var.get() and name in ENHANCEMENTS:
                all_types.append(ENHANCEMENTS[name])

        sections: list[str] = []
        if user_role:
            sections.append(f"# ROLE\nYou are: {user_role}.")
        elif all_types:
            sections.append(f"# ROLE\nYou are: {' AND '.join(t['role'] for t in all_types)}.")

        sections.append(f"# TASK\n{task}")
        for t in all_types:
            pc = t.get("platform_context", "")
            if pc:
                sections.append(f"# PLATFORM & ENVIRONMENT\n{pc}")
        if ctx_text:
            sections.append(f"# ADDITIONAL CONTEXT\n{ctx_text}")

        reasoning_block = REASONING_MODES.get(mode, {}).get("block", "")
        if reasoning_block:
            sections.append(f"# REASONING\n{reasoning_block}")
        fmt_block = OUTPUT_FORMATS.get(output_fmt, {}).get("block", "")
        if fmt_block:
            sections.append(f"# OUTPUT FORMAT\n{fmt_block}")

        constraints = self._gather_constraints()
        for t in all_types:
            constraints.extend(t.get("extra_constraints", []))
        seen: set[str] = set()
        unique = [c for c in constraints if c not in seen and not seen.add(c)]
        if unique:
            sections.append(f"# CONSTRAINTS\n" + "\n".join(f"- {c}" for c in unique))

        sections.append(
            "# QUALITY GATE\n"
            "Before finalizing your response, verify:\n"
            "1. All requirements from the TASK section are addressed.\n"
            "2. All CONSTRAINTS are satisfied.\n"
            "3. The code runs without errors in the target environment.\n"
            "4. Edge cases and error conditions are handled.\n"
            "5. The solution is complete -- no placeholder or TODO comments left behind."
        )
        return sections

    def _generate_conversation_sections(self, task, user_role, ctx_text, mode, output_fmt) -> list[str]:
        """Build sections for Conversation prompts."""
        style_key = self.conv_style_var.get()
        style_data = CONVERSATION_STYLES.get(style_key, {})
        tone_key = self.conv_tone_var.get()
        tone_desc = CONVERSATION_TONES.get(tone_key, "")

        sections: list[str] = []
        if user_role:
            sections.append(f"# ROLE\n{user_role}")
        elif style_data.get("block"):
            sections.append(f"# ROLE\n{style_data['block']}")

        if tone_desc:
            sections.append(f"# TONE\n{tone_desc}")

        sections.append(f"# TASK\n{task}")

        if ctx_text:
            sections.append(f"# CONTEXT\n{ctx_text}")

        reasoning_block = REASONING_MODES.get(mode, {}).get("block", "")
        if reasoning_block:
            sections.append(f"# REASONING\n{reasoning_block}")
        fmt_block = OUTPUT_FORMATS.get(output_fmt, {}).get("block", "")
        if fmt_block:
            sections.append(f"# OUTPUT FORMAT\n{fmt_block}")

        constraints = self._gather_constraints()
        if constraints:
            sections.append(f"# CONSTRAINTS\n" + "\n".join(f"- {c}" for c in constraints))
        return sections

    def _generate_image_sections(self, task, ctx_text) -> list[str]:
        """Build sections for Image generation prompts."""
        style = IMAGE_STYLES.get(self.image_style_var.get(), "")
        lighting = IMAGE_LIGHTING.get(self.image_lighting_var.get(), "")
        camera = IMAGE_CAMERAS.get(self.image_camera_var.get(), "")

        # Image prompts are structured differently - they're typically comma-separated descriptors
        parts = [task]
        if style:
            parts.append(style)
        if lighting:
            parts.append(lighting)
        if camera:
            parts.append(camera)

        prompt = ", ".join(parts)
        sections = [f"# IMAGE PROMPT\n{prompt}"]

        if ctx_text:
            sections.append(f"# ADDITIONAL NOTES\n{ctx_text}")

        # Negative prompt (common in image gen)
        sections.append(
            "# NEGATIVE PROMPT\n"
            "blurry, low quality, distorted, deformed, ugly, watermark, text, logo, "
            "oversaturated, underexposed, cropped, out of frame, extra limbs, bad anatomy"
        )
        return sections

    def _generate_video_sections(self, task, ctx_text) -> list[str]:
        """Build sections for Video generation prompts."""
        style = VIDEO_STYLES.get(self.video_style_var.get(), "")
        camera = VIDEO_CAMERA_MOVES.get(self.video_camera_var.get(), "")
        pacing = VIDEO_PACING.get(self.video_pacing_var.get(), "")

        sections = []
        parts = [task]
        if style:
            parts.append(style)
        if camera:
            parts.append(camera)
        if pacing:
            parts.append(pacing)

        sections.append(f"# VIDEO PROMPT\n{', '.join(parts)}")

        if ctx_text:
            sections.append(f"# ADDITIONAL NOTES\n{ctx_text}")

        sections.append(
            "# NEGATIVE\n"
            "static image, slideshow, watermark, blurry, jittery camera, "
            "low framerate, artifacts, morphing, unnatural motion"
        )
        return sections

    # ── Results Review ────────────────────────────────────────────

    def _build_results_review(self, original_task: str, final_prompt: str, category: str) -> str:
        """Build an analysis of the generated prompt shown below the prompt itself."""
        prompt_tokens = len(final_prompt) // 4
        prompt_chars = len(final_prompt)
        task_tokens = len(original_task) // 4
        sections_count = final_prompt.count("\n# ")  + (1 if final_prompt.startswith("# ") else 0)

        lines = [
            "=" * 60,
            "  PROMPT REVIEW",
            "=" * 60,
            "",
            f"  Total tokens:     ~{prompt_tokens:,}",
            f"  Total characters: {prompt_chars:,}",
            f"  Sections:         {sections_count}",
            "",
        ]

        # Token impact analysis
        if prompt_tokens < 500:
            lines.append("  Impact: LIGHT -- fits easily in any AI model's context window.")
            lines.append("  Works with: GPT-3.5, Claude Haiku, Gemini Flash, all models.")
        elif prompt_tokens < 2000:
            lines.append("  Impact: MODERATE -- good size for detailed instructions.")
            lines.append("  Works with: All current models. Leaves plenty of room for the AI's response.")
        elif prompt_tokens < 8000:
            lines.append("  Impact: LARGE -- comprehensive prompt. Uses significant context space.")
            lines.append("  Works with: GPT-4, Claude Sonnet/Opus, Gemini Pro. May crowd smaller models.")
        else:
            lines.append("  Impact: VERY LARGE -- may leave limited room for the AI's response.")
            lines.append("  Consider: Enable Low Token Mode or remove non-essential sections.")

        lines.append("")

        # Improvement over raw English
        improvement_ratio = prompt_tokens / max(task_tokens, 1)
        lines.append("  WHAT THIS PROMPT ADDS OVER YOUR RAW TEXT:")
        lines.append(f"  Your description:  ~{task_tokens:,} tokens")
        lines.append(f"  Engineered prompt: ~{prompt_tokens:,} tokens ({improvement_ratio:.1f}x)")
        lines.append("")

        improvements = []
        if category == "Code":
            if "# ROLE" in final_prompt:
                improvements.append("Expert role -- AI responds as a specialist, not a generalist")
            if "# PLATFORM" in final_prompt:
                improvements.append("Platform context -- AI knows exact tech stack and constraints")
            if "# REASONING" in final_prompt:
                improvements.append("Thinking framework -- AI plans before coding, catches more bugs")
            if "# CONSTRAINTS" in final_prompt:
                improvements.append("Quality rules -- enforces style, security, and robustness standards")
            if "# QUALITY GATE" in final_prompt:
                improvements.append("Self-check -- AI verifies its own work before presenting it")
        elif category == "Conversation":
            improvements.append("Conversation style -- AI knows the context (teaching, debate, etc.)")
            improvements.append("Tone control -- formal vs casual vs academic vs simple")
        elif category == "Image":
            improvements.append("Technical descriptors -- style, lighting, camera angle baked in")
            improvements.append("Negative prompt -- tells AI what to avoid (blurry, watermarks, etc.)")
        elif category == "Video":
            improvements.append("Motion descriptors -- camera movement, pacing, visual style")
            improvements.append("Negative prompt -- prevents common video AI artifacts")

        for imp in improvements:
            lines.append(f"  + {imp}")

        lines.append("")

        # Compression offer
        lines.append("  COMPRESSION OPTIONS:")
        if prompt_tokens > 500:
            compressed_est = int(prompt_tokens * 0.5)
            lines.append(f"  You could compress this to ~{compressed_est:,} tokens by:")
            lines.append("    - Removing the Quality Gate section (saves ~30 tokens)")
            lines.append("    - Shortening section headers (saves ~20 tokens)")
            lines.append("    - Trimming platform context to essentials (saves ~50-100 tokens)")
            lines.append("")
            lines.append("  PROS of compression:")
            lines.append("    + Cheaper per API call (fewer input tokens = lower cost)")
            lines.append("    + More room for the AI's response in the context window")
            lines.append("    + Faster response time (less to process)")
            lines.append("  CONS of compression:")
            lines.append("    - AI may miss edge cases without explicit constraints")
            lines.append("    - Less platform-specific guidance = more generic code")
            lines.append("    - No self-check step = more bugs in output")
        else:
            lines.append("  This prompt is already compact. No compression recommended.")

        # ── Effectiveness Analysis ──
        lines.append("")
        lines.append("  " + "-" * 50)
        lines.append("  EFFECTIVENESS ANALYSIS")
        lines.append("  " + "-" * 50)

        score = 0
        max_score = 0
        checks = []

        def _check(name, present, points, why_good, why_bad):
            nonlocal score, max_score
            max_score += points
            if present:
                score += points
                checks.append(f"  [+{points:>2}] {name}: {why_good}")
            else:
                checks.append(f"  [ 0] {name}: {why_bad}")

        _check("Expert Role", "# ROLE" in final_prompt, 12,
               "AI responds as a specialist, not a generic chatbot",
               "No role set -- AI defaults to generalist mode")

        task_words = len(original_task.split())
        _check("Task Clarity", task_words >= 15, 10,
               f"Good detail ({task_words} words) gives AI enough to work with",
               f"Only {task_words} words -- add inputs, outputs, edge cases")

        _check("Specific Details", task_words >= 40 or len(original_task) > 200, 8,
               "Rich description with specific requirements",
               "Could use more detail -- mention behaviors, edge cases, examples")

        _check("Platform Context",
               "# PLATFORM" in final_prompt or "# IMAGE PROMPT" in final_prompt or "# VIDEO PROMPT" in final_prompt,
               12, "AI knows the exact tech stack / medium / environment",
               "No platform guidance -- AI picks its own defaults")

        _check("Thinking Framework", "# REASONING" in final_prompt, 8,
               "AI plans before executing -- fewer bugs",
               "No thinking mode -- enable Structured CoT for better results")

        has_real_format = "# OUTPUT FORMAT" in final_prompt
        _check("Output Format", has_real_format, 8,
               "AI knows exactly what structure you expect",
               "No format set -- pick Code Only, JSON, or Markdown if needed")

        _check("Quality Rules", "# CONSTRAINTS" in final_prompt, 10,
               "Enforces coding standards, security, robustness",
               "No guardrails -- enable constraint presets for consistent quality")

        _check("Project Conventions", "# PROJECT CONTEXT" in final_prompt, 10,
               "Your patterns pre-loaded -- no re-explaining each session",
               "No project preset -- select from My Projects to save time")

        _check("Self-Check Gate", "# QUALITY GATE" in final_prompt, 8,
               "AI verifies its work before presenting it",
               "No self-check -- bugs pass through uncaught")

        _check("Anti-Patterns", "ANTI-PATTERN" in final_prompt or "Do NOT" in final_prompt, 6,
               "AI knows what to avoid (globals, print-debugging, etc.)",
               "No don't-list -- AI may use bad habits")

        _check("Context / Examples",
               "# ADDITIONAL CONTEXT" in final_prompt or "# CONTEXT" in final_prompt, 6,
               "Extra context guides the AI approach",
               "No extra context -- add examples if task is ambiguous")

        _check("Update Chain", len(self._update_chain) > 0, 6,
               f"{len(self._update_chain)} follow-up(s) active -- iterative dev in progress",
               "No follow-ups yet -- use Update Chain for incremental changes")

        if category in ("Image", "Video"):
            _check("Negative Prompt", "# NEGATIVE" in final_prompt, 6,
                   "Tells AI what to avoid (blur, watermarks, artifacts)",
                   "No negative prompt -- add one to prevent common issues")

        for c_line in checks:
            lines.append(c_line)

        pct = int((score / max(max_score, 1)) * 100)
        lines.append("")

        if pct >= 90: grade, verdict = "A+", "Excellent. Leaves very little to chance."
        elif pct >= 80: grade, verdict = "A", "Strong. Most bases covered."
        elif pct >= 70: grade, verdict = "B+", "Good. A few more options would make it great."
        elif pct >= 60: grade, verdict = "B", "Decent but check the [ 0] items."
        elif pct >= 45: grade, verdict = "C", "Fair. AI fills gaps on its own."
        elif pct >= 30: grade, verdict = "D", "Weak. Enable more options."
        else: grade, verdict = "F", "Minimal. AI is guessing what you want."

        lines.append(f"  SCORE: {score}/{max_score} ({pct}%) -- Grade: {grade}")
        lines.append(f"  {verdict}")
        lines.append("")

        raw_est = 10 if task_words >= 15 else 0
        raw_pct = int(raw_est / max(max_score, 1) * 100)
        lines.append(f"  vs RAW TEXT: Plain English = ~{raw_pct}%. This prompt = {pct}%.")
        if pct > raw_pct + 15:
            lines.append(f"  Improvement: +{pct - raw_pct}% more effective than raw text.")

        no_items = [c for c in checks if "[ 0]" in c]
        if no_items and pct < 90:
            lines.append("")
            lines.append("  QUICK WINS:")
            if any("Project" in n for n in no_items):
                lines.append("    -> Select a My Projects preset")
            if any("Thinking" in n for n in no_items):
                lines.append("    -> Set Thinking Style to Structured CoT")
            if any("Task" in n or "Specific" in n for n in no_items):
                lines.append("    -> Add detail: inputs, outputs, edge cases")
            if any("Output Format" in n for n in no_items):
                lines.append("    -> Set Output Format (Code Only, JSON, Markdown)")
            if any("Quality Rules" in n for n in no_items):
                lines.append("    -> Check: Python Best Practices, Security, Robustness")

        # Model recommendation block (default service = Claude; user can pick any)
        try:
            rec = self._recommend_model("Claude", final_prompt)
            lines.append("")
            lines.append(self._format_model_for_review(rec))
        except Exception as exc:
            logger.warning(f"Model recommendation failed: {exc}")

        lines.append("")
        lines.append("  TIP: Use Copy Prompt Only to grab just the prompt without this review.")
        lines.append("=" * 60)
        return "\n".join(lines)

    def _gather_constraints(self) -> list[str]:
        constraints: list[str] = []
        for name, var in self.constraint_vars.items():
            if var.get():
                constraints.extend(CONSTRAINT_PRESETS[name]["rules"])
        custom = self.custom_constraints.get("1.0", tk.END).strip()
        if custom:
            for line in custom.splitlines():
                line = line.strip()
                if line:
                    constraints.append(line)
        return constraints

    # ══════════════════════════════════════════════════════════════
    # ACTIONS
    # ══════════════════════════════════════════════════════════════

    def copy_to_clipboard(self) -> None:
        content = self.result_area.get("1.0", tk.END).strip()
        if not content:
            messagebox.showwarning("Empty", "Generate a prompt first.")
            return
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(content)
            self._toast("Copied to clipboard")
            self._set_status("Prompt copied")
            if self._auto_clear_clip.get():
                if self._clipboard_clear_id:
                    self.root.after_cancel(self._clipboard_clear_id)
                self._clipboard_clear_id = self.root.after(60000, self._clear_clipboard)
        except tk.TclError:
            messagebox.showerror("Error", "Could not access clipboard.")

    def _clear_clipboard(self) -> None:
        try:
            self.root.clipboard_clear()
            self._set_status("Clipboard auto-cleared")
        except tk.TclError:
            pass
        self._clipboard_clear_id = None

    def save_to_file(self) -> None:
        content = self.result_area.get("1.0", tk.END).strip()
        if not content:
            messagebox.showwarning("Empty", "Generate a prompt first.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text Files", "*.txt"), ("Markdown", "*.md"), ("All Files", "*.*")])
        if path:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)
                self._toast(f"Saved: {Path(path).name}")
                logger.info(f"Output saved: {Path(path).name}")
            except OSError as e:
                messagebox.showerror("Save Failed", f"Could not save: {e.strerror}")

    def clear_output(self) -> None:
        self.result_area.delete("1.0", tk.END)
        self._update_token_estimate("")
        self._set_status("Output cleared")

    def clear_inputs(self) -> None:
        """Clear task + context text boxes, keeping all settings intact."""
        self.task_input.delete("1.0", tk.END)
        self.context_input.delete("1.0", tk.END)
        self._set_status("Inputs cleared \u2014 settings preserved")

    def _clear_task(self) -> None:
        """Clear just the task description box."""
        self.task_input.delete("1.0", tk.END)
        self._set_status("Task cleared")

    def _clear_context(self) -> None:
        """Clear just the context box."""
        self.context_input.delete("1.0", tk.END)
        self._set_status("Context cleared")

    # ══════════════════════════════════════════════════════════════
    # COPY / PASTE HELPERS (result area)
    # ══════════════════════════════════════════════════════════════

    def _copy_prompt_only(self) -> None:
        """Copy just the generated prompt, without the review section at the bottom."""
        content = self.result_area.get("1.0", tk.END).strip()
        if not content:
            self._set_status("Nothing to copy", )
            return
        # Strip the review (everything from the first "=====" block onward)
        sep = "=" * 60
        if sep in content:
            content = content[:content.index(sep)].strip()
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(content)
            self._toast("Prompt copied (without review)")
            self._set_status("Prompt only copied")
        except tk.TclError:
            messagebox.showerror("Error", "Could not access clipboard.")

    def _copy_selection(self) -> None:
        """Copy the currently selected/highlighted text from result_area."""
        try:
            sel = self.result_area.selection_get()
            self.root.clipboard_clear()
            self.root.clipboard_append(sel)
            self._toast("Selection copied!")
            self._set_status("Selection copied")
        except tk.TclError:
            self._set_status("No text selected")

    def _select_all_result(self) -> None:
        """Select all text in the result area."""
        self.result_area.tag_add(tk.SEL, "1.0", tk.END)
        self.result_area.mark_set(tk.INSERT, "1.0")
        self._set_status("All text selected")

    def _paste_into_result(self) -> None:
        """Paste clipboard contents into the result area at cursor."""
        try:
            self.result_area.insert(tk.INSERT, self.root.clipboard_get())
        except tk.TclError:
            self._set_status("Clipboard empty")

    def _copy_history_item(self) -> None:
        """Copy the selected history item's prompt directly to clipboard."""
        sel = self.history_listbox.curselection()
        if not sel:
            self._set_status("Select a history item first")
            return
        display_text = self.history_listbox.get(sel[0])
        for entry in self.history:
            if f"[{entry['timestamp']}] {entry['task_preview']}" == display_text:
                try:
                    self.root.clipboard_clear()
                    self.root.clipboard_append(entry["prompt"])
                    self._toast("History prompt copied!")
                    self._set_status("History prompt copied to clipboard")
                except tk.TclError:
                    messagebox.showerror("Error", "Could not access clipboard.")
                return
        self._set_status("Could not find matching history entry")

    # ══════════════════════════════════════════════════════════════
    # MODEL RECOMMENDATION (v5.1)
    # ══════════════════════════════════════════════════════════════

    def _recommend_model(self, ai_name: str | None, prompt_text: str) -> dict:
        """Recommend the best model tier for this prompt based on task characteristics.

        Returns a dict with keys:
            - service: The AI service ("Claude", "ChatGPT", "Gemini", or None)
            - tier: "cheap" | "balanced" | "premium"
            - name: Concrete model name (e.g. "Claude Sonnet 4.5")
            - reason: One-sentence explanation for why
            - cost_estimate: Estimated input cost in dollars for this prompt
            - image_note / video_note: For image/video categories, suggests
              dedicated generation services instead of text models.

        If ai_name is None, defaults to "Claude" for the recommendation but
        returns generic guidance the user can apply across services.
        """
        category = self.prompt_category_var.get() if hasattr(self, "prompt_category_var") else "Code"

        # Image/Video → suggest dedicated generation services, not text models
        if category == "Image":
            suggested = "Midjourney v7 (quality) or DALL-E 3 (easy via ChatGPT Plus)"
            return {
                "service": None,
                "tier": "image",
                "name": suggested,
                "reason": "Image prompts go to image generation services, not LLMs.",
                "cost_estimate": 0.0,
                "image_note": "\n".join(f"  - {m}: {d}" for m, d in IMAGE_MODELS.items()),
            }
        if category == "Video":
            suggested = "Sora (quality) or Runway Gen-3 (fast)"
            return {
                "service": None,
                "tier": "video",
                "name": suggested,
                "reason": "Video prompts go to video generation services, not LLMs.",
                "cost_estimate": 0.0,
                "video_note": "\n".join(f"  - {m}: {d}" for m, d in VIDEO_MODELS.items()),
            }

        # Text/code: pick tier based on prompt characteristics
        service = ai_name if ai_name in MODEL_CATALOG else "Claude"
        service_data = MODEL_CATALOG[service]
        tiers = service_data["tiers"]

        token_estimate = max(1, len(prompt_text) // 4)

        # Services whose cheap/balanced tiers already have 1M+ context —
        # big prompts don't force them to premium.
        big_context_services = {"Gemini", "Qwen", "Grok (xAI)", "Llama (Meta)"}

        # Heuristics
        project_key = self.my_project_var.get() if hasattr(self, "my_project_var") else "(None)"
        has_project = project_key and project_key != "(None)"
        is_followup = bool(getattr(self, "_update_chain", []))
        low_token_on = hasattr(self, "_low_token_var") and self._low_token_var.get()
        has_reasoning = hasattr(self, "reasoning_var") and self.reasoning_var.get() != "None"
        has_constraints = any(
            v.get() for v in getattr(self, "constraint_vars", {}).values()
        )

        reason_parts: list[str] = []
        tier = "balanced"

        if token_estimate > 50_000:
            if service in big_context_services:
                tier = "balanced"
                reason_parts.append(
                    f"{token_estimate:,} tokens — {service}'s balanced tier has huge context, no need to escalate"
                )
            else:
                tier = "premium"
                reason_parts.append(f"{token_estimate:,} tokens — needs a big-context model")
        elif token_estimate < 300 and not has_project and not has_reasoning:
            tier = "cheap"
            reason_parts.append("small, simple prompt — cheap tier is enough")
        elif category == "Conversation" and not has_constraints:
            tier = "cheap"
            reason_parts.append("casual conversation doesn't need a coding model")
        elif is_followup and not low_token_on:
            tier = "cheap" if token_estimate < 1500 else "balanced"
            reason_parts.append(
                "follow-up update — AI already has context, cheaper model works"
            )
        elif has_project and token_estimate > 3000:
            tier = "premium"
            reason_parts.append(
                "large project context + complex task — premium tier reasons best"
            )
        elif category == "Code" and has_project:
            tier = "balanced"
            reason_parts.append("typical coding task with project context — balanced is ideal")
        elif category == "Code":
            tier = "balanced"
            reason_parts.append("general coding — balanced models handle most tasks well")

        if not reason_parts:
            reason_parts.append(f"{token_estimate:,} tokens — balanced tier default")

        model = tiers[tier]

        # Specialist override: if the service has a specialist model (Qwen3-Coder,
        # Codestral) and the category is Code, suggest that instead of the tier.
        specialist = service_data.get("specialist")
        if specialist and category == "Code":
            model = specialist
            reason_parts.append(
                f"— also consider the dedicated code model {specialist['name']}"
            )

        # Cost estimate (input tokens only)
        cost = (token_estimate / 1_000_000) * model["input_per_million"]

        # OpenRouter adds ~5% surcharge on top
        if service_data.get("is_router"):
            cost *= 1.05
            reason_parts.append("OpenRouter routes to the underlying model + ~5% fee")

        rec = {
            "service": service,
            "tier": tier,
            "name": model["name"],
            "reason": "; ".join(reason_parts),
            "cost_estimate": cost,
            "context_limit": model["context"],
            "best_for": model["best_for"],
            "docs_url": service_data["docs_url"],
        }
        # Attach any service-level note (e.g. OpenCoder/OpenRouter caveats)
        if service_data.get("note"):
            rec["service_note"] = service_data["note"]
        return rec

    def _format_model_toast(self, rec: dict) -> str:
        """Short toast message: Use [model name] — [reason]."""
        if rec.get("image_note") or rec.get("video_note"):
            return f"Suggested: {rec['name']} (see reference pane)"
        cost_str = f" ~${rec['cost_estimate']:.4f}" if rec.get("cost_estimate", 0) > 0 else ""
        return f"Use {rec['name']}{cost_str} — {rec['reason']}"

    def _format_model_for_review(self, rec: dict) -> str:
        """Multi-line block shown in the Results Review."""
        lines = [
            "  " + "-" * 50,
            "  MODEL RECOMMENDATION (suggestion only — not forced)",
            "  " + "-" * 50,
        ]
        if rec.get("image_note"):
            lines.append(f"  For image prompts, choose one of these services:")
            lines.append(rec["image_note"])
            lines.append("  Paste this prompt as your image description, plus any extras.")
            return "\n".join(lines)
        if rec.get("video_note"):
            lines.append(f"  For video prompts, choose one of these services:")
            lines.append(rec["video_note"])
            return "\n".join(lines)

        lines.append(f"  Suggested: {rec['name']}")
        lines.append(f"  Tier:      {rec['tier']}  ({rec['service']} service)")
        lines.append(f"  Context:   {rec['context_limit']:,} tokens available")
        lines.append(f"  Best for:  {rec['best_for']}")
        if rec.get("cost_estimate", 0) > 0:
            lines.append(f"  Est. cost: ~${rec['cost_estimate']:.4f} (input only)")
        else:
            lines.append("  Est. cost: $0.00 (self-hosted / free)")
        lines.append(f"  Why:       {rec['reason']}")
        if rec.get("service_note"):
            lines.append(f"  Note:      {rec['service_note']}")
        lines.append(f"  Docs:      {rec['docs_url']}")
        return "\n".join(lines)

    # ══════════════════════════════════════════════════════════════
    # SEND TO AI WINDOW
    # ══════════════════════════════════════════════════════════════

    def _search_terms_for(self, ai_name: str) -> list[str]:
        """Return window-title search terms for a given AI service.
        Looks up AI_SERVICES first, falls back to the name itself.
        """
        for display_name, _color, terms, _cat_key in AI_SERVICES:
            if display_name.lower() == ai_name.lower():
                return list(terms)
        return [ai_name]

    def _catalog_key_for(self, ai_name: str) -> str:
        """Map display name → MODEL_CATALOG key (handles 'Grok' → 'Grok (xAI)' etc)."""
        for display_name, _color, _terms, cat_key in AI_SERVICES:
            if display_name.lower() == ai_name.lower():
                return cat_key or ai_name
        return ai_name

    def _dispatch_other_ai(self, action: str) -> None:
        """Route 'Grab'/'Send'/'Copy & Show Model' for the AI picked in the More AIs combobox."""
        name = self._other_ai_var.get().strip()
        if not name:
            self._set_status("Pick an AI from the More AIs dropdown first")
            return
        if action == "grab":
            self._grab_enhance_send(name)
        elif action == "send":
            self._send_to_ai_window(name)
        elif action == "copy":
            content = self._get_prompt_text_for_send()
            if not content:
                self._set_status("Generate a prompt first")
                return
            try:
                import pyperclip
                pyperclip.copy(content)
            except Exception:
                pass
            rec = self._recommend_model(self._catalog_key_for(name), content)
            rec_msg = self._format_model_toast(rec)
            self._toast(f"Copied! {rec_msg}", duration=6000)
            self._set_status(f"Copied. {rec_msg}")

    def _get_prompt_text_for_send(self) -> str:
        """Get just the prompt (no review) for sending to AI."""
        content = self.result_area.get("1.0", tk.END).strip()
        if not content:
            return ""
        sep = "=" * 60
        if sep in content:
            content = content[:content.index(sep)].strip()
        return content

    def _send_to_ai_window(self, ai_name: str) -> None:
        """Find an AI browser window by name, focus it, and paste the prompt."""
        content = self._get_prompt_text_for_send()
        if not content:
            self._set_status("Generate a prompt first")
            return

        try:
            import pyperclip
            import pyautogui
        except ImportError:
            messagebox.showerror(
                "Missing Libraries",
                "This feature requires pyautogui and pyperclip.\n\n"
                "Install them with:\n  pip install pyautogui pyperclip"
            )
            return

        # Copy prompt to clipboard
        pyperclip.copy(content)

        # Resolve search terms + catalog key from AI_SERVICES
        terms = self._search_terms_for(ai_name)
        catalog_key = self._catalog_key_for(ai_name)

        # Try to find the window
        found = False
        for term in terms:
            try:
                windows = pyautogui.getAllWindows()
                for win in windows:
                    if term.lower() in win.title.lower() and win.visible:
                        win.activate()
                        found = True
                        break
                if found:
                    break
            except Exception:
                continue

        if not found:
            rec = self._recommend_model(catalog_key, content)
            rec_msg = self._format_model_toast(rec)
            messagebox.showwarning(
                f"{ai_name} Not Found",
                f"Could not find an open {ai_name} window.\n\n"
                f"Make sure {ai_name} is open in your browser, then try again.\n\n"
                f"The prompt has been copied to your clipboard — paste manually with Ctrl+V.\n\n"
                f"Model suggestion: {rec_msg}"
            )
            self._set_status(f"Copied to clipboard. {rec_msg}")
            return

        # Give the window time to come to front
        import time
        time.sleep(0.4)

        # Paste into the input field
        try:
            pyautogui.hotkey('ctrl', 'v')
            # Model recommendation toast: show which model the user should pick
            rec = self._recommend_model(catalog_key, content)
            rec_msg = self._format_model_toast(rec)
            self._toast(f"Pasted into {ai_name}! {rec_msg}", duration=6000)
            self._set_status(f"{ai_name}: {rec_msg}")
            logger.info(
                f"Send to {ai_name} ({catalog_key}): recommended {rec.get('name')} "
                f"(tier={rec.get('tier')}, reason={rec.get('reason')})"
            )
        except Exception as e:
            self._set_status(f"Paste failed: {e} — prompt is on clipboard, paste manually")

    def _send_to_any_window(self) -> None:
        """Let the user pick any window to paste the prompt into.
        Gives a 3-second countdown so the user can click the target window."""
        content = self._get_prompt_text_for_send()
        if not content:
            self._set_status("Generate a prompt first")
            return

        try:
            import pyperclip
            import pyautogui
        except ImportError:
            messagebox.showerror("Missing Libraries", "Install pyautogui and pyperclip:\n  pip install pyautogui pyperclip")
            return

        pyperclip.copy(content)

        # Countdown — give user time to click the target window
        self._toast("Click the AI input box now! Pasting in 3 seconds...")
        self._set_status("Pasting in 3 seconds — click your target window NOW")

        # Pre-compute recommendation so it's ready for the toast
        rec = self._recommend_model(None, content)
        rec_msg = self._format_model_toast(rec)

        def do_paste():
            import time
            time.sleep(3)
            try:
                pyautogui.hotkey('ctrl', 'v')
                self.root.after(0, lambda: self._toast(f"Pasted! {rec_msg}", duration=6000))
                self.root.after(0, lambda: self._set_status(rec_msg))
            except Exception as e:
                self.root.after(0, lambda: self._set_status(f"Paste failed: {e}"))

        import threading
        threading.Thread(target=do_paste, daemon=True).start()

    # ══════════════════════════════════════════════════════════════
    # GRAB + ENHANCE + SEND (v5.0)
    # ══════════════════════════════════════════════════════════════

    def _grab_enhance_send(self, ai_name: str | None) -> None:
        """Grab text currently in an AI's input box, enhance it with project context
        + token savings, and paste the enhanced version back into that same input box.

        If ai_name is None, uses a 3-second countdown: user clicks any input, script grabs.
        """
        try:
            import pyautogui
            import pyperclip
        except ImportError:
            messagebox.showerror(
                "Missing Libraries",
                "This feature requires pyautogui and pyperclip.\n\n"
                "Install with:\n  pip install pyautogui pyperclip",
            )
            return

        import time
        import threading

        def do_work():
            # Step 1: Find window (or countdown for manual pick)
            target_win = None
            if ai_name:
                terms = self._search_terms_for(ai_name)
                for term in terms:
                    try:
                        for win in pyautogui.getAllWindows():
                            if term.lower() in win.title.lower() and win.visible:
                                target_win = win
                                break
                        if target_win:
                            break
                    except Exception:
                        continue

                if not target_win:
                    self.root.after(0, lambda: messagebox.showwarning(
                        f"{ai_name} Not Found",
                        f"Could not find an open {ai_name} window.\n\n"
                        f"Falling back to 3-second countdown — click the {ai_name} input box now.",
                    ))
                    self.root.after(0, lambda: self._set_status(
                        f"Countdown: click {ai_name} input in 3 seconds..."))
                    time.sleep(3)
                else:
                    try:
                        target_win.activate()
                    except Exception:
                        pass
                    time.sleep(0.4)
            else:
                # No AI specified: pure countdown mode
                self.root.after(0, lambda: self._toast(
                    "Click the AI input box now! Grabbing in 3 seconds..."))
                self.root.after(0, lambda: self._set_status(
                    "Countdown: click target input in 3 seconds..."))
                time.sleep(3)

            # Step 2: Save clipboard, grab current input
            saved_clip = ""
            try:
                saved_clip = pyperclip.paste()
            except Exception:
                pass

            try:
                pyautogui.hotkey('ctrl', 'a')
                time.sleep(0.15)
                pyautogui.hotkey('ctrl', 'c')
                time.sleep(0.25)
                grabbed = pyperclip.paste()
            except Exception as exc:
                self.root.after(0, lambda: self._set_status(f"Grab failed: {exc}"))
                return

            grabbed = (grabbed or "").strip()
            if not grabbed or grabbed == saved_clip:
                self.root.after(0, lambda: self._set_status(
                    "Nothing grabbed — input box may be empty or clipboard unchanged"))
                return

            # Step 3: Put grabbed text in the task box (replace task)
            def put_into_task():
                self.task_input.delete("1.0", tk.END)
                self.task_input.insert("1.0", grabbed)
                self.generate()
                # After generate, grab enhanced prompt and put on clipboard
                enhanced = self._get_prompt_text_for_send()
                if enhanced:
                    try:
                        pyperclip.copy(enhanced)
                    except Exception:
                        pass
                    # Step 4: Paste back into AI
                    self._paste_back_into_window(target_win, ai_name)

            self.root.after(0, put_into_task)

        threading.Thread(target=do_work, daemon=True).start()

    def _paste_back_into_window(self, target_win, ai_name: str | None) -> None:
        """Called after generate(): activate target and paste enhanced prompt."""
        try:
            import pyautogui
        except ImportError:
            return
        import time
        import threading

        # Pre-compute recommendation (based on the enhanced prompt on clipboard)
        try:
            import pyperclip as _pc
            enhanced = _pc.paste() or ""
        except Exception:
            enhanced = ""
        rec = self._recommend_model(self._catalog_key_for(ai_name) if ai_name else None, enhanced)
        rec_msg = self._format_model_toast(rec)

        def do_paste():
            if target_win:
                try:
                    target_win.activate()
                except Exception:
                    pass
                time.sleep(0.4)
            else:
                # Need another countdown for paste
                self.root.after(0, lambda: self._toast(
                    "Click the AI input box again to paste enhanced prompt (3s)..."))
                time.sleep(3)

            try:
                # Select all in the input, then paste to overwrite
                pyautogui.hotkey('ctrl', 'a')
                time.sleep(0.15)
                pyautogui.hotkey('ctrl', 'v')
                self.root.after(0, lambda: self._toast(
                    f"Pasted into {ai_name or 'target'}. {rec_msg}", duration=6500))
                self.root.after(0, lambda: self._set_status(
                    f"Grab+Enhance+Send complete. {rec_msg}"))
            except Exception as exc:
                self.root.after(0, lambda: self._set_status(f"Paste-back failed: {exc}"))

        threading.Thread(target=do_paste, daemon=True).start()

    # ══════════════════════════════════════════════════════════════
    # FOLLOW-UP / UPDATE PROMPTS
    # ══════════════════════════════════════════════════════════════

    def _generate_followup(self) -> None:
        """Generate a focused update prompt and add it to the rolling chain."""
        change_request = self.followup_input.get("1.0", tk.END).strip()
        if not change_request:
            messagebox.showwarning("Missing Request", "Describe what you want changed.")
            return

        original_prompt = self.result_area.get("1.0", tk.END).strip()
        category = self.prompt_category_var.get()
        reasoning_block = REASONING_MODES.get(self.reasoning_var.get(), {}).get("block", "")
        update_num = len(self._update_chain) + 1

        lines = [
            f"# FOLLOW-UP REQUEST (Update #{update_num})",
            "I have already provided you with my code/content in a previous message.",
            "Do NOT rewrite the entire thing. Only modify what is needed for this change:",
            "",
            f"CHANGE REQUESTED: {change_request}",
            "",
            "# INSTRUCTIONS",
            "- Show ONLY the changed/new code, not the entire file.",
            "- If modifying an existing function, show the complete new version of that function only.",
            "- If adding something new, show only the new addition and where it goes.",
            "- Use comments like '# ... rest unchanged ...' to indicate unmodified sections.",
            "- Briefly explain what changed and why (2-3 sentences max).",
        ]

        # Carry forward previous update context so the AI knows the full chain
        if self._update_chain:
            prev_changes = [e["request"] for e in self._update_chain]
            lines.append("")
            lines.append("# PREVIOUS UPDATES ALREADY APPLIED")
            lines.append("These changes were already requested and should be in the code:")
            for i, prev in enumerate(prev_changes, 1):
                lines.append(f"  {i}. {prev}")

        if category == "Code":
            bt_key = self.build_target_var.get()
            if bt_key != "(none)" and bt_key in BUILD_TARGETS:
                first_line = BUILD_TARGETS[bt_key]["platform_context"].split("\n")[0]
                lines.append(f"\n# ENVIRONMENT\n{first_line}")
            active_constraints = [n for n, v in self.constraint_vars.items() if v.get()]
            if active_constraints:
                lines.append(f"\n# QUALITY RULES (same as original)")
                lines.append(f"Still follow: {', '.join(active_constraints)}.")

        if reasoning_block:
            lines.append(f"\n# REASONING\n{reasoning_block}")

        followup_prompt = "\n".join(lines)

        # Token stats
        orig_tokens = len(original_prompt) // 4 if original_prompt else 0
        fu_tokens = len(followup_prompt) // 4
        savings = max(0, orig_tokens - fu_tokens)

        # Save to chain
        entry = {
            "num": update_num,
            "request": change_request,
            "prompt": followup_prompt,
            "tokens": fu_tokens,
            "timestamp": datetime.now().strftime("%H:%M:%S"),
        }
        self._update_chain.append(entry)

        # Update the list display
        self.update_chain_list.insert(
            tk.END,
            f"#{update_num} [{entry['timestamp']}] {change_request[:60]}{'...' if len(change_request) > 60 else ''}"
        )

        # Show this update in the output
        self.followup_output.delete("1.0", tk.END)
        self.followup_output.insert(tk.END, followup_prompt)

        # Clear the input for the next update
        self.followup_input.delete("1.0", tk.END)

        save_str = f" (saves ~{savings:,} vs full)" if savings > 0 else ""
        self._toast(f"Update #{update_num} added to chain!")
        self._set_status(f"Update #{update_num}: ~{fu_tokens:,} tokens{save_str}")

    def _on_chain_select(self, event: tk.Event = None) -> None:
        """When user clicks an update in the chain list, show it in the output."""
        sel = self.update_chain_list.curselection()
        if not sel:
            return
        idx = sel[0]
        if 0 <= idx < len(self._update_chain):
            entry = self._update_chain[idx]
            self.followup_output.delete("1.0", tk.END)
            self.followup_output.insert(tk.END, entry["prompt"])

    def _copy_followup(self) -> None:
        """Copy the currently displayed follow-up prompt to clipboard."""
        content = self.followup_output.get("1.0", tk.END).strip()
        if not content:
            self._set_status("Select or generate an update first")
            return
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(content)
            self._toast("Update prompt copied!")
            self._set_status("Update prompt copied to clipboard")
        except tk.TclError:
            messagebox.showerror("Error", "Could not access clipboard.")

    def _copy_all_updates(self) -> None:
        """Copy the entire update chain as one block — all updates in order."""
        if not self._update_chain:
            self._set_status("No updates in the chain yet")
            return
        all_text = "\n\n---\n\n".join(e["prompt"] for e in self._update_chain)
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(all_text)
            self._toast(f"All {len(self._update_chain)} updates copied!")
            self._set_status(f"Copied {len(self._update_chain)} updates to clipboard")
        except tk.TclError:
            messagebox.showerror("Error", "Could not access clipboard.")

    def _clear_followup(self) -> None:
        """Clear the entire update chain."""
        if self._update_chain and not messagebox.askyesno("Confirm", f"Clear all {len(self._update_chain)} updates?"):
            return
        self._update_chain.clear()
        self.update_chain_list.delete(0, tk.END)
        self.followup_input.delete("1.0", tk.END)
        self.followup_output.delete("1.0", tk.END)
        self._set_status("Update chain cleared")

    # ══════════════════════════════════════════════════════════════
    # UNDO / REDO
    # ══════════════════════════════════════════════════════════════

    def _undo(self) -> None:
        w = self.root.focus_get()
        if isinstance(w, tk.Text):
            try:
                w.edit_undo()
            except tk.TclError:
                pass

    def _redo(self) -> None:
        w = self.root.focus_get()
        if isinstance(w, tk.Text):
            try:
                w.edit_redo()
            except tk.TclError:
                pass

    # ══════════════════════════════════════════════════════════════
    # PERSISTENCE
    # ══════════════════════════════════════════════════════════════

    def _start_autosave(self) -> None:
        self._do_autosave()

    def _do_autosave(self) -> None:
        try:
            state = self._collect_state()
            state_str = json.dumps(state, sort_keys=True)
            state_hash = hashlib.md5(state_str.encode()).hexdigest()
            if state_hash != self._autosave_hash:
                CONFIG_DIR.mkdir(parents=True, exist_ok=True)
                with open(AUTOSAVE_FILE, "w", encoding="utf-8") as f:
                    f.write(state_str)
                self._autosave_hash = state_hash
                logger.debug("Auto-saved form state")
        except Exception as e:
            logger.warning(f"Auto-save failed: {e}")
        self.root.after(AUTOSAVE_INTERVAL_MS, self._do_autosave)

    def _load_autosave(self) -> None:
        if AUTOSAVE_FILE.exists():
            try:
                with open(AUTOSAVE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    valid, _ = self._validate_template(data)
                    if valid:
                        self._apply_state(data)
                        logger.info("Restored from autosave")
            except (OSError, json.JSONDecodeError, ValueError) as e:
                logger.warning(f"Could not load autosave: {e}")

    def _save_history_to_disk(self) -> None:
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(self.history[-MAX_HISTORY:], f, indent=2)
        except Exception as e:
            logger.warning(f"History save failed: {e}")

    def _load_history_from_disk(self) -> None:
        if HISTORY_FILE.exists():
            try:
                with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    self.history = data[-MAX_HISTORY:]
                    for entry in self.history:
                        if isinstance(entry, dict) and "timestamp" in entry and "task_preview" in entry:
                            self.history_listbox.insert(tk.END, f"[{entry['timestamp']}] {entry['task_preview']}")
                    logger.info(f"Loaded {len(self.history)} history entries")
            except (OSError, json.JSONDecodeError) as e:
                logger.warning(f"Could not load history: {e}")

    def _save_geometry(self) -> None:
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

    def _restore_geometry(self) -> None:
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
            except (OSError, json.JSONDecodeError, ValueError):
                pass
        # First launch — start maximized
        self.root.geometry("1150x960")
        self.root.after(0, self._maximize_window)

    def _maximize_window(self) -> None:
        """Maximize the window cross-platform (zoomed on Windows, -zoomed on Linux/macOS)."""
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

    def _restore_window_size(self) -> None:
        """Restore the window from maximized to its normal size."""
        try:
            if platform.system() == "Windows":
                self.root.state("normal")
            else:
                self.root.attributes("-zoomed", False)
        except tk.TclError:
            pass
        self._set_status("Window restored")

    def _toggle_maximize(self) -> None:
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

    # ══════════════════════════════════════════════════════════════
    # SESSION MANAGEMENT
    # ══════════════════════════════════════════════════════════════

    def _new_session(self) -> None:
        self.build_target_var.set("(none)")
        for var in self.enhancement_vars.values():
            var.set(False)
        self.role_input.delete(0, tk.END)
        self.reasoning_var.set("Structured Chain of Thought (SCoT)")
        self.output_format_var.set("Free-form")
        for name, var in self.constraint_vars.items():
            var.set(name in ("Conciseness", "Python Best Practices"))
        self.custom_constraints.delete("1.0", tk.END)
        self.context_input.delete("1.0", tk.END)
        self.task_input.delete("1.0", tk.END)
        self.result_area.delete("1.0", tk.END)
        self._update_token_estimate("")
        self._dirty = False
        self._set_status("New session started")

    def _on_close(self) -> None:
        self._save_geometry()
        self._do_autosave()
        self.root.destroy()

    # ══════════════════════════════════════════════════════════════
    # HELPERS
    # ══════════════════════════════════════════════════════════════

    def _on_reasoning_change(self, value: str) -> None:
        self.reasoning_desc.config(text=REASONING_MODES.get(value, {}).get("description", ""))

    def _on_output_format_change(self, value: str) -> None:
        self.output_format_desc.config(text=OUTPUT_FORMATS.get(value, {}).get("description", ""))

    def _on_result_modified(self, event: tk.Event) -> None:
        self.result_area.edit_modified(False)
        self._update_token_estimate(self.result_area.get("1.0", tk.END))

    def _update_token_estimate(self, text: str) -> None:
        est = max(0, len(text) // 4)
        self.token_label.config(text=f"~{est:,} tokens")

    def _set_font_size(self, size: int) -> None:
        s = ttk.Style()
        s.configure("TLabel", font=("Segoe UI", size))
        s.configure("Sub.TLabel", font=("Segoe UI", max(size - 1, 7)))
        s.configure("Desc.TLabel", font=("Segoe UI", max(size - 1, 7)))
        s.configure("Warn.TLabel", font=("Segoe UI", max(size - 1, 7)))
        s.configure("Header.TLabel", font=("Segoe UI", size + 6, "bold"))
        s.configure("TCheckbutton", font=("Segoe UI", size))
        s.configure("TRadiobutton", font=("Segoe UI", size))
        self._set_status(f"Font size set to {size}")

    def _show_shortcuts(self) -> None:
        shortcuts = (
            "Keyboard Shortcuts\n"
            "\u2550" * 34 + "\n\n"
            "  Ctrl+Enter       Generate prompt\n"
            "  Ctrl+Shift+C     Copy output\n"
            "  Ctrl+S           Save output to file\n"
            "  Ctrl+D           Run diagnostics\n"
            "  Ctrl+N           New session\n"
            "  Ctrl+T           Toggle dark/light theme\n"
            "  Ctrl+Z           Undo (in text fields)\n"
            "  Ctrl+Y           Redo (in text fields)\n"
            "  Ctrl+A           Select all (in text fields)\n"
            "  F11              Toggle maximize/restore window\n"
        )
        messagebox.showinfo("Keyboard Shortcuts", shortcuts)

    def _show_about(self) -> None:
        about = (
            f"{APP_NAME} v{APP_VERSION}\n\n"
            f"A visual prompt builder for AI coding assistants.\n\n"
            f"Python {sys.version.split()[0]}\n"
            f"Tk {tk.TkVersion}\n\n"
            f"Theme: Catppuccin (Dark & Light)"
        )
        messagebox.showinfo("About", about)

    def _ask_string(self, title: str, prompt: str) -> str | None:
        c = self._active_colors()
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.geometry("350x130")
        dialog.configure(bg=c["bg"])
        dialog.transient(self.root)
        dialog.grab_set()
        ttk.Label(dialog, text=prompt).pack(padx=15, pady=(15, 5))
        entry = ttk.Entry(dialog, font=("Segoe UI", 10))
        entry.pack(padx=15, fill=tk.X)
        entry.focus_set()
        result = [None]

        def on_ok(event=None):
            result[0] = entry.get().strip()
            dialog.destroy()

        entry.bind("<Return>", on_ok)
        tk.Button(dialog, text="OK", command=on_ok, bg=c["green"], fg=c["dark"], font=("Segoe UI", 10, "bold"), relief=tk.FLAT, padx=20, pady=4).pack(pady=10)
        dialog.wait_window()
        return result[0]

    def _bind_shortcuts(self) -> None:
        self.root.bind("<Control-Return>", lambda e: self.generate())
        self.root.bind("<Control-Shift-C>", lambda e: self.copy_to_clipboard())
        self.root.bind("<Control-s>", lambda e: self.save_to_file())
        self.root.bind("<Control-d>", lambda e: self._run_diagnostics())
        self.root.bind("<Control-n>", lambda e: self._new_session())
        self.root.bind("<Control-t>", lambda e: self._toggle_theme())
        self.root.bind("<Control-z>", lambda e: self._undo())
        self.root.bind("<Control-y>", lambda e: self._redo())
        self.root.bind("<F11>", lambda e: self._toggle_maximize())

        # Add right-click context menus to ALL text input widgets
        # This fixes mouse copy/paste which tkinter doesn't provide by default
        self._add_text_context_menus()

    def _add_text_context_menus(self) -> None:
        """Add right-click copy/cut/paste/select-all context menus to every text widget."""
        text_widgets = [
            self.task_input,
            self.context_input,
            self.custom_constraints,
            self.followup_input,
            self.followup_output,
            self.diag_area,
        ]
        # Also add to any Entry widgets
        entry_widgets = [self.role_input]
        if hasattr(self, "_history_search"):
            entry_widgets.append(self._history_search)

        for widget in text_widgets:
            self._attach_text_menu(widget)

        for widget in entry_widgets:
            self._attach_entry_menu(widget)

    def _attach_text_menu(self, widget) -> None:
        """Attach a right-click context menu to a Text or ScrolledText widget."""
        c = self._active_colors()
        menu = tk.Menu(self.root, tearoff=0, bg=c["surface"], fg=c["text"],
                       activebackground=c["blue"], activeforeground=c["dark"],
                       font=("Segoe UI", 10))

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

        menu.add_command(label="Cut              Ctrl+X", command=do_cut)
        menu.add_command(label="Copy             Ctrl+C", command=do_copy)
        menu.add_command(label="Paste            Ctrl+V", command=do_paste)
        menu.add_separator()
        menu.add_command(label="Select All       Ctrl+A", command=do_select_all)
        menu.add_command(label="Clear", command=do_clear)

        widget.bind("<Button-3>", lambda e: menu.tk_popup(e.x_root, e.y_root))

        # Make sure Ctrl+C/V/X/A work natively in this widget
        widget.bind("<Control-c>", lambda e: (do_copy(), "break")[-1])
        widget.bind("<Control-x>", lambda e: (do_cut(), "break")[-1])
        widget.bind("<Control-v>", lambda e: (do_paste(), "break")[-1])
        widget.bind("<Control-a>", lambda e: (do_select_all(), "break")[-1])

    def _attach_entry_menu(self, widget) -> None:
        """Attach a right-click context menu to an Entry or ttk.Entry widget."""
        c = self._active_colors()
        menu = tk.Menu(self.root, tearoff=0, bg=c["surface"], fg=c["text"],
                       activebackground=c["blue"], activeforeground=c["dark"],
                       font=("Segoe UI", 10))

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

        menu.add_command(label="Cut              Ctrl+X", command=do_cut)
        menu.add_command(label="Copy             Ctrl+C", command=do_copy)
        menu.add_command(label="Paste            Ctrl+V", command=do_paste)
        menu.add_separator()
        menu.add_command(label="Select All       Ctrl+A", command=do_select_all)
        menu.add_command(label="Clear", command=do_clear)

        widget.bind("<Button-3>", lambda e: menu.tk_popup(e.x_root, e.y_root))


if __name__ == "__main__":
    root = tk.Tk()
    app = PromptArchitect(root)
    root.mainloop()

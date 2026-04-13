"""
Prompt Architect — Android / Mobile Edition (Kivy)

Touch-friendly prompt builder for phones and tablets.
Uses prompt_engine.py for all generation logic.

Desktop preview:  python prompt_architect_android.py
Android APK:      pip install buildozer && buildozer android debug
"""

import json
import os
from pathlib import Path

# Kivy config — must come before any kivy import
os.environ.setdefault("KIVY_NO_CONSOLELOG", "1")

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.togglebutton import ToggleButton
from kivy.uix.spinner import Spinner
from kivy.uix.screenmanager import ScreenManager, Screen, SlideTransition
from kivy.uix.popup import Popup
from kivy.core.clipboard import Clipboard
from kivy.metrics import dp, sp
from kivy.utils import get_color_from_hex
from kivy.core.window import Window
from kivy.clock import Clock

import prompt_engine as engine

# ═══════════════════════════════════════════════════════════════════
# THEME — Catppuccin Mocha (same as desktop)
# ═══════════════════════════════════════════════════════════════════

C = {
    "bg": "#1e1e2e", "surface": "#313244", "overlay": "#181825",
    "text": "#cdd6f4", "subtext": "#a6adc8", "blue": "#89b4fa",
    "green": "#a6e3a1", "red": "#f38ba8", "peach": "#fab387",
    "mauve": "#cba6f7", "yellow": "#f9e2af", "teal": "#94e2d5",
    "dark": "#11111b",
}


def rgb(key):
    return get_color_from_hex(C[key])


TEMPLATES_DIR = Path(os.path.dirname(os.path.abspath(__file__))) / "prompt_templates"


# ═══════════════════════════════════════════════════════════════════
# REUSABLE WIDGETS
# ═══════════════════════════════════════════════════════════════════

class SectionLabel(Label):
    """Bold section header."""
    def __init__(self, text, **kw):
        super().__init__(
            text=text, font_size=sp(16), bold=True,
            color=rgb("mauve"), size_hint_y=None, height=dp(36),
            halign="left", valign="middle",
        )
        self.bind(size=self.setter("text_size"))


class DescLabel(Label):
    """Small description text that wraps."""
    def __init__(self, text, **kw):
        super().__init__(
            text=text, font_size=sp(13), color=rgb("subtext"),
            size_hint_y=None, halign="left", valign="top",
            padding=(dp(8), dp(4)),
        )
        self.bind(size=self._update_height)
        self.bind(texture_size=self._update_height)
        self.text_size = (Window.width - dp(60), None)

    def _update_height(self, *args):
        self.height = max(dp(20), self.texture_size[1] + dp(8))
        self.text_size = (self.width - dp(16), None)


class RadioGroup(BoxLayout):
    """A group of radio-style toggle buttons."""
    def __init__(self, options, group_name, default=None, on_select=None, **kw):
        super().__init__(orientation="vertical", size_hint_y=None, spacing=dp(4), **kw)
        self.buttons = {}
        self.on_select_cb = on_select
        self.selected = default or (list(options.keys())[0] if options else "")
        for name in options:
            btn = ToggleButton(
                text=name, group=group_name,
                size_hint_y=None, height=dp(44),
                font_size=sp(14),
                background_normal="", background_color=rgb("surface"),
                color=rgb("text"),
                state="down" if name == self.selected else "normal",
            )
            btn.bind(on_press=lambda b, n=name: self._on_press(n))
            self.buttons[name] = btn
            self.add_widget(btn)
        self.height = len(options) * dp(48)

    def _on_press(self, name):
        self.selected = name
        for n, b in self.buttons.items():
            b.background_color = rgb("blue") if n == name else rgb("surface")
        if self.on_select_cb:
            self.on_select_cb(name)

    def get(self):
        return self.selected


class CheckGroup(BoxLayout):
    """A group of checkboxes (toggle buttons, multi-select)."""
    def __init__(self, options, defaults=None, **kw):
        super().__init__(orientation="vertical", size_hint_y=None, spacing=dp(4), **kw)
        self.buttons = {}
        defaults = defaults or []
        for name in options:
            btn = ToggleButton(
                text=name, size_hint_y=None, height=dp(44),
                font_size=sp(14),
                background_normal="", background_color=rgb("surface"),
                color=rgb("text"),
                state="down" if name in defaults else "normal",
            )
            btn.bind(on_press=lambda b, n=name: self._on_toggle(n))
            self.buttons[name] = btn
            self.add_widget(btn)
        self.height = len(options) * dp(48)

    def _on_toggle(self, name):
        btn = self.buttons[name]
        if btn.state == "down":
            btn.background_color = rgb("peach")
        else:
            btn.background_color = rgb("surface")

    def get_selected(self) -> list[str]:
        return [n for n, b in self.buttons.items() if b.state == "down"]


# ═══════════════════════════════════════════════════════════════════
# SCREENS
# ═══════════════════════════════════════════════════════════════════

class BuildScreen(Screen):
    """Main builder — category selection, options, task, generate."""
    def __init__(self, **kw):
        super().__init__(**kw)
        self.category = "Code"

        root = BoxLayout(orientation="vertical", padding=dp(8), spacing=dp(8))
        root.canvas.before.clear()
        from kivy.graphics import Color, Rectangle
        with root.canvas.before:
            Color(*rgb("bg"))
            self._bg_rect = Rectangle(pos=root.pos, size=root.size)
        root.bind(pos=self._update_bg, size=self._update_bg)

        # Scroll area
        scroll = ScrollView(do_scroll_x=False)
        self.content = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(8), padding=(dp(4), dp(4)))
        self.content.bind(minimum_height=self.content.setter("height"))
        scroll.add_widget(self.content)
        root.add_widget(scroll)

        # Build all the sections into self.content
        self._build_category_selector()
        self._build_code_panel()
        self._build_conv_panel()
        self._build_image_panel()
        self._build_video_panel()
        self._build_shared_options()
        self._build_task_section()
        self._build_generate_button()

        # Show only code panel initially
        self._show_category("Code")

        self.add_widget(root)

    def _update_bg(self, *args):
        self._bg_rect.pos = self.children[0].pos
        self._bg_rect.size = self.children[0].size

    def _build_category_selector(self):
        self.content.add_widget(SectionLabel("What Are You Prompting For?"))
        grid = GridLayout(cols=2, size_hint_y=None, height=dp(100), spacing=dp(6))
        cats = {"Code": rgb("green"), "Chat": rgb("blue"), "Image": rgb("peach"), "Video": rgb("mauve")}
        self._cat_buttons = {}
        for name, color in cats.items():
            btn = Button(
                text=name, font_size=sp(16), bold=True,
                background_normal="", background_color=color,
                color=rgb("dark"), size_hint_y=None, height=dp(46),
            )
            btn.bind(on_press=lambda b, n=name: self._on_category(n))
            grid.add_widget(btn)
            self._cat_buttons[name] = btn
        self.content.add_widget(grid)

    def _on_category(self, name):
        self.category = name
        self._show_category(name)
        # Visual feedback
        for n, b in self._cat_buttons.items():
            if n == name:
                b.font_size = sp(18)
            else:
                b.font_size = sp(16)

    def _show_category(self, cat):
        panels = {"Code": self._code_panel, "Chat": self._conv_panel, "Image": self._image_panel, "Video": self._video_panel}
        for name, panel in panels.items():
            if name == cat:
                if panel not in self.content.children:
                    # Insert after category selector (which is at the end of children list since Kivy reverses)
                    idx = len(self.content.children) - 2  # After the grid
                    self.content.add_widget(panel, index=idx)
            else:
                if panel in self.content.children:
                    self.content.remove_widget(panel)

    # ── Code panel ────────────────────────────────────────────────

    def _build_code_panel(self):
        self._code_panel = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(6))
        self._code_panel.add_widget(SectionLabel("Build Target (pick one)"))
        self.build_target = RadioGroup(engine.BUILD_TARGETS, "build_target", default="PC Desktop App")
        self._code_panel.add_widget(self.build_target)
        self._code_panel.add_widget(SectionLabel("Enhancements (pick any)"))
        self.enhancements = CheckGroup(engine.ENHANCEMENTS)
        self._code_panel.add_widget(self.enhancements)
        self._code_panel.height = sum(c.height for c in self._code_panel.children) + dp(20)
        self._code_panel.bind(minimum_height=self._code_panel.setter("height"))

    # ── Conversation panel ────────────────────────────────────────

    def _build_conv_panel(self):
        self._conv_panel = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(6))
        self._conv_panel.add_widget(SectionLabel("Conversation Style"))
        self.conv_style = RadioGroup(engine.CONVERSATION_STYLES, "conv_style", default="General Chat")
        self._conv_panel.add_widget(self.conv_style)
        self._conv_panel.add_widget(SectionLabel("Tone"))
        self.conv_tone = RadioGroup(engine.CONVERSATION_TONES, "conv_tone", default="Casual")
        self._conv_panel.add_widget(self.conv_tone)
        self._conv_panel.height = sum(c.height for c in self._conv_panel.children) + dp(20)

    # ── Image panel ───────────────────────────────────────────────

    def _build_image_panel(self):
        self._image_panel = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(6))
        self._image_panel.add_widget(SectionLabel("Image Style"))
        self.image_style = RadioGroup(engine.IMAGE_STYLES, "img_style", default="Photorealistic")
        self._image_panel.add_widget(self.image_style)
        self._image_panel.add_widget(SectionLabel("Lighting"))
        self.image_lighting = RadioGroup(engine.IMAGE_LIGHTING, "img_light", default="Natural / Soft")
        self._image_panel.add_widget(self.image_lighting)
        self._image_panel.add_widget(SectionLabel("Camera / Perspective"))
        self.image_camera = RadioGroup(engine.IMAGE_CAMERAS, "img_cam", default="Portrait (85mm)")
        self._image_panel.add_widget(self.image_camera)
        self._image_panel.height = sum(c.height for c in self._image_panel.children) + dp(20)

    # ── Video panel ───────────────────────────────────────────────

    def _build_video_panel(self):
        self._video_panel = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(6))
        self._video_panel.add_widget(SectionLabel("Video Style"))
        self.video_style = RadioGroup(engine.VIDEO_STYLES, "vid_style", default="Cinematic")
        self._video_panel.add_widget(self.video_style)
        self._video_panel.add_widget(SectionLabel("Camera Movement"))
        self.video_camera = RadioGroup(engine.VIDEO_CAMERA_MOVES, "vid_cam", default="Slow Pan")
        self._video_panel.add_widget(self.video_camera)
        self._video_panel.add_widget(SectionLabel("Pacing"))
        self.video_pacing = RadioGroup(engine.VIDEO_PACING, "vid_pace", default="Medium / Narrative")
        self._video_panel.add_widget(self.video_pacing)
        self._video_panel.height = sum(c.height for c in self._video_panel.children) + dp(20)

    # ── Shared options ────────────────────────────────────────────

    def _build_shared_options(self):
        # Role
        self.content.add_widget(SectionLabel("Role (optional)"))
        self.content.add_widget(DescLabel("Who should the AI act as? Leave blank for auto."))
        self.role_input = TextInput(
            hint_text="e.g. Senior Python Developer",
            size_hint_y=None, height=dp(44), font_size=sp(14),
            background_color=rgb("surface"), foreground_color=rgb("text"),
            cursor_color=rgb("blue"), multiline=False,
        )
        self.content.add_widget(self.role_input)

        # Reasoning
        self.content.add_widget(SectionLabel("Thinking Style"))
        self.reasoning_spinner = Spinner(
            text="Structured CoT (SCoT)",
            values=list(engine.REASONING_MODES.keys()),
            size_hint_y=None, height=dp(44), font_size=sp(14),
            background_color=rgb("surface"), color=rgb("text"),
        )
        self.content.add_widget(self.reasoning_spinner)

        # Output format
        self.content.add_widget(SectionLabel("Output Format"))
        self.format_spinner = Spinner(
            text="Free-form",
            values=list(engine.OUTPUT_FORMATS.keys()),
            size_hint_y=None, height=dp(44), font_size=sp(14),
            background_color=rgb("surface"), color=rgb("text"),
        )
        self.content.add_widget(self.format_spinner)

        # Constraints
        self.content.add_widget(SectionLabel("Quality Rules"))
        self.constraints = CheckGroup(engine.CONSTRAINT_PRESETS, defaults=["Conciseness", "Python Best Practices"])
        self.content.add_widget(self.constraints)

    # ── Task ──────────────────────────────────────────────────────

    def _build_task_section(self):
        hdr = BoxLayout(size_hint_y=None, height=dp(36), spacing=dp(8))
        hdr.add_widget(SectionLabel("Task / Prompt Description"))
        clear_btn = Button(
            text="Clear", size_hint=(None, None), size=(dp(70), dp(32)),
            font_size=sp(12), background_normal="",
            background_color=rgb("red"), color=rgb("dark"),
        )
        clear_btn.bind(on_press=lambda b: setattr(self.task_input, "text", ""))
        hdr.add_widget(clear_btn)
        self.content.add_widget(hdr)

        self.content.add_widget(DescLabel("Be specific — more detail = better results."))

        self.task_input = TextInput(
            text="Create a Python script that monitors CPU usage and logs to CSV every 5 seconds.",
            size_hint_y=None, height=dp(120), font_size=sp(14),
            background_color=rgb("surface"), foreground_color=rgb("text"),
            cursor_color=rgb("blue"), multiline=True,
        )
        self.content.add_widget(self.task_input)

        # Context
        ctx_hdr = BoxLayout(size_hint_y=None, height=dp(36), spacing=dp(8))
        ctx_hdr.add_widget(SectionLabel("Extra Context (optional)"))
        ctx_clear = Button(
            text="Clear", size_hint=(None, None), size=(dp(70), dp(32)),
            font_size=sp(12), background_normal="",
            background_color=rgb("red"), color=rgb("dark"),
        )
        ctx_clear.bind(on_press=lambda b: setattr(self.context_input, "text", ""))
        ctx_hdr.add_widget(ctx_clear)
        self.content.add_widget(ctx_hdr)

        self.context_input = TextInput(
            hint_text="Paste examples, docs, or extra info here...",
            size_hint_y=None, height=dp(80), font_size=sp(14),
            background_color=rgb("surface"), foreground_color=rgb("text"),
            cursor_color=rgb("blue"), multiline=True,
        )
        self.content.add_widget(self.context_input)

    # ── Generate ──────────────────────────────────────────────────

    def _build_generate_button(self):
        btn = Button(
            text="GENERATE PROMPT", size_hint_y=None, height=dp(56),
            font_size=sp(18), bold=True,
            background_normal="", background_color=rgb("green"),
            color=rgb("dark"),
        )
        btn.bind(on_press=lambda b: self.generate())
        self.content.add_widget(btn)

    def generate(self):
        task = self.task_input.text.strip()
        if not task:
            self._show_popup("Missing Task", "Enter a task description.")
            return

        context = self.context_input.text.strip()
        role = self.role_input.text.strip()
        reasoning = self.reasoning_spinner.text
        output_fmt = self.format_spinner.text
        constraint_presets = self.constraints.get_selected()
        cat = self.category

        if cat == "Code":
            prompt = engine.generate_code_prompt(
                task=task, role=role,
                build_target=self.build_target.get(),
                enhancements=self.enhancements.get_selected(),
                context=context, reasoning=reasoning,
                output_format=output_fmt,
                constraint_presets=constraint_presets,
            )
        elif cat == "Chat":
            prompt = engine.generate_conversation_prompt(
                task=task, role=role,
                style=self.conv_style.get(),
                tone=self.conv_tone.get(),
                context=context, reasoning=reasoning,
                output_format=output_fmt,
                constraint_presets=constraint_presets,
            )
        elif cat == "Image":
            prompt = engine.generate_image_prompt(
                task=task,
                style=self.image_style.get(),
                lighting=self.image_lighting.get(),
                camera=self.image_camera.get(),
                context=context,
            )
        elif cat == "Video":
            prompt = engine.generate_video_prompt(
                task=task,
                style=self.video_style.get(),
                camera_move=self.video_camera.get(),
                pacing=self.video_pacing.get(),
                context=context,
            )
        else:
            prompt = f"# TASK\n{task}"

        review = engine.build_results_review(task, prompt, cat if cat != "Chat" else "Conversation")

        # Switch to result screen
        app = App.get_running_app()
        result_screen = app.sm.get_screen("result")
        result_screen.set_result(prompt, review)
        app.sm.transition = SlideTransition(direction="left")
        app.sm.current = "result"

    def _show_popup(self, title, msg):
        content = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(12))
        content.add_widget(Label(text=msg, font_size=sp(14), color=rgb("text")))
        btn = Button(text="OK", size_hint_y=None, height=dp(44), background_normal="", background_color=rgb("blue"), color=rgb("dark"))
        content.add_widget(btn)
        popup = Popup(title=title, content=content, size_hint=(0.8, 0.35), background_color=rgb("bg"))
        btn.bind(on_press=popup.dismiss)
        popup.open()

    def collect_state(self) -> dict:
        return {
            "category": self.category,
            "build_target": self.build_target.get(),
            "enhancements": self.enhancements.get_selected(),
            "conv_style": self.conv_style.get(),
            "conv_tone": self.conv_tone.get(),
            "image_style": self.image_style.get(),
            "image_lighting": self.image_lighting.get(),
            "image_camera": self.image_camera.get(),
            "video_style": self.video_style.get(),
            "video_camera": self.video_camera.get(),
            "video_pacing": self.video_pacing.get(),
            "role": self.role_input.text,
            "reasoning": self.reasoning_spinner.text,
            "output_format": self.format_spinner.text,
            "constraints": self.constraints.get_selected(),
            "task": self.task_input.text,
            "context": self.context_input.text,
        }


class ResultScreen(Screen):
    """Shows generated prompt + review with copy/share/clear."""
    def __init__(self, **kw):
        super().__init__(**kw)
        self._prompt_text = ""

        root = BoxLayout(orientation="vertical", padding=dp(8), spacing=dp(6))
        from kivy.graphics import Color, Rectangle
        with root.canvas.before:
            Color(*rgb("bg"))
            self._bg = Rectangle(pos=root.pos, size=root.size)
        root.bind(pos=lambda *a: setattr(self._bg, "pos", root.pos),
                  size=lambda *a: setattr(self._bg, "size", root.size))

        # Header
        hdr = BoxLayout(size_hint_y=None, height=dp(40))
        back_btn = Button(
            text="< Back", size_hint=(None, 1), width=dp(80),
            font_size=sp(14), background_normal="",
            background_color=rgb("surface"), color=rgb("blue"),
        )
        back_btn.bind(on_press=self._go_back)
        hdr.add_widget(back_btn)
        hdr.add_widget(Label(text="Generated Prompt", font_size=sp(16), bold=True, color=rgb("yellow")))
        root.add_widget(hdr)

        # Result text
        self.result_text = TextInput(
            readonly=False, font_size=sp(13),
            background_color=rgb("overlay"), foreground_color=rgb("yellow"),
            cursor_color=rgb("blue"), multiline=True,
        )
        root.add_widget(self.result_text)

        # Action buttons
        actions = BoxLayout(size_hint_y=None, height=dp(52), spacing=dp(6))
        for txt, color, cb in [
            ("Copy Prompt", "green", self._copy),
            ("Share", "blue", self._share),
            ("Clear", "red", self._clear),
        ]:
            btn = Button(
                text=txt, font_size=sp(14), bold=True,
                background_normal="", background_color=rgb(color),
                color=rgb("dark"),
            )
            btn.bind(on_press=cb)
            actions.add_widget(btn)
        root.add_widget(actions)

        self.add_widget(root)

    def set_result(self, prompt: str, review: str):
        self._prompt_text = prompt
        self.result_text.text = prompt + "\n\n" + review

    def _copy(self, *args):
        if self._prompt_text:
            Clipboard.copy(self._prompt_text)
            self._show_toast("Prompt copied to clipboard!")

    def _share(self, *args):
        try:
            from plyer import share
            if self._prompt_text:
                share.share_text(self._prompt_text, title="Prompt Architect")
        except ImportError:
            # plyer not available (desktop preview mode)
            self._copy()

    def _clear(self, *args):
        self.result_text.text = ""
        self._prompt_text = ""

    def _go_back(self, *args):
        App.get_running_app().sm.transition = SlideTransition(direction="right")
        App.get_running_app().sm.current = "build"

    def _show_toast(self, msg):
        content = BoxLayout(padding=dp(12))
        content.add_widget(Label(text=msg, font_size=sp(14), color=rgb("text")))
        popup = Popup(title="", content=content, size_hint=(0.7, 0.15),
                      background_color=rgb("surface"), separator_height=0)
        popup.open()
        Clock.schedule_once(lambda dt: popup.dismiss(), 2)


class TemplatesScreen(Screen):
    """Save / load / delete prompt templates."""
    def __init__(self, **kw):
        super().__init__(**kw)

        root = BoxLayout(orientation="vertical", padding=dp(8), spacing=dp(8))
        from kivy.graphics import Color, Rectangle
        with root.canvas.before:
            Color(*rgb("bg"))
            self._bg = Rectangle(pos=root.pos, size=root.size)
        root.bind(pos=lambda *a: setattr(self._bg, "pos", root.pos),
                  size=lambda *a: setattr(self._bg, "size", root.size))

        root.add_widget(SectionLabel("Saved Templates"))
        root.add_widget(DescLabel("Tap a template to load it. Your current settings will be replaced."))

        # Button row
        btn_row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(6))
        save_btn = Button(text="Save Current", font_size=sp(14), bold=True, background_normal="", background_color=rgb("peach"), color=rgb("dark"))
        save_btn.bind(on_press=lambda b: self._save_template())
        btn_row.add_widget(save_btn)
        del_btn = Button(text="Delete Selected", font_size=sp(14), bold=True, background_normal="", background_color=rgb("red"), color=rgb("dark"))
        del_btn.bind(on_press=lambda b: self._delete_selected())
        btn_row.add_widget(del_btn)
        root.add_widget(btn_row)

        # Template list (scroll)
        scroll = ScrollView(do_scroll_x=False)
        self.list_layout = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(4))
        self.list_layout.bind(minimum_height=self.list_layout.setter("height"))
        scroll.add_widget(self.list_layout)
        root.add_widget(scroll)

        self.selected_template = None
        self.add_widget(root)

    def on_enter(self):
        self._refresh()

    def _refresh(self):
        self.list_layout.clear_widgets()
        self.selected_template = None
        TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
        for f in sorted(TEMPLATES_DIR.glob("*.json")):
            name = f.stem
            btn = ToggleButton(
                text=name, group="templates",
                size_hint_y=None, height=dp(44), font_size=sp(14),
                background_normal="", background_color=rgb("surface"),
                color=rgb("text"),
            )
            btn.bind(on_press=lambda b, n=name: self._on_select(n, b))
            self.list_layout.add_widget(btn)

    def _on_select(self, name, btn):
        self.selected_template = name
        # Load it
        path = TEMPLATES_DIR / f"{name}.json"
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            # Apply to build screen — simplified: just load task/context/role
            app = App.get_running_app()
            build = app.sm.get_screen("build")
            if "task" in data:
                build.task_input.text = data["task"]
            if "context" in data:
                build.context_input.text = data.get("context", "")
            if "role" in data:
                build.role_input.text = data.get("role", "")
            self._show_toast(f"Loaded '{name}'")
        except Exception as e:
            self._show_toast(f"Error: {e}")

    def _save_template(self):
        app = App.get_running_app()
        build = app.sm.get_screen("build")
        state = build.collect_state()

        # Ask for name via popup
        content = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(12))
        content.add_widget(Label(text="Template name:", font_size=sp(14), color=rgb("text"), size_hint_y=None, height=dp(30)))
        name_input = TextInput(
            hint_text="My Template", size_hint_y=None, height=dp(44),
            font_size=sp(14), multiline=False,
            background_color=rgb("surface"), foreground_color=rgb("text"),
        )
        content.add_widget(name_input)
        btn_row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        save_btn = Button(text="Save", background_normal="", background_color=rgb("green"), color=rgb("dark"), font_size=sp(14))
        cancel_btn = Button(text="Cancel", background_normal="", background_color=rgb("surface"), color=rgb("text"), font_size=sp(14))
        btn_row.add_widget(save_btn)
        btn_row.add_widget(cancel_btn)
        content.add_widget(btn_row)

        popup = Popup(title="Save Template", content=content, size_hint=(0.85, 0.4), background_color=rgb("bg"))

        def do_save(*args):
            name = name_input.text.strip()
            if not name:
                return
            import re
            safe = re.sub(r'[^\w\-_ ]', '', name).strip()
            if not safe:
                return
            TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
            path = TEMPLATES_DIR / f"{safe}.json"
            path.write_text(json.dumps(state, indent=2), encoding="utf-8")
            popup.dismiss()
            self._refresh()
            self._show_toast(f"Saved '{safe}'")

        save_btn.bind(on_press=do_save)
        cancel_btn.bind(on_press=popup.dismiss)
        popup.open()

    def _delete_selected(self):
        if not self.selected_template:
            return
        path = TEMPLATES_DIR / f"{self.selected_template}.json"
        if path.exists():
            path.unlink()
            self._refresh()
            self._show_toast(f"Deleted '{self.selected_template}'")

    def _show_toast(self, msg):
        content = BoxLayout(padding=dp(12))
        content.add_widget(Label(text=msg, font_size=sp(14), color=rgb("text")))
        popup = Popup(title="", content=content, size_hint=(0.7, 0.12), background_color=rgb("surface"), separator_height=0)
        popup.open()
        Clock.schedule_once(lambda dt: popup.dismiss(), 2)


# ═══════════════════════════════════════════════════════════════════
# MAIN APP
# ═══════════════════════════════════════════════════════════════════

class PromptArchitectApp(App):
    def build(self):
        self.title = "Prompt Architect"
        Window.clearcolor = rgb("bg")

        # Main layout: screen area + bottom nav
        layout = BoxLayout(orientation="vertical")

        self.sm = ScreenManager()
        self.sm.add_widget(BuildScreen(name="build"))
        self.sm.add_widget(ResultScreen(name="result"))
        self.sm.add_widget(TemplatesScreen(name="templates"))
        layout.add_widget(self.sm)

        # Bottom navigation bar
        nav = BoxLayout(size_hint_y=None, height=dp(56), spacing=dp(2))
        from kivy.graphics import Color, Rectangle
        with nav.canvas.before:
            Color(*rgb("dark"))
            nav._bg = Rectangle(pos=nav.pos, size=nav.size)
        nav.bind(pos=lambda *a: setattr(nav._bg, "pos", nav.pos),
                 size=lambda *a: setattr(nav._bg, "size", nav.size))

        tabs = [
            ("Build", "build", "green"),
            ("Result", "result", "yellow"),
            ("Templates", "templates", "peach"),
        ]
        for label, screen_name, color in tabs:
            btn = Button(
                text=label, font_size=sp(14), bold=True,
                background_normal="", background_color=rgb("surface"),
                color=rgb(color),
            )
            btn.bind(on_press=lambda b, sn=screen_name: self._switch_tab(sn))
            nav.add_widget(btn)
        layout.add_widget(nav)

        return layout

    def _switch_tab(self, screen_name):
        if self.sm.current != screen_name:
            direction = "left" if list(self.sm.screen_names).index(screen_name) > list(self.sm.screen_names).index(self.sm.current) else "right"
            self.sm.transition = SlideTransition(direction=direction)
            self.sm.current = screen_name


if __name__ == "__main__":
    PromptArchitectApp().run()

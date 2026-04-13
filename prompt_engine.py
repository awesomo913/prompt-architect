"""
Prompt Engine — Shared logic for Prompt Architect (all platforms).

This module contains all data dictionaries and prompt generation functions
with ZERO UI dependencies. It can be imported by the desktop app (tkinter),
the Android app (Kivy), or any other frontend.

Usage:
    from prompt_engine import (
        generate_code_prompt, generate_conversation_prompt,
        generate_image_prompt, generate_video_prompt,
        build_results_review, gather_constraints,
        BUILD_TARGETS, ENHANCEMENTS, REASONING_MODES, ...
    )
"""

# ═══════════════════════════════════════════════════════════════════
# BUILD TARGETS — Code category (pick one)
# ═══════════════════════════════════════════════════════════════════

BUILD_TARGETS = {
    "PC Desktop App": {
        "description": "Window app for Windows/Mac/Linux — like Notepad or Spotify.",
        "role": "Senior Desktop Application Engineer specializing in cross-platform GUI development, native OS integration, and production-grade packaging",
        "platform_context": (
            "TARGET PLATFORM: Windows / macOS / Linux desktop.\n"
            "- Python 3.10+ with tkinter/ttk, PyQt6, or wxPython for GUI.\n"
            "- Handle DPI scaling, window management, cross-platform paths (pathlib).\n"
            "- Save settings via JSON/TOML. Graceful shutdown. Threading for long ops."
        ),
        "extra_constraints": [
            "Separate UI, logic, and data layers.",
            "Include if __name__ == '__main__' guard.",
            "Use threading for long operations to keep UI responsive.",
            "Handle missing files and startup failures gracefully.",
        ],
    },
    "Raspberry Pi App": {
        "description": "Lightweight Pi app with GPIO, sensor, and camera support.",
        "role": "Embedded Systems Engineer specializing in Raspberry Pi, ARM Linux, GPIO programming, and resource-constrained design",
        "platform_context": (
            "TARGET PLATFORM: Raspberry Pi (ARM Linux).\n"
            "- Limited RAM. SD card wears out — minimize writes.\n"
            "- GPIO via gpiozero or lgpio. Camera via picamera2.\n"
            "- Design for headless use. Handle power loss gracefully."
        ),
        "extra_constraints": [
            "Include requirements.txt with pinned versions.",
            "Support both Pi 4 (RPi.GPIO) and Pi 5 (lgpio).",
            "Handle missing hardware with clear error messages.",
        ],
    },
    "Cross-Platform (PC + Pi)": {
        "description": "One codebase for both PC and Raspberry Pi.",
        "role": "Cross-Platform Architect for portable Python apps on x86 desktop and ARM Raspberry Pi",
        "platform_context": (
            "TARGET: Desktop AND Raspberry Pi.\n"
            "- Auto-detect platform at startup. GPIO optional on PC (stubs).\n"
            "- tkinter for GUI. Headless CLI fallback on Pi.\n"
            "- Use pathlib, conditional imports for Pi libraries."
        ),
        "extra_constraints": [
            "Abstract hardware interfaces with PC mock and Pi real implementations.",
            "Use try/except ImportError for Pi-specific libraries.",
        ],
    },
    "Game": {
        "description": "Video game with graphics, input, audio, and game loop.",
        "role": "Game Developer specializing in 2D/3D game architecture, rendering, physics, and player experience",
        "platform_context": (
            "TARGET: Game (pygame/pyglet/arcade).\n"
            "- 60 FPS game loop, delta-time movement.\n"
            "- Separate state, rendering, input. Scene manager.\n"
            "- Load assets from organized assets/ directory."
        ),
        "extra_constraints": [
            "All speeds/sizes/colors as named constants.",
            "Handle window close and pause/resume cleanly.",
            "No per-frame memory allocations in the game loop.",
        ],
    },
    "Website / Web App": {
        "description": "Browser-based web app — frontend, backend, database.",
        "role": "Full-Stack Web Developer specializing in responsive design, REST APIs, accessibility, and web security",
        "platform_context": (
            "TARGET: Web application.\n"
            "- Frontend: HTML5/CSS3/JS. Backend: Flask/FastAPI/Django.\n"
            "- Mobile-first responsive. Accessibility.\n"
            "- Security: CSRF, XSS prevention, env-based secrets."
        ),
        "extra_constraints": [
            "Validate input on both client and server side.",
            "Use HTTPS-only cookies for auth.",
        ],
    },
    "Android App": {
        "description": "Mobile app for Android phones and tablets.",
        "role": "Android Mobile Developer specializing in Kotlin, Jetpack Compose, Material Design 3, and Google Play Store requirements",
        "platform_context": (
            "TARGET: Android.\n"
            "- Kotlin + Jetpack Compose. Material Design 3.\n"
            "- MVVM architecture. Room database. Retrofit networking.\n"
            "- Handle permissions, lifecycle, rotation. Coroutines for threading.\n"
            "- Min SDK 24. Play Store compliance."
        ),
        "extra_constraints": [
            "Handle all screen sizes: phones, tablets, foldables.",
            "Support dark mode. Handle back button and gesture nav.",
            "Minimize battery drain. Use WorkManager for background tasks.",
        ],
    },
}

# ═══════════════════════════════════════════════════════════════════
# ENHANCEMENTS — Code category (pick any, they stack)
# ═══════════════════════════════════════════════════════════════════

ENHANCEMENTS = {
    "Modern GUI + UX": {
        "description": "Make it look modern — dark theme, hover effects, shortcuts.",
        "role": "UI/UX Modernization Specialist",
        "platform_context": "Modernize UI: dark theme, hover states, shortcuts, tooltips, responsive.",
        "extra_constraints": ["Preserve ALL existing functionality.", "Support display scaling.", "Separate theme code from logic."],
    },
    "Security + Compliance": {
        "description": "Fix security holes, prepare for app store rules.",
        "role": "Application Security and Compliance Specialist",
        "platform_context": "Security: sanitize input, encrypt data, no secrets, platform compliance, GDPR.",
        "extra_constraints": ["Create SECURITY_NOTES.md.", "Don't break existing features."],
    },
    "More Features + Robustness": {
        "description": "More features, fewer crashes, better errors.",
        "role": "Senior Engineer specializing in feature expansion and reliability",
        "platform_context": "Expand: validation, undo/redo, auto-save, logging, retry logic, progress bars.",
        "extra_constraints": ["No breaking changes.", "Error handling on everything."],
    },
    "Add Diagnostics": {
        "description": "Add a health-check report for troubleshooting.",
        "role": "Systems Reliability Engineer for diagnostics and logging",
        "platform_context": "Diagnostics: .txt report, OS/app/deps/errors/memory, rotating logs.",
        "extra_constraints": ["No secrets in reports."],
    },
    "Find Expansion Opportunities": {
        "description": "Analyze code for missed features and fork ideas.",
        "role": "Product Strategist for expansion analysis",
        "platform_context": "Analyze: missed features, fork paths, plugin points, quick wins.",
        "extra_constraints": ["Reference actual code.", "Concrete first steps."],
    },
}

# ═══════════════════════════════════════════════════════════════════
# CONVERSATION — style + tone options
# ═══════════════════════════════════════════════════════════════════

CONVERSATION_STYLES = {
    "General Chat": {"description": "Normal conversation — questions, brainstorming, advice.", "block": "You are a helpful, knowledgeable assistant. Be conversational and clear."},
    "Expert Consultation": {"description": "Talk to a specialist (doctor, engineer, etc.).", "block": "Act as a domain expert. Thorough, well-sourced analysis. Flag when to consult a real professional."},
    "Creative Writing": {"description": "Stories, poetry, scripts, worldbuilding.", "block": "You are a creative writing partner. Vivid language, original ideas, emotional resonance."},
    "Teaching / Explaining": {"description": "Step-by-step explanations like a patient teacher.", "block": "You are a patient teacher. Break topics into steps. Use analogies and examples."},
    "Debate / Devil's Advocate": {"description": "Challenge your ideas, stress-test thinking.", "block": "Act as a devil's advocate. Challenge assumptions. Present strongest counterarguments."},
    "Summarize / Analyze": {"description": "Summarize, extract key points, or analyze text.", "block": "Analyze thoroughly. Extract key themes. Be objective."},
}

CONVERSATION_TONES = {
    "Professional": "Use formal, professional language.",
    "Casual": "Be relaxed and conversational, like a knowledgeable friend.",
    "Academic": "Use precise, scholarly language with caveats.",
    "ELI5": "Extremely simple language. No jargon. Lots of analogies.",
}

# ═══════════════════════════════════════════════════════════════════
# IMAGE — style, lighting, camera options
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
    "Cinematic": "Cinematic still frame, dramatic lighting, film grain, anamorphic lens",
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
    "Aerial / Drone": "aerial drone photography, bird's eye view",
    "Fish-eye": "fish-eye lens, distorted perspective, 180-degree field of view",
}

# ═══════════════════════════════════════════════════════════════════
# VIDEO — style, camera move, pacing options
# ═══════════════════════════════════════════════════════════════════

VIDEO_STYLES = {
    "Cinematic": "Cinematic quality, 24fps film look, shallow depth of field, professional color grading",
    "Documentary": "Documentary style, handheld camera, natural lighting, observational",
    "Animation (2D)": "2D animation, smooth frame-by-frame, illustrated style",
    "Animation (3D)": "3D CGI animation, Pixar quality, realistic rendering",
    "Music Video": "Music video aesthetic, stylized editing, beat-synchronized cuts",
    "Commercial / Ad": "Polished commercial quality, product-focused, aspirational",
    "Social Media": "Short-form vertical video, fast-paced, eye-catching, trending style",
}

VIDEO_CAMERA_MOVES = {
    "Static / Tripod": "locked-off static shot, stable tripod",
    "Slow Pan": "slow smooth horizontal pan, revealing the scene gradually",
    "Tracking Shot": "camera tracking alongside subject, following action",
    "Dolly Zoom": "dolly zoom / vertigo effect, background scaling",
    "Drone / Aerial": "sweeping drone shot, rising aerial reveal",
    "Handheld": "handheld camera, slight shake, intimate feeling",
    "Timelapse": "timelapse, sped up passage of time",
}

VIDEO_PACING = {
    "Slow / Contemplative": "slow pacing, long takes, meditative, atmospheric",
    "Medium / Narrative": "medium pacing, story-driven, natural rhythm",
    "Fast / Energetic": "fast cuts, high energy, dynamic editing",
}

# ═══════════════════════════════════════════════════════════════════
# REASONING + OUTPUT + CONSTRAINTS
# ═══════════════════════════════════════════════════════════════════

REASONING_MODES = {
    "Standard CoT": {"description": "Step-by-step thinking.", "block": "REASONING: Think step by step. Show your reasoning."},
    "Structured CoT (SCoT)": {"description": "Pseudocode plan before coding.", "block": "REASONING: SCoT. Plan: 1.Sequential 2.Branches 3.Loops 4.Compose."},
    "Chain of Density": {"description": "Multiple drafts, packing more info each time.", "block": "REASONING: Chain of Density. Each iteration increases info density without increasing length."},
    "Tree of Thought": {"description": "Try 3 approaches, pick the best.", "block": "REASONING: ToT. 3 approaches, evaluate, pick best, implement."},
    "ReAct": {"description": "Think, do, observe, repeat.", "block": "REASONING: ReAct. THOUGHT -> ACTION -> OBSERVATION. Repeat until done."},
    "None": {"description": "Just answer directly.", "block": ""},
}

OUTPUT_FORMATS = {
    "Free-form": {"description": "AI picks the format.", "block": ""},
    "JSON": {"description": "Raw JSON data only.", "block": "OUTPUT: Strictly valid JSON. No markdown."},
    "Markdown": {"description": "Headers, bullets, code blocks.", "block": "OUTPUT: Well-structured Markdown."},
    "Code Only": {"description": "Just runnable code.", "block": "OUTPUT: Only executable code. No explanations."},
    "XML Tags": {"description": "Labeled <tags> for parsing.", "block": "OUTPUT: Semantic XML tags (<analysis>, <solution>, <code>)."},
}

CONSTRAINT_PRESETS = {
    "Python Best Practices": {"description": "PEP 8, hints, docstrings.", "rules": ["Follow PEP 8.", "Type hints.", "Docstrings."]},
    "Performance": {"description": "Fast, low memory.", "rules": ["Optimize complexity.", "Minimize memory."]},
    "Security": {"description": "Validate input, no secrets.", "rules": ["Sanitize inputs.", "No hardcoded secrets."]},
    "Conciseness": {"description": "No filler, no fluff.", "rules": ["No filler.", "No restating."]},
    "Robustness": {"description": "Handle errors gracefully.", "rules": ["Handle edge cases.", "Validate input.", "Meaningful errors."]},
}


# ═══════════════════════════════════════════════════════════════════
# GENERATION FUNCTIONS — Pure Python, no UI
# ═══════════════════════════════════════════════════════════════════

def gather_constraints(selected_presets: list[str], custom_text: str = "") -> list[str]:
    """Collect constraint rules from selected presets and custom text."""
    constraints = []
    for name in selected_presets:
        if name in CONSTRAINT_PRESETS:
            constraints.extend(CONSTRAINT_PRESETS[name]["rules"])
    if custom_text:
        for line in custom_text.splitlines():
            line = line.strip()
            if line:
                constraints.append(line)
    # Deduplicate while preserving order
    seen = set()
    return [c for c in constraints if c not in seen and not seen.add(c)]


def generate_code_prompt(
    task: str,
    role: str = "",
    build_target: str = "(none)",
    enhancements: list[str] | None = None,
    context: str = "",
    reasoning: str = "Structured CoT (SCoT)",
    output_format: str = "Free-form",
    constraint_presets: list[str] | None = None,
    custom_constraints: str = "",
) -> str:
    """Generate a code-focused prompt. Returns the final prompt string."""
    all_types = []
    if build_target != "(none)" and build_target in BUILD_TARGETS:
        all_types.append(BUILD_TARGETS[build_target])
    for name in (enhancements or []):
        if name in ENHANCEMENTS:
            all_types.append(ENHANCEMENTS[name])

    sections = []

    # Role
    if role:
        sections.append(f"# ROLE\nYou are: {role}.")
    elif all_types:
        sections.append(f"# ROLE\nYou are: {' AND '.join(t['role'] for t in all_types)}.")

    sections.append(f"# TASK\n{task}")

    for t in all_types:
        pc = t.get("platform_context", "")
        if pc:
            sections.append(f"# PLATFORM & ENVIRONMENT\n{pc}")

    if context:
        sections.append(f"# ADDITIONAL CONTEXT\n{context}")

    blk = REASONING_MODES.get(reasoning, {}).get("block", "")
    if blk:
        sections.append(f"# REASONING\n{blk}")

    fmt = OUTPUT_FORMATS.get(output_format, {}).get("block", "")
    if fmt:
        sections.append(f"# OUTPUT FORMAT\n{fmt}")

    cons = gather_constraints(constraint_presets or [], custom_constraints)
    for t in all_types:
        cons.extend(t.get("extra_constraints", []))
    seen = set()
    unique = [c for c in cons if c not in seen and not seen.add(c)]
    if unique:
        sections.append("# CONSTRAINTS\n" + "\n".join(f"- {c}" for c in unique))

    sections.append(
        "# QUALITY GATE\n"
        "Before finalizing, verify:\n"
        "1. All TASK requirements addressed.\n"
        "2. All CONSTRAINTS satisfied.\n"
        "3. Code runs without errors.\n"
        "4. Edge cases handled.\n"
        "5. No placeholder TODOs left."
    )
    return "\n\n".join(sections)


def generate_conversation_prompt(
    task: str,
    role: str = "",
    style: str = "General Chat",
    tone: str = "Casual",
    context: str = "",
    reasoning: str = "None",
    output_format: str = "Free-form",
    constraint_presets: list[str] | None = None,
    custom_constraints: str = "",
) -> str:
    """Generate a conversation-focused prompt."""
    style_data = CONVERSATION_STYLES.get(style, {})
    tone_desc = CONVERSATION_TONES.get(tone, "")

    sections = []
    if role:
        sections.append(f"# ROLE\n{role}")
    elif style_data.get("block"):
        sections.append(f"# ROLE\n{style_data['block']}")

    if tone_desc:
        sections.append(f"# TONE\n{tone_desc}")

    sections.append(f"# TASK\n{task}")

    if context:
        sections.append(f"# CONTEXT\n{context}")

    blk = REASONING_MODES.get(reasoning, {}).get("block", "")
    if blk:
        sections.append(f"# REASONING\n{blk}")

    fmt = OUTPUT_FORMATS.get(output_format, {}).get("block", "")
    if fmt:
        sections.append(f"# OUTPUT FORMAT\n{fmt}")

    cons = gather_constraints(constraint_presets or [], custom_constraints)
    if cons:
        sections.append("# CONSTRAINTS\n" + "\n".join(f"- {c}" for c in cons))

    return "\n\n".join(sections)


def generate_image_prompt(
    task: str,
    style: str = "Photorealistic",
    lighting: str = "Natural / Soft",
    camera: str = "Portrait (85mm)",
    context: str = "",
) -> str:
    """Generate an image generation prompt (DALL-E, Midjourney, SD, etc.)."""
    parts = [task]
    s = IMAGE_STYLES.get(style, "")
    if s:
        parts.append(s)
    l = IMAGE_LIGHTING.get(lighting, "")
    if l:
        parts.append(l)
    c = IMAGE_CAMERAS.get(camera, "")
    if c:
        parts.append(c)

    sections = [f"# IMAGE PROMPT\n{', '.join(parts)}"]
    if context:
        sections.append(f"# ADDITIONAL NOTES\n{context}")
    sections.append(
        "# NEGATIVE PROMPT\n"
        "blurry, low quality, distorted, deformed, ugly, watermark, text, logo, "
        "oversaturated, underexposed, cropped, out of frame, extra limbs, bad anatomy"
    )
    return "\n\n".join(sections)


def generate_video_prompt(
    task: str,
    style: str = "Cinematic",
    camera_move: str = "Slow Pan",
    pacing: str = "Medium / Narrative",
    context: str = "",
) -> str:
    """Generate a video generation prompt (Sora, Runway, Pika, etc.)."""
    parts = [task]
    s = VIDEO_STYLES.get(style, "")
    if s:
        parts.append(s)
    cm = VIDEO_CAMERA_MOVES.get(camera_move, "")
    if cm:
        parts.append(cm)
    p = VIDEO_PACING.get(pacing, "")
    if p:
        parts.append(p)

    sections = [f"# VIDEO PROMPT\n{', '.join(parts)}"]
    if context:
        sections.append(f"# ADDITIONAL NOTES\n{context}")
    sections.append(
        "# NEGATIVE\n"
        "static image, slideshow, watermark, blurry, jittery camera, "
        "low framerate, artifacts, morphing, unnatural motion"
    )
    return "\n\n".join(sections)


def build_results_review(original_task: str, final_prompt: str, category: str) -> str:
    """Build a human-readable analysis of the generated prompt."""
    prompt_tokens = len(final_prompt) // 4
    prompt_chars = len(final_prompt)
    task_tokens = max(len(original_task) // 4, 1)
    sections_count = final_prompt.count("\n# ") + (1 if final_prompt.startswith("# ") else 0)

    lines = [
        "=" * 50,
        "  PROMPT REVIEW",
        "=" * 50,
        "",
        f"  Tokens:     ~{prompt_tokens:,}",
        f"  Characters: {prompt_chars:,}",
        f"  Sections:   {sections_count}",
        "",
    ]

    if prompt_tokens < 500:
        lines.append("  Impact: LIGHT - fits any model.")
    elif prompt_tokens < 2000:
        lines.append("  Impact: MODERATE - good detail level.")
    elif prompt_tokens < 8000:
        lines.append("  Impact: LARGE - may crowd smaller models.")
    else:
        lines.append("  Impact: VERY LARGE - consider compressing.")

    ratio = prompt_tokens / task_tokens
    lines += [
        "",
        "  YOUR TEXT vs ENGINEERED PROMPT:",
        f"  Raw: ~{task_tokens:,} tokens",
        f"  Built: ~{prompt_tokens:,} tokens ({ratio:.1f}x)",
        "",
        "  WHAT THIS ADDS:",
    ]

    if category == "Code":
        for imp in ["Expert role", "Platform context", "Thinking framework", "Quality rules", "Self-check"]:
            lines.append(f"  + {imp}")
    elif category == "Conversation":
        lines += ["  + Conversation style", "  + Tone control"]
    elif category == "Image":
        lines += ["  + Technical descriptors", "  + Negative prompt"]
    elif category == "Video":
        lines += ["  + Motion descriptors", "  + Negative prompt"]

    lines.append("")
    if prompt_tokens > 500:
        lines += [
            "  COMPRESSION:",
            f"  Could reduce to ~{prompt_tokens // 2:,} tokens.",
            "  Pro: cheaper, faster, more room for response.",
            "  Con: less guidance, more generic output.",
        ]
    else:
        lines.append("  Already compact. No compression needed.")

    lines += ["", "  TIP: Copy only above this review.", "=" * 50]
    return "\n".join(lines)

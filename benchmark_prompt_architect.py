"""
benchmark_prompt_architect.py
=============================

Pressure test + hard data report for Prompt Architect v5.0.

Runs 6 scenarios, measures tokens/chars/words/effectiveness/cost, and
writes a reproducible report to benchmark_results.txt.

USAGE:
    python benchmark_prompt_architect.py

OUTPUT:
    - Console (pretty-printed)
    - benchmark_results.txt (saved alongside this script)
"""
from __future__ import annotations

import logging
import re
import sys
import tkinter as tk
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

# Claude Sonnet 4.5 pricing (as of late 2025): $3 / 1M input tokens
COST_PER_MILLION_INPUT_TOKENS_USD = 3.00
TOKENS_PER_CHAR = 0.25  # ~4 chars per token for English (standard heuristic)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BenchmarkResult:
    """Hard data for a single scenario."""
    name: str
    prompt_text: str
    score: int
    max_score: int
    grade: str
    section_count: int

    @property
    def tokens(self) -> int:
        return max(0, len(self.prompt_text) // 4)

    @property
    def chars(self) -> int:
        return len(self.prompt_text)

    @property
    def words(self) -> int:
        return len(self.prompt_text.split()) if self.prompt_text else 0

    @property
    def cost_per_call_usd(self) -> float:
        return (self.tokens / 1_000_000) * COST_PER_MILLION_INPUT_TOKENS_USD

    @property
    def score_pct(self) -> int:
        if self.max_score == 0:
            return 0
        return int(self.score / self.max_score * 100)


def _setup_app() -> tuple[tk.Tk, object]:
    """Create a Prompt Architect instance for programmatic use (no mainloop)."""
    # Import here to avoid polluting module-level state
    from prompt_architect import PromptArchitect
    root = tk.Tk()
    root.withdraw()  # Don't show the window during benchmarking
    app = PromptArchitect(root)
    return root, app


def _extract_review_parts(result_text: str) -> tuple[int, int, str, int]:
    """Parse the effectiveness review block to extract (score, max_score, grade, sections).

    Returns (0, 0, 'N/A', 0) if the review isn't found.
    """
    score_match = re.search(r"SCORE:\s*(\d+)\s*/\s*(\d+).*?Grade:\s*(\S+)", result_text)
    if not score_match:
        return 0, 0, "N/A", 0
    score = int(score_match.group(1))
    max_score = int(score_match.group(2))
    grade = score_match.group(3)

    sec_match = re.search(r"Sections:\s*(\d+)", result_text)
    sections = int(sec_match.group(1)) if sec_match else 0
    return score, max_score, grade, sections


def _get_pure_prompt(result_area_text: str) -> str:
    """Strip the effectiveness review from the result area, keeping just the prompt."""
    sep = "=" * 60
    if sep in result_area_text:
        return result_area_text[: result_area_text.index(sep)].strip()
    return result_area_text.strip()


def _reset_app(app: object) -> None:
    """Reset the app to a known starting state for a clean scenario."""
    app.task_input.delete("1.0", tk.END)
    app.context_input.delete("1.0", tk.END)
    app.custom_constraints.delete("1.0", tk.END)
    app.role_input.delete(0, tk.END)
    if hasattr(app, "workdir_var"):
        app.workdir_var.set("")
    if hasattr(app, "_low_token_var"):
        app._low_token_var.set(False)
    app.my_project_var.set("(None)")
    app.build_target_var.set("(none)")
    for var in app.enhancement_vars.values():
        var.set(False)
    for name, var in app.constraint_vars.items():
        var.set(False)
    app.prompt_category_var.set("Code")
    app._on_category_change()


def _run_scenario(
    app: object,
    name: str,
    task_text: str,
    *,
    project: str = "(None)",
    build_target: str = "(none)",
    enhancements: list[str] | None = None,
    constraints: list[str] | None = None,
    reasoning: str = "None",
    output_format: str = "Free-form",
    category: str = "Code",
    low_token: bool = False,
    workdir: str = "",
    conv_style: str = "General Chat",
    conv_tone: str = "Casual",
    image_style: str = "Photorealistic",
    image_lighting: str = "Natural / Soft",
    image_camera: str = "Portrait (85mm)",
) -> BenchmarkResult:
    """Configure the app for a scenario, generate, measure."""
    _reset_app(app)

    # Apply config
    app.task_input.insert("1.0", task_text)
    app.my_project_var.set(project)
    app.prompt_category_var.set(category)
    app._on_category_change()
    app.build_target_var.set(build_target)

    for enh in (enhancements or []):
        if enh in app.enhancement_vars:
            app.enhancement_vars[enh].set(True)
    for con in (constraints or []):
        if con in app.constraint_vars:
            app.constraint_vars[con].set(True)

    if category == "Conversation":
        app.conv_style_var.set(conv_style)
        app.conv_tone_var.set(conv_tone)
    elif category == "Image":
        app.image_style_var.set(image_style)
        app.image_lighting_var.set(image_lighting)
        app.image_camera_var.set(image_camera)

    app.reasoning_var.set(reasoning)
    app.output_format_var.set(output_format)
    if hasattr(app, "_low_token_var"):
        app._low_token_var.set(low_token)
    if workdir and hasattr(app, "workdir_var"):
        app.workdir_var.set(workdir)

    # Generate
    app.generate()
    full = app.result_area.get("1.0", tk.END)
    pure_prompt = _get_pure_prompt(full)
    score, max_score, grade, sections = _extract_review_parts(full)

    return BenchmarkResult(
        name=name,
        prompt_text=pure_prompt,
        score=score,
        max_score=max_score,
        grade=grade,
        section_count=sections,
    )


def _format_report(results: list[BenchmarkResult], discovered_count: int) -> str:
    """Format the final human-readable report."""
    lines: list[str] = []
    sep = "=" * 72
    lines.append(sep)
    lines.append("  PROMPT ARCHITECT v5.0 -- PRESSURE TEST RESULTS")
    lines.append(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"  Pricing assumption: ${COST_PER_MILLION_INPUT_TOKENS_USD}/M input tokens (Claude Sonnet)")
    lines.append(sep)
    lines.append("")

    # Per-scenario breakdown
    for r in results:
        lines.append(f"SCENARIO: {r.name}")
        lines.append(f"  Tokens (est.):  ~{r.tokens:,}")
        lines.append(f"  Characters:     {r.chars:,}")
        lines.append(f"  Words:          {r.words:,}")
        lines.append(f"  Sections:       {r.section_count}")
        lines.append(f"  Score:          {r.score}/{r.max_score} ({r.score_pct}%) -- Grade {r.grade}")
        lines.append(f"  Cost/call:      ${r.cost_per_call_usd:.5f}")
        lines.append("")

    # Pairwise analysis
    lines.append("-" * 72)
    lines.append("  COMPARATIVE ANALYSIS")
    lines.append("-" * 72)
    lines.append("")

    by_name = {r.name: r for r in results}

    # Baseline vs full Code
    s1 = by_name.get("1. Raw task, no enhancements")
    s2 = by_name.get("2. Full Code prompt (PC Desktop App + defaults)")
    if s1 and s2:
        tok_ratio = s2.tokens / max(s1.tokens, 1)
        pt_delta = s2.score_pct - s1.score_pct
        lines.append(f"Raw vs Engineered (Scenarios 1 -> 2):")
        lines.append(f"  Tokens:         {s1.tokens:,} -> {s2.tokens:,} ({tok_ratio:.1f}x)")
        lines.append(f"  Effectiveness:  {s1.score_pct}% -> {s2.score_pct}% (+{pt_delta} pts)")
        lines.append(f"  Verdict:        The engineered prompt is {pt_delta} points more effective"
                     f" at {tok_ratio:.1f}x the token cost. Well worth it for complex tasks.")
        lines.append("")

    # Low Token Mode impact
    s3 = by_name.get("3. Full + GBA ROM Hack project (full context)")
    s4 = by_name.get("4. Full + GBA ROM Hack + Low Token Mode")
    if s3 and s4:
        tok_saved = s3.tokens - s4.tokens
        tok_saved_pct = (tok_saved / max(s3.tokens, 1)) * 100
        cost_saved = s3.cost_per_call_usd - s4.cost_per_call_usd
        pt_loss = s3.score_pct - s4.score_pct
        lines.append(f"Low Token Mode impact (Scenarios 3 -> 4):")
        lines.append(f"  Tokens:         {s3.tokens:,} -> {s4.tokens:,} (-{tok_saved:,}, -{tok_saved_pct:.1f}%)")
        lines.append(f"  Effectiveness:  {s3.score_pct}% -> {s4.score_pct}% "
                     f"({'-' if pt_loss > 0 else '+'}{abs(pt_loss)} pts)")
        lines.append(f"  Cost savings:   ${cost_saved:.5f} per call")
        if tok_saved_pct >= 30 and pt_loss <= 10:
            verdict = "EXCELLENT tradeoff -- big savings, small quality loss"
        elif tok_saved_pct >= 15:
            verdict = "GOOD tradeoff -- worth using for iterative work"
        else:
            verdict = "MARGINAL -- low-token mode less impactful here"
        lines.append(f"  Verdict:        {verdict}")
        lines.append("")

    # Real-world projections
    lines.append("-" * 72)
    lines.append("  REAL-WORLD PROJECTIONS")
    lines.append("-" * 72)
    lines.append("")
    prompts_per_day = 50
    work_days = 22
    if s3 and s4:
        monthly_full = s3.cost_per_call_usd * prompts_per_day * work_days
        monthly_low = s4.cost_per_call_usd * prompts_per_day * work_days
        monthly_savings = monthly_full - monthly_low
        lines.append(f"At {prompts_per_day} prompts/day, {work_days} days/month:")
        lines.append(f"  Scenario 3 (full context):  ${monthly_full:.2f}/mo")
        lines.append(f"  Scenario 4 (low-token):     ${monthly_low:.2f}/mo")
        lines.append(f"  Savings:                     ${monthly_savings:.2f}/mo "
                     f"({(monthly_savings / max(monthly_full, 0.0001)) * 100:.1f}%)")
        lines.append("")

    # Time savings (typing-avoidance)
    # Each "convention block" auto-injected = roughly 30 seconds avoided
    if s2 and s3:
        convention_blocks = s3.section_count - s1.section_count if s1 else s3.section_count
        time_per_prompt_sec = convention_blocks * 30
        daily_sec = time_per_prompt_sec * prompts_per_day
        annual_hours = (daily_sec * 250) / 3600  # 250 work days/year
        lines.append(f"Time saved (typing-avoidance):")
        lines.append(f"  Convention blocks auto-injected: {convention_blocks} per prompt")
        lines.append(f"  Est. time saved per prompt:      ~{time_per_prompt_sec}s")
        lines.append(f"  Daily at {prompts_per_day} prompts/day:      ~{daily_sec / 60:.1f} min")
        lines.append(f"  Annual (250 work days):           ~{annual_hours:.0f} hours")
        lines.append("")

    # Personalization (auto-discovery)
    lines.append("-" * 72)
    lines.append("  PERSONALIZATION (auto-discovery)")
    lines.append("-" * 72)
    lines.append("")
    lines.append(f"  Projects auto-discovered:  {discovered_count}")
    lines.append(f"  Built-in projects:         6")
    lines.append(f"  Total available:           {discovered_count + 6}")
    if discovered_count >= 10:
        lines.append(f"  Verdict: Strong -- tool adapts to your actual workflow.")
    elif discovered_count >= 3:
        lines.append(f"  Verdict: Moderate -- picked up your real projects.")
    else:
        lines.append(f"  Verdict: Weak -- few projects found. Try rescanning a different folder.")
    lines.append("")

    # Final verdict
    lines.append("=" * 72)
    lines.append("  FINAL VERDICT")
    lines.append("=" * 72)
    lines.append("")

    # Scoring: does the tool earn its keep?
    verdict_items: list[tuple[bool, str]] = []
    if s1 and s2:
        verdict_items.append((
            s2.score_pct - s1.score_pct >= 30,
            f"Effectiveness gain > 30 pts? {s2.score_pct - s1.score_pct:>+3} pts",
        ))
    if s3 and s4:
        tok_saved_pct = ((s3.tokens - s4.tokens) / max(s3.tokens, 1)) * 100
        pt_loss = s3.score_pct - s4.score_pct
        verdict_items.append((
            tok_saved_pct >= 15 and pt_loss <= 10,
            f"Low-token saves >= 15% with <= 10pt loss? "
            f"{tok_saved_pct:.1f}% / {pt_loss} pt loss",
        ))
    verdict_items.append((
        discovered_count >= 10,
        f"Auto-discovery finds >= 10 projects? {discovered_count} found",
    ))

    passed = sum(1 for ok, _ in verdict_items if ok)
    total = len(verdict_items)
    for ok, desc in verdict_items:
        lines.append(f"  [{'PASS' if ok else 'FAIL'}]  {desc}")
    lines.append("")
    if passed == total:
        overall = "YES -- use this tool. All criteria met."
    elif passed >= total - 1:
        overall = "YES -- use this tool, with minor caveats."
    else:
        overall = "MARGINAL -- review which criteria failed and decide."
    lines.append(f"  Overall: {overall}")
    lines.append("")
    lines.append("=" * 72)

    return "\n".join(lines)


def main() -> int:
    """Run the full benchmark."""
    root, app = _setup_app()
    discovered = len(app._discovered_projects)

    print(f"Running 6 scenarios against Prompt Architect v5.0...")
    print(f"Discovered {discovered} projects from {app._scan_root}")
    print()

    results: list[BenchmarkResult] = []

    # Scenario 1: Raw task only (baseline)
    results.append(_run_scenario(
        app,
        name="1. Raw task, no enhancements",
        task_text="Build a CPU monitor.",
        category="Code",
    ))

    # Scenario 2: Full Code prompt with sensible defaults
    results.append(_run_scenario(
        app,
        name="2. Full Code prompt (PC Desktop App + defaults)",
        task_text=(
            "Build a Python desktop app that monitors CPU usage in real time, "
            "displays a live line chart of the last 60 seconds, logs all samples to "
            "a CSV file, and shows alerts when CPU exceeds 80 percent for more than 10 seconds."
        ),
        build_target="PC Desktop App",
        enhancements=["Modern GUI + UX", "Add Diagnostics"],
        constraints=["Python Best Practices", "Robustness", "Conciseness"],
        reasoning="Structured CoT (SCoT)",
        output_format="Code Only",
    ))

    # Scenario 3: Full + GBA project (large context_block)
    results.append(_run_scenario(
        app,
        name="3. Full + GBA ROM Hack project (full context)",
        task_text=(
            "Add a new function to the trainer healing system that makes trainer Pokemon "
            "restore status conditions when they heal, not just HP. It should read the trainer "
            "class flag to enable this only for Gym Leaders and Elite Four."
        ),
        project="GBA ROM Hack (pokeemerald C)",
        build_target="PC Desktop App",
        enhancements=["More Features + Robustness"],
        constraints=["Security", "Conciseness"],
        reasoning="Structured CoT (SCoT)",
        output_format="Code Only",
        workdir="C:/Users/computer/Desktop/AI/pokefirered",
    ))

    # Scenario 4: Same as 3, but Low Token Mode ON
    results.append(_run_scenario(
        app,
        name="4. Full + GBA ROM Hack + Low Token Mode",
        task_text=(
            "Add a new function to the trainer healing system that makes trainer Pokemon "
            "restore status conditions when they heal, not just HP. It should read the trainer "
            "class flag to enable this only for Gym Leaders and Elite Four."
        ),
        project="GBA ROM Hack (pokeemerald C)",
        build_target="PC Desktop App",
        enhancements=["More Features + Robustness"],
        constraints=["Security", "Conciseness"],
        reasoning="Structured CoT (SCoT)",
        output_format="Code Only",
        workdir="C:/Users/computer/Desktop/AI/pokefirered",
        low_token=True,
    ))

    # Scenario 5: Conversation category
    results.append(_run_scenario(
        app,
        name="5. Conversation prompt (Expert + Professional)",
        task_text=(
            "Explain the difference between input and output tokens for LLM pricing, "
            "when prompt caching kicks in, and what strategies reduce token usage."
        ),
        category="Conversation",
        conv_style="Expert Consultation",
        conv_tone="Professional",
        reasoning="Standard CoT",
        output_format="Markdown",
        constraints=["Conciseness"],
    ))

    # Scenario 6: Image category
    results.append(_run_scenario(
        app,
        name="6. Image prompt (Cinematic, all options)",
        task_text="A detective standing in a rain-soaked alley at night, trenchcoat, fedora.",
        category="Image",
        image_style="Cinematic",
        image_lighting="Dramatic",
        image_camera="Portrait (85mm)",
        constraints=["Conciseness"],
    ))

    # Format + write report
    report = _format_report(results, discovered)

    # Write to file
    out_path = Path(__file__).parent / "benchmark_results.txt"
    out_path.write_text(report, encoding="utf-8")
    print(report)
    print()
    print(f"Report saved to: {out_path}")

    # Clean shutdown
    try:
        root.destroy()
    except tk.TclError:
        pass

    return 0


if __name__ == "__main__":
    sys.exit(main())

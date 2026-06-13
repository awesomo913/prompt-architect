import importlib
import re
import sys
import types
import unittest


def _install_tkinter_stub() -> None:
    class Dummy:
        def __init__(self, *args, **kwargs):
            pass

    def _module(name: str) -> types.ModuleType:
        mod = types.ModuleType(name)
        mod.__getattr__ = lambda _attr: Dummy
        return mod

    tk = _module("tkinter")
    tk.Tk = Dummy
    tk.Widget = Dummy
    tk.Toplevel = Dummy
    tk.Event = Dummy
    tk.END = "end"
    tk.LEFT = "left"
    tk.SOLID = "solid"

    ttk = _module("tkinter.ttk")
    scrolledtext = _module("tkinter.scrolledtext")
    messagebox = _module("tkinter.messagebox")
    filedialog = _module("tkinter.filedialog")

    tk.ttk = ttk
    tk.scrolledtext = scrolledtext
    tk.messagebox = messagebox
    tk.filedialog = filedialog

    sys.modules["tkinter"] = tk
    sys.modules["tkinter.ttk"] = ttk
    sys.modules["tkinter.scrolledtext"] = scrolledtext
    sys.modules["tkinter.messagebox"] = messagebox
    sys.modules["tkinter.filedialog"] = filedialog


def _load_prompt_architect():
    try:
        return importlib.import_module("prompt_architect")
    except ModuleNotFoundError as exc:
        if exc.name != "tkinter":
            raise
        _install_tkinter_stub()
        sys.modules.pop("prompt_architect", None)
        return importlib.import_module("prompt_architect")


prompt_architect = _load_prompt_architect()
MAX_EFFECTIVENESS_SCORE = 104
SCORE_RE = re.compile(
    r"SCORE:\s*(\d+)\s*/\s*(\d+)\s*\((\d+)%\)\s*-- Grade:\s*(A\+|A|B\+|B|C|D|F)"
)


class DummyPromptArchitect:
    def __init__(self, update_chain=None):
        self._update_chain = update_chain or []

    def _recommend_model(self, _provider, _final_prompt):
        return {"name": "stub"}

    def _format_model_for_review(self, _rec):
        return "MODEL RECOMMENDATION (stub)"


def build_review(task: str, prompt: str, category: str = "Code", update_chain=None) -> str:
    app = DummyPromptArchitect(update_chain=update_chain)
    return prompt_architect.PromptArchitect._build_results_review(app, task, prompt, category)


def parse_effectiveness_score(review: str) -> tuple[int, int, int, str]:
    match = SCORE_RE.search(review)
    if not match:
        raise AssertionError(f"Could not find score line in review:\n{review}")
    score, max_score, pct = (int(match.group(1)), int(match.group(2)), int(match.group(3)))
    return score, max_score, pct, match.group(4)


class TestEffectivenessScoring(unittest.TestCase):
    def get_validated_score(self, review: str) -> tuple[int, int, int, str]:
        score, max_score, pct, grade = parse_effectiveness_score(review)
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, max_score)
        self.assertGreaterEqual(pct, 0)
        self.assertLessEqual(pct, 100)
        return score, max_score, pct, grade

    def assert_factor_points(self, points: int, factor_name: str, review: str) -> None:
        self.assertRegex(review, rf"\[\+\s*{points}\]\s+{re.escape(factor_name)}:")

    def test_strong_prompt_scores_full_marks(self):
        task = " ".join(["Design"] * 45)
        prompt = (
            "# ROLE\nSenior Python engineer\n"
            "# PLATFORM\nDesktop Python app\n"
            "# REASONING\nUse structured chain of thought\n"
            "# OUTPUT FORMAT\nMarkdown\n"
            "# CONSTRAINTS\n- Handle edge cases\n"
            "# PROJECT CONTEXT\nExisting repository conventions\n"
            "# QUALITY GATE\nVerify output quality\n"
            "Do NOT use global state\n"
            "# ADDITIONAL CONTEXT\nInput/output examples"
        )
        review = build_review(task, prompt, update_chain=[{"change": "v1"}])
        score, max_score, pct, grade = self.get_validated_score(review)

        self.assertEqual((score, max_score, pct, grade), (MAX_EFFECTIVENESS_SCORE, MAX_EFFECTIVENESS_SCORE, 100, "A+"))
        self.assert_factor_points(12, "Expert Role", review)
        self.assert_factor_points(10, "Task Clarity", review)
        self.assert_factor_points(8, "Specific Details", review)
        self.assert_factor_points(12, "Platform Context", review)
        self.assert_factor_points(8, "Thinking Framework", review)
        self.assert_factor_points(8, "Output Format", review)
        self.assert_factor_points(10, "Quality Rules", review)
        self.assert_factor_points(10, "Project Conventions", review)
        self.assert_factor_points(8, "Self-Check Gate", review)
        self.assert_factor_points(6, "Anti-Patterns", review)
        self.assert_factor_points(6, "Context / Examples", review)
        self.assert_factor_points(6, "Update Chain", review)

    def test_empty_inputs_score_zero(self):
        review = build_review("", "", "Code", update_chain=[])
        score, max_score, pct, grade = self.get_validated_score(review)

        self.assertEqual((score, max_score, pct, grade), (0, MAX_EFFECTIVENESS_SCORE, 0, "F"))
        self.assertIn("[ 0] Task Clarity", review)
        self.assertIn("[ 0] Specific Details", review)
        self.assertIn("[ 0] Update Chain", review)

    def test_midrange_prompt_combines_factors_correctly(self):
        task = " ".join(["Implement"] * 20)
        prompt = (
            "# ROLE\nBackend engineer\n"
            "# PLATFORM\nPython API service\n"
            "# CONSTRAINTS\n- Add tests\n"
            "Do NOT skip validation\n"
            "# CONTEXT\nLegacy integration details"
        )
        review = build_review(task, prompt, "Code", update_chain=[])
        score, max_score, pct, grade = self.get_validated_score(review)

        self.assertEqual((score, max_score, pct, grade), (56, MAX_EFFECTIVENESS_SCORE, 53, "C"))
        self.assert_factor_points(12, "Expert Role", review)
        self.assert_factor_points(10, "Task Clarity", review)
        self.assertIn("[ 0] Specific Details", review)
        self.assert_factor_points(12, "Platform Context", review)
        self.assertIn("[ 0] Output Format", review)
        self.assert_factor_points(10, "Quality Rules", review)
        self.assert_factor_points(6, "Anti-Patterns", review)
        self.assert_factor_points(6, "Context / Examples", review)
        self.assertIn("[ 0] Update Chain", review)

    def test_very_long_input_keeps_score_within_valid_range(self):
        very_long_task = " ".join(["requirements"] * 5000)
        review = build_review(very_long_task, "# ROLE\nSenior engineer", "Code", update_chain=[])
        score, max_score, pct, grade = self.get_validated_score(review)

        self.assertEqual((score, max_score, pct, grade), (30, MAX_EFFECTIVENESS_SCORE, 28, "F"))


if __name__ == "__main__":
    unittest.main()

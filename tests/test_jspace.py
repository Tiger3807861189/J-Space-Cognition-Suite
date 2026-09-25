"""Regression tests for the optional J-Space runtime controller."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parents[1]
CONTROLLER = ROOT / "j-space" / "scripts" / "jspace.py"
LEDGER_TEMPLATE = ROOT / "j-space" / "scripts" / "workspace-ledger.md"
CITATION = ROOT / "CITATION.cff"


class JSpaceControllerTests(unittest.TestCase):
    def test_advisory_ship_rejects_oversized_file_and_stdin_without_truncation(self):
        path = Path(self.workspace.name) / 'large.txt'
        limit = 8 * 1024 * 1024
        path.write_bytes(b'a' * (limit + 1))
        for result in (self.run_controller('ship', str(path)),
                       self.run_controller_bytes('ship', '-', stdin=b'a' * (limit + 1))):
            self.assertEqual(result.returncode, 2)
            output = result.stdout.decode('utf-8') if isinstance(result.stdout, bytes) else result.stdout
            self.assertIn('8 MiB advisory limit', output)

    def setUp(self):
        self.workspace = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.workspace.cleanup()

    @property
    def ledger(self):
        return Path(self.workspace.name) / ".jspace" / "WORKSPACE.md"

    @property
    def history(self):
        return Path(self.workspace.name) / ".jspace" / "history.json"

    def run_controller(self, *args, stdin=None):
        return subprocess.run(
            [sys.executable, str(CONTROLLER), *args],
            cwd=self.workspace.name,
            input=stdin,
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=False,
        )

    def run_controller_bytes(self, *args, stdin=None):
        return subprocess.run(
            [sys.executable, str(CONTROLLER), *args],
            cwd=self.workspace.name,
            input=stdin,
            capture_output=True,
            check=False,
        )

    def open_ledger(self, goal="Ship verified output", next_action="Inspect inputs"):
        result = self.run_controller(
            "note", "--goal", goal, "--next", next_action
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_documented_loop_lifecycle(self):
        self.open_ledger()
        for entry in (
            "constraints — preserve public behavior",
            "evidence — cover all affected files",
        ):
            result = self.run_controller("note", "--core", entry)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

        swap = self.run_controller(
            "note",
            "--core",
            "delivery — keep the outer register clean",
            "--core-slot",
            "1",
        )
        self.assertEqual(swap.returncode, 0, swap.stdout + swap.stderr)

        opened = self.run_controller(
            "note",
            "--open",
            "Does the parser preserve state?",
            "--settled-by",
            "controller tests over all ledger sections",
        )
        self.assertEqual(opened.returncode, 0, opened.stdout + opened.stderr)

        refused = self.run_controller("note", "--close", "1")
        self.assertEqual(refused.returncode, 2)
        self.assertIn("closes only against a recorded checkpoint", refused.stdout)

        closed = self.run_controller(
            "note",
            "--close",
            "1",
            "--check",
            "the parser preserves state",
            "--by",
            "unittest over all ledger sections and edge inputs",
            "--next",
            "Prepare delivery",
        )
        self.assertEqual(closed.returncode, 0, closed.stdout + closed.stderr)

        seam = self.run_controller("seam")
        self.assertEqual(seam.returncode, 0, seam.stdout + seam.stderr)
        self.assertIn("Goal:     Ship verified output", seam.stdout)
        self.assertIn("Next:     Prepare delivery", seam.stdout)

        resume = self.run_controller("resume")
        self.assertEqual(resume.returncode, 0, resume.stdout + resume.stderr)
        self.assertIn("The invariants:", resume.stdout)
        self.assertIn("[live] delivery", resume.stdout)

    def test_long_gap_prints_full_reentry(self):
        self.open_ledger()
        self.history.parent.mkdir(exist_ok=True)
        self.history.write_text(
            json.dumps(
                [
                    {
                        "t": int(time.time()) - 3601,
                        "next": "Inspect inputs",
                        "verified": 0,
                        "open": 0,
                    }
                ]
            ),
            encoding="utf-8",
        )

        result = self.run_controller("seam")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("long gap", result.stdout)
        self.assertIn("The invariants:", result.stdout)

    def test_copyable_ledger_template_starts_without_placeholder_state(self):
        source = LEDGER_TEMPLATE.read_text(encoding="utf-8")
        ledger = source.split("```markdown\n", 1)[1].split("\n```", 1)[0]
        self.ledger.parent.mkdir()
        self.ledger.write_text(ledger + "\n", encoding="utf-8")

        result = self.run_controller("resume")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Goal: (not set)", result.stdout)
        self.assertIn("Verified:\n  (none yet)", result.stdout)
        self.assertIn("Open:\n  (none)", result.stdout)
        self.assertIn("Next: (not set)", result.stdout)
        self.assertNotIn("One sentence", result.stdout)

    def test_scalar_values_round_trip_and_section_heading_is_refused(self):
        self.open_ledger(goal="- preserve leading punctuation")
        seam = self.run_controller("seam")
        self.assertEqual(seam.returncode, 0, seam.stdout + seam.stderr)
        self.assertIn("Goal:     - preserve leading punctuation", seam.stdout)

        refused = self.run_controller("note", "--goal", "## Verified")
        self.assertEqual(refused.returncode, 2)
        self.assertIn("must not begin with a ledger section heading", refused.stdout)

        unchanged = self.run_controller("seam")
        self.assertEqual(unchanged.returncode, 0, unchanged.stdout + unchanged.stderr)
        self.assertIn("Goal:     - preserve leading punctuation", unchanged.stdout)

    def test_unreadable_ledger_is_declined_without_traceback(self):
        self.ledger.parent.mkdir()
        self.ledger.write_bytes(b"\xff\xfe\x00\x80")

        result = self.run_controller("seam")
        self.assertEqual(result.returncode, 2)
        self.assertIn("ledger was unreadable", result.stdout)
        self.assertNotIn("Traceback", result.stderr)

    def test_history_recovery_and_register_inspection(self):
        self.open_ledger()
        self.history.write_text("{}", encoding="utf-8")
        seam = self.run_controller("seam")
        self.assertEqual(seam.returncode, 0, seam.stdout + seam.stderr)
        self.assertIn("invalid shape", seam.stderr)

        clean = self.run_controller("ship", "-", stdin="Verified all files by full scan.")
        self.assertEqual(clean.returncode, 0, clean.stdout + clean.stderr)
        self.assertIn("clean", clean.stdout)

        outgoing = Path(self.workspace.name) / "outgoing.txt"
        outgoing.write_text("I see meltdown ⇒ retry", encoding="utf-16")
        reported = self.run_controller("ship", os.fspath(outgoing))
        self.assertEqual(reported.returncode, 0, reported.stdout + reported.stderr)
        self.assertIn("Dense notation appears", reported.stdout)
        self.assertIn("state markers", reported.stdout)

        outgoing.write_bytes(b"\x81\x82\x83")
        declined = self.run_controller("ship", os.fspath(outgoing))
        self.assertEqual(declined.returncode, 2)
        self.assertIn("cannot decode safely", declined.stdout)

    def test_closed_open_identifier_is_not_reused(self):
        self.open_ledger()
        opened = self.run_controller(
            "note",
            "--open",
            "First question",
            "--settled-by",
            "test over all inputs",
        )
        self.assertEqual(opened.returncode, 0, opened.stdout + opened.stderr)

        closed = self.run_controller(
            "note",
            "--close",
            "1",
            "--check",
            "First question settled",
            "--by",
            "test over all inputs",
        )
        self.assertEqual(closed.returncode, 0, closed.stdout + closed.stderr)

        reopened = self.run_controller(
            "note",
            "--open",
            "Second question",
            "--settled-by",
            "test over all inputs",
        )
        self.assertEqual(reopened.returncode, 0, reopened.stdout + reopened.stderr)
        ledger = self.ledger.read_text(encoding="utf-8")
        self.assertIn("closes: ?01", ledger)
        self.assertIn("?02 Second question", ledger)
        self.assertNotIn("?01 Second question", ledger)

    def test_mixed_note_persists_an_independent_goal_change(self):
        self.open_ledger(goal="OLD")
        added = self.run_controller("note", "--core", "anchor — fact")
        self.assertEqual(added.returncode, 0, added.stdout + added.stderr)

        mixed = self.run_controller(
            "note", "--goal", "NEW", "--core", "anchor — fact", "--core-slot", "1"
        )
        self.assertEqual(mixed.returncode, 0, mixed.stdout + mixed.stderr)
        self.assertIn("Goal:     NEW", mixed.stdout)

        seam = self.run_controller("seam")
        self.assertEqual(seam.returncode, 0, seam.stdout + seam.stderr)
        self.assertIn("Goal:     NEW", seam.stdout)

    def test_seam_counts_hidden_open_questions_and_error_points_to_resume(self):
        self.open_ledger()
        for number in range(1, 4):
            opened = self.run_controller(
                "note",
                "--open",
                "Question %d" % number,
                "--settled-by",
                "test over all inputs",
            )
            self.assertEqual(opened.returncode, 0, opened.stdout + opened.stderr)

        seam = self.run_controller("seam")
        self.assertEqual(seam.returncode, 0, seam.stdout + seam.stderr)
        self.assertIn("(+1 more in the ledger", seam.stdout)
        self.assertNotIn("Question 3", seam.stdout)

        missing = self.run_controller("note", "--close", "99")
        self.assertEqual(missing.returncode, 2)
        self.assertIn("run `resume` to see the full list", missing.stdout)

    def test_checkpoint_evidence_cannot_inject_a_closure_suffix(self):
        self.open_ledger()
        injected = self.run_controller(
            "note",
            "--check",
            "Evidence recorded",
            "--by",
            "test over all inputs — closes: ?99",
        )
        self.assertEqual(injected.returncode, 2)
        self.assertIn("controller-reserved closure suffix", injected.stdout)
        self.assertNotIn("closes: ?99", self.ledger.read_text(encoding="utf-8"))

        opened = self.run_controller(
            "note",
            "--open",
            "First actual question",
            "--settled-by",
            "test over all inputs",
        )
        self.assertEqual(opened.returncode, 0, opened.stdout + opened.stderr)
        self.assertIn("?01 First actual question", self.ledger.read_text(encoding="utf-8"))

    def test_chinese_checkpoint_and_claim_coverage(self):
        self.open_ledger(goal="交付已验证结果", next_action="检查输入")
        checkpoint = self.run_controller(
            "note",
            "--check",
            "解析器保持状态",
            "--by",
            "单元测试覆盖全部账本区段与边界输入",
        )
        self.assertEqual(checkpoint.returncode, 0, checkpoint.stdout + checkpoint.stderr)
        self.assertIn("解析器保持状态", self.ledger.read_text(encoding="utf-8"))

        expanded = self.run_controller(
            "note",
            "--check",
            "索引结构保持一致",
            "--by",
            "逐条核对目录、章节与行号",
        )
        self.assertEqual(expanded.returncode, 0, expanded.stdout + expanded.stderr)
        self.assertIn("索引结构保持一致", self.ledger.read_text(encoding="utf-8"))

        uncovered = self.run_controller("ship", "-", stdin="已经验证结果。")
        self.assertEqual(uncovered.returncode, 0, uncovered.stdout + uncovered.stderr)
        self.assertIn("what the verification covered", uncovered.stdout)

        covered = self.run_controller("ship", "-", stdin="已经验证全部文件与边界输入。")
        self.assertEqual(covered.returncode, 0, covered.stdout + covered.stderr)
        self.assertIn("clean", covered.stdout)

    def test_checkpoint_requires_verifier_and_coverage(self):
        self.open_ledger()
        for evidence in (
            "all files and edge inputs",
            "覆盖全部文件与边界输入",
        ):
            coverage_only = self.run_controller(
                "note",
                "--check",
                "Result recorded",
                "--by",
                evidence,
            )
            self.assertEqual(
                coverage_only.returncode,
                2,
                coverage_only.stdout + coverage_only.stderr,
            )
            self.assertIn("coverage alone is not evidence", coverage_only.stdout)

        verifier_only = self.run_controller(
            "note",
            "--check",
            "Result recorded",
            "--by",
            "unit tests",
        )
        self.assertEqual(
            verifier_only.returncode,
            2,
            verifier_only.stdout + verifier_only.stderr,
        )
        self.assertIn("what the verification covered", verifier_only.stdout)
        self.assertNotIn("Result recorded", self.ledger.read_text(encoding="utf-8"))

        manual = self.run_controller(
            "note",
            "--check",
            "Manual inspection completed",
            "--by",
            "manual reading of all files and edge inputs",
        )
        self.assertEqual(manual.returncode, 0, manual.stdout + manual.stderr)

    def test_declines_echo_the_received_evidence_and_mark_examples(self):
        self.open_ledger()
        coverage_gap = self.run_controller(
            "note",
            "--check",
            "parser preserves state",
            "--by",
            "regression tests on the parser",
        )
        self.assertEqual(
            coverage_gap.returncode, 2, coverage_gap.stdout + coverage_gap.stderr
        )
        self.assertIn('received --by "regression tests on the parser"', coverage_gap.stdout)
        self.assertIn("example: --by", coverage_gap.stdout)

        verifier_gap = self.run_controller(
            "note",
            "--check",
            "helper is pure",
            "--by",
            "all inputs and both boundaries",
        )
        self.assertEqual(
            verifier_gap.returncode, 2, verifier_gap.stdout + verifier_gap.stderr
        )
        self.assertIn('received --by "all inputs and both boundaries"', verifier_gap.stdout)
        self.assertIn("example: --by", verifier_gap.stdout)

    def test_checkpoint_evidence_is_not_contaminated_across_invocations(self):
        """Distinct verifiers stay isolated across history, seams, and the close path."""
        self.open_ledger()
        a = self.run_controller(
            "note",
            "--check",
            "checkpoint A",
            "--by",
            "unit tests over all files and edge inputs",
        )
        self.assertEqual(a.returncode, 0, a.stdout + a.stderr)

        self.history.parent.mkdir(exist_ok=True)
        self.history.write_text(
            json.dumps(
                [
                    {
                        "t": int(time.time()) - 3600,
                        "next": "brute force, n ≤ 6, including empty and maximum",
                        "verified": 99,
                        "open": 99,
                    }
                ]
            ),
            encoding="utf-8",
        )

        b = self.run_controller(
            "note",
            "--check",
            "checkpoint B",
            "--by",
            "manual review of each changed section",
        )
        self.assertEqual(b.returncode, 0, b.stdout + b.stderr)

        seam = self.run_controller("seam")
        self.assertEqual(seam.returncode, 0, seam.stdout + seam.stderr)
        opened = self.run_controller(
            "note",
            "--open",
            "Is the ledger stable?",
            "--settled-by",
            "test over all inputs",
        )
        self.assertEqual(opened.returncode, 0, opened.stdout + opened.stderr)
        closed = self.run_controller(
            "note",
            "--close",
            "1",
            "--check",
            "ledger stable",
            "--by",
            "diff against the previous seam, every section",
        )
        self.assertEqual(closed.returncode, 0, closed.stdout + closed.stderr)

        ledger = self.ledger.read_text(encoding="utf-8")
        rows = {
            tag: next(line for line in ledger.splitlines() if tag in line)
            for tag in ("checkpoint A", "checkpoint B", "ledger stable")
        }
        self.assertIn("manual review of each changed section", rows["checkpoint B"])
        self.assertNotIn("unit tests over all files", rows["checkpoint B"])
        self.assertNotIn("brute force", rows["checkpoint B"])
        self.assertNotIn("brute force", rows["ledger stable"])
        self.assertNotIn("manual review", rows["ledger stable"])

    def test_hand_restated_unpadded_open_number_still_closes(self):
        self.ledger.parent.mkdir()
        self.ledger.write_text(
            "# J-Space Workspace Ledger\n\n## Goal\nShip verified output\n\n## Core\n\n"
            "## Verified\n\n## Open\n"
            "- ?9 Loose numbering from a hand restatement — settled by: test over all inputs\n"
            "\n## Next\nInspect inputs\n",
            encoding="utf-8",
        )
        closed = self.run_controller(
            "note",
            "--close",
            "9",
            "--check",
            "hand-restated ledger integrates",
            "--by",
            "diff against the previous seam, every section",
        )
        self.assertEqual(closed.returncode, 0, closed.stdout + closed.stderr)
        ledger = self.ledger.read_text(encoding="utf-8")
        self.assertNotIn("?9 Loose", ledger)
        self.assertIn("closes: ?09", ledger)

        reopened = self.run_controller(
            "note", "--open", "Next question", "--settled-by", "test over all inputs"
        )
        self.assertEqual(reopened.returncode, 0, reopened.stdout + reopened.stderr)
        self.assertIn("?10 Next question", self.ledger.read_text(encoding="utf-8"))

    def test_extra_goal_lines_in_a_hand_restated_ledger_warn(self):
        self.ledger.parent.mkdir()
        self.ledger.write_text(
            "# J-Space Workspace Ledger\n\n## Goal\nFirst goal line\nSecond goal line\n\n"
            "## Core\n\n## Verified\n\n## Open\n\n## Next\nInspect inputs\n",
            encoding="utf-8",
        )
        edited = self.run_controller("note", "--next", "Advance")
        self.assertEqual(edited.returncode, 0, edited.stdout + edited.stderr)
        self.assertIn("only the first was kept", edited.stderr)
        ledger = self.ledger.read_text(encoding="utf-8")
        self.assertIn("First goal line", ledger)
        self.assertNotIn("Second goal line", ledger)

    def test_utf8_bom_ledger_is_still_readable(self):
        self.ledger.parent.mkdir()
        self.ledger.write_text(
            "## Goal\nShip verified output\n\n## Core\n\n## Verified\n\n"
            "## Open\n\n## Next\nInspect inputs\n",
            encoding="utf-8-sig",
        )
        resumed = self.run_controller("resume")
        self.assertEqual(resumed.returncode, 0, resumed.stdout + resumed.stderr)
        self.assertIn("Goal: Ship verified output", resumed.stdout)

    def test_corrupt_history_warns_once_per_seam(self):
        self.open_ledger()
        self.history.write_text("[not json", encoding="utf-8")
        seam = self.run_controller("seam")
        self.assertEqual(seam.returncode, 0, seam.stdout + seam.stderr)
        self.assertEqual(seam.stderr.count("history was unreadable"), 1)

    def test_broken_output_pipe_exits_cleanly(self):
        self.open_ledger()
        rows = "\n".join(
            "- ✓%04d filler checkpoint — verified by: unit tests over all files and edge inputs" % n
            for n in range(4000)
        )
        self.ledger.write_text(
            "# J-Space Workspace Ledger\n\n## Goal\nShip verified output\n\n## Core\n\n"
            "## Verified\n%s\n\n## Open\n\n## Next\nInspect inputs\n" % rows,
            encoding="utf-8",
        )
        proc = subprocess.Popen(
            [sys.executable, str(CONTROLLER), "resume"],
            cwd=self.workspace.name,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        proc.stdout.close()
        stderr = proc.stderr.read()
        proc.stderr.close()
        proc.wait()
        self.assertNotIn(b"Traceback", stderr)
        self.assertEqual(proc.returncode, 0)

    def test_ship_skips_markdown_headings_but_checks_claim_lines(self):
        headings = self.run_controller(
            "ship",
            "-",
            stdin="# Verified\n  ### Confirmed\n",
        )
        self.assertEqual(headings.returncode, 0, headings.stdout + headings.stderr)
        self.assertIn("clean", headings.stdout)

        claim = self.run_controller(
            "ship",
            "-",
            stdin="## Verified\nResult verified by intuition.\n",
        )
        self.assertEqual(claim.returncode, 0, claim.stdout + claim.stderr)
        self.assertIn("line 2:", claim.stdout)
        self.assertNotIn("line 1:", claim.stdout)

    def test_ship_skips_inline_code_but_checks_surrounding_prose(self):
        documented = self.run_controller(
            "ship",
            "-",
            stdin=(
                "The `verified` flag is set after parsing.\n"
                "The token `A ⇒ B` is documented here.\n"
                "The ``A ` B ⇒ C`` token is also documented here.\n"
            ),
        )
        self.assertEqual(documented.returncode, 0, documented.stdout + documented.stderr)
        self.assertIn("clean", documented.stdout)

        multiline = self.run_controller(
            "ship",
            "-",
            stdin="The token `A\n⇒ B` is documented here.\n",
        )
        self.assertEqual(multiline.returncode, 0, multiline.stdout + multiline.stderr)
        self.assertIn("clean", multiline.stdout)

        escaped = self.run_controller(
            "ship",
            "-",
            stdin="The result was \\`verified\\`.\n",
        )
        self.assertEqual(escaped.returncode, 0, escaped.stdout + escaped.stderr)
        self.assertIn("line 1:", escaped.stdout)

        table_boundary = self.run_controller(
            "ship",
            "-",
            stdin=(
                "| A | B |\n"
                "|---|---|\n"
                "| value ` | open |\n"
                "| result verified by intuition. ` | closed |\n"
            ),
        )
        self.assertEqual(
            table_boundary.returncode,
            0,
            table_boundary.stdout + table_boundary.stderr,
        )
        self.assertIn("line 4:", table_boundary.stdout)

        fence_boundary = self.run_controller(
            "ship",
            "-",
            stdin="~~~text\n`\n~~~\nResult verified by intuition. `\n",
        )
        self.assertEqual(
            fence_boundary.returncode,
            0,
            fence_boundary.stdout + fence_boundary.stderr,
        )
        self.assertIn("line 4:", fence_boundary.stdout)

        claim = self.run_controller(
            "ship",
            "-",
            stdin="The `verified` flag is set after parsing.\nResult verified by intuition.\n",
        )
        self.assertEqual(claim.returncode, 0, claim.stdout + claim.stderr)
        self.assertIn("line 2:", claim.stdout)

    def test_ship_understands_soft_wrapped_coverage_and_structural_headings(self):
        for text in (
            "The result was verified.\nCoverage: all files and edge inputs.\n",
            "结果已经验证。\n覆盖：全部文件与边界输入。\n",
            "- The result was verified.\n  Coverage: all files and edge inputs.\n",
            "Verified\n--------\n",
            "| Verified | Result |\n|---|---|\n| Toolathlon-Verified | 77.7 |\n",
            "entry                         # aligned tree comment\n",
        ):
            checked = self.run_controller("ship", "-", stdin=text)
            self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)
            self.assertIn("clean", checked.stdout)

        separate = self.run_controller(
            "ship", "-", stdin="The result was verified.\n\nCoverage: all files.\n"
        )
        self.assertEqual(separate.returncode, 0, separate.stdout + separate.stderr)
        self.assertIn("line 1:", separate.stdout)

        next_item = self.run_controller(
            "ship", "-", stdin="- The result was verified.\n- Coverage: all files.\n"
        )
        self.assertEqual(next_item.returncode, 0, next_item.stdout + next_item.stderr)
        self.assertIn("line 1:", next_item.stdout)

        repeated = self.run_controller("ship", "-", stdin="..........................\n")
        self.assertEqual(repeated.returncode, 0, repeated.stdout + repeated.stderr)
        self.assertIn("character run of 20 or more", repeated.stdout)

    def test_ship_audits_markdown_table_bodies(self):
        uncovered = self.run_controller(
            "ship",
            "-",
            stdin="| Result | Status |\n|---|---|\n| parser | verified |\n",
        )
        self.assertEqual(uncovered.returncode, 0, uncovered.stdout + uncovered.stderr)
        self.assertIn("line 3:", uncovered.stdout)

        leaked = self.run_controller(
            "ship",
            "-",
            stdin="| Route | Trace |\n|---|---|\n| ordinary output | A ⇒ B |\n",
        )
        self.assertEqual(leaked.returncode, 0, leaked.stdout + leaked.stderr)
        self.assertIn("Dense notation appears", leaked.stdout)

        named_benchmark = self.run_controller(
            "ship",
            "-",
            stdin="| Benchmark | Score |\n|---|---|\n| SWE-bench Verified | 78.0 |\n",
        )
        self.assertEqual(
            named_benchmark.returncode,
            0,
            named_benchmark.stdout + named_benchmark.stderr,
        )
        self.assertIn("clean", named_benchmark.stdout)

    def test_ship_allows_sentence_opening_arrow_but_not_operator_arrow(self):
        ordinary = [
            "\u21d2 The decision was a per-table fact, not a global rule.\n",
            "2. \u27f9 **The persistence hypothesis is refuted.** It was not a one-off.\n",
            "The search finished. \u27f9 **The answer is not a larger weight.**\n",
            "The first run failed. \u21d2 The rerun used a fresh cache. \u21d2 It passed.\n",
            "\u21d2 \uadf8 \uacb0\uc815\uc740 \uc804\uc5ed \uaddc\uce59\uc774 \uc544\ub2c8\uc5c8\ub2e4.\n",
        ]
        for text in ordinary:
            result = self.run_controller("ship", "-", stdin=text)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertNotIn("Dense notation appears", result.stdout, text)

        dense = [
            "A \u21d2 B\n",
            "\u21d2 contradiction\n",
            "\u21d2 contradiction \u21d2 the capacity bound is too loose\n",
            "used[0] = FULL \u27f9 blocked?!\n",
            "The cache was cold.\n\u21d2 rebuild \u2234 slow\n",
            "Leg 0 is full\n\u21d2 the save is blocked.\n",
        ]
        for text in dense:
            result = self.run_controller("ship", "-", stdin=text)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("Dense notation appears", result.stdout, text)

    def test_ship_skips_fenced_code_but_checks_following_prose(self):
        fenced = self.run_controller(
            "ship",
            "-",
            stdin="```python\nverified = True\nroute = 'A ⇒ B'  # GRRR\n```\n",
        )
        self.assertEqual(fenced.returncode, 0, fenced.stdout + fenced.stderr)
        self.assertIn("clean", fenced.stdout)

        followed = self.run_controller(
            "ship",
            "-",
            stdin="```python\nverified = True\n```\nResult verified by intuition.\n",
        )
        self.assertEqual(followed.returncode, 0, followed.stdout + followed.stderr)
        self.assertIn("line 4:", followed.stdout)

    def test_ship_ignores_character_runs_inside_inline_code(self):
        clean = self.run_controller(
            "ship",
            "-",
            stdin="The token `........................` is documented here.\n",
        )
        self.assertEqual(clean.returncode, 0, clean.stdout + clean.stderr)
        self.assertIn("clean", clean.stdout)

        reported = self.run_controller(
            "ship", "-", stdin="A run like ........................ leaks.\n"
        )
        self.assertEqual(reported.returncode, 0, reported.stdout + reported.stderr)
        self.assertIn("character run of 20 or more", reported.stdout)

    def test_hyphenated_benchmark_label_is_not_an_uncovered_claim(self):
        checked = self.run_controller(
            "ship",
            "-",
            stdin="| Benchmark | Score |\n|---|---|\n| SWE-bench-Verified | 78.0 |\n",
        )
        self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)
        self.assertIn("clean", checked.stdout)

    def test_stdin_and_file_use_the_same_decoder(self):
        payload = "Résultat A ⇒ B ∴ terminé.\n".encode("utf-8")
        outgoing = Path(self.workspace.name) / "outgoing.txt"
        outgoing.write_bytes(payload)

        from_file = self.run_controller_bytes("ship", os.fspath(outgoing))
        from_stdin = self.run_controller_bytes("ship", "-", stdin=payload)
        self.assertEqual(from_file.returncode, 0, from_file.stderr.decode("utf-8"))
        self.assertEqual(from_stdin.returncode, 0, from_stdin.stderr.decode("utf-8"))
        self.assertEqual(from_stdin.stdout, from_file.stdout)
        self.assertEqual(from_stdin.stderr, from_file.stderr)

    def test_integrity_checker_rejects_controller_anchor_drift(self):
        copied_skill = Path(self.workspace.name) / "j-space"
        shutil.copytree(ROOT / "j-space", copied_skill)
        copied_controller = copied_skill / "scripts" / "jspace.py"
        text = copied_controller.read_text(encoding="utf-8")
        text = text.replace(
            "Everything fluent and automatic runs below it",
            "Fluent processing runs below it",
            1,
        )
        text = text.replace("its bound action never happened", "its move never happened", 1)
        copied_controller.write_text(text, encoding="utf-8")

        checked = subprocess.run(
            [sys.executable, str(copied_skill / "scripts" / "verify_suite.py")],
            cwd=self.workspace.name,
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=False,
        )
        self.assertEqual(checked.returncode, 1, checked.stdout + checked.stderr)
        self.assertIn("PREMISE differs from SKILL.md", checked.stdout)
        self.assertIn("INVARIANTS differ from SKILL.md", checked.stdout)

    def test_integrity_checker_requires_nonempty_unique_frontmatter_fields(self):
        for label, transform, expected in (
            (
                "missing",
                lambda text: text.replace("description:", "detail:", 1),
                "description must appear exactly once",
            ),
            (
                "empty",
                lambda text: text.replace(
                    text.splitlines()[2], "description:", 1
                ),
                "description must not be empty",
            ),
            (
                "duplicate",
                lambda text: text.replace("name: j-space", "name: j-space\nname: duplicate", 1),
                "name must appear exactly once",
            ),
        ):
            with self.subTest(label=label):
                copied_skill = Path(self.workspace.name) / ("j-space-" + label)
                shutil.copytree(ROOT / "j-space", copied_skill)
                entry = copied_skill / "SKILL.md"
                entry.write_text(transform(entry.read_text(encoding="utf-8")), encoding="utf-8")
                checked = subprocess.run(
                    [sys.executable, str(copied_skill / "scripts" / "verify_suite.py")],
                    cwd=self.workspace.name,
                    text=True,
                    encoding="utf-8",
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(checked.returncode, 1, checked.stdout + checked.stderr)
                self.assertIn(expected, checked.stdout)

    def test_integrity_checker_requires_exact_entry_routes(self):
        copied_skill = Path(self.workspace.name) / "j-space-routes"
        shutil.copytree(ROOT / "j-space", copied_skill)
        entry = copied_skill / "SKILL.md"
        text = entry.read_text(encoding="utf-8")
        text = text.replace("modules/introspection.md", "missing/introspection.md")
        entry.write_text(text, encoding="utf-8")

        checked = subprocess.run(
            [sys.executable, str(copied_skill / "scripts" / "verify_suite.py")],
            cwd=self.workspace.name,
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=False,
        )
        self.assertEqual(checked.returncode, 1, checked.stdout + checked.stderr)
        self.assertIn("modules{}introspection.md: not routed".format(os.sep), checked.stdout)

    def test_integrity_checker_requires_exact_reference_routes(self):
        copied_skill = Path(self.workspace.name) / "j-space-reference-routes"
        shutil.copytree(ROOT / "j-space", copied_skill)
        entry = copied_skill / "SKILL.md"
        text = entry.read_text(encoding="utf-8")
        text = text.replace("references/problem-model.md", "references/missing-model.md")
        entry.write_text(text, encoding="utf-8")

        checked = subprocess.run(
            [sys.executable, str(copied_skill / "scripts" / "verify_suite.py")],
            cwd=self.workspace.name,
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=False,
        )
        self.assertEqual(checked.returncode, 1, checked.stdout + checked.stderr)
        self.assertIn(
            "references{}problem-model.md: not reachable".format(os.sep),
            checked.stdout,
        )

    def test_citation_metadata_does_not_claim_an_unpublished_release(self):
        citation = CITATION.read_text(encoding="utf-8")
        self.assertNotIn("link to be added", citation)
        self.assertRegex(citation, r'(?m)^version:\s*["\']?SV1["\']?\s*$')
        self.assertIn("10.5281/zenodo.21971181", citation)
        self.assertNotRegex(citation, r"(?m)^doi:")
        self.assertNotRegex(citation, r"(?m)^date-released:")


if __name__ == "__main__":
    unittest.main()

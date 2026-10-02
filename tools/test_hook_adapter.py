"""Tests for hook_adapter — each platform's real payload shape, run through the real
board_lint.py, so a gate that silently fails open on a platform shows up here.

Run from the repo root:
    PYTHONPATH=tools python3 -m unittest test_hook_adapter -v
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ADAPTER = TOOLS / "hook_adapter.py"
BOARD_LINT = f"{sys.executable} {TOOLS / 'board_lint.py'}"
ECHO = f"{sys.executable} -c \"import sys,os;print(os.getcwd());print(sys.stdin.read())\""

DONE_NO_EVIDENCE = "- [ ] T7 [senior-dev] Build  prio:P1  status:done"
DONE_WITH_EVIDENCE = "- [ ] T7 [senior-dev] Build  prio:P1  status:done  evidence:logs/tester.md#T7"


def codex_patch(rel: str, *added: str, kind: str = "Update") -> str:
    body = "\n".join(f"+{a}" for a in added)
    return f"*** Begin Patch\n*** {kind} File: {rel}\n@@\n-old line\n{body}\n*** End Patch\n"


class _Project(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name).resolve()
        (self.root / ".claude/logs").mkdir(parents=True)
        (self.root / ".claude/task-board.md").write_text("# board\n")
        (self.root / ".claude/logs/tester.md").write_text("- [T7] PASS\n")
        (self.root / "src/deep").mkdir(parents=True)

    def tearDown(self):
        self._tmp.cleanup()

    def run_adapter(self, platform, event, payload, command=BOARD_LINT, cwd=None):
        return subprocess.run(
            [sys.executable, str(ADAPTER), platform, event, "--", command],
            input=json.dumps(payload), capture_output=True, text=True,
            cwd=cwd or self.root / "src/deep")


class Codex(_Project):
    def payload(self, tool_name, command):
        return {"hook_event_name": "PreToolUse", "cwd": str(self.root / "src/deep"),
                "tool_name": tool_name, "tool_input": {"command": command}}

    def test_patch_marking_done_without_evidence_is_blocked(self):
        patch = codex_patch("../../.claude/task-board.md", DONE_NO_EVIDENCE)
        r = self.run_adapter("codex", "PreToolUse", self.payload("apply_patch", patch))
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("board-lint: BLOCKED", r.stderr)

    def test_patch_with_resolving_evidence_passes(self):
        patch = codex_patch("../../.claude/task-board.md", DONE_WITH_EVIDENCE)
        r = self.run_adapter("codex", "PreToolUse", self.payload("apply_patch", patch))
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_any_bad_file_in_a_multi_file_patch_blocks(self):
        patch = (codex_patch("a.py", "x = 1").replace("*** End Patch\n", "")
                 + "*** Add File: " + str(self.root / ".claude/task-board.md") + "\n"
                 + f"+{DONE_NO_EVIDENCE}\n*** End Patch\n")
        r = self.run_adapter("codex", "PreToolUse", self.payload("apply_patch", patch))
        self.assertEqual(r.returncode, 2, r.stderr)

    def test_bash_write_to_board_is_blocked(self):
        r = self.run_adapter("codex", "PreToolUse",
                             self.payload("Bash", "echo x >> .claude/task-board.md"))
        self.assertEqual(r.returncode, 2)

    def test_unrelated_edit_passes(self):
        r = self.run_adapter("codex", "PreToolUse",
                             self.payload("apply_patch", codex_patch("a.py", "x = 1")))
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_script_runs_at_project_root_with_absolute_paths(self):
        r = self.run_adapter("codex", "PostToolUse",
                             self.payload("apply_patch", codex_patch("a.py", "x = 1")), ECHO)
        cwd, seen = r.stdout.split("\n", 1)
        self.assertEqual(Path(cwd).resolve(), self.root)
        seen = json.loads(seen)
        self.assertEqual(seen["tool_name"], "Edit")
        self.assertEqual(seen["tool_input"]["file_path"], str(self.root / "src/deep/a.py"))


class Antigravity(_Project):
    def payload(self, name, **args):
        return {"workspacePaths": [str(self.root)], "toolCall": {"name": name, "args": args}}

    def test_write_marking_done_without_evidence_denied_as_json(self):
        r = self.run_adapter("antigravity", "PreToolUse", self.payload(
            "write_to_file", TargetFile=str(self.root / ".claude/task-board.md"),
            CodeContent=DONE_NO_EVIDENCE + "\n", Overwrite=True))
        self.assertEqual(r.returncode, 0)
        out = json.loads(r.stdout)
        self.assertEqual(out["decision"], "deny")
        self.assertIn("evidence", out["reason"])

    def test_replace_and_multi_replace_are_checked(self):
        board = str(self.root / ".claude/task-board.md")
        for name, args in (
                ("replace_file_content", {"TargetFile": board, "TargetContent": "x",
                                          "ReplacementContent": DONE_NO_EVIDENCE}),
                ("multi_replace_file_content", {"TargetFile": board, "ReplacementChunks": [
                    {"TargetContent": "x", "ReplacementContent": DONE_NO_EVIDENCE}]})):
            r = self.run_adapter("antigravity", "PreToolUse", self.payload(name, **args))
            self.assertEqual(json.loads(r.stdout)["decision"], "deny", name)

    def test_allowed_call_prints_nothing(self):
        r = self.run_adapter("antigravity", "PreToolUse", self.payload(
            "run_command", CommandLine="cat .claude/task-board.md", Cwd=str(self.root)))
        self.assertEqual((r.returncode, r.stdout), (0, ""))


class OpenCode(_Project):
    def payload(self, tool, **args):
        return {"tool": tool, "args": args, "directory": str(self.root)}

    def test_edit_marking_done_without_evidence_exits_2(self):
        r = self.run_adapter("opencode", "PreToolUse", self.payload(
            "edit", filePath=str(self.root / ".claude/task-board.md"),
            oldString="x", newString=DONE_NO_EVIDENCE))
        self.assertEqual(r.returncode, 2)
        self.assertIn("BLOCKED", r.stderr)

    def test_write_with_evidence_passes(self):
        r = self.run_adapter("opencode", "PreToolUse", self.payload(
            "write", filePath=str(self.root / ".claude/task-board.md"),
            content=DONE_WITH_EVIDENCE + "\n"))
        self.assertEqual(r.returncode, 0, r.stderr)


class Robustness(_Project):
    def test_unknown_tools_and_garbage_pass_through_without_running_the_script(self):
        for payload in ({"tool_name": "WebFetch", "tool_input": {}}, {"toolCall": None}, []):
            r = self.run_adapter("codex", "PreToolUse", payload, ECHO)
            self.assertEqual((r.returncode, r.stdout), (0, ""), payload)

    def test_session_events_run_at_project_root(self):
        r = self.run_adapter("codex", "SessionStart",
                             {"hook_event_name": "SessionStart",
                              "cwd": str(self.root / "src/deep")}, ECHO)
        self.assertEqual(Path(r.stdout.split("\n", 1)[0]).resolve(), self.root)

    def test_post_tool_failures_never_block(self):
        r = self.run_adapter("antigravity", "PostToolUse", {
            "workspacePaths": [str(self.root)], "toolCall": {"name": "write_to_file", "args": {
                "TargetFile": str(self.root / "a.py"), "CodeContent": "x"}}},
            f"{sys.executable} -c \"import sys;sys.exit(2)\"")
        self.assertEqual((r.returncode, r.stdout), (0, ""))


if __name__ == "__main__":
    unittest.main()

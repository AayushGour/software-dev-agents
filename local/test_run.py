"""Unit tests for the local dispatcher. Run from repo root:
    python3 -m unittest local.test_run -v
"""
import tempfile
import unittest
from pathlib import Path

from installer import source
from local import run

BOARD = """\
Format:
`- [ ] T<id> [owner] <title>  prio:<P0|P1|P2|P3>  status:<todo|wip|review|test|done|blocked>  deps:<ids|->`

- [x] T0 [business-analyst] Requirements → project-context.md  prio:P1  status:done  evidence:project-context.md
- [ ] T1 [architect] Design + task split  prio:P1  status:wip
- [ ] T1a [ux-designer] Flows → design.md  prio:P2  status:todo  deps:T1
- [ ] T2 [senior-dev] Build /auth  prio:P1  status:todo  deps:T0
- [ ] T3 [junior-dev] Login form  prio:P2  status:review  deps:-
"""


class ParseTasks(unittest.TestCase):
    def setUp(self):
        self.tasks = {t["id"]: t for t in run.parse_tasks(BOARD)}

    def test_format_line_skipped(self):
        self.assertNotIn("<id>", self.tasks)

    def test_fields(self):
        t = self.tasks["2"]
        self.assertEqual((t["owner"], t["title"], t["status"], t["deps"]),
                         ("senior-dev", "Build /auth", "todo", ["T0"]))

    def test_alnum_ids_and_no_deps(self):
        self.assertEqual(self.tasks["1a"]["deps"], ["T1"])
        self.assertEqual(self.tasks["1"]["deps"], [])
        self.assertEqual(self.tasks["3"]["deps"], [])

    def test_canonical_template_parses(self):
        tasks = run.parse_tasks((source.DOTCLAUDE / "task-board.md").read_text())
        self.assertGreaterEqual(len(tasks), 5)


class NextTask(unittest.TestCase):
    def test_skips_unmet_deps_and_routes_review_to_reviewer(self):
        tasks = run.parse_tasks(BOARD)
        task, agent = run.next_task(tasks)
        self.assertEqual((task["id"], agent), ("2", "senior-dev"))
        tasks = [t for t in tasks if t["id"] != "2"]
        task, agent = run.next_task(tasks)
        self.assertEqual((task["id"], agent), ("3", "reviewer"))


class Prompts(unittest.TestCase):
    def test_agent_prompt_is_canonical_body(self):
        prompt = run.load_agent_prompt("senior-dev")
        self.assertEqual(prompt, source.load_agent("senior-dev").body)
        self.assertFalse(prompt.startswith("---"))

    def test_system_prompt_has_body_rulebook_and_runtime_notes(self):
        system = run.system_prompt("tester")
        self.assertIn(source.load_agent("tester").body, system)
        self.assertIn(source.RULEBOOK.read_text(), system)
        self.assertIn(run.RUNTIME_NOTES.read_text(), system)

    def test_context_read_from_dotclaude(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / ".claude").mkdir()
            (Path(d) / ".claude/task-board.md").write_text("BOARD")
            self.assertIn("BOARD", run.build_context(Path(d)))


if __name__ == "__main__":
    unittest.main()

"""Tests for the multi-platform installer. Run from repo root:
    python3 -m unittest discover -s installer/tests -t . -v
"""
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from installer import blocks, cli, links, source
from installer.manifest import REL as MANIFEST
from installer.platforms import AVAILABLE

SKILL = "tdd"
ANTIGRAVITY_RULE_LIMIT = 24_000  # bytes per rules file; scope doc [AG1]


class _Tmp(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.target = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def install(self, platforms="claude", *extra, tty=False, stdin=None):
        argv = [str(self.target), "--platforms", platforms, "--yes", *extra]
        with mock.patch.object(cli, "_interactive", return_value=tty), \
             mock.patch("builtins.input", side_effect=stdin or []), \
             redirect_stdout(io.StringIO()) as out:
            code = cli.main(argv)
        self.out = out.getvalue()
        return code

    def read(self, rel):
        return (self.target / rel).read_text()

    def manifest(self):
        return json.loads(self.read(MANIFEST.as_posix()))


class Source(unittest.TestCase):
    def test_agents_loaded_with_frontmatter_split_from_body(self):
        sd = source.load_agent("senior-dev")
        self.assertTrue(sd.description)
        self.assertIn("Read", sd.tools)
        self.assertFalse(sd.body.startswith("---"))

    def test_agent_names_unique(self):
        names = [a.name for a in source.load_agents()]
        self.assertEqual(len(names), len(set(names)))

    def test_layout_is_the_installed_layout(self):
        self.assertEqual(source.CLAUDE_STUB.read_text().strip(), "@../AGENTS.md")
        self.assertIn(SKILL, source.skill_names())
        self.assertFalse((source.DOTCLAUDE / "skills").exists())

    def test_rulebook_fits_antigravity_limit_once_wrapped(self):
        size = len(blocks.render(source.RULEBOOK.read_text()).encode())
        self.assertLess(size, ANTIGRAVITY_RULE_LIMIT)

    def test_no_stale_paths_in_canonical_text(self):
        for p in [source.RULEBOOK, *source.AGENTS_DIR.rglob("*.md")]:
            text = p.read_text()
            self.assertNotIn("Read CLAUDE.md", text, p)
            self.assertNotRegex(text, r"(?<!~/)\.claude/skills/", p)

    def test_mcp_servers_have_absolute_tool_paths(self):
        for srv in source.mcp_servers().values():
            for arg in srv.get("args", []):
                self.assertNotIn("../tools/", str(arg))


class Blocks(unittest.TestCase):
    def test_roundtrip_keeps_user_text(self):
        text = blocks.append("mine\n", "rules v1")
        text = blocks.replace(text, "rules v2")
        self.assertIn("mine", text)
        self.assertIn("rules v2", text)
        self.assertNotIn("rules v1", text)
        self.assertEqual(blocks.strip(text), "mine\n")


class SharedAndClaude(_Tmp):
    def test_fresh_install(self):
        self.assertEqual(self.install(), 0)
        self.assertIn(source.RULEBOOK.read_text().strip(), self.read("AGENTS.md"))
        self.assertIn("@../AGENTS.md", self.read(".claude/CLAUDE.md"))
        self.assertTrue(blocks.has_block(self.read(".claude/CLAUDE.md")))
        # root CLAUDE.md is left free: Copilot reads it AND AGENTS.md, which doubled the rulebook
        self.assertFalse((self.target / "CLAUDE.md").exists())
        for src, rel in source.skill_files():
            self.assertEqual((self.target / ".agents/skills" / rel).read_bytes(), src.read_bytes())
        link = self.target / ".claude/skills" / SKILL
        self.assertTrue(links.points_to(link, self.target / ".agents/skills" / SKILL))
        self.assertTrue((link / "SKILL.md").exists())
        self.assertIn(f"/{SKILL}\n", self.read(".claude/skills/.gitignore"))
        self.assertNotIn("../tools/", self.read(".claude/settings.json"))
        self.assertEqual(json.loads(self.read(".mcp.json"))["mcpServers"], source.mcp_servers())
        self.assertEqual(self.manifest()["platforms"], ["claude"])

    def test_without_claude_no_claude_files(self):
        self.install("cursor,copilot")
        self.assertFalse((self.target / ".claude/CLAUDE.md").exists())
        self.assertFalse((self.target / ".claude/skills").exists())
        self.assertTrue((self.target / "AGENTS.md").exists())
        self.assertTrue((self.target / ".claude/agents/senior-dev.md").exists())

    def test_rerun_without_force_skips_and_keeps_edits(self):
        self.install()
        (self.target / ".claude/agents/tester.md").write_text("mine")
        self.install()
        self.assertEqual(self.read(".claude/agents/tester.md"), "mine")
        self.assertIn("skip (exists)", self.out)

    def test_force_refreshes_framework_keeps_working_docs_and_user_text(self):
        self.install()
        (self.target / ".claude/task-board.md").write_text("my board")
        agents_md = self.target / "AGENTS.md"
        agents_md.write_text("my notes\n" + agents_md.read_text().replace("Two modes", "X"))
        self.install("claude", "--force")
        self.assertEqual(self.read(".claude/task-board.md"), "my board")
        self.assertTrue(self.read("AGENTS.md").startswith("my notes\n"))
        self.assertIn("Two modes", self.read("AGENTS.md"))

    def test_users_own_agents_md_gets_block_appended_by_default(self):
        (self.target / "AGENTS.md").write_text("# my project rules\n")
        self.install()
        text = self.read("AGENTS.md")
        self.assertTrue(text.startswith("# my project rules\n"))
        self.assertTrue(blocks.has_block(text))

    def test_declining_the_append_keeps_users_file_untouched(self):
        (self.target / "AGENTS.md").write_text("# mine\n")
        self.install("claude", tty=True, stdin=["n", "n"])  # --force? no · append to AGENTS.md? no
        self.assertEqual(self.read("AGENTS.md"), "# mine\n")

    def test_users_own_root_claude_md_never_touched(self):
        (self.target / "CLAUDE.md").write_text("my rules\n")
        self.install("claude", "--force")
        self.assertEqual(self.read("CLAUDE.md"), "my rules\n")
        self.install("cursor")
        self.assertEqual(self.read("CLAUDE.md"), "my rules\n")

    def test_users_own_skill_dir_left_alone(self):
        own = self.target / ".claude/skills/my-skill"
        own.mkdir(parents=True)
        (own / "SKILL.md").write_text("mine")
        self.install("claude", "--force")
        self.assertEqual((own / "SKILL.md").read_text(), "mine")
        self.assertFalse(links.is_link(own))
        self.assertNotIn("/my-skill", self.read(".claude/skills/.gitignore"))


class LegacyMigration(_Tmp):
    def make_old_install(self):
        (self.target / "CLAUDE.md").write_text(source.LEGACY_CLAUDE_MD_MARKER + " -->\nold rules\n")
        old = self.target / ".claude/skills" / SKILL
        old.mkdir(parents=True)
        (old / "SKILL.md").write_text("old shipped text")
        (old / "my-extra.md").write_text("user added")

    def test_force_migrates_rulebook_and_skills(self):
        self.make_old_install()
        self.install("claude", "--force")
        self.assertFalse((self.target / "CLAUDE.md").exists())  # was entirely the harness's
        self.assertIn("@../AGENTS.md", self.read(".claude/CLAUDE.md"))
        self.assertIn(source.RULEBOOK.read_text().strip(), self.read("AGENTS.md"))
        self.assertTrue(links.is_link(self.target / ".claude/skills" / SKILL))
        moved = self.target / ".agents/skills" / SKILL
        self.assertEqual((moved / "my-extra.md").read_text(), "user added")
        self.assertEqual((moved / "SKILL.md").read_bytes(),
                         (source.SKILLS_DIR / SKILL / "SKILL.md").read_bytes())

    def test_without_force_old_install_is_untouched(self):
        self.make_old_install()
        self.install()
        self.assertIn("old rules", self.read("CLAUDE.md"))
        self.assertFalse(links.is_link(self.target / ".claude/skills" / SKILL))
        self.assertEqual(self.read(f".claude/skills/{SKILL}/SKILL.md"), "old shipped text")


class Deselect(_Tmp):
    def test_dropping_claude_removes_only_its_generated_items(self):
        self.install("claude,cursor")
        self.install("cursor")
        self.assertFalse((self.target / ".claude/CLAUDE.md").exists())
        self.assertFalse((self.target / ".claude/skills" / SKILL).exists())
        self.assertTrue((self.target / ".agents/skills" / SKILL / "SKILL.md").exists())
        self.assertTrue((self.target / "AGENTS.md").exists())
        self.assertEqual(self.manifest()["platforms"], ["cursor"])
        self.assertEqual({e["platform"] for e in self.manifest()["generated"].values()}, {"cursor"})
        self.assertFalse((self.target / ".claude/skills").exists())  # emptied dir pruned

    def test_user_text_in_claude_md_survives_deselect(self):
        self.install()
        (self.target / ".claude/CLAUDE.md").write_text("mine\n" + self.read(".claude/CLAUDE.md"))
        self.install("cursor")
        self.assertEqual(self.read(".claude/CLAUDE.md"), "mine\n")

    def test_edited_generated_file_survives_deselect(self):
        self.install()
        (self.target / ".claude/skills/.gitignore").write_text("my edit\n")
        self.install("claude", "--force")
        self.assertEqual(self.read(".claude/skills/.gitignore"), "my edit\n")
        self.install("cursor")
        self.assertEqual(self.read(".claude/skills/.gitignore"), "my edit\n")
        self.assertIn("keep (you changed it)", self.out)

    def test_scripted_rerun_keeps_previous_platforms(self):
        self.install("claude,copilot")
        with mock.patch.object(cli, "_interactive", return_value=False), \
             redirect_stdout(io.StringIO()):
            cli.main([str(self.target)])
        self.assertEqual(self.manifest()["platforms"], ["claude", "copilot"])


class CopyFallback(_Tmp):
    def test_copy_when_links_unavailable_and_safe_removal(self):
        with mock.patch.object(Path, "symlink_to", side_effect=OSError("no symlinks")):
            self.install()
        copy = self.target / ".claude/skills" / SKILL
        self.assertFalse(links.is_link(copy))
        self.assertTrue((copy / "SKILL.md").exists())
        self.assertEqual(self.manifest()["generated"][f".claude/skills/{SKILL}"]["mode"], "copy")
        (self.target / ".claude/skills/prd/SKILL.md").write_text("edited")
        self.install("cursor")
        self.assertFalse(copy.exists())
        self.assertTrue((self.target / ".claude/skills/prd").exists())  # changed copy kept


class Cli(_Tmp):
    def test_unknown_platform_rejected(self):
        self.assertEqual(self.install("nope"), 2)
        self.assertIn("unknown platform", self.out)
        self.assertFalse((self.target / ".claude").exists())

    def test_non_interactive_without_target_errors(self):
        with mock.patch.object(cli, "_interactive", return_value=False), \
             redirect_stdout(io.StringIO()) as out:
            self.assertEqual(cli.main([]), 2)
        self.assertIn("target", out.getvalue())

    def test_interactive_full_flow(self):
        with mock.patch.object(cli, "_interactive", return_value=True), \
             mock.patch("builtins.input", side_effect=[str(self.target), "a", "n", "y"]), \
             redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main([]), 0)
        self.assertEqual(self.manifest()["platforms"], AVAILABLE)

    def test_menu_says_installed_only_for_platforms_already_in_the_project(self):
        def menu(argv, answers):
            with mock.patch.object(cli, "_interactive", return_value=True), \
                 mock.patch("builtins.input", side_effect=answers), \
                 redirect_stdout(io.StringIO()) as out:
                cli.main(argv)
            return out.getvalue()
        fresh = menu([str(self.target)], ["claude", "n", "y"])
        self.assertNotIn("installed", fresh)
        again = menu([str(self.target)], ["", "n", "n"])
        claude_line = next(l for l in again.splitlines() if "[claude]" in l)
        cursor_line = next(l for l in again.splitlines() if "[cursor]" in l)
        self.assertIn("installed", claude_line)
        self.assertNotIn("installed", cursor_line)

    def test_interactive_decline_writes_nothing(self):
        with mock.patch.object(cli, "_interactive", return_value=True), \
             mock.patch("builtins.input", side_effect=["1", "n", "n"]), \
             redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main([str(self.target)]), 1)
        self.assertEqual(list(self.target.iterdir()), [])

    def test_ctrl_d_or_ctrl_c_at_a_prompt_aborts_cleanly(self):
        for exc in (EOFError, KeyboardInterrupt):
            with mock.patch.object(cli, "_interactive", return_value=True), \
                 mock.patch("builtins.input", side_effect=exc), \
                 redirect_stdout(io.StringIO()) as out:
                self.assertEqual(cli.main([str(self.target)]), 130)
            self.assertIn("Aborted", out.getvalue())
            self.assertEqual(list(self.target.iterdir()), [])

    def test_parse_selection(self):
        keys = AVAILABLE
        self.assertEqual(cli.parse_selection("a", keys), keys)
        self.assertEqual(cli.parse_selection("1", keys), keys[:1])
        self.assertEqual(cli.parse_selection("cursor,claude", keys), ["claude", "cursor"])
        for bad in ("99", "", "gemini"):
            with self.assertRaises(ValueError):
                cli.parse_selection(bad, keys)


if __name__ == "__main__":
    unittest.main()

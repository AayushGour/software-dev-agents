"""Tests for the generated platforms (Codex, OpenCode, Antigravity, Hermes, Amp, Kiro,
Cursor MCP). Run from repo root:
    python3 -m unittest discover -s installer/tests -t . -v
"""
import io
import json
import shutil
import subprocess
import tempfile
import tomllib
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from installer import cli, source, translate
from installer.manifest import REL as MANIFEST
from installer.platforms import AVAILABLE, REGISTRY

ALL = ",".join(AVAILABLE)
DONE_NO_EVIDENCE = "- [ ] T7 [senior-dev] Build  prio:P1  status:done"


class _Tmp(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.target = Path(self._tmp.name).resolve()

    def tearDown(self):
        self._tmp.cleanup()

    def install(self, platforms=ALL, *extra):
        with mock.patch.object(cli, "_interactive", return_value=False), \
             redirect_stdout(io.StringIO()) as out:
            code = cli.main([str(self.target), "--platforms", platforms, *extra])
        self.out = out.getvalue()
        self.assertEqual(code, 0, self.out)

    def read(self, rel):
        return (self.target / rel).read_text()

    def json(self, rel):
        return json.loads(self.read(rel))

    def names(self):
        return [r.name for r in translate.project_roles(self.target)]


class Codex(_Tmp):
    def test_config_agents_and_hooks(self):
        self.install()
        config = tomllib.loads(self.read(".codex/config.toml"))
        self.assertEqual(set(config["mcp_servers"]), set(source.mcp_servers()))
        self.assertEqual(config["mcp_servers"]["deepwiki"]["url"], "https://mcp.deepwiki.com/mcp")
        for name in self.names():
            agent = tomllib.loads(self.read(f".codex/agents/{name}.toml"))
            self.assertEqual(agent["name"], name)
            self.assertTrue(agent["description"])
        self.assertEqual(tomllib.loads(self.read(".codex/agents/researcher.toml"))["sandbox_mode"],
                         "read-only")
        self.assertNotIn("sandbox_mode", tomllib.loads(self.read(".codex/agents/senior-dev.toml")))
        hooks = self.json(".codex/hooks.json")["hooks"]
        self.assertEqual(set(hooks), {"SessionStart", "SessionEnd", "PreToolUse", "PostToolUse"})
        self.assertEqual(hooks["PreToolUse"][0]["matcher"], "apply_patch|Bash")
        self.assertLessEqual(hooks["SessionEnd"][0]["hooks"][0]["timeout"], 3)

    def test_generated_pre_hook_really_blocks_a_codex_patch(self):
        self.install("codex")
        command = self.json(".codex/hooks.json")["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
        patch = ("*** Begin Patch\n*** Update File: .claude/task-board.md\n@@\n"
                 f"+{DONE_NO_EVIDENCE}\n*** End Patch\n")
        r = subprocess.run(command, shell=True, cwd=self.target, capture_output=True, text=True,
                           input=json.dumps({"cwd": str(self.target), "tool_name": "apply_patch",
                                             "tool_input": {"command": patch}}))
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("board-lint: BLOCKED", r.stderr)

    def test_users_config_toml_survives_install_and_deselect(self):
        (self.target / ".codex").mkdir()
        (self.target / ".codex/config.toml").write_text('model = "o4"\n')
        self.install("codex")
        self.assertTrue(self.read(".codex/config.toml").startswith('model = "o4"\n'))
        tomllib.loads(self.read(".codex/config.toml"))
        self.install("claude")
        self.assertEqual(self.read(".codex/config.toml"), 'model = "o4"\n')
        self.assertFalse((self.target / ".codex/agents").exists())


class OpenCode(_Tmp):
    def test_config_agents_and_plugin(self):
        self.install("opencode")
        mcp = self.json("opencode.json")["mcp"]
        self.assertEqual(mcp["graphify"]["type"], "local")
        self.assertEqual(mcp["graphify"]["command"][0], "uvx")
        self.assertEqual(mcp["deepwiki"], {"type": "remote", "url": "https://mcp.deepwiki.com/mcp",
                                           "enabled": True})
        stub = self.read(".opencode/agents/researcher.md")
        self.assertIn("mode: subagent", stub)
        self.assertIn("edit: deny", stub)
        plugin = self.read(".opencode/plugins/harness-hooks.js")
        self.assertIn("hook_adapter.py opencode PreToolUse", plugin)
        self.assertIn("board_lint.py", plugin)

    @unittest.skipUnless(shutil.which("node"), "node not installed")
    def test_plugin_is_valid_javascript(self):
        self.install("opencode")
        js = self.target / ".opencode/plugins/harness-hooks.js"
        mjs = js.with_suffix(".mjs")
        shutil.copy(js, mjs)
        r = subprocess.run(["node", "--check", str(mjs)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_users_opencode_json_keys_survive(self):
        (self.target / "opencode.json").write_text(json.dumps(
            {"theme": "dark", "mcp": {"mine": {"type": "remote", "url": "https://x"}}}))
        self.install("opencode")
        data = self.json("opencode.json")
        self.assertEqual(data["theme"], "dark")
        self.assertIn("mine", data["mcp"])
        self.assertIn("graphify", data["mcp"])
        self.install("claude")
        self.assertEqual(self.json("opencode.json"),
                         {"theme": "dark", "mcp": {"mine": {"type": "remote", "url": "https://x"}}})

    def test_users_same_named_server_is_kept_and_survives_deselect(self):
        mine = {"type": "local", "command": ["my-graphify"]}
        (self.target / "opencode.json").write_text(json.dumps({"mcp": {"graphify": mine}}))
        self.install("opencode")
        self.assertEqual(self.json("opencode.json")["mcp"]["graphify"], mine)
        self.assertIn("keep mcp.graphify (yours)", self.out)
        self.install("claude")
        self.assertEqual(self.json("opencode.json"), {"mcp": {"graphify": mine}})


class Antigravity(_Tmp):
    def test_config_agents_and_hooks(self):
        self.install("antigravity")
        mcp = self.json(".agents/mcp_config.json")["mcpServers"]
        self.assertEqual(mcp["deepwiki"], {"serverUrl": "https://mcp.deepwiki.com/mcp"})
        group = self.json(".agents/hooks.json")["harness"]
        self.assertTrue(group["enabled"])
        self.assertNotIn("SessionStart", group)
        self.assertIn("write_to_file", group["PreToolUse"][0]["matcher"])
        self.assertIn("model: inherit", self.read(".agents/agents/tester.md"))


class AmpKiroCursorHermes(_Tmp):
    def test_amp(self):
        self.install("amp")
        self.assertEqual(set(self.json(".amp/settings.json")["amp.mcpServers"]),
                         set(source.mcp_servers()))
        self.assertIn("amp mcp approve", REGISTRY["amp"].next_steps)

    def test_kiro_prompt_pointer_resolves(self):
        self.install("kiro")
        for name in self.names():
            agent = self.json(f".kiro/agents/{name}.json")
            prompt = agent["prompt"].removeprefix("file://")
            self.assertTrue((self.target / ".kiro/agents" / prompt).resolve().is_file(), prompt)
        self.assertIn("mcpServers", self.json(".kiro/settings/mcp.json"))

    def test_cursor_mcp(self):
        self.install("cursor")
        self.assertEqual(set(self.json(".cursor/mcp.json")["mcpServers"]), set(source.mcp_servers()))

    def test_hermes_writes_nothing_of_its_own(self):
        self.install("hermes")
        self.assertEqual(self.json(MANIFEST.as_posix())["generated"], {})
        self.assertIn("mcp_servers:", REGISTRY["hermes"].next_steps)


class NoDuplication(_Tmp):
    def test_stubs_point_at_role_files_and_never_copy_them(self):
        self.install()
        roles = translate.project_roles(self.target)
        self.assertTrue(roles)
        stubs = [p for p in self.target.glob(".*/agents/*") if not p.is_relative_to(
            self.target / ".claude")] + list(self.target.glob(".kiro/agents/*"))
        self.assertGreaterEqual(len(stubs), 3 * len(roles))
        for role in roles:
            body = source.load_agent(role.name).body if role.name in {
                a.name for a in source.load_agents()} else ""
            snippet = body.strip().splitlines()[0] if body.strip() else None
            self.assertTrue((self.target / role.rel).is_file())
            for stub in stubs:
                if stub.stem == role.name and snippet:
                    self.assertNotIn(snippet, stub.read_text(), stub)

    def test_specialists_sync_and_removed_agents_are_cleaned(self):
        self.install("codex,opencode")
        spec = self.target / ".claude/agents/ml-eng.md"
        spec.write_text("---\nname: ml-eng\ndescription: ML specialist\ntools: Read, Bash\n---\nbody\n")
        self.install("codex,opencode")
        self.assertTrue((self.target / ".codex/agents/ml-eng.toml").exists())
        self.assertTrue((self.target / ".opencode/agents/ml-eng.md").exists())
        spec.unlink()
        self.install("codex,opencode")
        self.assertFalse((self.target / ".codex/agents/ml-eng.toml").exists())
        self.assertFalse((self.target / ".opencode/agents/ml-eng.md").exists())

    def test_deselecting_everything_but_claude_leaves_only_shared_and_claude(self):
        self.install()
        self.install("claude")
        for rel in (".codex", ".opencode", "opencode.json", ".agents/agents", ".agents/hooks.json",
                    ".agents/mcp_config.json", ".amp", ".kiro", ".cursor"):
            self.assertFalse((self.target / rel).exists(), rel)
        generated = self.json(MANIFEST.as_posix())["generated"]
        self.assertTrue(generated)
        self.assertEqual({e["platform"] for e in generated.values()}, {"claude"})

    def test_rerun_is_idempotent(self):
        self.install()
        before = {p: p.read_bytes() for p in self.target.rglob("*") if p.is_file()}
        self.install()
        after = {p: p.read_bytes() for p in self.target.rglob("*") if p.is_file()}
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()

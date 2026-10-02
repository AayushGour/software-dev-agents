"""Platforms that need generated config: agent stubs pointing at the shared role files,
MCP servers derived from .mcp.json, and hooks routed through tools/hook_adapter.py.

Everything here is recorded in the manifest, so deselecting a platform removes it and a
re-run refreshes it (including stubs for specialists the architect added since).
"""
from installer import translate
from installer.context import Context
from installer.platforms.base import Platform


def _mcp(ctx: Context, rel: str, parent: tuple, servers: dict, key: str) -> None:
    ctx.merge_json(rel, {(*parent, name): srv for name, srv in servers.items()}, key)


def _stubs(ctx: Context, key: str, folder: str, ext: str, render) -> None:
    for role in translate.project_roles(ctx.target):
        ctx.generated(f"{folder}/{role.name}{ext}", render(role), key)


class Codex(Platform):
    key, label, binaries = "codex", "OpenAI Codex", ("codex",)
    next_steps = ("trust the project when Codex asks (its .codex/ config, agents and hooks "
                  "load only in trusted projects), then run /hooks once and trust the "
                  "harness hooks — until then the board-lint DONE gate does not run.")

    def install(self, ctx: Context) -> None:
        print("codex:")
        ctx.block(".codex/config.toml", translate.mcp_codex_toml(), self.key)
        _stubs(ctx, self.key, ".codex/agents", ".toml", translate.codex_agent)
        ctx.merge_json(".codex/hooks.json",
                       {("hooks", ev): groups for ev, groups in translate.hooks_codex().items()},
                       self.key)


class OpenCode(Platform):
    key, label, binaries = "opencode", "OpenCode", ("opencode",)
    next_steps = ("start opencode in the project; agents are @-mentionable, and the "
                  "harness hooks run from .opencode/plugins/harness-hooks.js.")

    def install(self, ctx: Context) -> None:
        print("opencode:")
        _mcp(ctx, "opencode.json", ("mcp",), translate.mcp_opencode(), self.key)
        _stubs(ctx, self.key, ".opencode/agents", ".md", translate.opencode_agent)
        ctx.generated(".opencode/plugins/harness-hooks.js", translate.opencode_plugin(), self.key)


class Antigravity(Platform):
    key, label, binaries = "antigravity", "Antigravity CLI", ("agy",)
    next_steps = ("Gemini CLI's successor. Antigravity has no session hooks, so the code "
                  "brain isn't built at session start — run `python3 <harness>/tools/graphify/"
                  "ensure_graph.py --build` once in the project.")

    def install(self, ctx: Context) -> None:
        print("antigravity:")
        _mcp(ctx, ".agents/mcp_config.json", ("mcpServers",), translate.mcp_antigravity(), self.key)
        _stubs(ctx, self.key, ".agents/agents", ".md", translate.antigravity_agent)
        ctx.merge_json(".agents/hooks.json", {("harness",): translate.hooks_antigravity()},
                       self.key)


class Hermes(Platform):
    """Reads AGENTS.md and .agents/skills from the project. Its MCP servers and hooks
    exist only in the user-global ~/.hermes/config.yaml, so nothing is written there:
    the snippet is printed for the user to add. No hooks: Hermes hook payloads aren't
    documented well enough to route board-lint through them safely."""
    key, label, binaries = "hermes", "Hermes Agent", ("hermes",)

    @property
    def next_steps(self) -> str:
        return ("reads AGENTS.md, but caps context files at 20,000 chars (keeps the head and "
                "tail, and tells the model to read the full file for the middle). Project "
                "skills: on versions with `hermes skills trust`, run it here; otherwise agents "
                "read .agents/skills by path. MCP servers are user-global in Hermes — add to "
                "~/.hermes/config.yaml:\n" + translate.mcp_hermes_yaml()
                + "  No named subagents or project hooks: roles run via delegate_task, and the "
                "DONE gate holds by convention only (see AGENTS.md › Platform notes).")


class Amp(Platform):
    key, label, binaries = "amp", "Amp", ("amp",)

    @property
    def next_steps(self) -> str:
        names = " ".join(translate.mcp_standard())
        return (f"approve the workspace MCP servers once: `amp mcp approve <name>` for each of: "
                f"{names}. Amp has no custom subagents or hooks: roles run inline and the DONE "
                "gate holds by convention only.")

    def install(self, ctx: Context) -> None:
        print("amp:")
        _mcp(ctx, ".amp/settings.json", ("amp.mcpServers",), translate.mcp_standard(), self.key)


class Kiro(Platform):
    key, label, binaries = "kiro", "Kiro", ("kiro-cli", "kiro")
    next_steps = ("agents in .kiro/agents point at .claude/agents natively and load skills "
                  "from .agents/skills. No harness hooks on Kiro yet: the DONE gate holds by "
                  "convention only.")

    def install(self, ctx: Context) -> None:
        print("kiro:")
        _mcp(ctx, ".kiro/settings/mcp.json", ("mcpServers",), translate.mcp_standard(), self.key)
        _stubs(ctx, self.key, ".kiro/agents", ".json", translate.kiro_agent)

"""Platform registry: key → adapter, in menu order.

Cursor and Copilot read the shared assets natively (AGENTS.md, .agents/skills,
.claude/agents, .claude/settings.json hooks; Copilot also .mcp.json), so Cursor only
adds its MCP file and Copilot adds nothing. See
docs/superpowers/specs/2026-10-02-multi-platform-shared-install-scope.md.
"""
from installer import translate
from installer.context import Context
from installer.platforms.base import Platform
from installer.platforms.claude import ClaudeCode
from installer.platforms.generated import Amp, Antigravity, Codex, Hermes, Kiro, OpenCode


class Cursor(Platform):
    key, label, binaries = "cursor", "Cursor", ("cursor-agent", "cursor")
    next_steps = ("reads AGENTS.md, .agents/skills and .claude/agents natively; Claude hooks "
                  "load via Settings › 'Include third-party configs' (on by default).")

    def install(self, ctx: Context) -> None:
        print("cursor:")
        ctx.merge_json(".cursor/mcp.json", {("mcpServers", n): s
                                            for n, s in translate.mcp_standard().items()},
                       self.key)


class Copilot(Platform):
    key, label, binaries = "copilot", "GitHub Copilot", ("copilot",)
    next_steps = ("CLI reads AGENTS.md, .agents/skills, .claude/agents, .claude/settings.json "
                  "hooks and .mcp.json natively. VS Code: enable chat.useClaudeHooks for hooks.")


REGISTRY: dict[str, Platform] = {p.key: p for p in (
    ClaudeCode(), Cursor(), Copilot(), Codex(), OpenCode(), Antigravity(), Hermes(), Amp(), Kiro(),
)}

AVAILABLE = list(REGISTRY)

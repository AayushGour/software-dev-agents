"""Platform registry: key → adapter, in menu order.

Cursor and Copilot read every shared asset natively (AGENTS.md, .agents/skills,
.claude/agents, .claude/settings.json hooks, and for Copilot .mcp.json), so their
adapters write nothing. See docs/superpowers/specs/2026-10-02-multi-platform-shared-install-scope.md.
"""
from installer.platforms.base import ComingSoon, Platform
from installer.platforms.claude import ClaudeCode


class Cursor(Platform):
    key, label, binaries = "cursor", "Cursor", ("cursor-agent", "cursor")
    next_steps = ("reads AGENTS.md, .agents/skills and .claude/agents natively; Claude hooks "
                  "load via Settings › 'Include third-party configs' (on by default). MCP "
                  "servers arrive in a later release (.cursor/mcp.json).")


class Copilot(Platform):
    key, label, binaries = "copilot", "GitHub Copilot", ("copilot",)
    next_steps = ("CLI reads AGENTS.md, .agents/skills, .claude/agents, .claude/settings.json "
                  "hooks and .mcp.json natively. VS Code: enable chat.useClaudeHooks for hooks.")


REGISTRY: dict[str, Platform] = {p.key: p for p in (
    ClaudeCode(),
    Cursor(),
    Copilot(),
    ComingSoon("codex", "OpenAI Codex", "codex"),
    ComingSoon("opencode", "OpenCode", "opencode"),
    ComingSoon("antigravity", "Antigravity CLI", "agy"),
    ComingSoon("hermes", "Hermes Agent", "hermes"),
    ComingSoon("amp", "Amp", "amp"),
    ComingSoon("kiro", "Kiro", "kiro-cli"),
)}

AVAILABLE = [k for k, p in REGISTRY.items() if p.available]

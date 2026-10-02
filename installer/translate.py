"""Canonical team → each platform's formats. Pure functions; adapters do the writing.

Agent stubs never copy a role prompt: their body (or Kiro's native `file://` prompt)
points at the one copy in `.claude/agents/`. MCP servers and hooks come from the one copy
in `.mcp.json` / `.claude/settings.json`. Format facts and sources:
docs/superpowers/specs/2026-10-02-multi-platform-shared-install-scope.md
"""
import json
from dataclasses import dataclass
from pathlib import Path

from installer import source
from agent_lint import parse_frontmatter, tools_of  # on sys.path via installer.source

WRITE_TOOLS = {"Write", "Edit", "MultiEdit", "Bash", "NotebookEdit"}
ADAPTER = f"python3 {(source.TOOLS_DIR / 'hook_adapter.py').as_posix()}"


@dataclass(frozen=True)
class Role:
    name: str
    description: str
    read_only: bool
    rel: str  # path of the role file from the project root, e.g. .claude/agents/tester.md


def project_roles(target: Path) -> list[Role]:
    """Agents in the PROJECT's .claude/agents (shipped + specialists the architect added),
    so re-running setup also wires up specialists on stub-based platforms."""
    roles = []
    for path in sorted((target / ".claude" / "agents").rglob("*.md")):
        fm = parse_frontmatter(path.read_text(errors="replace")) or {}
        if not fm.get("name"):
            continue
        tools = set(tools_of(fm) or WRITE_TOOLS)  # no tools: key = inherits everything
        roles.append(Role(fm["name"], fm.get("description", ""), not tools & WRITE_TOOLS,
                          path.relative_to(target).as_posix()))
    return roles


def pointer(role: Role) -> str:
    return (f"Your full role prompt is `{role.rel}` (from the project root). Read it now and "
            "follow it exactly, ignoring its YAML header; the team rulebook is `AGENTS.md`.\n")


def q(text: str) -> str:
    """A string literal valid in TOML, YAML and JSON alike."""
    return json.dumps(text, ensure_ascii=False)


# ---- MCP -------------------------------------------------------------------------

def _remote(srv: dict) -> bool:
    return "url" in srv


def mcp_standard() -> dict:
    """{name: {command,args,env} | {url,headers}} — Cursor, Amp, Kiro, Hermes."""
    out = {}
    for name, srv in source.mcp_servers().items():
        if _remote(srv):
            out[name] = {k: srv[k] for k in ("url", "headers") if k in srv}
        else:
            out[name] = {k: srv[k] for k in ("command", "args", "env") if k in srv}
    return out


def mcp_antigravity() -> dict:
    """Remote servers use `serverUrl` — `url` is not accepted [AG4]."""
    return {n: ({"serverUrl": s["url"], **({"headers": s["headers"]} if "headers" in s else {})}
                if "url" in s else s) for n, s in mcp_standard().items()}


def mcp_opencode() -> dict:
    """`mcp` entries: local servers take `command` as one array [O4]."""
    out = {}
    for name, srv in mcp_standard().items():
        if "url" in srv:
            out[name] = {"type": "remote", "url": srv["url"], "enabled": True}
        else:
            out[name] = {"type": "local", "command": [srv["command"], *srv.get("args", [])],
                         "enabled": True, **({"environment": srv["env"]} if "env" in srv else {})}
    return out


def mcp_codex_toml() -> str:
    lines = []
    for name, srv in mcp_standard().items():
        lines.append(f"[mcp_servers.{name}]")
        if "url" in srv:
            lines.append(f"url = {q(srv['url'])}")
        else:
            lines.append(f"command = {q(srv['command'])}")
            lines.append("args = [" + ", ".join(q(a) for a in srv.get("args", [])) + "]")
            if srv.get("env"):
                lines.append("env = { " + ", ".join(f"{k} = {q(v)}" for k, v in srv["env"].items()) + " }")
        lines.append("")
    return "\n".join(lines)


def mcp_hermes_yaml() -> str:
    lines = ["mcp_servers:"]
    for name, srv in mcp_standard().items():
        lines.append(f"  {name}:")
        for k, v in srv.items():
            lines.append(f"    {k}: {json.dumps(v)}")
    return "\n".join(lines) + "\n"


# ---- hooks -----------------------------------------------------------------------

@dataclass(frozen=True)
class Hook:
    event: str          # Claude event name
    tools: tuple        # Claude tool names it matches; () = not a tool event
    command: str        # absolute command, Claude-shaped payload expected


def canonical_hooks() -> list[Hook]:
    settings = json.loads(source.absolutize((source.DOTCLAUDE / "settings.json").read_text()))
    hooks = []
    for event, groups in settings.get("hooks", {}).items():
        for group in groups:
            tools = tuple(t for t in group.get("matcher", "").split("|") if t)
            for h in group.get("hooks", []):
                if h.get("type") == "command":
                    hooks.append(Hook(event, tools, h["command"]))
    return hooks


def wrapped(platform: str, hook: Hook) -> str:
    return f"{ADAPTER} {platform} {hook.event} -- {hook.command}"


def _matcher(tools: tuple, names: dict) -> str:
    seen = []
    for t in tools:
        for n in names.get(t, "").split("|"):
            if n and n not in seen:
                seen.append(n)
    return "|".join(seen)


CODEX_TOOLS = {"Edit": "apply_patch", "Write": "apply_patch", "MultiEdit": "apply_patch",
               "Bash": "Bash"}
ANTIGRAVITY_TOOLS = {"Edit": "replace_file_content|multi_replace_file_content",
                     "Write": "write_to_file", "MultiEdit": "multi_replace_file_content",
                     "Bash": "run_command"}
OPENCODE_TOOLS = {"Edit": "edit|multiedit|patch|apply_patch", "Write": "write",
                  "MultiEdit": "multiedit", "Bash": "bash"}


def hooks_codex() -> dict:
    """.codex/hooks.json — Claude's own shape; SessionEnd is capped at 3 s [X5]."""
    out = {}
    for h in canonical_hooks():
        group = {"hooks": [{"type": "command", "command": wrapped("codex", h),
                            **({"timeout": 3} if h.event == "SessionEnd" else {})}]}
        if h.tools:
            group["matcher"] = _matcher(h.tools, CODEX_TOOLS)
        out.setdefault(h.event, []).append(group)
    return out


def hooks_antigravity() -> dict:
    """One named group for .agents/hooks.json. No session events exist there [AG5]."""
    group = {"enabled": True}
    for h in canonical_hooks():
        if not h.tools:
            continue
        group.setdefault(h.event, []).append({
            "matcher": _matcher(h.tools, ANTIGRAVITY_TOOLS),
            "hooks": [{"type": "command", "command": wrapped("antigravity", h)}]})
    return group


def opencode_plugin() -> str:
    """A plugin that feeds OpenCode tool/session events through hook_adapter [O5]."""
    table = {}
    for h in canonical_hooks():
        tools = [n for n in _matcher(h.tools, OPENCODE_TOOLS).split("|") if n] if h.tools else None
        table.setdefault(h.event, []).append({"tools": tools, "command": wrapped("opencode", h)})
    return OPENCODE_PLUGIN.replace("__HOOKS__", json.dumps(table, indent=2))


OPENCODE_PLUGIN = """\
// Generated by setup-team.py — do not edit; re-run setup to refresh.
// Runs the harness hooks (board-lint DONE gate, code-brain refresh, session start/stop)
// through tools/hook_adapter.py, which speaks Claude Code's hook protocol to them.
import { spawnSync } from "node:child_process";

const HOOKS = __HOOKS__;
const pending = new Map();

function run(hook, payload) {
  return spawnSync(hook.command, { input: JSON.stringify(payload), shell: true, encoding: "utf8" });
}

function fire(event, tool, payload) {
  for (const hook of HOOKS[event] || []) {
    if (hook.tools && !hook.tools.includes(tool)) continue;
    const r = run(hook, payload);
    if (event === "PreToolUse" && r.status === 2) {
      throw new Error((r.stderr || "blocked by a harness hook").trim());
    }
  }
}

export const HarnessHooks = async ({ directory }) => ({
  "tool.execute.before": async (input, output) => {
    pending.set(input.callID, output.args);
    fire("PreToolUse", input.tool, { tool: input.tool, args: output.args, directory });
  },
  "tool.execute.after": async (input) => {
    const args = pending.get(input.callID) || input.args || {};
    pending.delete(input.callID);
    fire("PostToolUse", input.tool, { tool: input.tool, args, directory });
  },
  event: async ({ event }) => {
    if (event.type === "session.created") fire("SessionStart", null, { directory });
    if (event.type === "session.deleted") fire("SessionEnd", null, { directory });
  },
});
"""


# ---- agent stubs -----------------------------------------------------------------

def codex_agent(role: Role) -> str:
    """.codex/agents/<name>.toml — no tools allowlist; read-only roles get a read-only
    sandbox instead [X3]."""
    lines = [f"name = {q(role.name)}", f"description = {q(role.description)}",
             f"developer_instructions = {q(pointer(role))}"]
    if role.read_only:
        lines.append('sandbox_mode = "read-only"')
    return "\n".join(lines) + "\n"


def opencode_agent(role: Role) -> str:
    """.opencode/agents/<name>.md — subagent; read-only roles get edit/bash denied [O2]."""
    fm = [f"description: {q(role.description)}", "mode: subagent"]
    if role.read_only:
        fm += ["permission:", "  edit: deny", "  bash: deny"]
    return "---\n" + "\n".join(fm) + "\n---\n" + pointer(role)


def antigravity_agent(role: Role) -> str:
    """.agents/agents/<name>.md — tools inherited; `inherit` keeps the session model [AG2]."""
    fm = [f"name: {q(role.name)}", f"description: {q(role.description)}", "model: inherit"]
    return "---\n" + "\n".join(fm) + "\n---\n" + pointer(role)


def kiro_agent(role: Role) -> str:
    """.kiro/agents/<name>.json — `prompt` points at the role file natively (relative to
    the agent file); skills are read from .agents/skills via a resource glob [K2]."""
    return json.dumps({
        "name": role.name,
        "description": role.description,
        "prompt": f"file://../../{role.rel}",  # stubs sit flat in .kiro/agents/
        "tools": ["read", "web"] if role.read_only else ["*"],
        "includeMcpJson": True,
        "resources": ["file://AGENTS.md", "skill://.agents/skills/**/SKILL.md"],
    }, indent=2) + "\n"

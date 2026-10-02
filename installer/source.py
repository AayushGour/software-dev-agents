"""The canonical team definition — the ONE place every platform installs from.

`claude-code/` is the source of truth: agents (`.claude/agents/**/*.md`), the shared
rulebook (`AGENTS.md`), skills (`.agents/skills/`), working-doc templates, hooks
(`.claude/settings.json`) and MCP servers (`.mcp.json`). Its layout is the installed
layout. Platform adapters read it through this module and add only what their platform
can't read natively; no per-platform copy is ever committed.
"""
import json
import sys
from dataclasses import dataclass
from pathlib import Path

HARNESS_ROOT = Path(__file__).resolve().parent.parent
SOURCE = HARNESS_ROOT / "claude-code"
DOTCLAUDE = SOURCE / ".claude"
AGENTS_DIR = DOTCLAUDE / "agents"
RULEBOOK = SOURCE / "AGENTS.md"
# Claude Code's pointer to the rulebook. It lives in .claude/, not the project root, because
# Copilot reads a root CLAUDE.md as well as AGENTS.md and would load the rulebook twice.
CLAUDE_STUB = DOTCLAUDE / "CLAUDE.md"   # one line: @../AGENTS.md
_PLATFORM_OWNED = {"CLAUDE.md"}  # in .claude/ but written by the Claude adapter, not shared
SKILLS_DIR = SOURCE / ".agents" / "skills"
MCP_JSON = SOURCE / ".mcp.json"
TOOLS_DIR = HARNESS_ROOT / "tools"
README = HARNESS_ROOT / "README.md"

# First line of the pre-AGENTS.md harness rulebook, which was installed as the whole of
# CLAUDE.md. Only used to recognise and migrate those old installs.
LEGACY_CLAUDE_MD_MARKER = "<!-- harness-team-protocol"

# Per-project working docs: seeded once as blank templates, then filled in by the
# agents. NEVER overwritten — not even with --force — or you'd wipe real project data.
SEED_ONCE = {"project-context.md", "coding-standards.md", "task-board.md", "design.md"}

_JUNK_PARTS = {"__pycache__"}
_JUNK_SUFFIXES = (".pyc", ".DS_Store")

sys.path.insert(0, str(TOOLS_DIR))
from agent_lint import parse_frontmatter, tools_of  # noqa: E402  (one frontmatter parser)


@dataclass(frozen=True)
class Agent:
    name: str
    description: str
    tools: list
    model: str
    body: str
    rel_path: Path  # relative to AGENTS_DIR, e.g. research/rsr-x.md


def absolutize(text: str) -> str:
    """Rewrite the in-repo `../tools/` form (resolves from claude-code/ when dogfooding)
    to the harness's absolute tools dir, so deployed projects resolve it anywhere."""
    return text.replace("../tools/", f"{TOOLS_DIR.as_posix()}/")


def _split(text: str) -> str:
    """Body of an agent file, frontmatter removed."""
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            return text[end + 5:].lstrip("\n")
    return text


def load_agents() -> list[Agent]:
    agents = []
    for path in sorted(AGENTS_DIR.rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        fm = parse_frontmatter(text) or {}
        agents.append(Agent(
            name=fm.get("name", path.stem),
            description=fm.get("description", ""),
            tools=tools_of(fm) or [],
            model=fm.get("model", ""),
            body=_split(text),
            rel_path=path.relative_to(AGENTS_DIR),
        ))
    return agents


def load_agent(name: str) -> Agent:
    for agent in load_agents():
        if agent.name == name:
            return agent
    raise KeyError(f"no canonical agent named {name!r}")


def dotclaude_files():
    """(source path, path relative to .claude/) for every shippable file in the tree."""
    for src in sorted(p for p in DOTCLAUDE.rglob("*") if p.is_file()):
        rel = src.relative_to(DOTCLAUDE)
        if (_JUNK_PARTS & set(rel.parts) or src.name.endswith(_JUNK_SUFFIXES)
                or rel.as_posix() in _PLATFORM_OWNED):
            continue
        yield src, rel


def mcp_servers() -> dict:
    """MCP server definitions with tool paths made absolute."""
    servers = json.loads(MCP_JSON.read_text())["mcpServers"]
    for srv in servers.values():
        srv["args"] = [absolutize(a) if isinstance(a, str) else a for a in srv.get("args", [])]
    return servers


def skill_names() -> list[str]:
    return sorted(p.name for p in SKILLS_DIR.iterdir() if p.is_dir())


def skill_files():
    """(source path, path relative to .agents/skills/) for every shippable skill file."""
    for src in sorted(p for p in SKILLS_DIR.rglob("*") if p.is_file()):
        rel = src.relative_to(SKILLS_DIR)
        if _JUNK_PARTS & set(rel.parts) or src.name.endswith(_JUNK_SUFFIXES):
            continue
        yield src, rel

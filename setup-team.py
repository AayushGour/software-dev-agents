#!/usr/bin/env python3
"""Install the claude-code dev team (agents + instructions + mcp tools + templates)
into any target project folder. Cross-platform: Windows, Linux, macOS.

Usage:
    python setup-team.py <target-dir> [--force]

--force   overwrite existing files (default: skip files that already exist)
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

HARNESS_ROOT = Path(__file__).resolve().parent
SOURCE = HARNESS_ROOT / "claude-code"
TOOLS_DIR = HARNESS_ROOT / "tools"


def copy_file(src: Path, dst: Path, force: bool) -> str:
    if dst.exists() and not force:
        return "skip (exists)"
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return "ok"


def install_agents(target: Path, force: bool) -> None:
    src_dir = SOURCE / ".claude" / "agents"
    dst_dir = target / ".claude" / "agents"
    for f in sorted(src_dir.glob("*.md")):
        status = copy_file(f, dst_dir / f.name, force)
        print(f"  agents/{f.name:<22} {status}")


def install_instructions(target: Path, force: bool) -> None:
    status = copy_file(SOURCE / "instructions.md", target / ".claude" / "instructions.md", force)
    print(f"  .claude/instructions.md{'':<7} {status}")


def install_logs(target: Path, force: bool) -> None:
    """One log file per agent (.claude/logs/<agent>.md). Each agent writes only
    its own file, so parallel agents never collide — no shared file, no lock."""
    logs_dir = target / ".claude" / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    agent_names = sorted(f.stem for f in (SOURCE / ".claude" / "agents").glob("*.md"))
    for name in agent_names:
        dst = logs_dir / f"{name}.md"
        if dst.exists() and not force:
            print(f"  .claude/logs/{name}.md{'':<{max(0, 12 - len(name))}} skip (exists)")
            continue
        dst.write_text(
            f"# {name} log\n"
            "This agent's own log — only {name} writes here. 1 line per task at handoff/done.\n"
            "Format: `- <date> [T<id>] one-line summary`\n\n".replace("{name}", name)
        )
        print(f"  .claude/logs/{name}.md{'':<{max(0, 12 - len(name))}} ok")


def install_templates(target: Path, force: bool) -> None:
    for f in sorted((SOURCE / "templates").glob("*.md")):
        status = copy_file(f, target / ".claude" / f.name, force)
        print(f"  .claude/{f.name:<14} {status}")


def install_mcp(target: Path, force: bool) -> None:
    dst = target / ".mcp.json"
    if dst.exists() and not force:
        print(f"  .mcp.json{'':<21} skip (exists)")
        return
    with open(SOURCE / ".mcp.json") as fh:
        config = json.load(fh)

    # Rewrite the relative "../tools/..." path to an absolute path so it
    # works regardless of where <target> lives on disk / which OS.
    web_search = config.get("mcpServers", {}).get("web-search")
    if web_search:
        script = TOOLS_DIR / "web_search" / "mcp_server.py"
        web_search["args"] = [str(script)]

    dst.parent.mkdir(parents=True, exist_ok=True)
    with open(dst, "w") as fh:
        json.dump(config, fh, indent=2)
        fh.write("\n")
    print(f"  .mcp.json{'':<21} ok (paths made absolute)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", help="project folder to install the dev team into")
    parser.add_argument("--force", action="store_true", help="overwrite existing files")
    args = parser.parse_args()

    if not SOURCE.exists():
        sys.exit(f"error: {SOURCE} not found — run this script from inside the harness repo")

    target = Path(args.target).expanduser().resolve()
    target.mkdir(parents=True, exist_ok=True)

    print(f"Installing dev team into: {target}\n")
    print("agents:")
    install_agents(target, args.force)
    print(".claude files:")
    install_instructions(target, args.force)
    install_templates(target, args.force)
    print("root files:")
    install_mcp(target, args.force)
    print("logs:")
    install_logs(target, args.force)

    print("\nDone. cd into the project and describe the work — Claude Code")
    print("auto-discovers .claude/agents/*.md and routes to the right agent.")
    print("(web-search MCP tool needs: pip install mcp)")


if __name__ == "__main__":
    main()

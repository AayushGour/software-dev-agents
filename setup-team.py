#!/usr/bin/env python3
"""Install the claude-code dev team into any target project folder.

`claude-code/.claude/` already mirrors the exact layout an installed project
uses, so install is a straight copy of that tree, plus `.mcp.json` and the
README at the project root. Cross-platform: Windows, Linux, macOS.

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
DOTCLAUDE = SOURCE / ".claude"
TOOLS_DIR = HARNESS_ROOT / "tools"
README = HARNESS_ROOT / "README.md"

# Per-project working docs: seeded once as blank templates, then filled in by the
# agents. NEVER overwritten — not even with --force — or you'd wipe real project
# data (requirements, tasks, standards, design). Everything else (agents,
# instructions, skills, README, .mcp.json) is framework and --force replaces it.
SEED_ONCE = {
    "project-context.md",
    "coding-standards.md",
    "task-board.md",
    "design.md",
}


def copy_file(src: Path, dst: Path, force: bool, label: str, protected: bool = False) -> None:
    if dst.exists() and (protected or not force):
        reason = "keep (your data)" if protected else "skip (exists)"
        print(f"  {label:<32} {reason}")
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    print(f"  {label:<32} ok")


def install_dotclaude(target: Path, force: bool) -> None:
    """Copy the whole .claude tree (agents, instructions, skills, working-doc
    templates) — source already has the right shape. Working docs in SEED_ONCE are
    written only if absent (never clobbered). Note: `.claude/logs/` is NOT shipped;
    each agent creates its own `logs/<agent>.md` on first write."""
    for src in sorted(p for p in DOTCLAUDE.rglob("*") if p.is_file()):
        rel = src.relative_to(DOTCLAUDE)
        if "__pycache__" in rel.parts or src.suffix == ".pyc":
            continue
        protected = rel.as_posix() in SEED_ONCE
        copy_file(src, target / ".claude" / rel, force, f".claude/{rel.as_posix()}", protected)


def rewrite_settings_hooks(target: Path) -> None:
    """Make hook tool-paths absolute in <target>/.claude/settings.json.

    settings.json is copied verbatim with the .claude tree, but its hook commands use a
    relative "../tools/..." path that only resolves when running from claude-code/. Rewrite
    "../tools/" -> the harness's absolute tools dir so the SessionStart (code brain) and
    SessionEnd (searxng) hooks work from the deployed project root. Idempotent — no-op if
    the file is absent or already absolute."""
    dst = target / ".claude" / "settings.json"
    if not dst.exists():
        return
    text = dst.read_text()
    if "../tools/" not in text:
        return
    dst.write_text(text.replace("../tools/", f"{TOOLS_DIR.as_posix()}/"))
    print(f"  {'.claude/settings.json':<32} ok (hook paths made absolute)")


def install_mcp(target: Path, force: bool) -> None:
    dst = target / ".mcp.json"
    if dst.exists() and not force:
        print(f"  {'.mcp.json':<32} skip (exists)")
        return
    with open(DOTCLAUDE.parent / ".mcp.json") as fh:
        config = json.load(fh)

    # Rewrite any relative "../tools/..." arg to absolute so it resolves from wherever
    # <target> lives on disk / whichever OS. The relative form is for in-harness
    # dogfooding (cwd = claude-code/); deployed projects need the absolute path. This
    # preserves surrounding wrapper args (e.g. `uv run --with mcp<2 python <script>`).
    tools_prefix = f"{TOOLS_DIR.as_posix()}/"
    for srv in config.get("mcpServers", {}).values():
        srv["args"] = [a.replace("../tools/", tools_prefix) if isinstance(a, str) else a
                       for a in srv.get("args", [])]

    dst.parent.mkdir(parents=True, exist_ok=True)
    with open(dst, "w") as fh:
        json.dump(config, fh, indent=2)
        fh.write("\n")
    print(f"  {'.mcp.json':<32} ok (paths made absolute)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", help="project folder to install the dev team into")
    parser.add_argument("--force", action="store_true", help="overwrite existing files")
    args = parser.parse_args()

    if not DOTCLAUDE.exists():
        sys.exit(f"error: {DOTCLAUDE} not found — run this script from inside the harness repo")

    target = Path(args.target).expanduser().resolve()
    target.mkdir(parents=True, exist_ok=True)

    print(f"Installing dev team into: {target}\n")
    print(".claude:")
    install_dotclaude(target, args.force)
    rewrite_settings_hooks(target)
    copy_file(README, target / ".claude" / "README.md", args.force, ".claude/README.md")
    # .mcp.json is the ONE file that must live at the project root — Claude Code
    # only discovers project MCP servers from <project>/.mcp.json, not from .claude/.
    print("root files:")
    install_mcp(target, args.force)

    print("\nDone. cd into the project and describe the work — Claude Code")
    print("auto-discovers .claude/agents/*.md and routes to the right agent.")
    print("(web-search + code brain both run via uv — install: https://astral.sh/uv)")
    print("(web-search also needs Docker running for the SearXNG backend)")


if __name__ == "__main__":
    main()

"""Assets every platform reads from ONE copy in the installed project.

AGENTS.md (rulebook, managed block) · .agents/skills/ · .claude/ (agents, hooks, working
docs, templates) · .claude/README.md · .mcp.json. Written whatever platforms are picked:
agent bodies are what every platform's agent stub points at, and the rest is read natively.
"""
import json
import shutil

from installer import links, source
from installer.context import Context


def migrate_legacy_skills(ctx: Context) -> None:
    """Pre-AGENTS.md installs kept real skill dirs in .claude/skills/. Under --force, move
    each shipped one to .agents/skills/ (extra files the user added survive; the shipped
    files are then refreshed like any --force upgrade). The Claude adapter links it back."""
    if not ctx.force:
        return
    for name in source.skill_names():
        old = ctx.target / ".claude" / "skills" / name
        new = ctx.target / ".agents" / "skills" / name
        rel = f".claude/skills/{name}"
        if not old.is_dir() or links.is_link(old) or ctx.manifest.get(rel):
            continue
        if new.exists():
            ctx.writer.report(rel, "keep (also in .agents/skills — merge by hand)")
            continue
        new.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(old), str(new))
        ctx.writer.report(rel, "moved → .agents/skills (migrated)")


def install(ctx: Context) -> None:
    print("shared (read by every platform):")
    migrate_legacy_skills(ctx)
    ctx.block("AGENTS.md", source.RULEBOOK.read_text())
    for src, rel in source.skill_files():
        ctx.writer.copy(src, f".agents/skills/{rel.as_posix()}")
    for src, rel in source.dotclaude_files():
        dst = f".claude/{rel.as_posix()}"
        if rel.as_posix() == "settings.json":
            # Hook commands use ../tools/ (valid from claude-code/); make them absolute.
            ctx.writer.write_text(dst, source.hook_settings_text(),
                                  note="ok (hook paths made absolute)")
        else:
            ctx.writer.copy(src, dst, protected=rel.as_posix() in source.SEED_ONCE)
    ctx.writer.copy(source.README, ".claude/README.md")
    mcp = json.dumps({"mcpServers": source.mcp_servers()}, indent=2) + "\n"
    ctx.writer.write_text(".mcp.json", mcp, note="ok (paths made absolute)")

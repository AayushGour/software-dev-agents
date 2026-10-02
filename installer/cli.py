"""Interactive installer for the dev team, across agent platforms.

    python3 setup-team.py                                    # guided: asks everything
    python3 setup-team.py <target>                           # guided platform pick (TTY)
    python3 setup-team.py <target> --platforms claude,cursor --yes   # scripted

Shared content (AGENTS.md, .agents/skills, .claude/agents, hooks, MCP, working docs) is
written once; each platform adds only what it can't read natively. Without a terminal
(CI, pipes) nothing is asked: <target> is required, --platforms defaults to whatever the
project already has (else claude), and questions take their default answer.
"""
import argparse
import sys
from pathlib import Path

from installer import shared, source
from installer.context import Context
from installer.fsops import Writer
from installer.manifest import Manifest
from installer.platforms import AVAILABLE, REGISTRY

DEFAULT_PLATFORMS = ["claude"]


def _interactive() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def parse_selection(raw: str, keys: list[str]) -> list[str]:
    """'a'/'all' → every key; else comma list of menu numbers or keys, menu order kept."""
    raw = raw.strip().lower()
    if raw in ("a", "all"):
        return list(keys)
    picked = set()
    for tok in filter(None, (t.strip() for t in raw.split(","))):
        if tok.isdigit() and 1 <= int(tok) <= len(keys):
            picked.add(keys[int(tok) - 1])
        elif tok in keys:
            picked.add(tok)
        else:
            raise ValueError(f"unknown platform {tok!r}")
    if not picked:
        raise ValueError("pick at least one platform")
    return [k for k in keys if k in picked]


def _yes(prompt: str, default: bool) -> bool:
    hint = "[Y/n]" if default else "[y/N]"
    answer = input(f"{prompt} {hint} ").strip().lower()
    return default if not answer else answer.startswith("y")


def _ask_platforms(preselected: list[str], installed: list[str]) -> list[str]:
    print("Platforms:")
    for i, key in enumerate(AVAILABLE, 1):
        p = REGISTRY[key]
        tags = [t for t, on in (("detected", p.detected()), ("installed", key in installed)) if on]
        print(f"  {i}) {p.label:<16} [{key}]{'  (' + ', '.join(tags) + ')' if tags else ''}")
    while True:
        raw = input(f"Install for which? numbers/keys, comma-separated, 'a' = all "
                    f"[{','.join(preselected)}]: ") or ",".join(preselected)
        try:
            return parse_selection(raw, AVAILABLE)
        except ValueError as exc:
            print(f"  {exc}")


def main(argv=None) -> int:
    try:
        return _run(argv)
    except (EOFError, KeyboardInterrupt):
        print("\nAborted.")
        return 130


def _run(argv) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("target", nargs="?", help="project folder to install the dev team into")
    parser.add_argument("--platforms", help=f"comma list or 'all': {', '.join(AVAILABLE)}")
    parser.add_argument("--force", action="store_true",
                        help="overwrite framework files (working docs are always kept)")
    parser.add_argument("--yes", "-y", action="store_true", help="skip the confirmation")
    args = parser.parse_args(argv)
    interactive = _interactive()

    if not source.SOURCE.exists():
        print(f"error: {source.SOURCE} not found — run from inside the harness repo")
        return 2

    target = args.target
    if not target:
        if not interactive:
            print("error: target directory required when not running in a terminal")
            return 2
        target = input(f"Project folder [{Path.cwd()}]: ").strip() or str(Path.cwd())
    target = Path(target).expanduser().resolve()
    manifest = Manifest(target, source.HARNESS_ROOT)
    previous = [k for k in manifest.platforms if k in AVAILABLE]

    if args.platforms:
        try:
            platforms = parse_selection(args.platforms, AVAILABLE)
        except ValueError as exc:
            print(f"error: {exc} (available: {', '.join(AVAILABLE)})")
            return 2
    elif interactive:
        detected = [k for k in AVAILABLE if REGISTRY[k].detected()]
        platforms = _ask_platforms(previous or detected or DEFAULT_PLATFORMS, previous)
    else:
        platforms = previous or DEFAULT_PLATFORMS

    force = args.force
    if interactive and not args.force:
        force = _yes("Overwrite framework files that already exist (--force)? "
                     "Working docs are always kept.", default=False)

    dropped = [k for k in previous if k not in platforms]
    labels = ", ".join(REGISTRY[k].label for k in platforms)
    print(f"\nInstall for {labels} into {target}{' (force)' if force else ''}")
    if dropped:
        print(f"Deselected since last run (their generated files are removed): "
              f"{', '.join(REGISTRY[k].label for k in dropped)}")
    if interactive and not args.yes and not _yes("Proceed?", default=True):
        print("Nothing written.")
        return 1

    target.mkdir(parents=True, exist_ok=True)
    writer = Writer(target, force)
    ask = _yes if interactive else (lambda _q, default: default)
    ctx = Context(target, force, writer, manifest, ask)
    try:
        shared.install(ctx)
        for key in platforms:
            print(f"\n== {REGISTRY[key].label} ==")
            REGISTRY[key].install(ctx)
            # anything this platform generated before but not now (e.g. a removed agent)
            manifest.remove_platform(key, writer.report, keep=ctx.touched.get(key, set()))
        for key in dropped:
            manifest.remove_platform(key, writer.report)
    except KeyboardInterrupt:
        # keep deselected platforms listed until their cleanup has run, so the next
        # run still knows to remove their files
        manifest.save(list(dict.fromkeys(platforms + dropped)))
        print("\nInterrupted mid-install — re-run to finish (existing files are skipped).")
        return 130
    manifest.save(platforms)

    print("\nDone.")
    for key in platforms:
        print(f"- {REGISTRY[key].label}: {REGISTRY[key].next_steps}")
    print("(web-search + code brain run via uv — https://astral.sh/uv; "
          "web-search also needs Docker for SearXNG)")
    return 0

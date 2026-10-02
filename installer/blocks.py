"""Harness-managed blocks inside files the user may also own (AGENTS.md, CLAUDE.md).

Only the text between the markers belongs to the harness; anything above or below it is
the user's and survives every re-run.
"""
import re

BEGIN = "<!-- harness:begin — managed by setup-team.py; edits inside this block are overwritten -->"
END = "<!-- harness:end -->"
_BLOCK_RE = re.compile(r"<!-- harness:begin[^\n]*-->\n.*?<!-- harness:end -->\n?", re.S)


def render(content: str) -> str:
    return f"{BEGIN}\n{content.rstrip()}\n{END}\n"


def has_block(text: str) -> bool:
    return bool(_BLOCK_RE.search(text))


def replace(text: str, content: str) -> str:
    """Swap the existing block's content; text outside the block is untouched."""
    return _BLOCK_RE.sub(lambda _: render(content), text, count=1)


def append(text: str, content: str) -> str:
    sep = "" if not text else ("\n" if text.endswith("\n") else "\n\n")
    return f"{text}{sep}{render(content)}"


def strip(text: str) -> str:
    """Text with the block removed (used when a platform is deselected)."""
    return _BLOCK_RE.sub("", text, count=1).strip("\n") + "\n" if has_block(text) else text

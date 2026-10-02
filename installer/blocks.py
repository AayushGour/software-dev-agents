"""Harness-managed blocks inside files the user may also own.

Only the text between the markers belongs to the harness; anything above or below it is
the user's and survives every re-run. Markdown (AGENTS.md, CLAUDE.md) uses HTML-comment
markers; TOML (Codex config) uses `#` comments.
"""
import re

_NOTE = "managed by setup-team.py; edits inside this block are overwritten"
STYLES = {
    "html": (f"<!-- harness:begin — {_NOTE} -->", "<!-- harness:end -->",
             re.compile(r"<!-- harness:begin[^\n]*-->\n.*?<!-- harness:end -->\n?", re.S)),
    "hash": (f"# harness:begin — {_NOTE}", "# harness:end",
             re.compile(r"# harness:begin[^\n]*\n.*?# harness:end\n?", re.S)),
}


def style_for(rel: str) -> str:
    return "hash" if rel.endswith((".toml", ".yaml", ".yml")) else "html"


def render(content: str, style: str = "html") -> str:
    begin, end, _ = STYLES[style]
    return f"{begin}\n{content.rstrip()}\n{end}\n"


def has_block(text: str, style: str = "html") -> bool:
    return bool(STYLES[style][2].search(text))


def replace(text: str, content: str, style: str = "html") -> str:
    """Swap the existing block's content; text outside the block is untouched."""
    return STYLES[style][2].sub(lambda _: render(content, style), text, count=1)


def append(text: str, content: str, style: str = "html") -> str:
    sep = "" if not text else ("\n" if text.endswith("\n") else "\n\n")
    return f"{text}{sep}{render(content, style)}"


def strip(text: str, style: str = "html") -> str:
    """Text with the block removed (used when a platform is deselected)."""
    if not has_block(text, style):
        return text
    return STYLES[style][2].sub("", text, count=1).strip("\n") + "\n"

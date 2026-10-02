"""Everything an install step needs, passed as one object."""
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from installer import blocks
from installer.fsops import Writer
from installer.manifest import Manifest


@dataclass
class Context:
    target: Path
    force: bool
    writer: Writer
    manifest: Manifest
    ask: Callable[[str, bool], bool]  # (question, default) -> answer; scripted runs return default

    def block(self, rel: str, content: str, platform: str = "") -> None:
        """Write `content` as the harness block of `rel`, never touching the user's text.

        new file → just the block · has our block → refresh it (only with force) ·
        user's own file → ask to append (default yes). With `platform`, the block is
        recorded in the manifest so deselecting that platform strips it again."""
        path = self.target / rel
        text = path.read_text() if path.exists() else None
        if text is None:
            new, note = blocks.render(content), "ok"
        elif blocks.has_block(text):
            if not self.force:
                self.writer.report(rel, "skip (exists)")
                return
            new, note = blocks.replace(text, content), "ok (harness block refreshed)"
        elif self.ask(f"{rel} exists and isn't the harness's. Append the harness block "
                      "(your text is kept)?", True):
            new, note = blocks.append(text, content), "ok (harness block appended; your text kept)"
        else:
            self.writer.report(rel, "keep (yours — harness block not added)")
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(new)
        self.writer.report(rel, note)
        if platform:
            self.manifest.add(rel, platform, "block")

"""Everything an install step needs, passed as one object, plus the three ways a platform
writes its own files without clobbering the user's: managed blocks, generated files and
merged JSON keys. Each records itself in the manifest so it can be undone safely."""
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from installer import blocks
from installer.fsops import Writer
from installer.manifest import Manifest, sha256, value_hash


@dataclass
class Context:
    target: Path
    force: bool
    writer: Writer
    manifest: Manifest
    ask: Callable[[str, bool], bool]  # (question, default) -> answer; scripted runs return default
    touched: dict = field(default_factory=dict)  # platform -> rels generated this run

    def touch(self, platform: str, rel: str) -> None:
        """Mark `rel` as generated for `platform` this run (others get cleaned up)."""
        if platform:
            self.touched.setdefault(platform, set()).add(rel)

    def block(self, rel: str, content: str, platform: str = "") -> None:
        """Write `content` as the harness block of `rel`, never touching the user's text.

        new file → just the block · has our block → refresh it (only with force, unless
        it's a platform file we generated) · user's own file → ask to append (default yes).
        With `platform`, the block is recorded so deselecting that platform strips it."""
        style = blocks.style_for(rel)
        path = self.target / rel
        text = path.read_text() if path.exists() else None
        self.touch(platform, rel)
        if text is None:
            new, note = blocks.render(content, style), "ok"
        elif blocks.has_block(text, style):
            if not (self.force or platform):
                self.writer.report(rel, "skip (exists)")
                return
            new = blocks.replace(text, content, style)
            if new == text:
                self.writer.report(rel, "ok (up to date)")
                return
            note = "ok (harness block refreshed)"
        elif self.ask(f"{rel} exists and isn't the harness's. Append the harness block "
                      "(your text is kept)?", True):
            new, note = blocks.append(text, content, style), "ok (harness block appended; your text kept)"
        else:
            self.writer.report(rel, "keep (yours — harness block not added)")
            self.touched.get(platform, set()).discard(rel)
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(new)
        self.writer.report(rel, note)
        if platform:
            self.manifest.add(rel, platform, "block")

    def generated(self, rel: str, text: str, platform: str) -> None:
        """A file that belongs to one platform. Refreshed on every run while it still
        matches what we wrote; a file the user wrote or edited is kept (unless --force)."""
        path = self.target / rel
        ours = self.manifest.get(rel)
        self.touch(platform, rel)
        if path.exists():
            if path.read_text() == text:
                self.writer.report(rel, "ok (up to date)")
                self.manifest.add(rel, platform, "file", sha256=sha256(path))
                return
            unchanged = ours and sha256(path) == ours.get("sha256")
            if not (unchanged or self.force):
                self.writer.report(rel, "keep (yours or edited — --force replaces it)")
                return
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        self.manifest.add(rel, platform, "file", sha256=sha256(path))
        self.writer.report(rel, "ok")

    def merge_json(self, rel: str, entries: dict, platform: str) -> None:
        """Add `entries` ({(key, path, ...): value}) to a JSON file, leaving every other
        key alone. A key the user already set differently is kept unless --force."""
        path = self.target / rel
        prior = self.manifest.get(rel)
        created = prior.get("created", False) if prior else not path.exists()
        try:
            data = json.loads(path.read_text()) if path.exists() else {}
        except ValueError:
            data = None
        if not isinstance(data, dict):
            self.writer.report(rel, "keep (not a JSON object — add the harness entries by hand)")
            return
        self.touch(platform, rel)
        ours = {tuple(k): d for k, d in (prior or {}).get("keys", [])}
        recorded, changed = [], False
        for key_path, value in entries.items():
            parent = data
            for depth, k in enumerate(key_path[:-1]):
                if not isinstance(parent.setdefault(k, {}), dict):
                    self.writer.report(rel, f"keep {'.'.join(key_path[:depth + 1])} "
                                            "(yours — not an object; add the harness entries by hand)")
                    parent = None
                    break
                parent = parent[k]
            if parent is None:
                continue
            leaf = key_path[-1]
            current = parent.get(leaf)
            if current != value:
                mine = key_path in ours and value_hash(current) == ours[key_path]
                if leaf in parent and not (mine or self.force):
                    self.writer.report(rel, f"keep {'.'.join(key_path)} (yours)")
                    continue
                parent[leaf] = value
                changed = True
            recorded.append([list(key_path), value_hash(value)])
        if changed or not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data, indent=2) + "\n")
        self.manifest.add(rel, platform, "json", keys=recorded, created=created)
        self.writer.report(rel, "ok (merged)" if changed else "ok (up to date)")

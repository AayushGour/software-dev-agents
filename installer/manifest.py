"""`.agents/harness.json` — what this installer generated in a project, per platform.

Shared files (rulebook, agents, skills, working docs, hooks, MCP) are never listed: they
are not removed when a platform is deselected. Platform-specific items are, with enough
information to remove them safely later:
  file  → sha256; deleted only if unchanged
  link  → mode (symlink/junction/copy) + tree hash for copies; copies deleted only if unchanged
  block → the managed block is stripped; the file is deleted if nothing else is left
  json  → key paths we added to a JSON file, each with the value's hash; a key is removed
          only if unchanged, and the file only if we created it and it ends up empty
"""
import hashlib
import json
from pathlib import Path

from installer import blocks, links

REL = Path(".agents") / "harness.json"
VERSION = 1


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def value_hash(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


class Manifest:
    def __init__(self, target: Path, harness: Path):
        self.target = target
        self.path = target / REL
        self.data = {"version": VERSION, "harness": harness.as_posix(),
                     "platforms": [], "generated": {}}
        if self.path.exists():
            try:
                self.data.update(json.loads(self.path.read_text()))
            except (OSError, ValueError):
                pass  # unreadable manifest = fresh start; nothing gets deleted

    @property
    def platforms(self) -> list[str]:
        return list(self.data["platforms"])

    def get(self, rel: str):
        return self.data["generated"].get(rel)

    def add(self, rel: str, platform: str, kind: str, **info) -> None:
        self.data["generated"][rel] = {"platform": platform, "kind": kind, **info}

    def remove_platform(self, platform: str, report, keep: set = frozenset()) -> None:
        """Undo a platform's generated items (all of them on deselect; on a re-run, the
        ones not regenerated — everything outside `keep`), leaving anything the user changed."""
        for rel, entry in list(self.data["generated"].items()):
            if entry["platform"] != platform or rel in keep:
                continue
            if self._undo(rel, entry, report):
                report(rel, f"removed ({platform}: no longer generated)")
            del self.data["generated"][rel]
            self._prune((self.target / rel).parent)

    def _undo(self, rel: str, entry: dict, report) -> bool:
        path = self.target / rel
        kind = entry["kind"]
        if kind == "file" and path.is_file():
            if sha256(path) != entry.get("sha256"):
                report(rel, "keep (you changed it)")
                return False
            path.unlink()
        elif kind == "link" and (links.is_link(path) or path.is_dir()):
            if not links.is_link(path) and links.tree_hash(path) != entry.get("tree"):
                report(rel, "keep (you changed it)")
                return False
            links.remove(path)
        elif kind == "block" and path.is_file():
            rest = blocks.strip(path.read_text(), blocks.style_for(rel))
            if rest.strip():
                path.write_text(rest)
            else:
                path.unlink()
        elif kind == "json" and path.is_file():
            try:
                data = json.loads(path.read_text())
            except ValueError:
                report(rel, "keep (not valid JSON any more)")
                return False
            for key_path, digest in entry.get("keys", []):
                parent, leaf = _walk(data, key_path[:-1]), key_path[-1]
                if isinstance(parent, dict) and leaf in parent and value_hash(parent[leaf]) == digest:
                    del parent[leaf]
            _drop_empty(data)
            if entry.get("created") and not data:
                path.unlink()
            else:
                path.write_text(json.dumps(data, indent=2) + "\n")
        else:
            return False
        return True

    def _prune(self, folder: Path) -> None:
        """Remove folders left empty by a removal, stopping at the project root."""
        while folder != self.target and self.target in folder.parents:
            try:
                folder.rmdir()  # only succeeds when empty
            except OSError:
                return
            folder = folder.parent

    def save(self, platforms: list[str]) -> None:
        self.data["platforms"] = platforms
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=2, sort_keys=True) + "\n")


def _walk(data, keys):
    for k in keys:
        if not isinstance(data, dict):
            return None
        data = data.get(k)
    return data


def _drop_empty(data: dict) -> None:
    for k in list(data):
        if isinstance(data[k], dict):
            _drop_empty(data[k])
            if not data[k]:
                del data[k]

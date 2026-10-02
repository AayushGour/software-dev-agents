"""File writes for an install, with the harness's overwrite rules in one place.

- default: skip any file that already exists (re-running never touches data)
- force:   overwrite framework files
- protected (working docs): never overwritten, not even with force
"""
import shutil
from pathlib import Path


class Writer:
    def __init__(self, target: Path, force: bool):
        self.target = target
        self.force = force

    def _may_write(self, rel: str, protected: bool) -> bool:
        dst = self.target / rel
        if dst.exists() and (protected or not self.force):
            self.report(rel, "keep (your data)" if protected else "skip (exists)")
            return False
        dst.parent.mkdir(parents=True, exist_ok=True)
        return True

    def copy(self, src: Path, rel: str, protected: bool = False, note: str = "ok") -> None:
        if self._may_write(rel, protected):
            shutil.copy2(src, self.target / rel)
            self.report(rel, note)

    def write_text(self, rel: str, text: str, protected: bool = False, note: str = "ok") -> None:
        if self._may_write(rel, protected):
            (self.target / rel).write_text(text)
            self.report(rel, note)

    @staticmethod
    def report(rel: str, status: str) -> None:
        print(f"  {rel:<32} {status}")

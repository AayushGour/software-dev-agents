"""Directory links that degrade gracefully: symlink → Windows junction → copy.

Symlinks need Developer Mode or admin on Windows; junctions don't. A copy always works
but drifts, so the manifest records which mode was used.
"""
import hashlib
import os
import shutil
import subprocess
from pathlib import Path

_isjunction = getattr(os.path, "isjunction", lambda _p: False)  # Python 3.12+


def is_link(path: Path) -> bool:
    return path.is_symlink() or _isjunction(path)


def points_to(path: Path, src: Path) -> bool:
    return is_link(path) and path.resolve() == src.resolve()


def make_link(src: Path, dst: Path) -> str:
    """Link dst → src. Returns the mode used: symlink | junction | copy."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        dst.symlink_to(os.path.relpath(src, dst.parent), target_is_directory=True)
        return "symlink"
    except OSError:
        pass
    if os.name == "nt":
        done = subprocess.run(["cmd", "/c", "mklink", "/J", str(dst), str(src)],
                              capture_output=True)
        if done.returncode == 0:
            return "junction"
    shutil.copytree(src, dst)
    return "copy"


def remove(path: Path) -> None:
    if path.is_symlink():
        path.unlink()
    elif _isjunction(path):
        os.rmdir(path)  # removes the junction, never its target's contents
    elif path.is_dir():
        shutil.rmtree(path)


def tree_hash(root: Path) -> str:
    h = hashlib.sha256()
    for p in sorted(q for q in root.rglob("*") if q.is_file()):
        h.update(p.relative_to(root).as_posix().encode() + b"\0" + p.read_bytes())
    return h.hexdigest()

"""The adapter contract every platform implements."""
import shutil

from installer.context import Context


class Platform:
    key: str = ""         # CLI id, e.g. "claude"
    label: str = ""       # human name, e.g. "Claude Code"
    binaries: tuple = ()  # executables that indicate the platform is installed
    available: bool = True  # False = listed as "coming soon", not selectable
    next_steps: str = ""  # printed after a successful install

    def detected(self) -> bool:
        return any(shutil.which(b) for b in self.binaries)

    def install(self, ctx: Context) -> None:
        """Write this platform's own files. Shared assets are already in place."""


class ComingSoon(Platform):
    available = False

    def __init__(self, key: str, label: str, *binaries: str):
        self.key, self.label, self.binaries = key, label, binaries

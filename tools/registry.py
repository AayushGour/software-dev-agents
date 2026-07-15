"""Local tool registry — the Hermes dispatcher (local/run.py) loads this and
passes these callables to the agent alongside hermes_tools.

Add a tool:
  1. Drop a folder under tools/ with a python function in tool.py.
  2. Add a _load(...) line below (its own try/except, so a missing dep for one
     tool never breaks the others).
The dict key is the name the model calls; the value is the callable.
"""

import importlib.util
from pathlib import Path

_TOOLS_DIR = Path(__file__).parent
TOOLS = {}


def _module(subdir: str):
    """Import tools/<subdir>/tool.py under a unique name (avoids tool.py clashes)."""
    spec = importlib.util.spec_from_file_location(
        f"{subdir}_tool", _TOOLS_DIR / subdir / "tool.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load(subdir: str, names: dict):
    """names = {registered_name: attr_on_module}. Skip the tool if import fails."""
    try:
        mod = _module(subdir)
        for reg_name, attr in names.items():
            TOOLS[reg_name] = getattr(mod, attr)
    except Exception as e:  # missing dep / offline — keep the rest working
        print(f"(tool '{subdir}' skipped: {e})")


_load("web_search", {"web_search": "web_search"})
_load("deepwiki", {
    "deepwiki_ask": "deepwiki_ask",
    "deepwiki_read": "deepwiki_read",
    "deepwiki_structure": "deepwiki_structure",
})

"""
Reference dispatcher for the local org (llama.cpp + Hermes).

It reads .claude/task-board.md, finds the next actionable task, builds that agent's
system prompt from the CANONICAL team definition (claude-code/ — the same agents and
rulebook every other platform installs) plus runtime.md, and runs the Hermes agent
with hermes_tools. Agents coordinate through files only.

Wire the two seams marked TODO to your own runtime, then:  python -m local.run <project_dir>
(from the harness root, so the canonical source is importable)
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from installer import source  # noqa: E402

RUNTIME_NOTES = Path(__file__).parent / "runtime.md"
BOARD = Path(".claude") / "task-board.md"
CONTEXT_DOCS = ("project-context.md", "coding-standards.md", "task-board.md")

# Custom tools (tools/registry.py) — handed to the agent next to hermes_tools.
CUSTOM_TOOLS = {}
try:
    sys.path.insert(0, str(source.TOOLS_DIR))
    from registry import TOOLS as CUSTOM_TOOLS  # e.g. {"web_search": <callable>}
except Exception as e:  # tools optional — run without them
    print(f"(no custom tools loaded: {e})")

# canonical task line:
# - [ ] T2 [senior-dev] build /auth  prio:P1  status:todo  deps:T1
TASK_RE = re.compile(
    r"-\s*\[[ xX]\]\s*T(?P<id>[A-Za-z0-9]+)\s+\[(?P<owner>[\w-]+)\]\s+(?P<title>.*?)\s{2,}"
    r".*?status:(?P<status>[a-z]+)(?:.*?deps:(?P<deps>\S+))?"
)

ACTIONABLE = {"todo", "review", "test"}  # states the dispatcher will pick up
STATUS_AGENT = {"review": "reviewer", "test": "tester"}  # else the task owner


def parse_tasks(board: str):
    tasks = []
    for line in board.splitlines():
        m = TASK_RE.search(line)
        if m:
            d = m.groupdict()
            d["deps"] = [x for x in (d["deps"] or "").split(",") if x and x != "-"]
            tasks.append(d)
    return tasks


def next_task(tasks):
    done = {t["id"] for t in tasks if t["status"] == "done"}
    for t in tasks:
        if t["status"] in ACTIONABLE and all(dep.lstrip("T") in done for dep in t["deps"]):
            return t, STATUS_AGENT.get(t["status"], t["owner"])
    return None, None


def load_agent_prompt(agent: str) -> str:
    return source.load_agent(agent).body


def system_prompt(agent: str) -> str:
    return (f"{load_agent_prompt(agent)}\n\n---\n# Team rulebook\n{source.RULEBOOK.read_text()}"
            f"\n\n---\n# This runtime\n{RUNTIME_NOTES.read_text()}")


def build_context(project: Path) -> str:
    parts = []
    for name in CONTEXT_DOCS:
        f = project / ".claude" / name
        if f.exists():
            parts.append(f"### {name}\n{f.read_text()}")
    return "\n\n".join(parts)


def run_agent(agent: str, task: dict, project: Path):
    system = system_prompt(agent)
    user = (
        f"Project dir: {project}\n"
        f"Your task: T{task['id']} — {task['title']}\n"
        f"Current status: {task['status']}\n\n"
        f"# Project context\n{build_context(project)}\n\n"
        "Do exactly this task. Use hermes_tools. When done, update the task's "
        f"status in {BOARD.as_posix()} and append one log line."
    )
    # TODO(seam 1): call your llama.cpp + Hermes agent here, giving it hermes_tools
    #   (read_file, write_file, append_file, grep, list_dir, run) PLUS CUSTOM_TOOLS.
    #   e.g.  tools = {**HERMES_TOOLS, **CUSTOM_TOOLS}
    #         return hermes_agent.run(system_prompt=system, user_prompt=user, tools=tools)
    raise NotImplementedError("Wire seam 1 to your Hermes runtime")


def main(project_dir: str):
    project = Path(project_dir)
    board_path = project / BOARD
    for _ in range(1000):  # safety cap; dispatcher stops when no task is actionable
        tasks = parse_tasks(board_path.read_text())
        task, agent = next_task(tasks)
        if not task:
            print("No actionable task. Done or blocked.")
            return
        print(f"→ T{task['id']} [{task['status']}] → {agent}: {task['title']}")
        run_agent(agent, task, project)
        # TODO(seam 2): agent edits the board itself; loop re-reads it next pass.


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ".")

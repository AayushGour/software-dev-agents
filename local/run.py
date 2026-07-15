"""
Reference dispatcher for the local org (llama.cpp + Hermes).

It reads task-board.md, finds the next actionable task, loads that agent's
prompt + instructions + project context, and runs the Hermes agent with
hermes_tools. Agents coordinate through files only.

Wire the two seams marked TODO to your own runtime, then:  python run.py <project_dir>
"""

import re
import sys
from pathlib import Path

AGENTS_DIR = Path(__file__).parent / "agents"
INSTRUCTIONS = (Path(__file__).parent / "instructions.md").read_text()

# Custom tools (tools/registry.py) — handed to the agent next to hermes_tools.
CUSTOM_TOOLS = {}
try:
    sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))
    from registry import TOOLS as CUSTOM_TOOLS  # e.g. {"web_search": <callable>}
except Exception as e:  # tools optional — run without them
    print(f"(no custom tools loaded: {e})")

# task line: - T2 owner=senior-dev title="build /auth" deps=T1 status=todo
TASK_RE = re.compile(
    r"-\s*T(?P<id>\S+)\s+owner=(?P<owner>\S+)\s+title=\"(?P<title>[^\"]*)\""
    r".*?(?:deps=(?P<deps>\S+))?\s*status=(?P<status>\S+)"
)

ACTIONABLE = {"todo", "review", "test"}  # states the dispatcher will pick up


def parse_tasks(board: str):
    tasks = []
    for line in board.splitlines():
        m = TASK_RE.search(line)
        if m and m.group("id").isalnum():  # skip format/example lines like T{id}
            d = m.groupdict()
            d["deps"] = [x for x in (d["deps"] or "").split(",") if x and x != "-"]
            tasks.append(d)
    return tasks


def next_task(tasks):
    done = {t["id"] for t in tasks if t["status"] == "done"}
    for t in tasks:
        if t["status"] in ACTIONABLE and all(dep.lstrip("T") in done for dep in t["deps"]):
            # review → senior-dev reviews; test → tester validates; else the task owner
            agent = {"review": "senior-dev", "test": "tester"}.get(t["status"], t["owner"])
            return t, agent
    return None, None


def load_agent_prompt(agent: str) -> str:
    return (AGENTS_DIR / f"{agent}.md").read_text()


def build_context(project: Path) -> str:
    parts = []
    for name in ("project-context.md", "coding-standards.md", "task-board.md"):
        f = project / name
        if f.exists():
            parts.append(f"### {name}\n{f.read_text()}")
    return "\n\n".join(parts)


def run_agent(agent: str, task: dict, project: Path):
    system = f"{load_agent_prompt(agent)}\n\n---\n# Instructions\n{INSTRUCTIONS}"
    user = (
        f"Project dir: {project}\n"
        f"Your task: T{task['id']} — {task['title']}\n"
        f"Current status: {task['status']}\n\n"
        f"# Project context\n{build_context(project)}\n\n"
        "Do exactly this task. Use hermes_tools. When done, update the task's "
        "status line in task-board.md and append one log line."
    )
    # TODO(seam 1): call your llama.cpp + Hermes agent here, giving it hermes_tools
    #   (read_file, write_file, append_file, grep, list_dir, run) PLUS CUSTOM_TOOLS.
    #   e.g.  tools = {**HERMES_TOOLS, **CUSTOM_TOOLS}
    #         return hermes_agent.run(system_prompt=system, user_prompt=user, tools=tools)
    raise NotImplementedError("Wire seam 1 to your Hermes runtime")


def main(project_dir: str):
    project = Path(project_dir)
    board_path = project / "task-board.md"
    for _ in range(1000):  # safety cap; dispatcher stops when no task is actionable
        tasks = parse_tasks(board_path.read_text())
        task, agent = next_task(tasks)
        if not task:
            print("No actionable task. Done or blocked.")
            return
        print(f"→ T{task['id']} [{task['status']}] → {agent}: {task['title']}")
        run_agent(agent, task, project)
        # TODO(seam 2): agent edits task-board.md itself; loop re-reads it next pass.


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ".")

# Task board — <project>

architect creates/assigns. Each agent edits its own task's status.
Dispatcher (run.py) runs the next actionable task. review→senior-dev, test→tester.

Line format (id is a number; deps `-` if none):
`- T{id} owner={agent} title="{title}" deps={ids} status={todo|wip|review|test|done|blocked}`
owners: business-analyst | architect | senior-dev | junior-dev | devops | tester

## Plan mode
- T0 owner=business-analyst title="requirements -> project-context.md" deps=- status=done
- T1 owner=architect title="design + standards + task split" deps=- status=wip

## Dev mode
- T2 owner=senior-dev title="build /auth API" deps=T1 status=todo
- T3 owner=junior-dev title="add login form" deps=T1 status=todo
- T4 owner=devops title="CI pipeline" deps=T2 status=todo
- T5 owner=tester title="validate auth vs AC" deps=T2 status=todo

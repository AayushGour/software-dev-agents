# Decisions — why the harness is built this way

A running log of non-obvious design decisions for this harness (the AI dev-org). Newest at top. Each entry: **what** was decided and **why** (+ the alternative rejected). This file documents the *harness itself*; it is not copied into installed projects.

---

## 2026-07 — Team sizing: one dial (S/M/L), PM sets, architect composes
**What:** PM tags each project/request `S`/`M`/`L` at intake; that sets the default team + how much ceremony; architect adjusts within it during team formation.
- S: 1 dev + self-verify, skip plan mode. M: full loop (plan→build→reviewer→tester), default team. L: full team + specialists + parallel devs on own branches.
**Why:** the org needs to fit micro→large work without either drowning a one-line fix in ceremony or under-staffing a big build. A single size dial owned by the existing front door (PM) is the least machinery that achieves it.
**Rejected:** a 5-tier (micro→XL) matrix with per-tier parallelism counts and a per-task ceremony ladder — over-engineered; too many knobs for a prompt-driven team to track. Collapsed to 3 buckets.

## 2026-07 — Integrity rule 1: single-writer task board (no race)
**What:** a *spawned* worker never edits `task-board.md`; it returns status to its spawner, and the spawner writes the board. Parallel code at size L uses branch-per-task; same-file tasks serialized via `deps`.
**Why:** `task-board.md` is one file with many would-be writers. Parallel `Task` spawns doing read-modify-write on it = lost updates. Funnelling all board writes through the single spawner removes the race without a lock or a DB. Mirrors the logs design (one file per agent = collision-free).
**Rejected:** per-task files + a status-generator script — more scalable at hundreds of tasks but adds a second storage mechanism; deferred until a real XL project needs it (YAGNI).

## 2026-07 — Integrity rule 2: `done` is earned, tester-only, with evidence
**What:** devs can push a task only to `status:test`; only **tester** sets `done`, and only after pasting the real test/lint command output.
**Why:** the DONE gate was self-attested — an agent could claim "tests pass, done" with nothing verifying it. Making `done` a separate role's job gated on pasted command output closes the hallucinated-done hole. Pure prompt-level, so it works in any prod env with no harness hooks.
**Rejected:** an enforcement hook (pre-commit/Stop) running the test suite — real enforcement but needs the project's test command wired and is harness-specific; kept as an optional future add, not the baseline.

## 2026-07 — Integrity rule 3: default security path (not just a specialist)
**What:** reviewer runs a security checklist every review; **any** change touching auth/secrets/PII/user-input/external-I/O requires a mandatory security pass before `done`.
**Why:** security previously only entered as an optional specialist "if the architect hired one." Routine auth/data changes had no guaranteed security eyes. A checklist on every review + a hard trigger gives every sensitive change coverage regardless of team size.
**Rejected:** a standing 11th `security-reviewer` core role — coverage is strong but it burdens every project (even a static page) with an extra standing agent + handoff.

## 2026-07 — P0 with no human: default-safe action, never silent stall
**What:** if a P0 fires and no human is reachable, PM takes the safe action (roll back / disable flag / halt deploy), keeps escalating, and logs it — rather than blocking forever waiting on a human.
**Why:** human escalation was a single point of failure; "wait for human" with no fallback stalls the whole pipeline and can leave prod broken. A safe hold is always better than an unbounded stall.

## 2026-07 — Cost caps: deliberately deferred
**What:** no budget guard / fan-out ceiling in the prompts.
**Why:** the org must stay generic to any prod environment; hard cost caps are deployment-specific and would bake one operator's economics into the shared prompts. Model tier per role (opus for architect/reviewer reasoning, sonnet default, haiku for junior-dev) already biases cost sensibly. Revisit if a concrete budget policy is needed.

## 2026-07 — Team formation: architect is team lead, can author specialists
**What:** after the plan is clear, architect reviews the 10 core roles vs the project's needs and — only for a genuine ongoing domain gap — authors a specialist from `.claude/agent-template.md` into `.claude/agents/`. PM consults + logs it.
**Why:** a fixed 10-role team can't cover every domain (ML, mobile, a niche stack). Letting the team lead add a scoped specialist keeps the default team small while allowing project-specific depth.
**Confirmed:** Claude Code hot-loads new `.claude/agents/*.md` mid-session (docs: sub-agents), so a specialist is usable the same session with no restart — the flow doesn't depend on an unverified claim. (The agents dir must exist at session start, which it does — we ship it.)

## 2026-07 — ui-ux-pro-max skill: vendored, run via Bash not the Skill tool
**What:** the design-intelligence skill is vendored into `.claude/skills/`; ux-designer runs its `search.py` directly with Bash. `SKILL.md`'s `${CLAUDE_PLUGIN_ROOT}` paths were rewritten to project-root-relative.
**Why:** (a) a subagent should not list `Skill` in its `tools` (per docs) — direct Bash on the script is the reliable path and was the cause of an earlier indefinite hang; (b) `CLAUDE_PLUGIN_ROOT` is set only for *plugin* skills — vendored into a project it is unset, producing a broken path. The script resolves its own data via `Path(__file__)`, so only the path to `search.py` matters. See `.claude/skills/ui-ux-pro-max/SOURCE.md`.

## 2026-07 — Brand design briefs: fetch from GitHub, don't vendor
**What:** ux-designer pulls real-site DESIGN.md briefs on demand from `VoltAgent/awesome-design-md` via `curl`, rather than vendoring the catalog.
**Why:** the GitHub files are the full source (getdesign.md renders from them); fetching live keeps installs light and always-current with zero sync burden. Falls back to the local DB when offline / brand absent.

## 2026-07 — Folder layout: claude-code/.claude mirrors the installed project
**What:** `claude-code/.claude/` holds exactly what an installed project's `.claude/` gets (agents, instructions, working-doc templates, skill, agent-template). `setup-team.py` is a straight copy.
**Why:** originally the source kept `instructions.md` and templates outside `.claude/`, so every `.claude/...` reference in the agents was dead when browsing the source and only resolved after install — and agents run in-place couldn't read their own rules. Mirroring the install layout makes references resolve both in-place and post-install, and makes setup a plain copy.

## 2026-07 — setup-team.py: seed-once working docs, framework files upgradable
**What:** `--force` refreshes framework files (agents, instructions, skills, README, .mcp.json) but never overwrites the per-project working docs (`project-context.md`, `coding-standards.md`, `task-board.md`, `design.md`). Logs are not shipped (agents create their own on first write).
**Why:** users need to pull new agent prompts/skills without losing filled-in project state. An all-or-nothing `--force` destroyed real data; seed-once protects it. Logs are runtime artifacts, so shipping stubs was wrong.

## 2026-07 — One README, kept out of the project root
**What:** a single root `README.md` is the source of truth; on install it lands at `.claude/README.md`. The only file placed at the project root is `.mcp.json`.
**Why:** two drifting READMEs (root said 7 roles, claude-code said 10) is a maintenance trap — collapsed to one. Installing it to `.claude/` avoids clobbering the target project's own root README. `.mcp.json` must sit at the project root because Claude Code only discovers project MCP servers from `<project>/.mcp.json`.

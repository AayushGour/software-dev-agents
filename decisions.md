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

## 2026-08 — Review-driven hardening: orchestrator brief, evidence-gated done, self-healing search, skills
**What:** (1) `claude-code/CLAUDE.md` — an orchestrator brief seeded to the project root (never overwritten), because Claude Code's main thread never auto-reads `.claude/instructions.md`; it now carries routing, board-pen duty, delegation spec, cost rules, and a no-relayed-consent rule. (2) Integrity rule 2 reworded: tester *authorizes* `done` (PASS + pasted evidence), the board writer *records* it as `status:done  evidence:<ref>` — resolving the rule-1/rule-2 collision for a spawned tester; enforced mechanically by a new PreToolUse hook (`tools/board_lint.py`) that blocks evidence-less done lines. (3) `web_search` is self-healing — it calls `ensure()` itself and starts the SearXNG container, fixing the dead-from-session-2 path caused by the SessionEnd stop hook; `ensure_searxng` also granted to every agent holding `web_search`. (4) `project-context.md` decisions follow the same single-writer discipline as the board (spawned workers return decisions in their handoff). (5) junior-dev is self-contained (no 2.6K-token shared rulebook on haiku). (6) Two on-demand skills added — `security-review`, `data-modeling` (content adapted from myOrganisation's database-architect) — plus stolen orchestration-efficiency rules (carry findings downward, don't subagent a grep, context tiering) and the anti-prompt-injection consent rule from myOrganisation's scrum-master.
**Why:** two independent adversarial reviews (harness vs myOrganisation) converged on the same severe flaws: uninstructed main thread, contradictory done-ownership, prompt-only gates, a structurally dead research path, a shared-file write race, and instruction decay on the weakest model. Fixes convert prompts into structure where possible (hook, tool grants, single-writer), and adopt Agent-Skills progressive disclosure so expertise costs ~nothing until triggered.

## 2026-08 — Vendored 6 external skills (discovered via claudeskills.info)
**What:** `tdd` + `diagnosing-bugs` (mattpocock/skills@0ab1b63, MIT), `webapp-testing` (anthropics/skills@0a64e39, Apache-2.0), `property-based-testing` + `differential-review` (trailofbits/skills@7be90d6, CC-BY-SA-4.0), `prd` (github/awesome-copilot@83561bd, MIT) — into `.claude/skills/`, each with a `SOURCE.md` (origin, commit, license, what was dropped). Wired: senior-dev → tdd + diagnosing-bugs; tester → webapp-testing + property-based-testing; reviewer → differential-review (the security hard-trigger's deep pass) + PBT reviewing lens; business-analyst → prd on M/L asks. Dropped from vendored copies: OpenAI agent manifests, plugin evals, logos, the differential-review subagent (reviewer runs that phase inline via its adversarial.md).
**Why:** claudeskills.info is a usable discovery layer (42k+ skills) but its install counts are repo-level and unreliable — selection was by author reputation (Anthropic, Trail of Bits, GitHub, Matt Pocock) + content audit. Every skill was security-audited pre-vendor (risky-pattern grep + full read of all executables: `with_server.py` and `hitl-loop.template.sh` are local-only, no network egress). These fill real gaps the org reviews flagged: no debugging methodology, no browser-evidence path for the tester, example-only testing, no requirements-discovery interview, and a checklist-only security pass. Skipped deliberately: mutation-testing (locked to ToB's mewt/muton tools), insecure-defaults (plugin-shaped, no plain skill dir), accessibility (ux-designer already carries WCAG 2.2 AA + ui-ux-pro-max), mattpocock code-review (overlaps the reviewer's Google eng-practices method), skill-vetter (unknown author).

## 2026-08 — One rulebook: instructions.md merged into root CLAUDE.md
**What:** `.claude/instructions.md` is gone; its full content (modes, team formation, intake, size dial, shared files, code brain, logging, task line, delegation, 4 integrity rules, DONE gate, common rules, roles) now lives in the project-root `CLAUDE.md`, alongside the orchestrator brief — one merged, deduplicated rulebook with a `<!-- harness-team-protocol -->` marker as line 1. All 10 agent first-lines + agent-template now say "Read CLAUDE.md (project root) first"; junior-dev stays self-contained. `setup-team.py` treats CLAUDE.md as a framework file (`--force` upgrades it) but only when the existing root CLAUDE.md starts with the marker — a user's own CLAUDE.md is kept untouched with a "merge manually" notice.
**Why:** two rule files created a split brain: the main thread auto-loaded only CLAUDE.md, agents read only instructions.md, and shared rules (board pen, consent, skills roster) had started duplicating across both. One file = one source of truth for orchestrator and workers alike, auto-loaded where Claude Code actually looks. The marker check resolves the framework-vs-user-data conflict that a root-level file has and `.claude/` files never had.

## 2026-08 — Enforcement hardening (external review round 2)
**What:** (1) `board_lint.py` v2 — PreToolUse matcher now includes **Bash**: any write-shaped Bash command touching `task-board.md` is blocked outright, funneling all board changes through the linted Edit/Write path; and `evidence:` refs are now **resolved**, not substring-checked — the file must exist (searched vs `.claude/` and project root) and a `#T<id>` anchor must appear in its content, so `evidence:whatever` no longer passes. (2) New debounced **PostToolUse hook** (`tools/code_review_graph/refresh_graph.py`, 120s debounce, skips .claude//.git//markdown) auto-refreshes the code brain after source edits — the "remember to rebuild" rule is deleted; `build_or_update_graph_tool` stays as manual override. (3) **`bounces:N`** field on the task line: every reviewer/tester REJECT increments it; at `bounces:3` the loop stops and the task escalates to the human — replaces the undefined "repeated test failures" trigger. (4) Doc honesty: unsourced "~82× fewer tokens" cut from the rulebook; README now labels `local/` a design sketch (unwired seams, no hooks, integrity rules unenforced there).
**Why:** a second external review correctly showed the enforcement layer was thinner than the docs claimed: the evidence gate was a substring check, Bash was an unhooked board-write path available to five agents, reject loops had no bound, and graph freshness relied on agent self-assessment. Known remaining limits, accepted deliberately: hooks can't see subagent identity (dev-ceiling and `deps` serialization stay prose — a Claude Code runtime constraint), and evidence resolution proves the tester log line exists, not that its pasted output is genuine.

## 2026-09 — Research agents: researcher, deep-researcher, and special mode
**What:** Two roles — `researcher` (leaf: one question, no fan-out, no files) and
`deep-researcher` (orchestrator: recon → decompose → fan out → synthesize → report to
`.claude/research/`). Three modes chosen per invocation via a **main-thread depth menu**
(Quick 1 / Deep 5 / Special 21 / Custom): `deep` fans out with stock generic children
specialised by prompt; `special` authors tailored `rsr-<domain>.md` specialists under
`.claude/agents/research/` that persist for reuse — at depth ≥ 1 these are built as
orchestrator variants, deep-researcher's whole working body copied in (including its
`## Fences` and `## Special mode` sections), not a leaf with extra tools bolted on, and
any child that will itself fan out is handed `MODE` and `BREADTH` alongside remaining
depth or it stalls on its own missing-budget rule. Wired through one `## Research` block
in `CLAUDE.md` rather than editing ten agent files. `tools/agent_lint.py` enforces the
frontmatter invariants. Mirrored into `local/` for parity, fanning out via task-board rows.

**Why:** the team had research tools but no research role — every agent researched inline,
burning its own planning context, with no budget and no artifact. Four platform facts
shaped the design and each corrected an earlier assumption: subagent nesting is real but
capped at 3 layers; `Agent(type)` allowlists are **ignored inside a subagent definition**,
so containment is a prompt rule and the linter covers what it can; an omitted `tools:` key
inherits every subagent tool, which would silently stop the leaf being a leaf; and
`AskUserQuestion` is unavailable to subagents, which is why the depth menu must fire in the
main thread. Rejected: a fixed typed roster (too rigid for arbitrary domains), and having
`deep-researcher` hand a spawn plan back to the main thread (kills the context isolation
that makes fan-out worth doing).

## 2026-10 — Code brain: code-review-graph replaced by graphify
**What:** `tools/code_review_graph/` → `tools/graphify/`. `.mcp.json` server `graphify` runs
`uvx --from 'graphifyy[mcp]<0.10' graphify-mcp` (pinned below 0.10:
pre-1.0 package, and agent allowlists hardcode its tool names); the SessionStart/PostToolUse hooks now run a
detached `graphify update .` (local tree-sitter AST, no LLM, no API key) into the gitignored
`graphify-out/`. Agent allowlists move to `mcp__graphify__*` (`query_graph`, `get_node`,
`get_neighbors`, `shortest_path`, `god_nodes`, `graph_stats`, `get_community`); blast radius,
which graphify has no MCP tool for, is `graphify affected "<symbol>"` via Bash for
senior-dev and reviewer.
**Why:** code-review-graph wasn't working in practice. graphify's code path is lighter (no
torch/embeddings download), and its MCP server starts before the graph exists and hot-reloads
`graph.json`, so a background rebuild needs no restart. Lost: embedding-based semantic search
(`query_graph` is keyword/BFS), the risk-scored `detect_changes` (reviewer uses `git diff` +
`affected` instead), and the MCP-side "build now" tool (agents with Bash run `graphify update .`).


## 2026-10 — One canonical team source; interactive multi-platform installer
**What:** `claude-code/` is now the single source of truth for the team. `setup-team.py` is a
thin entry point to `installer/`: `source.py` loads the canonical agents, rulebook, skills,
working docs, hooks and MCP servers (frontmatter parsed by `tools/agent_lint.py`, so there is
one parser); `platforms/<key>.py` adapters translate it at install time; `cli.py` is
interactive in a terminal (project folder, platform multi-select with detection, force,
confirm) and fully flag-driven otherwise (`--platforms`, `--force`, `--yes`). The Claude
adapter's output is byte-identical to the old script's. `local/agents/`, `local/templates/`
and `local/instructions.md` are deleted: `local/run.py` loads the canonical agent bodies and
rulebook and parses the canonical board format; `local/runtime.md` holds only the
runtime differences (hermes_tools substitutions, board-row delegation, no hooks).
**Why:** the user is adding Cursor, Gemini CLI, Codex, OpenCode, Hermes Agent and more.
Hand-kept per-platform copies had already drifted once (`local/` had 9 of 12 roles, a
different board format, and older prompts), so every platform must be generated from one
definition. Claude Code's format was kept as the canonical one because it is the richest
(tools, model, skills, hooks) and keeps in-repo dogfooding working with no migration.
Accepted cost: the local runtime loses its hand-compressed short prompts for small models.
Writing shared content once *inside the installed project* (one rulebook, one skills dir
for all selected platforms) is scoped separately before any config changes.

## 2026-10 — Shared install: AGENTS.md rulebook, .agents/skills, write-once in the project
**What:** the rulebook is `claude-code/AGENTS.md` (was `CLAUDE.md`); `claude-code/.claude/CLAUDE.md`
is a one-line `@../AGENTS.md` import — in `.claude/`, not the root, because a real Copilot CLI
run showed it reads a root `CLAUDE.md` *and* `AGENTS.md`, loading the rulebook twice (+5.9k
input tokens); with the stub in `.claude/` both Copilot and Claude Code load it once, and
Claude Code still loads a user's own root `CLAUDE.md` alongside. Skills moved from `claude-code/.claude/skills/` to
`claude-code/.agents/skills/`, and every agent/rulebook path now reads them there. The installer
writes shared content once (`AGENTS.md`, `.agents/skills`, `.claude/agents`, hooks, `.mcp.json`,
working docs) and each platform adds only what it can't read natively: Claude Code gets the
`.claude/CLAUDE.md` stub plus per-skill links in `.claude/skills/` (symlink → junction → copy); Cursor and
Copilot get nothing extra. `AGENTS.md`/`CLAUDE.md` content lives in a `harness:begin/end` block so
user text survives. `.agents/harness.json` records the platforms and every generated item, so a
deselected platform is cleaned up without deleting anything the user changed. `--force` migrates
pre-AGENTS.md installs. A "Platform notes" section maps Claude tool names for other runtimes;
a test keeps the wrapped rulebook under Antigravity's 24 KB per-file cap.
**Why:** `AGENTS.md` is read natively by every target except Claude Code, which documents the
`@AGENTS.md` import; `.agents/skills` is read by every target except Claude Code, which documents
following skill symlinks. So one copy serves all platforms. Tool names in agent files were kept as
Claude's (Cursor ignores `tools:`, Copilot maps them) rather than rewritten. Facts and sources:
`docs/superpowers/specs/2026-10-02-multi-platform-shared-install-scope.md`. Codex, OpenCode,
Antigravity, Hermes, Amp and Kiro followed in the next entry.

## 2026-10 — Hook adapter + generated platforms (Codex, OpenCode, Antigravity, Hermes, Amp, Kiro)
**What:** `tools/hook_adapter.py` runs the Claude-shaped hooks on other platforms: it turns Codex
`apply_patch` patch text, Antigravity `toolCall` args and OpenCode plugin args into Claude's
Write/Edit/MultiEdit/Bash payload, runs the script at the project root, and maps a block to the
platform's protocol. The installer generates, per platform, only config it can't share: agent
*stubs* whose body points at `.claude/agents/<role>.md` (Kiro uses its native `file://` prompt),
MCP config derived from `.mcp.json` (merged key-by-key into the user's own JSON; a managed block in
Codex's TOML), and hook wiring through the adapter (Codex `hooks.json`, an OpenCode plugin,
Antigravity's `hooks.json` group). Stubs come from the project's own `.claude/agents`, so re-running
setup wires up architect-authored specialists and removes stubs for deleted ones. Hermes gets a
printed `config.yaml` snippet: its MCP and hooks are user-global and are not written.
**Why:** `board_lint.py` keys on Claude tool names and fails open on anything else, so without the
adapter the DONE gate would silently stop enforcing on Codex (edits arrive as `apply_patch`).
Verified live: Codex and OpenCode both blocked an evidence-less `status:done` edit through the
generated hooks, Codex's spawned `tester` stub answered with its role file's DONE line (pointer
followed), and Codex/OpenCode load the rulebook once, all 9 skills and the 3 MCP servers (Codex
only once the project is trusted — a `-c` override doesn't count). Found live: Hermes truncates
context files at 20,000 chars (head 70% + tail 20%, with a marker telling the model to read the
full file), so the ~23.3k-char rulebook's middle is reached there by a file read; this Hermes has
no `skills trust`, so skills are read by path. Not verified live: Cursor and Amp (not logged in),
Antigravity and Kiro (not installed) — format facts are sourced in the scope doc. Unknown: whether
Cursor lists agents twice when `.codex/agents` stubs sit beside `.claude/agents`.

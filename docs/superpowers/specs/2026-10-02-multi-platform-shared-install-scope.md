# Multi-platform install, option 2 (one shared copy in the installed project): scope

**Date:** 2026-10-02
**Status:** Scoping only. Nothing is implemented. Facts were checked against official docs on 2026-10-02.
Source IDs such as `[C1]` point to the list at the bottom. Anything not checked is marked **UNVERIFIED**.
**Companion:** "option 1" (one canonical definition per agent/rule/skill in the REPO, with
per-platform generators) is being built separately. This doc covers the INSTALLED project only:
write each shared asset once there, and have each platform's config point to that one copy.

## 0. Headline findings (read first)

1. **Gemini CLI is retired.** Consumer access ended on 2026-06-18. The successor is **Antigravity CLI (`agy`)**, and enterprise licences keep the legacy CLI [G0]. Treat "Gemini" in the installer as **Antigravity CLI**, and offer legacy Gemini CLI only as an optional enterprise target.
2. **Windsurf now redirects to Devin Desktop docs** (`docs.windsurf.com` → `docs.devin.ai/desktop`; config moved to `.devin/`) [W1][W2]. **Roo Code shut down** on 2026-05-15 and merged back into Cline [R1].
3. **"Hermes" means Nous Research's Hermes Agent** (`hermes`, `~/.hermes/`) [H1]. `local/` in this repo is an unrelated llama.cpp dispatcher and is not affected.
4. **`AGENTS.md` is now the common rulebook file.** Every target reads it natively except Claude Code with a `CLAUDE.md` present. Claude Code v2.1.277+ reads `AGENTS.md` only when no `CLAUDE.md` exists; otherwise it needs a `CLAUDE.md` containing `@AGENTS.md` [C1].
5. **`.agents/skills/` is the common skills directory** (Codex, Cursor, Antigravity, Gemini, OpenCode, Copilot, Amp, Hermes). **Claude Code is the exception:** it reads only `.claude/skills/`. It does document following symlinked skill folders and loading a shared target once [C2].
6. **Claude-format files are read by other platforms too:**
   - `.claude/agents/*.md` is read by Cursor [CU2], Copilot CLI [GH2] and VS Code [V2].
   - `.claude/settings.json` hooks are read by Cursor (on by default) [CU6], Copilot CLI [GH4] and VS Code (opt-in) [V5].
   - `.mcp.json` is read by Copilot CLI [GH2] and the VS Code Agent Host [V4].
   So keeping `.claude/agents`, `.claude/settings.json` and `.mcp.json` canonical covers 4 platforms at no extra cost.
7. **Size limit.** Our rulebook is 22,837 bytes. Limits elsewhere:

   | Platform | Limit | Our rulebook |
   |---|---|---|
   | Codex | 32 KiB for all instruction files combined [X1] | fits |
   | Antigravity | 24 KB per file [AG1] | fits, close to the limit |
   | Devin Desktop/Windsurf | 12,000 chars per workspace rule file [W1] | would be truncated |

## 1. Per-platform fact sheets

### 1.1 Claude Code
| Area | Fact | Src |
|---|---|---|
| Rules | `./CLAUDE.md` or `./.claude/CLAUDE.md`, plus `.claude/rules/*.md` (frontmatter `paths`). Loaded from the cwd and its parents; subdirectories load lazily; files are concatenated. `@path` imports: relative to the importing file, max 4 hops; imports outside the project need one approval. | [C1] |
| AGENTS.md | Native from v2.1.277, **only if no CLAUDE.md/CLAUDE.local.md exists in the cwd or above**. A `CLAUDE.md` containing `@AGENTS.md` is the documented sharing pattern, and the import never double-loads. Anything under `.agents/` is not read. Symlink is not recommended on Windows. | [C1] |
| Agents | `.claude/agents/**/*.md` (recursive). Frontmatter: `name`, `description`, `tools` (comma string or list), `disallowedTools`, `model` (`sonnet`/`opus`/`haiku`/`fable`/full id/`inherit`), `skills`, `mcpServers`, `hooks`, `memory`, `effort`, `isolation`. MCP tool names: `mcp__<server>__<tool>`. | [C3] |
| Skills | `.claude/skills/<name>/SKILL.md`, read from cwd up to the repo root. **Does not read `.agents/skills`.** A `<name>` entry may be a symlink, and a shared target is loaded once. | [C2] |
| MCP | `.mcp.json` → `mcpServers{}`. stdio: `command,args,env`. Remote: `type:"http",url,headers`. Supports `${VAR}`/`${VAR:-d}`. No include mechanism. | [C4] |
| Hooks | `.claude/settings.json` → `hooks.{SessionStart,SessionEnd,PreToolUse,PostToolUse,…}[{matcher,hooks:[{type:"command",command}]}]`. Exit code 2 blocks. (This is the harness's current, working config.) | [C5] |
| Other | Per-agent `model:` is supported. | [C3] |

### 1.2 Cursor (IDE + CLI)
| Area | Fact | Src |
|---|---|---|
| Rules | `.cursor/rules/*.mdc` (frontmatter `description`/`globs`/`alwaysApply`; plain `.md` is ignored). `AGENTS.md` at the root and in subdirectories. `@file` references. | [CU1] |
| CLAUDE.md | The "Include third-party Plugins, Skills and other configs" toggle loads `CLAUDE.md` and `.claude/skills`, but not `.claude/rules`. | [CU7] |
| Agents | Reads `.cursor/agents/`, **`.claude/agents/`** and `.codex/agents/` (on a name clash, `.cursor` wins). Frontmatter: `name`, `description`, `model` (`inherit` or an id), `readonly`, `is_background`. **No tools allowlist field.** Subagents inherit all parent tools, including MCP. Nesting is limited to 2 levels. | [CU2] |
| Skills | `.agents/skills/`, `.cursor/skills/`, plus `.claude/skills/` and `.codex/skills/`. | [CU3] |
| MCP | `.cursor/mcp.json` → `mcpServers{command,args,env,envFile,url,type}`. Interpolation uses `${env:X}` and `${workspaceFolder}`. **Does not read `.mcp.json`.** | [CU4] |
| Hooks | `.cursor/hooks.json` `{version:1,hooks:{sessionStart,sessionEnd,preToolUse,postToolUse,…}}`. Exit code 2 = deny. Project hooks run from the project root. Also **loads Claude hooks from `.claude/settings.json`** (toggle on by default), mapping `Bash→Shell` and `Edit/Write→Write`. | [CU5][CU6] |

### 1.3 OpenAI Codex CLI
| Area | Fact | Src |
|---|---|---|
| Rules | `AGENTS.override.md` › `AGENTS.md` › `project_doc_fallback_filenames`, one file per directory, git root down to cwd, concatenated. `project_doc_max_bytes` defaults to 32 KiB. **No imports.** | [X1] |
| Agents | `.codex/agents/*.toml`. Required: `name`, `description`, `developer_instructions`. Optional: any `config.toml` key (`model`, `model_reasoning_effort`, `sandbox_mode`, `mcp_servers`, `skills.config`). **No tools allowlist**; restriction is done through `sandbox_mode` and MCP `enabled_tools`. Delegates when the user, AGENTS.md or a skill asks it to. Does not read `.claude/agents`. | [X3] |
| Skills | `.agents/skills` in the cwd, its parents and the repo root; `~/.agents/skills`. Follows symlinks. | [X2] |
| MCP | `.codex/config.toml` `[mcp_servers.<n>]`. stdio: `command,args,env,env_vars,cwd`. HTTP: `url,bearer_token_env_var,http_headers`. Also `enabled_tools`/`disabled_tools`. Does not read `.mcp.json`. | [X4] |
| Hooks | `.codex/hooks.json` `{hooks:{SessionStart,SessionEnd,PreToolUse,PostToolUse,…}}`. Exit code 2 or `permissionDecision:"deny"` blocks. File edits arrive as `tool_name:"apply_patch"`, with the patch text in `tool_input.command`; matchers `Edit`/`Write` alias to it. Hooks run with the session cwd. **Each hook definition needs a one-time trust** (`/hooks`). | [X5] |
| Other | `.codex/` layers (config, hooks, rules) load **only for trusted projects**. | [X6] |

### 1.4 Antigravity CLI (`agy`, successor to Gemini CLI)
| Area | Fact | Src |
|---|---|---|
| Rules | `AGENTS.md`/`GEMINI.md`, also `.agents/AGENTS.md` and `.agents/rules/*.md` (rules need a `trigger` frontmatter field). Read by walking up the tree. Includes: `@[label](path)` inlines the file; `@file` only references it. 24 KB per file; 20k-token budget for always-on rules. | [AG1] |
| Agents | `.agents/agents/<name>.md` or `.agents/agents/<name>/agent.md`. Frontmatter: `name`, `description`, `tools` (e.g. `view_file`, `replace_file_content`, `grep_search`, `run_command`), `model` (`inherit`/`flash`/`pro`), `subagent`, `mainAgent`, `mcpServers`, `skills`, `commandExecutionPolicy`. Max nesting depth 10. Does not read `.claude/agents`. | [AG2][AG6] |
| Skills | `.agents/skills/` (the old `.gemini/skills` must be moved). | [AG3] |
| MCP | `.agents/mcp_config.json` → `mcpServers{command,args,env,cwd \| serverUrl,headers}`. **`url`/`httpUrl` are not accepted.** | [AG4] |
| Hooks | `.agents/hooks.json`: named groups `{"<name>":{enabled,PreToolUse,PostToolUse,PreInvocation,PostInvocation,Stop}}`. PreToolUse returns `decision: allow\|deny\|ask…`. **No SessionStart/SessionEnd events.** | [AG5] |

### 1.5 Gemini CLI (legacy; enterprise only after 2026-06-18)
| Area | Fact | Src |
|---|---|---|
| Rules | `GEMINI.md`. `context.fileName` accepts a list (e.g. `["AGENTS.md","GEMINI.md"]`). `@file.md` imports. | [GL1] |
| Agents | `.gemini/agents/*.md`. Frontmatter: `name`, `description`, `kind`, `tools` (`read_file`, `write_file`, `replace`, `run_shell_command`, `mcp_<server>_*`), `model`, `max_turns`. **Subagents cannot call subagents.** | [GL3] |
| Skills | `.gemini/skills/` or the `.agents/skills/` alias (`.agents` wins). | [GL2] |
| MCP / hooks | `.gemini/settings.json` (`mcpServers`; hooks `SessionStart`, `SessionEnd`, `BeforeTool`, `AfterTool`; exit code 2 blocks; project hooks are fingerprinted). | [GL4][AG3] |

### 1.6 OpenCode
| Area | Fact | Src |
|---|---|---|
| Rules | `AGENTS.md` (walks up). Falls back to **`CLAUDE.md` only if there is no AGENTS.md** (`OPENCODE_DISABLE_CLAUDE_CODE=1` turns this off). The `instructions:[paths/globs/urls]` key lives in `opencode.json`. | [O1][O6] |
| Agents | `.opencode/agents/*.md`. Frontmatter: `description` (required), `mode: subagent\|primary\|all`, `model: provider/model-id`, `permission{edit,bash…}`, `temperature`, `tools`. Invoked via the Task tool or `@name`. `.claude/agents` is not read (not documented). | [O2][O6] |
| Skills | `.opencode/skills/`, **`.claude/skills/`** and **`.agents/skills/`**, walking up to the git worktree. | [O3] |
| MCP | `opencode.json` → `mcp{<n>:{type:"local",command:[…],environment,cwd}\|{type:"remote",url,headers}}`. Supports `{env:X}` and `{file:path}`. Does not read `.mcp.json`. | [O4][O6] |
| Hooks | No JSON hooks. A JS/TS plugin in `.opencode/plugins/` handles `session.created`, `session.idle`, `session.deleted`, `tool.execute.before` (block by throwing) and `tool.execute.after`. Does not read `.claude/settings.json`. | [O5] |

### 1.7 Hermes Agent (Nous Research)
| Area | Fact | Src |
|---|---|---|
| Rules | First match wins: `.hermes.md` › `AGENTS.override.md` › **`AGENTS.md`** › `CLAUDE.md` › `.cursorrules`. In a git repo, files are merged from the git root down to the cwd. **No imports.** | [H1] |
| Agents | **No named or custom subagent files.** `delegate_task` is ad hoc and inherits the parent's toolsets. One global `delegation.model`. `max_spawn_depth` is configurable. | [H3] |
| Skills | `~/.hermes/skills/`. Project `.hermes/skills/` and **`.agents/skills/`** need a one-time `hermes skills trust`. **Conflict:** epic [H6] says project skills are not shipped yet. | [H2][H6] |
| MCP | **User-global only:** `~/.hermes/config.yaml` → `mcp_servers{command,args,env \| url,headers}`. Tools are named `mcp_<server>_<tool>`. | [H4] |
| Hooks | User-global `config.yaml` `hooks:` (`on_session_start`, `on_session_end`, `pre_tool_call` returning `{"decision":"block"}`, `post_tool_call`). No project-level hooks. | [H5] |

### 1.8 GitHub Copilot (CLI + VS Code)
| Area | Fact | Src |
|---|---|---|
| Rules | CLI: `.github/copilot-instructions.md`, `.github/instructions/**`, **`AGENTS.md`, `CLAUDE.md`, `GEMINI.md`**, all combined, with identical copies deduped. `@relative/path` is expanded in AGENTS.md, CLAUDE.md and copilot-instructions.md. VS Code: AGENTS.md always; CLAUDE.md with `chat.useClaudeMdFile`; `.claude/rules` supported. | [GH1][V1] |
| Agents | CLI load order: `~/.copilot/agents`, `.github/agents`, **`.claude/agents`**. VS Code: `.github/agents/*.agent.md` and **`.claude/agents/*.md`** (Claude tool names are mapped automatically). Native frontmatter: `name`, `description`, `tools` (aliases `read`/`edit`/`search`/`execute`/`agent`; MCP as `server/*`), `model`, `mcp-servers`, `disable-model-invocation`. | [GH2][V2][GH5] |
| Skills | `.github/skills`, **`.claude/skills`**, **`.agents/skills`**. | [GH3][V3] |
| MCP | CLI: **`.mcp.json`** or `.github/mcp.json`. VS Code: `.vscode/mcp.json` with key **`servers`**; the Agent Host reads `.mcp.json`. | [GH2][V4] |
| Hooks | CLI: `.github/hooks/*.json` `{version:1,hooks:{sessionStart,sessionEnd,preToolUse,postToolUse…}}`. **Also reads `.claude/settings.json`**: PascalCase events get Claude matcher semantics and Claude tool names. Denial is `permissionDecision:"deny"`. VS Code: `.github/hooks`, and `.claude/settings.json` when `chat.useClaudeHooks` is on (no SessionEnd). | [GH4][GH6][V5] |

### 1.9 Other platforms (worth it?)
| Platform | Rules | Agents | Skills | MCP | Hooks | Verdict |
|---|---|---|---|---|---|---|
| **Amp** | AGENTS.md (CLAUDE.md fallback), `@` imports and globs [A1] | not documented | `.agents/skills`, `.claude/skills` [A2] | `.amp/settings.json` `amp.mcpServers` [A3] | not documented | **Tier 2:** cheap (one generated file), but no team delegation |
| **Kiro** | AGENTS.md always included [K3] | `.kiro/agents/*.md\|json`; `prompt` accepts a **`file://` URI**; tools `read`/`write`/`shell`/`@server/tool` [K2] | `.kiro/skills` only [K1] | `.kiro/settings/mcp.json` (via `includeMcpJson`) [K2] | per agent (`agentSpawn`, `preToolUse`, `postToolUse`, `stop`) [K2] | **Tier 2:** agent prompt pointer is native |
| **Devin Desktop (ex-Windsurf)** | AGENTS.md, `.devin/rules` (**12k-char cap**) [W1] | none | `.windsurf/skills`, `.agents/skills` (secondary source) | global only | `.devin/hooks.json`, no session events [W2] | **Tier 3:** skip for now |
| **Cline** | `.clinerules`, AGENTS.md (UNVERIFIED) | UNVERIFIED | `.cline/skills` (secondary) | global (UNVERIFIED) | SDK plugins | **Tier 3:** skip; Roo is dead [R1] |
| **Aider** | `--read CONVENTIONS.md` | none | none | not native (secondary [AI1]) | none | **Skip:** cannot run a team |

**Recommended platform set:** Tier 1 is Claude Code, Cursor, Copilot (CLI+VS Code), Codex, OpenCode, Antigravity, plus Hermes (rules and skills only). Amp and Kiro come next. Skip the rest.

## 2. Option-2 sharing matrix

Preference order: **N** native shared copy > **P** config pointer > **S** tiny stub > **L** symlink > **G** generated per-platform copy. A dash means not applicable.

| Asset | Claude | Cursor | Copilot | Codex | OpenCode | Antigravity | Hermes | Amp | Kiro |
|---|---|---|---|---|---|---|---|---|---|
| Rulebook `AGENTS.md` | **S** `CLAUDE.md` = `@AGENTS.md` | N | N | N | N | N | N | N | N |
| Agents `.claude/agents/*.md` | N | N | N | **S/G** TOML stub | **S/G** md stub | **S/G** md stub | — (pointer text in AGENTS.md) | — | **P** `prompt: file://` |
| Skills `.agents/skills/` | **L** per-skill link (copy on Windows) | N | N | N | N | N | N (after trust) | N | **L** `.kiro/skills/<n>` |
| MCP `.mcp.json` | N | **G** (same schema; L possible) | N | **G** TOML | **G** `opencode.json` | **G** (`serverUrl`) | **G** user-global, opt-in | **G** | **G** (or L, UNVERIFIED) |
| Hooks `.claude/settings.json` | N | N (via toggle) | N | **G** `.codex/hooks.json` (same shape) + adapter | **G** JS shim | **G** partial | user-global, opt-in | — | **G** inside agent |
| Working docs `.claude/*.md` | N | N | N | N | N | N | N | N | N |
| Tools (absolute harness path) | N | N | N | N | N | N | N | N | N |

Notes:
- **Agent stubs.** "S/G" means the platform needs its own frontmatter (different keys, tool names and model ids), which has to be generated. The body can be a one-line pointer: `Your full role prompt is .claude/agents/<name>.md. Read it now and follow it, ignoring its YAML header.` That avoids copying the body. The cost is one extra Read per spawn and some risk the model skims the file. Provide `--inline-agent-bodies` to switch to full copies (option-1 generators already produce these).
- **Working docs** are plain files that agents read by path, so one copy at `.claude/` serves every platform. Only their *location name* is Claude-flavoured.
- **Skills canonical location.** `.agents/skills` should be canonical rather than `.claude/skills`:
  - 8 of 9 targets read `.agents/skills`, while only 5 read `.claude/skills`.
  - The one platform that needs a link (Claude Code) is the one that documents following skill symlinks and deduping them [C2].
  - The platforms that would need links in the other direction (Codex, Antigravity, Hermes) do not all document symlink support.
- **Duplicate skills.** Cursor, OpenCode, Copilot and Amp scan both dirs, so with Claude selected they will see each skill twice. Behaviour is unknown except in Claude Code (dedupes by symlink target). This must be tested.

## 3. Proposed installed layout (all platforms selected)

```
<project>/
  AGENTS.md                     # THE rulebook, inside a harness-managed block:
                                #   <!-- harness:begin v=N --> … <!-- harness:end -->
  CLAUDE.md                     # stub: same managed block containing only "@AGENTS.md"
  .mcp.json                     # MCP source of truth (Claude, Copilot CLI, VS Code Agent Host)
  opencode.json                 # GEN: "mcp" block only                      [OpenCode]
  .agents/
    skills/<9 skills>/          # THE skills (real dirs)
    agents/<12>.md              # GEN stubs: Antigravity frontmatter + pointer body
    mcp_config.json             # GEN                                        [Antigravity]
    hooks.json                  # GEN (PreToolUse/PostToolUse only)          [Antigravity]
    harness.json                # manifest: platforms, generated files + hashes, harness path
  .claude/
    agents/*.md                 # THE agent definitions (Claude format)      [Claude, Cursor, Copilot]
    skills/<n> -> ../../.agents/skills/<n>   # per-skill link (POSIX symlink / Windows junction / copy)
    settings.json               # THE hooks                                  [Claude, Cursor, Copilot]
    project-context.md coding-standards.md task-board.md design.md   # THE working docs (seed-once)
    agent-template.md researcher-template.md README.md research/ logs/
  .codex/
    config.toml                 # GEN: [mcp_servers.*]
    hooks.json                  # GEN: copy of the settings.json hooks block, commands via adapter
    agents/<12>.toml            # GEN stubs (sandbox_mode from tools: no Write/Edit/Bash -> read-only)
  .cursor/mcp.json              # GEN (or symlink to ../.mcp.json)
  .opencode/agents/<12>.md      # GEN stubs (mode: subagent, permission from tools)
  .opencode/plugins/harness-hooks.js         # static shim -> python hook scripts
  .kiro/agents/<12>.md + .kiro/skills/<n> links + .kiro/settings/mcp.json   # Tier 2 only
  .amp/settings.json            # GEN amp.mcpServers                          # Tier 2 only
~/.hermes/config.yaml           # NOT written by default; print the snippet, or write with --hermes-global (consent)
```

**Totals:**
- Shared content is written once: 1 rulebook, 12 agent bodies, 9 skills, 1 MCP definition, 1 hook set, 4 working docs.
- Per-platform files are small generated configs: about 1 + 12 per platform for Codex/OpenCode/Antigravity, and 1 for Cursor/Amp.
- Claude-specific additions are 1 stub and 9 links.

**When only a subset is selected:**
| Selection | What changes |
|---|---|
| Claude only | `AGENTS.md`, `CLAUDE.md` stub, `.claude/*`, `.mcp.json`, `.agents/skills` plus `.claude/skills` links (copies on Windows). Nothing else. |
| No Claude | No `CLAUDE.md` and no `.claude/skills` links. `.claude/agents` and `.claude/settings.json` are still written if Cursor or Copilot is selected; otherwise agent bodies are still needed as the pointer target, so `.claude/agents/` is always written. |
| Deselect on re-run | The manifest lists every generated file. A re-run deletes generated files for platforms no longer selected, only if their hash matches the manifest; otherwise it warns and keeps them. |
| Copilot / Cursor only | Zero generated files (everything is native). |

## 4. Changes to existing harness conventions

| # | Change | Why | Size |
|---|---|---|---|
| 1 | Rulebook moves from root `CLAUDE.md` into **`AGENTS.md`**; `CLAUDE.md` becomes `@AGENTS.md`. Both use a **managed block** (begin/end markers) instead of the current "first line is the marker" rule, so a user's own AGENTS.md or CLAUDE.md content outside the block survives. | Read natively by 8 platforms; Claude reads it via import [C1] | S |
| 2 | Rulebook and agent text: "Read CLAUDE.md (project root) first" becomes "Read AGENTS.md…" (20 occurrences in the agents, plus the rulebook's own "main thread auto-loads this file"). Replace Claude-only wording (`Task`/`Agent` tool, `mcp__x__y` names, "hot-loads within seconds") with platform-neutral phrasing plus a short per-platform note. | On Codex/Hermes, CLAUDE.md is just one line; tool names differ (`mcp_x_y`, `server/tool`) | M |
| 3 | Skills move from `.claude/skills/` to **`.agents/skills/`** (15 path references in the rulebook/agents), with per-skill links into `.claude/skills/`. | See §2 | S |
| 4 | `setup-team.py` gains interactive platform selection: detect `claude`, `cursor-agent`, `copilot`, `codex`, `opencode`, `agy`, `hermes`, `amp`, `kiro-cli` on PATH and pre-tick them. Also adds `--platforms a,b`, `--yes`, a manifest, and a link helper (symlink → Windows junction → copy). | Interactive requirement | M |
| 5 | MCP source of truth stays **`.mcp.json`**; the other files are derived from it. Note `serverUrl` for Antigravity, TOML for Codex, `command` as an array for OpenCode, user-global for Hermes. | Copilot reads it natively | M (shared with option 1) |
| 6 | **Hook adapter** `tools/hook_adapter.py --platform X <script>`: normalises the stdin payload to Claude shape (Codex `apply_patch` patch text → added lines; Cursor `Write`/`Shell`; Antigravity/Gemini tool names) and maps the block result (exit 2, or `permissionDecision`/`decision` JSON). It also resolves the project root, because Codex hooks run in the session cwd [X5], not the root. `board_lint.py` and `refresh_graph.py` currently key on `Edit`/`Write`/`MultiEdit`/`Bash` and fail open on anything else, so **the DONE gate silently stops enforcing** on Codex without this. | Enforcement must not silently vanish | M–L |
| 7 | Working docs stay in `.claude/` (no move). A rename to a neutral dir (e.g. `.team/`) is deferred: it touches about 70 path references plus `board_lint` and existing user data, for cosmetic gain. | Zero data migration | — |
| 8 | Specialist authoring (`agent-template.md`, `researcher-template.md` → runtime-written `.claude/agents/*.md`) stays Claude-format. Only Claude, Cursor and Copilot pick these up at runtime. On Codex/OpenCode/Antigravity, a newly authored specialist needs `setup-team.py --sync` (regenerate stubs) or a restart. Document it as a limit. | Runtime authoring in N formats is out of scope | S (docs) |

**Hook portability (our 4 hooks):**
| Hook | Claude | Cursor | Copilot CLI | Codex | Antigravity | OpenCode | Hermes |
|---|---|---|---|---|---|---|---|
| SessionStart graph build | ✓ | ✓ (via .claude) | ✓ | ✓ | ✗ (no event; PreInvocation per turn is too costly) | ✓ `session.created` | global only |
| PreToolUse board_lint (blocks) | ✓ | ✓, payload names UNVERIFIED | ✓ | ✓ via adapter (`apply_patch`) | ✓ via adapter (`decision:deny`) | ✓ throw | global only |
| PostToolUse graph refresh | ✓ | ✓ | ✓ | ✓ via adapter | ✓ | ✓ | global only |
| SessionEnd searxng stop | ✓ | ✓ | ✓ (`sessionEnd`) | ✓ | ✗ | ~ `session.deleted` (not exit) | global only |

When the stop hook is missing, the container stays up. That is acceptable: `ensure_searxng` is idempotent.

## 5. Migration of an existing install (`setup-team.py <old> --force`)

| Old state | New behaviour |
|---|---|
| Root `CLAUDE.md` starts with `<!-- harness-team-protocol` | Rewrite it as the `@AGENTS.md` stub in a managed block. Write the rulebook into `AGENTS.md`. |
| User-owned `AGENTS.md` exists (no markers) | **Ask:** append a managed block (default), or skip AGENTS.md and keep the full rulebook in CLAUDE.md (Claude-only, other platforms disabled with a warning). |
| `.claude/skills/<shipped-name>/` real dirs | Compare against the shipped content. If unchanged, replace with a link to `.agents/skills/<n>`. If modified, move the user's copy to `.agents/skills/<n>` (their edits win) and link it. User-added skills are untouched; offer to move them. |
| `.claude/agents`, `settings.json`, `.mcp.json` | Unchanged location. `--force` refreshes them as today. Hook commands are re-pointed through the adapter only for generated platform files. |
| Working docs | Untouched (still `SEED_ONCE`). |
| Old install never re-run | Keeps working for Claude exactly as today. Nothing breaks until the installer is re-run. |

## 6. Risks and unknowns (not verified)

1. **Cursor:**
   - Hook payload for Claude-format hooks (`tool_name` "Edit" or "Write"? `new_string` present?) is undocumented [CU6]. A silent fail-open of `board_lint` is possible.
   - Recursion into `.claude/agents/research/` is undocumented.
   - Whether Cursor tolerates `tools:` and `model: sonnet` (not a Cursor id) is undocumented [CU2].
   - Whether Cursor expands `@AGENTS.md` inside CLAUDE.md is unknown (harmless either way).
2. **Copilot CLI:**
   - How `model: sonnet/opus` in `.claude/agents` resolves is unknown.
   - Whether PascalCase `SessionEnd` from `.claude/settings.json` fires is unknown.
   - Whether the rulebook appears twice (AGENTS.md plus the CLAUDE.md import) is unknown; the docs claim identical copies are deduped [GH1].
3. **Codex:**
   - Exact inner shape of hook groups is assumed to be Claude-style `{matcher,hooks:[…]}` [X5].
   - Recursion of `.codex/agents` is undocumented.
   - Trust must be granted by the user: project trust plus per-hook trust [X5][X6]. The installer can only print instructions.
4. **Antigravity:**
   - Docs are thin.
   - There are no session hooks.
   - Symlinked skills are undocumented.
   - The rulebook is 22.8 KB against a 24 KB per-file cap, with no headroom to grow [AG1].
5. **Hermes:**
   - Docs claim project `.agents/skills` works (after trust) while epic [H6] says it is unshipped. Test on the installed version.
   - MCP and hooks are user-global only, so writing them touches `~/.hermes/config.yaml` and needs explicit consent.
   - There are no named agents: the team runs only as "orchestrator reads AGENTS.md and passes role files to `delegate_task`".
6. **Duplicate skills.** When both `.claude/skills` and `.agents/skills` exist, Cursor, OpenCode, Copilot and Amp may list each skill twice.
7. **Windows links:**
   - Symlinks need Developer Mode or admin. Directory **junctions** do not, so use the order symlink → junction → copy.
   - Git does not store junctions as symlinks. If users commit `.claude/skills`, it lands as real files (a copy). Recommend gitignoring `.claude/skills/` when it is generated, and recording it in the manifest.
8. **Delegation depth differs** (Cursor 2, Gemini-legacy 1, Antigravity 10, Hermes configurable). L-size flows (senior-dev → junior-dev, deep-researcher → researchers) may not nest everywhere. This is a rulebook concern and needs a per-platform fallback ("if you cannot spawn, do it inline and say so").
9. **Model mapping.** `sonnet`/`opus` mean nothing outside Claude. The default for generated stubs should be `inherit`, with an optional per-platform map in the installer (e.g. Codex `model`, OpenCode `provider/id`, Antigravity `flash`/`pro`).
10. Pointer-body stubs depend on the model actually reading the role file. Measure this before making it the default.

## 7. Size and suggested order

| Step | Piece | Size | Depends on |
|---|---|---|---|
| 1 | AGENTS.md rulebook + CLAUDE.md stub + managed blocks + wording pass (§4 #1, #2) | M | — |
| 2 | Skills → `.agents/skills` + link helper (symlink/junction/copy) + manifest | S–M | — |
| 3 | Interactive platform picker + `--platforms`/`--yes` + deselect cleanup | M | 2 |
| 4 | Native-only platforms: Copilot + Cursor (validate the §6 #1–2 unknowns by running them) | S | 1–3 |
| 5 | MCP derivation (Cursor, Codex, OpenCode, Antigravity; then Amp, Kiro) | M | option-1 MCP generator |
| 6 | Agent stubs (Codex TOML, OpenCode md, Antigravity md; Kiro `file://`), with `--inline-agent-bodies` | M | option-1 agent generator |
| 7 | Hook adapter + Codex hooks.json + OpenCode plugin shim + Antigravity hooks | M–L | — |
| 8 | Hermes: rules and skills native; print `config.yaml` snippet; opt-in global write | S | 5 |
| 9 | Migration path for old installs + tests (fixture of an old install, re-run `--force`) | M | 1–3 |
| 10 | Tier 2: Amp, Kiro | S each | 5, 6 |

**Interface with option 1:** generators should take `body_mode = inline | pointer` and a `model_map`, and emit into an installed-project root. Option 2 decides per asset which platforms get N/P/S/L/G (matrix §2).

## Sources
- [C1] https://code.claude.com/docs/en/memory · [C2] https://code.claude.com/docs/en/skills · [C3] https://code.claude.com/docs/en/sub-agents · [C4] https://code.claude.com/docs/en/mcp · [C5] https://code.claude.com/docs/en/hooks (and the harness's working `claude-code/.claude/settings.json`)
- [CU1] https://cursor.com/docs/context/rules · [CU2] https://cursor.com/docs/context/subagents · [CU3] https://cursor.com/docs/context/skills · [CU4] https://cursor.com/docs/context/mcp · [CU5] https://cursor.com/docs/agent/hooks · [CU6] https://cursor.com/docs/reference/third-party-hooks · [CU7] https://forum.cursor.com/t/claude-project-level-rules-not-loaded-with-the-include-third-party-toggle-enabled/157087 (Cursor staff reply)
- [X1] https://learn.chatgpt.com/docs/agent-configuration/agents-md · [X2] https://learn.chatgpt.com/docs/build-skills · [X3] https://learn.chatgpt.com/docs/agent-configuration/subagents · [X4] https://learn.chatgpt.com/docs/extend/mcp?surface=cli · [X5] https://learn.chatgpt.com/docs/hooks · [X6] https://learn.chatgpt.com/docs/config-file/config-advanced (developers.openai.com/codex/* now 308-redirects to learn.chatgpt.com)
- [G0] https://developers.googleblog.com/an-important-update-transitioning-gemini-cli-to-antigravity-cli/
- [AG1] https://antigravity.google/docs/rules/ · [AG2] https://antigravity.google/docs/subagents/ · [AG3] https://antigravity.google/docs/cli/gcli-migration/ · [AG4] https://antigravity.google/docs/mcp/ · [AG5] https://antigravity.google/docs/hooks/ · [AG6] https://antigravity.google/docs/cli/commands/agents/
- [GL1] https://geminicli.com/docs/cli/gemini-md/ · [GL2] https://geminicli.com/docs/cli/skills/ · [GL3] https://geminicli.com/docs/core/subagents/ · [GL4] https://geminicli.com/docs/hooks/
- [O1] https://opencode.ai/docs/rules/ · [O2] https://opencode.ai/docs/agents/ · [O3] https://opencode.ai/docs/skills/ · [O4] https://opencode.ai/docs/mcp-servers/ · [O5] https://opencode.ai/docs/plugins/ · [O6] https://opencode.ai/docs/config/
- [H1] https://hermes-agent.nousresearch.com/docs/user-guide/features/context-files · [H2] …/features/skills · [H3] …/features/delegation · [H4] …/features/mcp · [H5] …/features/hooks · [H6] https://github.com/NousResearch/hermes-agent/issues/48970
- [GH1] https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-custom-instructions · [GH2] https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-config-dir-reference · [GH3] https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-skills · [GH4] https://docs.github.com/en/copilot/reference/hooks-configuration · [GH5] https://docs.github.com/en/copilot/reference/custom-agents-configuration · [GH6] https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/use-hooks
- [V1] https://code.visualstudio.com/docs/copilot/customization/custom-instructions · [V2] …/custom-agents · [V3] …/agent-skills · [V4] …/mcp-servers · [V5] …/hooks
- [A1] https://ampcode.com/docs/customize/agents-md · [A2] https://ampcode.com/docs/customize/skills · [A3] https://ampcode.com/docs/customize/mcp
- [K1] https://kiro.dev/docs/skills/ · [K2] https://kiro.dev/docs/custom-agents/configuration-reference/ · [K3] https://kiro.dev/docs/steering/
- [W1] https://docs.devin.ai/desktop/cascade/memories · [W2] https://docs.devin.ai/desktop/cascade/hooks
- [R1] https://x.com/cline/status/2046645935762198953 · [AI1] https://www.wearewarp.com/agents/mcp/aider (secondary) · Agent Skills standard: https://agentskills.io

# deepwiki

AI-generated docs + Q&A for **public** GitHub repos. Hosted MCP server at
`https://mcp.deepwiki.com/mcp` — nothing to run locally.

Use it to understand a dependency/library/framework before building against it.

## Claude Code
Native remote MCP — registered in `claude-code/.mcp.json`. Tools:
- `mcp__deepwiki__ask_question(repoName, question)`
- `mcp__deepwiki__read_wiki_contents(repoName)`
- `mcp__deepwiki__read_wiki_structure(repoName)`

## Local (Hermes)
`tool.py` wraps the remote server via the MCP client SDK (`pip install mcp`).
Registered in `tools/registry.py`:
- `deepwiki_ask(repo, question)`
- `deepwiki_read(repo)`
- `deepwiki_structure(repo)`

`repo` = `"owner/name"`, e.g. `"anthropics/anthropic-sdk-python"`.

## Config
`DEEPWIKI_URL` (default `https://mcp.deepwiki.com/mcp`). Public repos only.

## Smoke test (needs `pip install mcp` + network)
```bash
python -c "import sys; sys.path.insert(0,'tools'); from registry import TOOLS; \
print(TOOLS['deepwiki_ask']('facebook/react','what is the reconciler?')[:400])"
```

"""DeepWiki — AI docs for public GitHub repos, via the hosted MCP server.

Remote MCP at https://mcp.deepwiki.com/mcp. In Claude Code it's a native remote
server (see claude-code/.mcp.json). Here we wrap it as plain callables so the
local Hermes runtime gets the same capability.

Needs:  pip install mcp
"""

import os
import asyncio

DEEPWIKI_URL = os.environ.get("DEEPWIKI_URL", "https://mcp.deepwiki.com/mcp")


def _text(result) -> str:
    """Flatten an MCP CallToolResult into plain text."""
    parts = []
    for block in getattr(result, "content", []) or []:
        parts.append(getattr(block, "text", str(block)))
    return "\n".join(parts).strip()


async def _call(tool: str, args: dict) -> str:
    # imported lazily so the module loads even if `mcp` isn't installed
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    async with streamablehttp_client(DEEPWIKI_URL) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return _text(await session.call_tool(tool, args))


def deepwiki_ask(repo: str, question: str) -> str:
    """Ask a question about a public GitHub repo. repo = 'owner/name'."""
    return asyncio.run(_call("ask_question", {"repoName": repo, "question": question}))


def deepwiki_read(repo: str) -> str:
    """Read the generated wiki for a public GitHub repo. repo = 'owner/name'."""
    return asyncio.run(_call("read_wiki_contents", {"repoName": repo}))


def deepwiki_structure(repo: str) -> str:
    """List documentation topics for a public GitHub repo. repo = 'owner/name'."""
    return asyncio.run(_call("read_wiki_structure", {"repoName": repo}))

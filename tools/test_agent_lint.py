"""Unit tests for agent_lint — frontmatter invariants for .claude/agents/*.md.

Pure logic, no filesystem beyond tmp dirs. Run from the repo root:
    PYTHONPATH=tools python3 -m unittest test_agent_lint -v
"""

import tempfile
import unittest
from pathlib import Path

import agent_lint as al


def write(d: Path, rel: str, body: str) -> None:
    p = d / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body)


LEAF = """---
name: researcher
description: Research specialist — answers ONE question.
tools: Read, Grep, Glob
model: sonnet
---
body
"""


class ParseFrontmatter(unittest.TestCase):
    def test_parses_leading_block(self):
        fm = al.parse_frontmatter(LEAF)
        self.assertEqual(fm["name"], "researcher")
        self.assertEqual(fm["model"], "sonnet")

    def test_none_when_absent(self):
        self.assertIsNone(al.parse_frontmatter("# just a heading\n"))

    def test_tools_absent_is_none_not_empty(self):
        fm = al.parse_frontmatter("---\nname: x\ndescription: y\n---\n")
        self.assertIsNone(al.tools_of(fm))

    def test_tools_split_and_stripped(self):
        self.assertEqual(al.tools_of({"tools": "Read,  Grep , Glob"}),
                         ["Read", "Grep", "Glob"])


class LintTree(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def test_clean_tree_has_no_violations(self):
        write(self.d, "researcher.md", LEAF)
        self.assertEqual(al.lint_tree(self.d), [])

    def test_missing_tools_key_is_a_violation(self):
        write(self.d, "a.md", "---\nname: a\ndescription: d\n---\n")
        self.assertTrue(any("declare tools" in v for v in al.lint_tree(self.d)))

    def test_duplicate_names_across_subdirs_flagged(self):
        write(self.d, "researcher.md", LEAF)
        write(self.d, "research/copy.md", LEAF)
        self.assertTrue(any("duplicate name" in v for v in al.lint_tree(self.d)))

    def test_researcher_must_not_hold_write_or_agent(self):
        bad = LEAF.replace("tools: Read, Grep, Glob",
                           "tools: Read, Grep, Glob, Write, Agent")
        write(self.d, "researcher.md", bad)
        vs = al.lint_tree(self.d)
        self.assertTrue(any("researcher" in v and "Write" in v for v in vs))
        self.assertTrue(any("researcher" in v and "Agent" in v for v in vs))

    def test_research_subdir_requires_rsr_prefix(self):
        write(self.d, "research/grpc.md", LEAF.replace("name: researcher", "name: grpc"))
        self.assertTrue(any("rsr-" in v for v in al.lint_tree(self.d)))

    def test_rsr_agent_requires_description_prefix(self):
        body = LEAF.replace("name: researcher", "name: rsr-grpc") \
                   .replace("description: Research specialist — answers ONE question.",
                            "description: gRPC expert.")
        write(self.d, "research/rsr-grpc.md", body)
        self.assertTrue(any("Research specialist" in v for v in al.lint_tree(self.d)))

    def test_agent_type_allowlist_is_rejected(self):
        body = LEAF.replace("name: researcher", "name: deep-researcher") \
                   .replace("tools: Read, Grep, Glob", "tools: Read, Agent(researcher)")
        write(self.d, "deep-researcher.md", body)
        self.assertTrue(any("ignored inside a subagent" in v for v in al.lint_tree(self.d)))

    def test_task_alias_allowlist_also_rejected(self):
        body = LEAF.replace("name: researcher", "name: deep-researcher") \
                   .replace("tools: Read, Grep, Glob", "tools: Read, Write, Task(researcher)")
        write(self.d, "deep-researcher.md", body)
        self.assertTrue(any("ignored inside a subagent" in v for v in al.lint_tree(self.d)))

    def test_deep_researcher_needs_agent_and_write(self):
        body = LEAF.replace("name: researcher", "name: deep-researcher")
        write(self.d, "deep-researcher.md", body)
        vs = al.lint_tree(self.d)
        self.assertTrue(any("deep-researcher" in v and "Agent" in v for v in vs))
        self.assertTrue(any("deep-researcher" in v and "Write" in v for v in vs))

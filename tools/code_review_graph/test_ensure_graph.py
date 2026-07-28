"""Unit tests for ensure_graph — install/build orchestration logic, all side effects mocked.
Run from repo root:
    PYTHONPATH=tools/code_review_graph python3 -m unittest test_ensure_graph -v
"""

import os
import tempfile
import unittest
from unittest import mock
from pathlib import Path

import ensure_graph as es


class _InTmp(unittest.TestCase):
    def setUp(self):
        self._cwd = os.getcwd()
        self._tmp = tempfile.TemporaryDirectory()
        os.chdir(self._tmp.name)

    def tearDown(self):
        os.chdir(self._cwd)
        self._tmp.cleanup()


class BuildOrUpdate(_InTmp):
    def test_build_when_no_db(self):
        with mock.patch.object(es.subprocess, "Popen") as P:
            es.build_or_update()
        chain = P.call_args.args[0][2]
        self.assertIn("'build'", chain)
        self.assertNotIn("'update'", chain)

    def test_update_when_db_exists(self):
        Path(es.GRAPH_DIR).mkdir()
        Path(es.GRAPH_DB).write_text("x")
        with mock.patch.object(es.subprocess, "Popen") as P:
            es.build_or_update()
        chain = P.call_args.args[0][2]
        self.assertIn("'update'", chain)

    def test_chain_includes_embed(self):
        with mock.patch.object(es.subprocess, "Popen") as P:
            es.build_or_update()
        chain = P.call_args.args[0][2]
        self.assertIn("'embed'", chain)


class Gitignore(_InTmp):
    def test_appended_once(self):
        es.graph_gitignored()
        es.graph_gitignored()
        content = Path(".gitignore").read_text()
        self.assertEqual(content.count(".code-review-graph/"), 1)

    def test_respects_existing_entry(self):
        Path(".gitignore").write_text(".code-review-graph/\n")
        es.graph_gitignored()
        self.assertEqual(Path(".gitignore").read_text().count(".code-review-graph/"), 1)


class EnsureUv(_InTmp):
    def test_false_when_absent(self):
        with mock.patch.object(es.shutil, "which", return_value=None), \
             mock.patch.object(es.subprocess, "run"):
            self.assertFalse(es.ensure_uv())

    def test_true_when_present(self):
        with mock.patch.object(es.shutil, "which", return_value="/x/uvx"):
            self.assertTrue(es.ensure_uv())


if __name__ == "__main__":
    unittest.main()

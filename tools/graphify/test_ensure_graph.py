"""Unit tests for ensure_graph — install/build orchestration logic, all side effects mocked.
Run from repo root:
    PYTHONPATH=tools/graphify python3 -m unittest test_ensure_graph -v
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
    def test_runs_graphify_update_on_cwd(self):
        with mock.patch.object(es.subprocess, "Popen") as P:
            es.build_or_update()
        cmd = P.call_args.args[0]
        self.assertEqual(cmd[-2:], ["update", "."])
        self.assertIn("graphifyy[mcp]<0.10", cmd)

    def test_detached_and_logged(self):
        with mock.patch.object(es.subprocess, "Popen") as P:
            es.build_or_update()
        self.assertTrue(P.call_args.kwargs["start_new_session"])
        self.assertTrue((Path(es.GRAPH_DIR) / "ensure.log").exists())


class Status(_InTmp):
    def test_absent_then_up(self):
        with mock.patch("builtins.print") as pr:
            es.main(["x", "--status"])
        pr.assert_called_with("absent")
        Path(es.GRAPH_DIR).mkdir()
        Path(es.GRAPH_JSON).write_text("{}")
        with mock.patch("builtins.print") as pr:
            es.main(["x", "--status"])
        pr.assert_called_with("up")


class Gitignore(_InTmp):
    def test_appended_once(self):
        es.graph_gitignored()
        es.graph_gitignored()
        content = Path(".gitignore").read_text()
        self.assertEqual(content.count("graphify-out/"), 1)

    def test_respects_existing_entry(self):
        Path(".gitignore").write_text("graphify-out/\n")
        es.graph_gitignored()
        self.assertEqual(Path(".gitignore").read_text().count("graphify-out/"), 1)


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

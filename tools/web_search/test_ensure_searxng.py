"""Unit tests for ensure_searxng.ensure() branches and tool.web_search error paths.

Pure logic — Docker and network are mocked, so these run anywhere (no Docker needed).
Run from the repo root:
    PYTHONPATH=tools/web_search python3 -m unittest test_ensure_searxng -v
"""

import unittest
from unittest import mock
import urllib.error

import ensure_searxng as es
import tool


class EnsureStatus(unittest.TestCase):
    def test_up_when_json_ok(self):
        with mock.patch.object(es, "_json_ok", return_value=True):
            self.assertEqual(es.ensure(), "up")

    def test_port_busy_when_listening_but_no_json(self):
        with mock.patch.object(es, "_json_ok", return_value=False), \
             mock.patch.object(es, "_listening", return_value=True):
            self.assertTrue(es.ensure().startswith("port-busy"))

    def test_no_docker(self):
        with mock.patch.object(es, "_json_ok", return_value=False), \
             mock.patch.object(es, "_listening", return_value=False), \
             mock.patch.object(es, "_docker_bin", return_value=None):
            self.assertEqual(es.ensure(), "no-docker")

    def test_daemon_down(self):
        with mock.patch.object(es, "_json_ok", return_value=False), \
             mock.patch.object(es, "_listening", return_value=False), \
             mock.patch.object(es, "_docker_bin", return_value="/usr/bin/docker"), \
             mock.patch.object(es, "_docker_daemon_up", return_value=False):
            self.assertEqual(es.ensure(), "daemon-down")

    def test_spawned_when_becomes_healthy(self):
        with mock.patch.object(es, "_json_ok", return_value=False), \
             mock.patch.object(es, "_listening", return_value=False), \
             mock.patch.object(es, "_docker_bin", return_value="/usr/bin/docker"), \
             mock.patch.object(es, "_docker_daemon_up", return_value=True), \
             mock.patch.object(es, "_write_settings_if_absent"), \
             mock.patch.object(es, "_start_container"), \
             mock.patch.object(es, "_wait_json", return_value=True):
            self.assertEqual(es.ensure(), "spawned")

    def test_failed_when_not_healthy(self):
        with mock.patch.object(es, "_json_ok", return_value=False), \
             mock.patch.object(es, "_listening", return_value=False), \
             mock.patch.object(es, "_docker_bin", return_value="/usr/bin/docker"), \
             mock.patch.object(es, "_docker_daemon_up", return_value=True), \
             mock.patch.object(es, "_write_settings_if_absent"), \
             mock.patch.object(es, "_start_container"), \
             mock.patch.object(es, "_wait_json", return_value=False):
            self.assertTrue(es.ensure().startswith("failed:"))


class WebSearchRaises(unittest.TestCase):
    def test_raises_on_connection_refused(self):
        with mock.patch.object(tool.urllib.request, "urlopen",
                               side_effect=urllib.error.URLError("Connection refused")):
            with self.assertRaises(RuntimeError) as cm:
                tool.web_search("anything")
        self.assertIn("ensure_searxng", str(cm.exception))

    def test_raises_on_403_json_disabled(self):
        err = urllib.error.HTTPError("http://x", 403, "Forbidden", {}, None)
        with mock.patch.object(tool.urllib.request, "urlopen", side_effect=err):
            with self.assertRaises(RuntimeError) as cm:
                tool.web_search("anything")
        self.assertIn("403", str(cm.exception))


class DockerBin(unittest.TestCase):
    def test_uses_path_first(self):
        with mock.patch.object(es.shutil, "which", return_value="/p/docker"):
            self.assertEqual(es._docker_bin(), "/p/docker")

    def test_falls_back_to_candidate(self):
        target = es._DOCKER_CANDIDATES[2]
        with mock.patch.object(es.shutil, "which", return_value=None), \
             mock.patch.object(es.os.path, "exists", side_effect=lambda p: p == target), \
             mock.patch.object(es.os, "access", return_value=True):
            self.assertEqual(es._docker_bin(), target)

    def test_none_when_absent(self):
        with mock.patch.object(es.shutil, "which", return_value=None), \
             mock.patch.object(es.os.path, "exists", return_value=False):
            self.assertIsNone(es._docker_bin())


if __name__ == "__main__":
    unittest.main()

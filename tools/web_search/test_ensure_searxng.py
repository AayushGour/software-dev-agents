"""Unit tests for ensure_searxng.ensure() branches and tool.web_search behaviour.

Pure logic — Docker, the filesystem and the network are mocked or redirected to a
tmpdir, so these run anywhere (no Docker needed).
Run from the repo root:
    PYTHONPATH=tools/web_search python3 -m unittest test_ensure_searxng -v
"""

import re
import time
import shutil
import tempfile
import threading
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

import ensure_searxng as es
import tool


class EnsureStatus(unittest.TestCase):
    """ensure() maps backend/docker state onto its documented status strings."""

    def setUp(self):
        # ensure() syncs settings before anything else; every test here is about the
        # branch *after* that, so default to "already in sync".
        p = mock.patch.object(es, "_sync_settings", return_value=False)
        self.sync = p.start()
        self.addCleanup(p.stop)

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
             mock.patch.object(es, "_start_container"), \
             mock.patch.object(es, "_wait_json", return_value=True):
            self.assertEqual(es.ensure(), "spawned")

    def test_failed_when_not_healthy(self):
        with mock.patch.object(es, "_json_ok", return_value=False), \
             mock.patch.object(es, "_listening", return_value=False), \
             mock.patch.object(es, "_docker_bin", return_value="/usr/bin/docker"), \
             mock.patch.object(es, "_docker_daemon_up", return_value=True), \
             mock.patch.object(es, "_start_container"), \
             mock.patch.object(es, "_wait_json", return_value=False):
            self.assertTrue(es.ensure().startswith("failed:"))


class EnsureReloadsOnTemplateDrift(unittest.TestCase):
    """A running container on a stale settings.yml gets restarted, not left alone."""

    def setUp(self):
        p = mock.patch.object(es, "_sync_settings", return_value=True)
        p.start()
        self.addCleanup(p.stop)

    def test_reloaded_when_restart_succeeds(self):
        with mock.patch.object(es, "_json_ok", return_value=True), \
             mock.patch.object(es, "_restart_container", return_value=True) as restart, \
             mock.patch.object(es, "_wait_json", return_value=True):
            self.assertEqual(es.ensure(), "reloaded")
        restart.assert_called_once()

    def test_stays_up_when_restart_not_possible(self):
        # Stale config is strictly better than no backend, so don't fail the call.
        with mock.patch.object(es, "_json_ok", return_value=True), \
             mock.patch.object(es, "_restart_container", return_value=False):
            self.assertEqual(es.ensure(), "up")

    def test_failed_when_container_does_not_come_back(self):
        with mock.patch.object(es, "_json_ok", return_value=True), \
             mock.patch.object(es, "_restart_container", return_value=True), \
             mock.patch.object(es, "_wait_json", return_value=False):
            self.assertTrue(es.ensure().startswith("failed:"))

    def test_no_restart_attempted_when_in_sync(self):
        with mock.patch.object(es, "_sync_settings", return_value=False), \
             mock.patch.object(es, "_json_ok", return_value=True), \
             mock.patch.object(es, "_restart_container") as restart:
            self.assertEqual(es.ensure(), "up")
        restart.assert_not_called()


class SyncSettings(unittest.TestCase):
    """settings.yml is rendered from the template and tracks changes to it."""

    TEMPLATE_V1 = 'server:\n  secret_key: "__SECRET_KEY__"\n  limiter: false\n'
    TEMPLATE_V2 = 'server:\n  secret_key: "__SECRET_KEY__"\n  limiter: false\nengines: []\n'

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.template = self.dir / "settings.template.yml"
        self.settings = self.dir / "settings.yml"
        self.template.write_text(self.TEMPLATE_V1)
        for name, value in (("CFG_DIR", self.dir), ("TEMPLATE", self.template),
                            ("SETTINGS", self.settings)):
            p = mock.patch.object(es, name, value)
            p.start()
            self.addCleanup(p.stop)

    def _secret(self) -> str:
        m = re.search(r'secret_key:\s*"([^"]+)"', self.settings.read_text())
        assert m, "no secret_key in rendered settings.yml"
        return m.group(1)

    def test_creates_with_real_secret_and_stamp(self):
        self.assertTrue(es._sync_settings())
        body = self.settings.read_text()
        self.assertNotIn("__SECRET_KEY__", body)
        self.assertRegex(self._secret(), r"^[0-9a-f]{64}$")
        self.assertIn(es._STAMP_PREFIX, body)

    def test_second_call_is_a_noop(self):
        self.assertTrue(es._sync_settings())
        before = self.settings.read_text()
        self.assertFalse(es._sync_settings())
        self.assertEqual(self.settings.read_text(), before)

    def test_template_change_rewrites_and_keeps_secret(self):
        es._sync_settings()
        secret = self._secret()
        self.template.write_text(self.TEMPLATE_V2)
        self.assertTrue(es._sync_settings())
        self.assertEqual(self._secret(), secret, "regenerating the secret would log users out")
        self.assertIn("engines: []", self.settings.read_text())

    def test_legacy_settings_without_a_stamp_are_migrated(self):
        # What every install created before stamping existed.
        self.settings.write_text(self.TEMPLATE_V1.replace("__SECRET_KEY__", "deadbeef"))
        self.assertTrue(es._sync_settings())
        self.assertEqual(self._secret(), "deadbeef")
        self.assertIn(es._STAMP_PREFIX, self.settings.read_text())

    def test_reports_no_change_when_the_filesystem_fails(self):
        with mock.patch.object(es.Path, "read_bytes", side_effect=OSError("boom")):
            self.assertFalse(es._sync_settings())


class HealthCheckIsCheap(unittest.TestCase):
    """The pre-search probe must not fan out to the scraped engines."""

    def test_json_ok_pins_a_single_engine(self):
        captured = {}

        class FakeResp:
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def read(self): return b"{}"

        def fake_urlopen(req, timeout=None):
            captured["url"] = req.full_url
            return FakeResp()

        with mock.patch.object(es.urllib.request, "urlopen", fake_urlopen), \
             mock.patch.object(es.json, "load", return_value={}):
            self.assertTrue(es._json_ok())
        self.assertIn("format=json", captured["url"])
        self.assertIn("engines=wikipedia", captured["url"])


class WebSearchRaises(unittest.TestCase):
    def setUp(self):
        reset_tool_state(self)

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

    def test_failures_are_not_cached(self):
        err = urllib.error.URLError("down")
        with mock.patch.object(tool.urllib.request, "urlopen", side_effect=err):
            with self.assertRaises(RuntimeError):
                tool.web_search("q")
        self.assertIsNone(tool._cache_get("q"))


def reset_tool_state(case, *, min_interval=0.0, concurrency=None):
    """Give a test a clean, fast throttle/cache so module state can't leak between tests."""
    tool._cache.clear()
    tool._next_start = 0.0
    case.addCleanup(tool._cache.clear)
    p = mock.patch.object(tool, "MIN_INTERVAL", min_interval)
    p.start()
    case.addCleanup(p.stop)
    if concurrency is not None:
        q = mock.patch.object(tool, "_slots", threading.BoundedSemaphore(concurrency))
        q.start()
        case.addCleanup(q.stop)


def _results(n):
    return [{"title": f"t{i}", "url": f"http://e/{i}", "snippet": ""} for i in range(n)]


class Caching(unittest.TestCase):
    def setUp(self):
        reset_tool_state(self)

    def test_repeat_query_does_not_refetch(self):
        with mock.patch.object(tool, "_fetch", return_value=_results(10)) as fetch:
            first = tool.web_search("same", 3)
            second = tool.web_search("same", 3)
        fetch.assert_called_once()
        self.assertEqual(first, second)

    def test_cache_holds_the_full_list_not_the_truncated_one(self):
        # A 3-result call must not poison a later 8-result call.
        with mock.patch.object(tool, "_fetch", return_value=_results(10)) as fetch:
            self.assertEqual(len(tool.web_search("q", 3)), 3)
            self.assertEqual(len(tool.web_search("q", 8)), 8)
        fetch.assert_called_once()

    def test_expired_entry_refetches(self):
        with mock.patch.object(tool, "_fetch", return_value=_results(2)) as fetch, \
             mock.patch.object(tool, "CACHE_TTL", 0.01):
            tool.web_search("q")
            time.sleep(0.05)
            tool.web_search("q")
        self.assertEqual(fetch.call_count, 2)

    def test_callers_cannot_mutate_the_cache(self):
        with mock.patch.object(tool, "_fetch", return_value=_results(3)):
            got = tool.web_search("q")
            got[0]["url"] = "http://tampered"
            self.assertNotEqual(tool.web_search("q")[0]["url"], "http://tampered")

    def test_eviction_is_bounded(self):
        with mock.patch.object(tool, "_fetch", return_value=_results(1)), \
             mock.patch.object(tool, "CACHE_MAX_ENTRIES", 4):
            for i in range(10):
                tool.web_search(f"q{i}")
        self.assertLessEqual(len(tool._cache), 4)
        self.assertIsNone(tool._cache_get("q0"), "oldest entry should have been evicted")
        self.assertIsNotNone(tool._cache_get("q9"))

    def test_ttl_zero_disables_caching(self):
        with mock.patch.object(tool, "_fetch", return_value=_results(2)) as fetch, \
             mock.patch.object(tool, "CACHE_TTL", 0):
            tool.web_search("q")
            tool.web_search("q")
        self.assertEqual(fetch.call_count, 2)


class Throttling(unittest.TestCase):
    def test_concurrency_is_capped(self):
        reset_tool_state(self, concurrency=2)
        live = 0
        peak = 0
        lock = threading.Lock()

        def slow_fetch(_query):
            nonlocal live, peak
            with lock:
                live += 1
                peak = max(peak, live)
            time.sleep(0.05)
            with lock:
                live -= 1
            return _results(1)

        with mock.patch.object(tool, "_fetch", slow_fetch):
            threads = [threading.Thread(target=tool.web_search, args=(f"q{i}",))
                       for i in range(8)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
        self.assertLessEqual(peak, 2, f"{peak} fan-outs in flight; cap is 2")

    def test_requests_are_paced(self):
        reset_tool_state(self, min_interval=0.05, concurrency=4)
        starts = []

        def stamping_fetch(_query):
            starts.append(time.monotonic())
            return _results(1)

        with mock.patch.object(tool, "_fetch", stamping_fetch):
            for i in range(4):
                tool.web_search(f"q{i}")
        gaps = [b - a for a, b in zip(starts, starts[1:])]
        self.assertTrue(all(g >= 0.04 for g in gaps), f"gaps too tight: {gaps}")


class HealthyStatusContract(unittest.TestCase):
    """Every status ensure() uses to mean "serving" must pass the MCP server's gate.

    Regression: adding "reloaded" to ensure() while mcp_server still matched only
    ("up", "spawned") made a healthy backend report as unavailable and pushed agents
    onto the external fallback.
    """

    def test_mcp_server_gates_on_the_shared_tuple(self):
        import mcp_server
        self.assertIs(mcp_server._HEALTHY, es.HEALTHY)

    def test_every_serving_status_is_listed(self):
        serving = {
            "up": dict(_sync_settings=False, _json_ok=True),
            "reloaded": dict(_sync_settings=True, _json_ok=True,
                             _restart_container=True, _wait_json=True),
            "spawned": dict(_sync_settings=False, _json_ok=False, _listening=False,
                            _docker_bin="/usr/bin/docker", _docker_daemon_up=True,
                            _start_container=None, _wait_json=True),
        }
        for expected, patches in serving.items():
            with self.subTest(expected):
                with mock.patch.multiple(
                    es, **{k: mock.DEFAULT if v is None else mock.Mock(return_value=v)
                           for k, v in patches.items()}
                ):
                    status = es.ensure()
                self.assertEqual(status, expected)
                self.assertTrue(status.startswith(es.HEALTHY))

    def test_failure_statuses_do_not_pass_the_gate(self):
        for status in ("no-docker", "daemon-down", "port-busy: ...", "failed:nope"):
            self.assertFalse(status.startswith(es.HEALTHY), status)


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

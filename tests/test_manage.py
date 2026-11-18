import importlib.util
import io
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

spec = importlib.util.spec_from_file_location("manage", Path(__file__).parents[1] / "scripts/manage.py")
manage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(manage)


class SetupTests(unittest.TestCase):
    def setUp(self):
        parent = Path(__file__).resolve().parents[1] / ".test-data"
        parent.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="PixlStash test with spaces ", dir=parent)
        self.root = Path(self.temp.name)
        self.patch = patch.multiple(manage, ROOT=self.root, DATA=self.root / "data",
                                    CONFIG=self.root / "data/server-config.json",
                                    MARKER=self.root / "env/pixlstash-installed.json")
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.temp.cleanup()

    def test_first_run_and_repair_preserve_user_settings(self):
        config = manage.prepare()
        self.assertEqual(config["host"], "127.0.0.1")
        self.assertEqual(config["image_root"], str(self.root / "data/images"))
        config["image_root"] = "custom photo library"
        config["custom_setting"] = True
        manage.write_json(manage.CONFIG, config)
        self.assertEqual(manage.prepare(), config)

    def test_corrupt_configuration_is_not_overwritten(self):
        manage.CONFIG.parent.mkdir()
        manage.CONFIG.write_text("broken", encoding="utf-8")
        with self.assertRaises(json.JSONDecodeError):
            manage.prepare()
        self.assertEqual(manage.CONFIG.read_text(), "broken")

    def test_occupied_port_uses_another_port(self):
        with socket.socket() as occupied:
            occupied.bind(("127.0.0.1", 0))
            occupied.listen()
            preferred = occupied.getsockname()[1]
            self.assertNotEqual(manage.available_port(preferred), preferred)

    def test_readiness_requires_pixlstash_api_and_html(self):
        opener = Mock()
        opener.open.side_effect = [io.BytesIO(b'{"status": "ok"}')]
        self.assertFalse(manage.webui_responds(opener, "http://127.0.0.1:9537"))
        self.assertEqual(opener.open.call_count, 1)
        for page, expected in [(b"loading", False), (b"<html>PixlStash</html>", True)]:
            api = io.BytesIO(b'{"message": "PixlStash REST API"}')
            html = io.BytesIO(page)
            html.status = 200
            opener.open.side_effect = [api, html]
            self.assertEqual(manage.webui_responds(opener, "http://127.0.0.1:9537"), expected)

    def test_readiness_timeout_reports_failure_and_interrupts_server(self):
        finished, ready, stopping, timed_out = (threading.Event() for _ in range(4))
        with patch.object(manage, "READINESS_TIMEOUT", 0), patch.object(manage, "report_fatal") as report, \
                patch.object(manage._thread, "interrupt_main") as interrupt:
            manage.watch_server(9537, self.root / "no-stop", finished, ready, stopping, timed_out)
        report.assert_called_once()
        self.assertIn("readiness timed out", report.call_args.args[0])
        interrupt.assert_called_once()
        self.assertTrue(timed_out.is_set())
        self.assertFalse(stopping.is_set())
        self.assertFalse(ready.is_set())

    def test_process_exit_reports_startup_failure_or_unexpected_exit(self):
        manage.write_json(manage.MARKER, {"backend": "cpu"})
        for online, status, message in [
            (False, 1, "initialization failed"),
            (True, 0, "server exited unexpectedly"),
        ]:
            with self.subTest(online=online):
                def watch(_port, _stop_file, _finished, ready, _stopping, _timed_out):
                    if online:
                        ready.set()

                with patch.object(manage, "watch_server", side_effect=watch), \
                        patch.object(manage.runpy, "run_module", side_effect=SystemExit(status)), \
                        patch.object(manage, "report_fatal") as report, \
                        patch.object(manage.sys, "argv", []), patch.dict(os.environ), \
                        self.assertRaises(SystemExit) as exit_:
                    manage.serve()
                self.assertEqual(exit_.exception.code, manage.SERVER_FAILURE)
                self.assertIn(message, report.call_args.args[0])
                self.assertFalse((manage.DATA / "server-session.json").exists())

    def test_install_refuses_global_python(self):
        with self.assertRaisesRegex(RuntimeError, "virtual environment"):
            manage.install("cpu")

    def test_install_failure_clears_completion_marker(self):
        manage.write_json(manage.MARKER, {"backend": "cpu"})
        with patch.object(manage.sys, "prefix", str(self.root / "env")), \
             patch.object(manage.shutil, "which", return_value="uv"), \
             patch.object(manage.subprocess, "run", side_effect=RuntimeError("download failed")):
            with self.assertRaisesRegex(RuntimeError, "download failed"):
                manage.install("cpu")
        self.assertFalse(manage.MARKER.exists())

    def test_failed_gpu_preflight_preserves_working_install(self):
        manage.write_json(manage.MARKER, {"backend": "cpu"})
        with patch.object(manage.sys, "prefix", str(self.root / "env")), \
             patch.object(manage, "check_nvidia", side_effect=RuntimeError("old driver")):
            with self.assertRaisesRegex(RuntimeError, "old driver"):
                manage.install("nvidia")
        self.assertTrue(manage.MARKER.exists())

    def test_lifecycle_lock_excludes_concurrent_actions_and_releases_after_error(self):
        with manage.lifecycle_lock():
            with patch.object(manage.time, "monotonic", side_effect=[0, 100]):
                with self.assertRaisesRegex(RuntimeError, "still running"):
                    with manage.lifecycle_lock():
                        self.fail("Concurrent action entered the lock")
        with manage.lifecycle_lock():
            pass

    def test_update_fast_forwards_and_refuses_conflicting_local_edits(self):
        def git(directory, *args):
            return subprocess.run(["git", "-C", str(directory), "-c", "user.name=Test",
                                   "-c", "user.email=test@example.com", "-c", "commit.gpgsign=false", *args],
                                  check=True, capture_output=True, text=True)
        origin = self.root / "origin"
        checkout = self.root / "checkout"
        origin.mkdir()
        git(origin, "init")
        (origin / "version.txt").write_text("first\n")
        git(origin, "add", ".")
        git(origin, "commit", "-m", "initial")
        git(self.root, "clone", str(origin), str(checkout))
        (origin / "version.txt").write_text("second\n")
        git(origin, "commit", "-am", "update")
        git(checkout, "pull", "--ff-only")
        self.assertEqual((checkout / "version.txt").read_text(), "second\n")
        (checkout / "version.txt").write_text("local edit\n")
        (origin / "version.txt").write_text("third\n")
        git(origin, "commit", "-am", "next update")
        with self.assertRaises(subprocess.CalledProcessError):
            git(checkout, "pull", "--ff-only")
        self.assertEqual((checkout / "version.txt").read_text(), "local edit\n")


if __name__ == "__main__":
    unittest.main()

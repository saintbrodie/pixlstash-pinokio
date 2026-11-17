import importlib.util
import json
from pathlib import Path
import socket
import subprocess
import tempfile
import unittest
from unittest.mock import patch

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

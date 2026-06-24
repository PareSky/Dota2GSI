import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))


class ResourcePathTests(unittest.TestCase):
    def test_source_mode_resolves_from_project_root(self):
        from resource_utils import resource_path

        with patch.object(sys, "frozen", False, create=True):
            resolved = Path(resource_path("config.yaml"))
        self.assertEqual(resolved, PROJECT_ROOT / "config.yaml")

    def test_frozen_mode_resolves_from_meipass(self):
        from resource_utils import resource_path

        with tempfile.TemporaryDirectory() as bundle_dir:
            with (
                patch.object(sys, "frozen", True, create=True),
                patch.object(sys, "_MEIPASS", bundle_dir, create=True),
            ):
                resolved = Path(resource_path("src", "speak.ps1"))
        self.assertEqual(resolved, Path(bundle_dir) / "src" / "speak.ps1")


class PyInstallerResourceTests(unittest.TestCase):
    def test_spec_and_build_script_bundle_all_runtime_resources(self):
        spec = (PROJECT_ROOT / "Dota2GSI.spec").read_text(encoding="utf-8")
        build = (PROJECT_ROOT / "build.bat").read_text(encoding="utf-8")
        for resource in ("config.yaml", "AIPromt.md", "src/speak.ps1"):
            self.assertIn(resource, spec.replace("\\", "/"))
            self.assertIn(resource, build.replace("\\", "/"))


if __name__ == "__main__":
    unittest.main()

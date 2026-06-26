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
        build_norm = build.replace("\\", "/")
        # 打进 exe 的内部文件
        for resource in ("src/speak.ps1", "gamestate_integration_gsi_config.cfg"):
            self.assertIn(resource, spec.replace("\\", "/"))
            self.assertIn(resource, build_norm)
        # 暴露在 dist\ 的用户可编辑文件（build.bat copy/xcopy，不在 spec datas 中）
        spec_norm = spec.replace("\\", "/")
        for resource in ("config.yaml", "AIPromt.md", "Dota2MechanismOntology"):
            self.assertIn(resource, build_norm)
            self.assertNotIn(resource, spec_norm)


if __name__ == "__main__":
    unittest.main()

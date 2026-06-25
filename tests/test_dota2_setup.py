import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


class Dota2DiscoveryTests(unittest.TestCase):
    def test_finds_dota2_in_primary_steam_library(self):
        with tempfile.TemporaryDirectory() as root:
            steam_root = Path(root) / "Steam"
            dota_dir = steam_root / "steamapps" / "common" / "dota 2 beta"
            dota_dir.mkdir(parents=True)

            from dota2_setup import find_dota2_directory

            found = find_dota2_directory(steam_roots=[steam_root])

            self.assertEqual(found, dota_dir)

    def test_finds_dota2_in_extra_library_from_vdf(self):
        with tempfile.TemporaryDirectory() as root:
            steam_root = Path(root) / "Steam"
            extra_library = Path(root) / "Games"
            (steam_root / "steamapps").mkdir(parents=True)
            dota_dir = (
                extra_library / "steamapps" / "common" / "dota 2 beta"
            )
            dota_dir.mkdir(parents=True)
            escaped_path = str(extra_library).replace("\\", "\\\\")
            (steam_root / "steamapps" / "libraryfolders.vdf").write_text(
                '"libraryfolders"\n{\n'
                f'  "1" {{ "path" "{escaped_path}" }}\n'
                '}\n',
                encoding="utf-8",
            )

            from dota2_setup import find_dota2_directory

            found = find_dota2_directory(steam_roots=[steam_root])

            self.assertEqual(found, dota_dir)

class GsiConfigInstallTests(unittest.TestCase):
    def test_copies_config_when_target_is_missing(self):
        from dota2_setup import ensure_gsi_config, GSI_CONFIG_FILENAME, GSI_CONFIG_RELATIVE_PATH

        with tempfile.TemporaryDirectory() as root:
            root_path = Path(root)
            dota_dir = root_path / "dota 2 beta"
            dota_dir.mkdir()
            source = root_path / GSI_CONFIG_FILENAME
            source.write_text("new config", encoding="utf-8")

            result = ensure_gsi_config(dota_dir=dota_dir, source_path=source)

            target = dota_dir / GSI_CONFIG_RELATIVE_PATH
            self.assertTrue(result.ok)
            self.assertTrue(result.installed)
            self.assertEqual(target.read_text(encoding="utf-8"), "new config")

    def test_existing_config_is_not_overwritten(self):
        from dota2_setup import ensure_gsi_config, GSI_CONFIG_RELATIVE_PATH, GSI_CONFIG_FILENAME

        with tempfile.TemporaryDirectory() as root:
            root_path = Path(root)
            dota_dir = root_path / "dota 2 beta"
            target = dota_dir / GSI_CONFIG_RELATIVE_PATH
            target.parent.mkdir(parents=True)
            target.write_text("user config", encoding="utf-8")
            source = root_path / GSI_CONFIG_FILENAME
            source.write_text("bundled config", encoding="utf-8")

            result = ensure_gsi_config(dota_dir=dota_dir, source_path=source)

            self.assertTrue(result.ok)
            self.assertFalse(result.installed)
            self.assertEqual(target.read_text(encoding="utf-8"), "user config")

    def test_missing_source_returns_warning_result(self):
        with tempfile.TemporaryDirectory() as root:
            root_path = Path(root)
            dota_dir = root_path / "dota 2 beta"
            dota_dir.mkdir()

            from dota2_setup import ensure_gsi_config

            result = ensure_gsi_config(
                dota_dir=dota_dir,
                source_path=root_path / "missing.cfg",
            )

            self.assertFalse(result.ok)
            self.assertIn("不存在", result.message)

    def test_missing_dota_directory_returns_warning_result(self):
        from dota2_setup import ensure_gsi_config

        result = ensure_gsi_config(
            dota_dir=None,
            source_path=Path("unused.cfg"),
        )

        self.assertFalse(result.ok)
        self.assertIn("Dota 2", result.message)


    def test_invalid_library_file_does_not_raise(self):
        with tempfile.TemporaryDirectory() as root:
            steam_root = Path(root) / "Steam"
            (steam_root / "steamapps").mkdir(parents=True)
            (steam_root / "steamapps" / "libraryfolders.vdf").write_bytes(
                b"\xff\xfe"
            )

            from dota2_setup import find_dota2_directory

            found = find_dota2_directory(steam_roots=[steam_root])

            self.assertIsNone(found)


class StartupSetupTests(unittest.TestCase):
    def test_setup_uses_discovered_directory_and_resource(self):
        from dota2_setup import setup_gsi_config, GSI_CONFIG_FILENAME

        with tempfile.TemporaryDirectory() as root:
            root_path = Path(root)
            dota_dir = root_path / "dota 2 beta"
            dota_dir.mkdir()
            source = root_path / GSI_CONFIG_FILENAME
            source.write_text("config", encoding="utf-8")

            with (
                patch("dota2_setup.find_dota2_directory", return_value=dota_dir),
                patch("dota2_setup.resource_path", return_value=str(source)),
            ):
                result = setup_gsi_config()

            self.assertTrue(result.ok)
            self.assertTrue(result.installed)

    def test_setup_converts_unexpected_discovery_error_to_warning(self):
        from dota2_setup import setup_gsi_config

        with patch(
            "dota2_setup.find_dota2_directory",
            side_effect=RuntimeError("registry failed"),
        ):
            result = setup_gsi_config()

        self.assertFalse(result.ok)
        self.assertIn("registry failed", result.message)

    def test_server_starts_even_when_setup_fails(self):
        import server

        mock_handler_instance = MagicMock()
        mock_handler_instance.log_dir = "logs/test"

        with (
            patch.object(server, "setup_gsi_config", return_value=SetupResult(False, False, "test error")) as mock_setup,
            patch.object(server, "GSIHandler", return_value=mock_handler_instance) as mock_handler,
            patch.object(server.app, "run") as mock_run,
            patch.object(server, "load_config", return_value={}),
        ):
            server.main()

        mock_setup.assert_called_once()
        mock_handler.assert_called_once()
        mock_run.assert_called_once()

    def test_server_starts_when_setup_succeeds(self):
        import server

        mock_handler_instance = MagicMock()
        mock_handler_instance.log_dir = "logs/test"

        with (
            patch.object(server, "setup_gsi_config", return_value=SetupResult(True, True, "all good")) as mock_setup,
            patch.object(server, "GSIHandler", return_value=mock_handler_instance) as mock_handler,
            patch.object(server.app, "run") as mock_run,
            patch.object(server, "load_config", return_value={}),
        ):
            server.main()

        mock_setup.assert_called_once()
        mock_handler.assert_called_once()
        mock_run.assert_called_once()


# Import at module level for StartupSetupTests to use
from dota2_setup import SetupResult, GSI_CONFIG_FILENAME


"""Locate Steam libraries and the Dota 2 installation on Windows."""

from dataclasses import dataclass
from pathlib import Path
import os
import re
import shutil


DOTA2_RELATIVE_PATH = Path("steamapps/common/dota 2 beta")
_VDF_PATH_PATTERN = re.compile(r'"path"\s*"((?:\\\\.|[^"])*)"', re.IGNORECASE)


def parse_library_folders(vdf_path: Path) -> list[Path]:
    try:
        text = vdf_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return []
    return [
        Path(value.replace("\\\\", "\\"))
        for value in _VDF_PATH_PATTERN.findall(text)
    ]


def _registry_steam_roots() -> list[Path]:
    if os.name != "nt":
        return []
    try:
        import winreg
    except ImportError:
        return []

    locations = (
        (winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath"),
        (
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\WOW6432Node\Valve\Steam",
            "InstallPath",
        ),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam", "InstallPath"),
    )
    roots = []
    for hive, key_name, value_name in locations:
        try:
            with winreg.OpenKey(hive, key_name) as key:
                value, _ = winreg.QueryValueEx(key, value_name)
        except OSError:
            continue
        if value:
            roots.append(Path(value))
    return roots


def default_steam_roots() -> list[Path]:
    roots = _registry_steam_roots()
    for env_name in ("PROGRAMFILES(X86)", "PROGRAMFILES"):
        base = os.environ.get(env_name)
        if base:
            roots.append(Path(base) / "Steam")
    return roots


def find_dota2_directory(
    steam_roots: list[Path] | None = None,
) -> Path | None:
    primary_roots = steam_roots if steam_roots is not None else default_steam_roots()
    libraries = []
    for root in primary_roots:
        root = Path(root)
        libraries.append(root)
        libraries.extend(parse_library_folders(root / "steamapps/libraryfolders.vdf"))

    seen = set()
    for library in libraries:
        normalized = str(library.resolve(strict=False)).casefold()
        if normalized in seen:
            continue
        seen.add(normalized)
        candidate = library / DOTA2_RELATIVE_PATH
        if candidate.is_dir():
            return candidate
    return None


GSI_CONFIG_FILENAME = "gamestate_integration_gsi_config.cfg"
GSI_CONFIG_RELATIVE_PATH = (
    Path("game/dota/cfg/gamestate_integration") / GSI_CONFIG_FILENAME
)


@dataclass(frozen=True)
class SetupResult:
    ok: bool
    installed: bool
    message: str
    path: Path | None = None


def ensure_gsi_config(
    dota_dir: Path | None,
    source_path: Path,
) -> SetupResult:
    if dota_dir is None:
        return SetupResult(False, False, "未找到 Dota 2 游戏目录")

    target = Path(dota_dir) / GSI_CONFIG_RELATIVE_PATH
    if target.is_file():
        return SetupResult(True, False, "GSI 配置已就绪", target)
    if not source_path.is_file():
        return SetupResult(
            False,
            False,
            f"内置 GSI 配置不存在: {source_path}",
            target,
        )

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target)
    except OSError as exc:
        return SetupResult(
            False,
            False,
            f"安装 GSI 配置失败: {exc}",
            target,
        )
    return SetupResult(True, True, "已自动安装 GSI 配置", target)


from resource_utils import resource_path


def setup_gsi_config() -> SetupResult:
    try:
        dota_dir = find_dota2_directory()
        source = Path(resource_path(GSI_CONFIG_FILENAME))
        return ensure_gsi_config(dota_dir, source)
    except Exception as exc:
        return SetupResult(False, False, f"GSI 配置自检失败: {exc}")

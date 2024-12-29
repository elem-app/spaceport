"""Global variables and objects.

This module provides centralized access to application-wide resources:

Environment Variables
    Access to configuration via environment variables and .env files

Template Manager
    Global template manager instance for rendering templates
"""

import asyncio
import os
import sys
from pathlib import Path

import dotenv
from pydantic import BaseModel, ConfigDict, Field

from pylib.tem import TemplateManager

_EDITION = "spaceport"


def edition() -> str:
    return _EDITION


def get_global_data_dir() -> Path:
    """Get the global data directory.

    The data directory is used for storing data that is not configuration, such as
    extension installations or custom subject implementation packages.
    """
    if os.environ.get(f"{edition().upper()}_DATA_DIR"):
        return Path(os.environ[f"{edition().upper()}_DATA_DIR"])

    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", "~/.local"))
    elif sys.platform == "darwin":
        base = Path("~/Library/Application Support")
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", "~/.local/share"))
    base = base.expanduser()
    return base / edition()


def get_global_config_dir() -> Path:
    """Get the global configuration directory.

    The configuration directory is used for storing configuration files, such as
    environment variables.
    """
    if os.environ.get(f"{edition().upper()}_CONFIG_DIR"):
        return Path(os.environ[f"{edition().upper()}_CONFIG_DIR"])

    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", "~/.local"))
    elif sys.platform == "darwin":
        base = Path("~/Library/Application Support")
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", "~/.config"))
    base = base.expanduser()
    return base / edition()


def _config_dirs() -> list[Path]:
    """
    Get list of paths to search for config file in priority order:
    1. Current working directory
    2. Executable's directory (for packaged apps)
    3. OS-specific config directories
    4. User's home directory
    """
    import sys

    paths: list[Path] = []

    # 1. Executable's directory
    if getattr(sys, "frozen", False):  # Running as packaged executable
        paths.append(Path(sys.executable).parent)

    # 2. User's home directory
    paths.append(get_global_config_dir())

    # 3. Current working directory
    paths.append(Path.cwd())

    return paths


# -- Initialization --
def initialize_global_dirs() -> None:
    get_global_data_dir().mkdir(parents=True, exist_ok=True)
    get_global_config_dir().mkdir(parents=True, exist_ok=True)


# -- Envvars --
def _load_envvars() -> dict[str, str | None]:
    # Get the project root directory (where pyproject.toml is located)
    envvars: dict[str, str | None] = {}

    for path in _config_dirs():
        env_file = path / ".env"
        if env_file.exists():
            envvars.update(dotenv.dotenv_values(env_file))

        env_test_file = path / ".env.test"
        if env_test_file.exists():
            envvars.update(dotenv.dotenv_values(env_test_file))

    envvars.update(os.environ)

    return envvars


class EnvVars(BaseModel):
    # Each field corresponds to an envvar whose name is the field name in uppercase
    # plus the edition prefix
    model_config = ConfigDict(
        alias_generator=lambda s: f"{edition().upper()}_{s.upper()}"
    )

    openai_api_key: str
    anthropic_api_key: str
    template_dir: str = Field(default="templates")
    speccer_llm_vendor: str = Field(default="Anthropic")
    speccer_llm_model: str = Field(default="claude-3-5-sonnet-20241022")


# -- Template  --
def _init_templates() -> TemplateManager:
    # Convert template_dir to absolute path if it's relative
    template_dir = Path(globals.envvars.template_dir)
    if not template_dir.is_absolute():
        template_dir = get_global_data_dir() / template_dir

    if not template_dir.exists():
        copy_package_data()

    manager = TemplateManager(str(template_dir))
    # No other loop should be running at this moment, so we can safely call `asyncio.run()`
    asyncio.run(manager.load_templates_from_files())
    return manager


def copy_package_data() -> None:
    import shutil
    from importlib import resources

    src = resources.files(f"{edition()}.data")
    dest_dir = get_global_data_dir()
    with resources.as_file(src) as src_dir:
        shutil.copytree(src_dir, dest_dir, dirs_exist_ok=True)


class _Globals:
    def __init__(self):
        self._envvars = None
        self._templates = None

    @property
    def envvars(self) -> EnvVars:
        if self._envvars is None:
            self._envvars = EnvVars.model_validate(_load_envvars())
        return self._envvars

    @property
    def templates(self) -> TemplateManager:
        if self._templates is None:
            self._templates = _init_templates()
        return self._templates


globals = _Globals()

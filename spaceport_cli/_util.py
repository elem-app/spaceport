import sys
from pathlib import Path
from typing import Any

import click

from spaceport.globals import get_global_data_dir


def cyan(text: Any) -> str:
    return click.style(text, fg="cyan")


def underline(text: Any) -> str:
    return click.style(text, underline=True)


def bold(text: Any) -> str:
    return click.style(text, bold=True)


def red(text: Any) -> str:
    return click.style(text, fg="red")


def green(text: Any) -> str:
    return click.style(text, fg="green")


def get_exts_path() -> Path:
    return get_global_data_dir() / "exts"


def _site_packages(root: Path) -> Path:
    if sys.platform == "win32":
        return root / "lib" / "site-packages"
    else:
        return (
            root
            / "lib"
            / f"python{sys.version_info.major}.{sys.version_info.minor}"
            / "site-packages"
        )


def set_sys_path_for_exts() -> None:
    exts_path = get_exts_path()
    if exts_path.exists():
        for p in exts_path.iterdir():
            if p.is_dir():
                sys.path.insert(1, str(_site_packages(p)))

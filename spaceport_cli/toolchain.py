import subprocess
import sys
import venv

import click

from spaceport.globals import get_global_config_dir

from ._util import cyan, get_exts_path

DEPS = {
    "simpl.browser": ["playwright>=1.49.0"],
    "simpl.sqldb": ["sqlalchemy>=2.0.0"],
    "simpl.container": ["docker>=7.1.0"],
}


class _PostExecPy(tuple[str, ...]):
    pass


class _PostExec(tuple[str, ...]):
    pass


POSTS = {
    "simpl.container": [
        _PostExec(("sp", "env", "add-manifest", "container")),
    ],
    "simpl.browser": [
        _PostExecPy(("playwright", "install")),
        _PostExec(("sp", "env", "add-manifest", "browser")),
    ],
}


@click.group(
    options_metavar=False,
    subcommand_metavar=cyan("<command>"),
)
def tc():
    """Toolchain commands."""
    pass


@tc.command(options_metavar=cyan("[options]"))
@click.option("--skip-post", is_flag=True, help="Skip post-install actions")
@click.argument("extension", metavar=cyan("<extension>..."), nargs=-1, required=True)
def install(extension: tuple[str, ...], skip_post: bool):
    """Install extensions."""
    for ext in extension:
        _install_exts(ext, skip_post)


def _install_exts(ext_str: str, skip_post: bool):
    try:
        dep = DEPS[ext_str]
    except KeyError:
        click.echo(f"Extension {ext_str} not found")
        sys.exit(1)

    venv_path = get_exts_path() / ext_str
    venv_path.mkdir(parents=True, exist_ok=True)
    venv.create(venv_path, with_pip=True)
    if sys.platform == "win32":
        py_bin = str(venv_path / "Scripts" / "python.exe")
    else:
        py_bin = str(venv_path / "bin" / "python")

    cmd = [py_bin, "-m", "pip", "install"]
    cmd.extend(dep)
    subprocess.run(cmd, check=True)

    if not skip_post and ext_str in POSTS:
        for post in POSTS[ext_str]:
            if isinstance(post, _PostExecPy):
                subprocess.run([py_bin, "-m", *post], check=True)
            else:
                subprocess.run(post, check=True)


@tc.command("list-exts", options_metavar=cyan("[options]"))
def list_exts():
    """List installed extensions."""
    import importlib.util

    from packaging import requirements

    for ext, deps in DEPS.items():
        installed: list[str] = []
        for dep in deps:
            # Parse requirement string to get package name without version
            req = requirements.Requirement(dep)
            pkg = req.name
            if importlib.util.find_spec(pkg) is not None:
                installed.append(dep)

        if installed:
            click.echo(f"{cyan(ext)}:")
            for dep in installed:
                click.echo(f"    - {dep}")


@tc.command("get-config-dir")
def get_config_dir():
    """Get the path to the toolchain config directory."""
    click.echo(get_global_config_dir())


@tc.command("check-config")
def check_config():
    """Check the toolchain configuration."""
    from pydantic import ValidationError

    from spaceport.globals import globals

    try:
        _ = globals.envvars
    except Exception as e:
        from ._util import red

        if isinstance(e, ValidationError):
            missing_fields = [
                str(err["loc"][0]) for err in e.errors() if err["type"] == "missing"
            ]
            if missing_fields:
                click.echo("Missing required configs:")
                for field in missing_fields:
                    click.echo(f"    - {red(field)}")
            else:
                click.echo(red("Invalid config values"))
        else:
            click.echo(red(f"Error loading config: {e}"))
        sys.exit(1)

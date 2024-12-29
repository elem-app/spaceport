import sys
from pathlib import Path

import click

from ._util import cyan


@click.group(
    options_metavar=False,
    subcommand_metavar=cyan("<command>"),
)
def env():
    """Environment commands."""
    pass


@env.command("add-manifest", options_metavar=False)
@click.argument("template", metavar=cyan("<template>..."), nargs=-1)
def add_manifest(template: tuple[str, ...]):
    """Add a template manifest to the workspace.

    Multiple templates can be added at once.
    """
    from spaceport.workspace.env import Env

    Env.load_and_add_template(Path.cwd(), template)


@env.command("check-manifest", options_metavar=False)
def check_manifest():
    """Check the environment manifest for missing values.

    Errors if the manifest file is missing or contains not-given values.
    """
    from spaceport.workspace.env import Env

    try:
        _ = Env.load_manifest(Path.cwd())
    except (FileNotFoundError, ValueError) as e:
        click.echo(e)
        sys.exit(1)

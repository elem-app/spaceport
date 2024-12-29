from typing import List

import click

from . import workspace
from ._util import cyan, set_sys_path_for_exts
from .test import test
from .toolchain import tc
from .env import env
from .transpile import transpile


# click sorts the commands by default, but we want to show them in a custom order
class _Group(click.Group):
    def list_commands(self, ctx: click.Context) -> List[str]:
        return list(self.commands)


@click.group(
    cls=_Group,
    options_metavar=False,
    subcommand_metavar=cyan("<command>"),
    context_settings={"help_option_names": ["-h", "--help"]},
)
def cli():
    """Command line interface for Spaceport."""
    set_sys_path_for_exts()


cli.add_command(workspace.init)
cli.add_command(workspace.add)
cli.add_command(workspace.rename)
cli.add_command(workspace.list)
cli.add_command(workspace.make)
cli.add_command(workspace.code)
cli.add_command(test)
cli.add_command(env)
cli.add_command(transpile)
cli.add_command(tc)

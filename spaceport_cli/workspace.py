import asyncio
from pathlib import Path

import click

from ._util import bold, cyan, red, underline


@click.command(options_metavar=cyan("[options]"))
def init():
    """Create a new workspace.

    This will attempt to create a workspace manifest and an env manifest in the current
    working directory. If any of these files already exist, they will be left untouched.
    """
    _init()


def _init():
    from spaceport.workspace import Workspace

    Workspace.dump_new_manifest(Path.cwd())


@click.command(options_metavar=cyan("[options]"))
@click.argument("name", metavar=cyan("<name>"), required=True)
@click.option(
    "-a",
    "--artifact",
    is_flag=False,
    flag_value="default",
    metavar=cyan("<path>"),
    help=(
        f"Specify the artifact file for the project. If {cyan('<path>')} "
        "is not specified, will use the default artifact path sp-projects/"
        f"{cyan('<name>')}.md."
    ),
)
@click.option(
    "-p",
    "--primary",
    metavar=cyan("<path_or_url>"),
    help="Specify the primary source for the project. Can be a local file path or a URL.",
)
@click.option(
    "-o",
    "--other",
    multiple=True,
    metavar=cyan("<path_or_url>"),
    help="Specify a supplementary source for the project. Can be a local file path or a URL.",
)
def add(
    name: str, artifact: str | None, primary: str | None, other: tuple[str, ...] | None
):
    """Add a project to the workspace.

    Must either use -a/--artifact to specify an artifact file, or -p/--primary to specify
    a primary source document.
    """

    if not artifact and not primary:
        raise click.BadParameter("Either --artifact or --primary must be provided")
    if artifact and primary:
        raise click.BadParameter("Cannot specify both --artifact and --primary")

    from spaceport.workspace import Workspace

    # This does nothing if the workspace is initialized so we do the user a favor
    _init()
    workspace = Workspace(Path.cwd())
    if artifact:
        workspace.add_project(name, artifact=(artifact == "default") or artifact)
    elif primary:
        workspace.add_project(name, sources=[primary, *(other or [])])


@click.command(options_metavar=False)
@click.argument("old", metavar=cyan("<old name>"))
@click.argument("new", metavar=cyan("<new name>"))
def rename(old: str, new: str):
    """Rename a project.

    If the project's artifact file exists, its metadata will be updated to reflect the
    new name. If the file path is not explicitly set, the default artifact file will be
    updated to the new name as well.
    """
    from spaceport.workspace import Workspace

    workspace = Workspace(Path.cwd())
    workspace.rename_project(old, new)


@click.command(options_metavar=False)
@click.argument("projects", nargs=-1, metavar=cyan("[<project>...]"))
def list(projects: tuple[str, ...]):
    """List projects and their specs.

    If no projects are specified, all projects in the workspace will be listed.
    """
    from spaceport.workspace import Workspace

    workspace = Workspace(Path.cwd())
    for name, artifact, sources, specs in workspace.list_projects(projects or None):
        click.echo(f"{underline(bold(name))}")
        if artifact:
            click.echo(f"  - Artifact: {cyan(artifact)}")
        else:
            click.echo(f"  - {red('No artifact file')}")
        if sources:
            click.echo(f"  - Sources: {', '.join(map(cyan, sources))}")
        if specs:
            click.echo("  - Specs:")
            for spec in specs:
                click.echo(f"      ({spec.code_status}) {cyan(spec.name)}")
        click.echo()
    click.echo("(spec status: (*) - test code present, ( ) - test code incomplete)")


@click.command(options_metavar=cyan("[options]"))
@click.option(
    "--all",
    is_flag=True,
    help="Generate artifacts for all projects in the workspace.",
)
@click.argument("projects", nargs=-1, metavar=cyan("[<project>...]"))
def make(all: bool, projects: tuple[str, ...]):
    """Generate artifacts for projects.

    Only works on projects that are added with reference sources. The generated
    artifacts will be placed in the sp-projects directory.
    """
    from spaceport.workspace import Workspace

    workspace = Workspace(Path.cwd())
    paths = asyncio.run(workspace.rewrite(None if all else projects))
    n_rewritten = len(paths)
    renameds = [old.name for _, old in paths if old is not None]
    click.echo(f"Generated {bold(n_rewritten)} artifacts")
    if renameds:
        click.echo("Renamed existing artifact files to:")
        for n in renameds:
            click.echo(f"  - {cyan(n)}")


@click.command(options_metavar=cyan("[options]"))
@click.option(
    "--all",
    is_flag=True,
    help="Generate code for all executable specs in the workspace.",
)
@click.argument("projects", nargs=-1, metavar=cyan("[<project>...]"))
@click.option(
    "-s",
    "--spec",
    multiple=True,
    metavar=cyan("<spec>"),
    help="Specify specs to generate code for; if omitted, will generate code for all executable specs in the project(s).",
)
def code(all: bool, projects: tuple[str, ...], spec: tuple[str, ...]):
    """Generate test code for executable specs.

    Generated code are written into the project artifacts.
    """
    from spaceport.workspace import Workspace

    workspace = Workspace(Path.cwd())
    if spec:
        assert len(projects) == 1, "Must specify a single project when specifying specs"
        asyncio.run(workspace.transpile_specs(projects[0], spec))
    else:
        asyncio.run(workspace.transpile(None if all else projects))

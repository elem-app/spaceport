import asyncio
from pathlib import Path

import click

from ._util import cyan, underline


@click.command(options_metavar=cyan("[options]"))
@click.option(
    "--print-preamble",
    is_flag=True,
    help="Print the system preamble instead of transpiling input.",
)
@click.option(
    "--tsl",
    is_flag=True,
    help=f"Extract TSLs from the input or print TSL preamble if {underline('--print-preamble')} is set.",
)
@click.argument("input", metavar=cyan("[<input>]"))
def transpile(input: str | None, tsl: bool, print_preamble: bool):
    """Transpile text into test code."""
    if not input and not print_preamble:
        ctx = click.get_current_context()
        click.echo(ctx.get_help())
        return
    asyncio.run(
        _handle_transpile_command(
            input=input,
            tsl=tsl,
            print_preamble=print_preamble,
        )
    )


async def _handle_transpile_command(
    input: str | None, tsl: bool, print_preamble: bool
) -> None:
    """Handle the transpile command based on provided arguments.

    Args:
        args: Parsed command line arguments
    """
    if print_preamble:
        _print_preamble(tsl)
    elif input:
        input_path = Path(input)
        if input_path.exists():
            spec_text = input_path.read_text()
        else:
            spec_text = input

        if tsl:
            await _transpile_tsl(spec_text)
        else:
            await _transpile(spec_text)


async def _transpile(spec_text: str) -> None:
    try:
        from spaceport.speccer.transpiler import SpecTranspiler

        transpiler = SpecTranspiler()
        code = await transpiler.transpile(spec_text)

        print("\nGenerated test code:")
        for line in code.splitlines():
            print(f"  {line}")

    except Exception as e:
        print(f"Error during transpilation: {type(e).__name__}: {e}")
        raise


async def _transpile_tsl(spec_text: str) -> None:
    try:
        from spaceport.speccer.transpiler import SpecTranspiler

        transpiler = SpecTranspiler()
        code = await transpiler.extract_tsls(spec_text)

        print(f"\nExtracted {len(code)} TSL mappings:")
        for tsl in code:
            print(f"  {tsl.text!r} -> {tsl.tsl!r}")
    except Exception as e:
        print(f"Error during TSL extraction: {type(e).__name__}: {e}")
        raise


def _print_preamble(tsl: bool = False) -> None:
    """Print the system preamble used in transpilation.

    Args:
        verbose: If True, print additional information
    """
    try:
        from spaceport.speccer.transpiler import SpecTranspiler

        transpiler = SpecTranspiler()
        if tsl:
            preamble = transpiler.tsl_system_preamble
        else:
            preamble = transpiler.system_preamble
        print(preamble)
    except Exception as e:
        print(f"Error accessing preamble: {type(e).__name__}: {e}")
        raise

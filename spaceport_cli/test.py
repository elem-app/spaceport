import asyncio
import datetime
import os
import sys
from typing import TYPE_CHECKING, Any, Mapping, Sequence, TypedDict

import click

from ._util import bold, cyan, green, red


@click.command(options_metavar=cyan("[options]"))
@click.argument("projects", nargs=-1, metavar=cyan("<project>..."), required=True)
@click.option(
    "-s",
    "--spec",
    multiple=True,
    metavar=cyan("<spec>"),
    help=(
        "Specify specs to test; if omitted, will test all specs in the project(s). "
        "Only one project can be specified when specifying specs."
    ),
)
@click.option(
    "--json",
    "json_output",
    metavar=cyan("<path>"),
    help="Output the test results in JSON format to the given path.",
)
@click.option(
    "--junit-xml",
    "junit_xml_output",
    metavar=cyan("<path>"),
    help="Output the test results in JUnit XML format to the given path.",
)
def test(
    projects: tuple[str, ...],
    spec: tuple[str, ...],
    json_output: str | None,
    junit_xml_output: str | None,
):
    """Test executable specs in projects.

    Prints a human-readable summary to stdout by default.
    """

    from spaceport.workspace.workspace import Workspace

    workspace = Workspace()

    if spec:
        assert (
            len(projects) == 1
        ), "Must only specify a single project when specifying specs"
        coll = asyncio.run(_test_specs(workspace, projects[0], spec))
    else:
        coll = asyncio.run(_test_projects(workspace, projects))

    if json_output:
        import json

        with open(json_output, "w") as f:
            json.dump(structurize(coll), f)
    elif junit_xml_output:
        convert_to_junit_xml(structurize(coll), junit_xml_output)
    else:
        print_reports(coll)


_OK = green("OK")
_ERROR = red("ERROR")

if TYPE_CHECKING:
    from spaceport.workspace.workspace import TestReport, Workspace


type ReportCollection = dict[str, Sequence["TestReport"]]
"""A dict of project names to its test reports."""


async def _test_specs(
    workspace: "Workspace", project: str, specs: tuple[str, ...]
) -> ReportCollection:
    async with asyncio.TaskGroup() as tg:
        tasks = {project: tg.create_task(workspace.test(project, specs))}
    return {project: tasks[project].result()}


async def _test_projects(
    workspace: "Workspace", names: tuple[str, ...]
) -> ReportCollection:
    async with asyncio.TaskGroup() as tg:
        tasks = {name: tg.create_task(workspace.test(name)) for name in names}
    return {name: tasks[name].result() for name in names}


def _get_terminal_width() -> int:
    try:
        return max(os.get_terminal_size(sys.stderr.fileno()).columns, 80)
    except OSError:
        return 80


def print_reports(report_coll: ReportCollection) -> None:
    terminal_width = _get_terminal_width()
    for project_name, reports in report_coll.items():
        msgs: list[str] = []
        n_ok = 0
        n_err = 0
        for spec_name, err, _, _ in reports:
            if err is None:
                n_ok += 1
                err_msg = _OK
            else:
                n_err += 1
                err_loc = bold(f"{err.filename}:{err.lineno}")
                if err.locals:
                    locals_list = [
                        f"{cyan(k)} = {repr(v)}" for k, v in err.locals.items()
                    ]
                    locals_msg = (
                        f"\n |- {bold('Local variables:')}\n |   |- "
                        + "\n |   |- ".join(locals_list)
                    )
                else:
                    locals_msg = ""
                err_msg = f"{_ERROR} {err_loc} - {err.message}{locals_msg}"
            msgs.append(f"{spec_name} - {err_msg}")

        ok = green("ok")
        errors = red("errors")
        title_1 = f" {bold(project_name)}"
        plain_title_1 = f" {project_name}"
        if n_ok > 0 and n_err > 0:
            title_2 = f" - {green(n_ok)} {ok}, {red(n_err)} {errors} "
            plain_title_2 = f" - {n_ok} ok, {n_err} errors "
        elif n_ok > 0:
            title_2 = f" - {green(n_ok)} {ok} "
            plain_title_2 = f" - {n_ok} ok "
        else:
            title_2 = f" - {red(n_err)} {errors} "
            plain_title_2 = f" - {n_err} errors "

        total_len = len(plain_title_1) + len(plain_title_2)

        divider_pad = (
            "=" * ((terminal_width - total_len) // 2)
            if terminal_width >= total_len + 8
            else "===="
        )
        extra_pad = (
            "="
            if (terminal_width - total_len) % 2 and terminal_width >= total_len + 8
            else ""
        )
        click.echo(f"{divider_pad}{title_1}{title_2}{divider_pad}{extra_pad}")

        click.echo("\n".join(msgs))
        click.echo()


class StructuredReport(TypedDict):
    project: str
    spec: str
    timestamp: datetime.datetime
    time: float
    err: Mapping[str, Any] | None


class StructuredSummary(TypedDict):
    tests: Sequence[StructuredReport]


def structurize(report_coll: ReportCollection) -> StructuredSummary:
    return {
        "tests": [
            StructuredReport(project=p, **r._asdict())
            for p, rs in report_coll.items()
            for r in rs
        ]
    }


def convert_to_junit_xml(summary: StructuredSummary, output_file: str) -> None:
    """
    Convert Spaceport JSON test results to JUnit XML format.

    Args:
        summary: Test results in Spaceport's structured format
        output_file: Path to write the JUnit XML output
    """
    import xml.etree.ElementTree as ET

    # Create the root testsuites element
    testsuites = ET.Element("testsuites")

    # Group tests by project
    project_tests: dict[str, list[StructuredReport]] = {}
    for test in summary["tests"]:
        project_tests.setdefault(test["project"], []).append(test)

    # Create a testsuite for each project
    for project_name, project_reports in project_tests.items():
        testsuite = ET.SubElement(testsuites, "testsuite")
        testsuite.set("name", project_name)

        # Count metrics
        total = len(project_reports)
        failures = sum(1 for t in project_reports if t["err"] is not None)

        testsuite.set("tests", str(total))
        testsuite.set("failures", str(failures))
        testsuite.set(
            "errors", "0"
        )  # We treat all issues as failures rather than errors
        testsuite.set("skipped", "0")  # We don't have skipped tests yet

        # Add each test case
        for report in project_reports:
            testcase = ET.SubElement(testsuite, "testcase")
            testcase.set("name", report["spec"])
            testcase.set("time", str(report["time"]))
            testcase.set("timestamp", report["timestamp"].isoformat())

            # If there's an error, add failure element
            if report["err"] is not None:
                failure = ET.SubElement(testcase, "failure")

                error_data = report["err"]
                error_type = error_data["type_"]
                error_message = error_data["message"]
                error_filename = error_data["filename"]
                error_lineno = error_data["lineno"]
                error_locals = error_data["locals"]

                failure.set("type", error_type)
                failure.set("message", error_message)

                # Create detailed error text including line number and local variables
                error_detail = [
                    f"Error at {error_filename}:{error_lineno}:",
                    error_message,
                    "",
                    "Local variables at time of failure:",
                ]
                for var_name, var_value in error_locals.items():
                    error_detail.append(f"  {var_name} = {var_value}")

                failure.text = "\n".join(error_detail)

    # Create the XML string with proper formatting
    tree = ET.ElementTree(testsuites)
    tree.write(output_file, encoding="utf-8", xml_declaration=True)

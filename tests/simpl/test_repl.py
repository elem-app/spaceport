from typing import Any

import pytest

from spaceport import tpyi
from spaceport.tpyi.errors import TpyOperationError
from spaceport_simpl import BashREPL


class _Resolver:
    def __init__(self):
        self.subject = BashREPL()

    async def resolve(self, name: str | None, **kwargs: Any) -> BashREPL | None:
        if name == "terminal":
            return self.subject
        return None


@pytest.fixture
def resolver():
    return _Resolver()


@pytest.mark.asyncio
async def test_local_bash_repl(resolver: _Resolver):
    script_code = """\
T.use("terminal")
# Input the command "echo hello"
T.input_text("term//input", "echo hello")
T.input_enter("term//input")
# Wait for the command to complete
T.wait_till_complete("term//", timeout=3)
# Read the latest output
output = T.read_text("term//output/-1")
# Assert that the output is "hello"
assert output == "hello\\n"
"""
    await tpyi.execute(script_code, resolver)


@pytest.mark.asyncio
async def test_local_bash_repl_ctrl_d(resolver: _Resolver):
    script_code = """\
T.use("terminal")
T.input_keys("term//input", ["Control", "d"])
T.wait_till_complete("term//", timeout=1)
assert not T.is_alive("term//")
"""
    await tpyi.execute(script_code, resolver)


@pytest.mark.asyncio
async def test_local_bash_repl_workingdir(resolver: _Resolver):
    import pathlib

    script_code = """\
T.use("terminal")
T.set_working_dir("term//", dest="..")
cwd = T.get_working_dir("term//")
"""
    ret = await tpyi.execute(script_code, resolver)

    assert ret["cwd"] == str((pathlib.Path.cwd() / "..").resolve())


@pytest.mark.asyncio
async def test_local_bash_repl_exec_fail(resolver: _Resolver):
    script_code = """\
T.use("terminal")
T.input_text("term//input", "false")
T.input_enter("term//input")
T.wait_till_complete("term//", timeout=1)
"""
    with pytest.raises(TpyOperationError):
        await tpyi.execute(script_code, resolver)


@pytest.mark.asyncio
async def test_local_bash_repl_exec_timeout(resolver: _Resolver):
    script_code = """\
T.use("terminal")
T.input_text("term//input", "sleep 3")
T.input_enter("term//input")
T.wait_till_complete("term//", timeout=0.5)
"""
    with pytest.raises(TpyOperationError):
        await tpyi.execute(script_code, resolver)


@pytest.mark.asyncio
async def test_workingdir(resolver: _Resolver):
    import os
    import time

    dir_name = f"tmp-{time.time()}"
    script_code = f"""\
T.use("terminal")
T.set_working_dir("term//", dest="{dir_name!r}")
cwd = T.get_working_dir("term//")
"""
    ret = await tpyi.execute(script_code, resolver)
    assert ret["cwd"].endswith(dir_name)

    os.rmdir(dir_name)

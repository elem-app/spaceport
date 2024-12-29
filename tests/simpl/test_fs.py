import os
import shutil
import uuid
from pathlib import Path
from typing import Any, Callable

import pytest

from spaceport.tpyi import execute
from spaceport.tpyi.errors import TpyAssertionError, TpyOperationError
from spaceport_simpl.fs import FS


@pytest.fixture(name="make_temp_file_name")
def make_temp_file_name_():
    created: list[str] = []

    def make_temp_file_name():
        name = f"tmp-{uuid.uuid4()}"
        created.append(name)
        return name

    yield make_temp_file_name

    for name in created:
        try:
            os.remove(name)
        except FileNotFoundError:
            pass


@pytest.fixture(name="make_temp_folder_name")
def make_temp_folder_name_():
    created: list[str] = []

    def make_temp_folder_name():
        name = f"tmpdir-{uuid.uuid4()}"
        created.append(name)
        return name

    yield make_temp_folder_name

    for name in created:
        try:
            shutil.rmtree(name)
        except FileNotFoundError:
            pass


class _Resolver:
    def __init__(self):
        self.subject = FS()

    async def resolve(self, name: str | None, **kwargs: Any) -> FS:
        if name == "fs":
            return self.subject
        raise ValueError(f"Unknown subject: {name}")


@pytest.fixture
def resolver():
    return _Resolver()


@pytest.mark.asyncio
async def test_create_file_with_string(
    resolver: _Resolver, make_temp_file_name: Callable[[], str]
):
    temp_file_name = make_temp_file_name()
    string = "Hello, world!"
    script_code = f"""\
T.use("fs")
T.create_file("fs//{temp_file_name}", data={string!r})
"""

    await execute(script_code, resolver)

    path = Path(temp_file_name)
    assert path.exists()
    assert path.is_file()
    assert path.stat().st_size == len(string)
    assert path.read_text() == string


@pytest.mark.asyncio
async def test_create_file_with_bytes(
    resolver: _Resolver, make_temp_file_name: Callable[[], str]
):
    temp_file_name = make_temp_file_name()
    data = "🐶".encode("utf-8")
    script_code = f"""\
T.use("fs")
T.create_file("fs//{temp_file_name}", data={data!r})
"""

    await execute(script_code, resolver)

    path = Path(temp_file_name)
    assert path.exists()
    assert path.is_file()
    assert path.read_bytes() == bytes(data)


@pytest.mark.asyncio
async def test_move_folder(
    resolver: _Resolver, make_temp_folder_name: Callable[[], str]
):
    src_dir = make_temp_folder_name()
    dest_dir = make_temp_folder_name()
    print(f"src_dir: {src_dir}")
    print(f"dest_dir: {dest_dir}")
    src_path = Path(src_dir)
    src_path.mkdir()

    script_code = f"""\
T.use("fs")
T.move("fs//{src_dir}", dest={dest_dir!r})
"""

    await execute(script_code, resolver)

    dest_path = Path(dest_dir)
    assert dest_path.exists()
    assert dest_path.is_dir()
    assert not Path(src_dir).exists()


@pytest.mark.asyncio
async def test_move_files_in_folder(
    resolver: _Resolver, make_temp_folder_name: Callable[[], str]
):
    src_dir = make_temp_folder_name()
    dest_dir = make_temp_folder_name()

    src_path = Path(src_dir)
    src_path.mkdir()
    for i in range(3):
        (src_path / f"file-{i}").touch()

    dest_path = Path(dest_dir)
    dest_path.mkdir()

    script_code = f"""\
T.use("fs")
T.move("all:fs//{src_dir}/", dest="{dest_dir}/")
"""

    await execute(script_code, resolver)

    assert src_path.exists()
    assert len(list(dest_path.glob("*"))) == 3


@pytest.mark.asyncio
async def test_move_files_to_file(
    resolver: _Resolver,
    make_temp_folder_name: Callable[[], str],
    make_temp_file_name: Callable[[], str],
):
    src_dir = make_temp_folder_name()
    dest_file = make_temp_file_name()

    src_path = Path(src_dir)
    src_path.mkdir()
    for i in range(3):
        (src_path / f"file-{i}").touch()

    script_code = f"""\
T.use("fs")
T.move("all:fs//{src_dir}/", dest={dest_file!r})
"""

    with pytest.raises(TpyOperationError):
        await execute(script_code, resolver)


@pytest.mark.asyncio
async def test_target_exists(
    resolver: _Resolver,
    make_temp_folder_name: Callable[[], str],
    make_temp_file_name: Callable[[], str],
):
    dir_1 = make_temp_folder_name()
    dir_2 = make_temp_folder_name()
    file_1 = make_temp_file_name()
    file_2 = make_temp_file_name()

    Path(dir_1).mkdir()
    Path(file_1).touch()

    script_code = f"""\
T.use("fs")
assert T.size("fs//{dir_1}") > 0
"""

    await execute(script_code, resolver)

    script_code = f"""\
T.use("fs")
assert T.size("fs//{dir_2}") > 0
"""
    with pytest.raises(TpyAssertionError):
        await execute(script_code, resolver)

    script_code = f"""\
T.use("fs")
assert T.size("fs//{file_1}") > 0
"""
    await execute(script_code, resolver)

    script_code = f"""\
T.use("fs")
assert T.size("fs//{file_2}") > 0
"""
    with pytest.raises(TpyAssertionError):
        await execute(script_code, resolver)


@pytest.mark.asyncio
async def test_workingdir(
    resolver: _Resolver, make_temp_folder_name: Callable[[], str]
):
    tmp_dir = make_temp_folder_name()

    script_code = f"""\
T.use("fs")
T.set_working_dir("fs//", {tmp_dir!r})
cwd = T.get_working_dir("fs//")
"""

    ret = await execute(script_code, resolver)

    assert ret["cwd"].endswith(tmp_dir)

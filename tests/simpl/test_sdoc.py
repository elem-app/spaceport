import os
import uuid
from typing import Any, Callable

import pytest

from spaceport import tpyi
from spaceport.tpyi.errors import TpyOperationError
from spaceport_simpl import SDocEditor


@pytest.fixture(name="make_temp_file_name")
def make_temp_file_name_():
    created: list[str] = []

    def make_temp_file_name(suffix: str = ""):
        name = f"tmp-{uuid.uuid4()}{suffix}"
        created.append(name)
        return name

    yield make_temp_file_name

    if not os.environ.get("TEST_NO_CLEANUP"):
        for name in created:
            try:
                os.remove(name)
            except FileNotFoundError:
                pass


class _Resolver:
    def __init__(self):
        self.subject = SDocEditor()

    async def resolve(self, name: str | None, **kwargs: Any) -> SDocEditor | None:
        if name == "sdoc":
            return self.subject
        return None


@pytest.fixture
def resolver():
    return _Resolver()


@pytest.mark.asyncio
async def test_read_node(resolver: _Resolver, make_temp_file_name: Callable[[], str]):
    file_1_name = make_temp_file_name()
    file_2_name = make_temp_file_name()

    with open(file_1_name, "w+") as f:
        f.write("""a: 1""")

    with open(file_2_name, "w+") as f:
        f.write("""b: 2""")

    script_code = f"""\
T.use("sdoc")
T.open_document("sdoc//", path={file_1_name!r}, doc_type="application/yaml")
a = T.read_node("sdoc//a")
assert a[0] == 1
T.open_document("sdoc//", path={file_2_name!r}, doc_type="application/yaml")
b = T.read_node("sdoc//b")
assert b[0] == 2
"""

    await tpyi.execute(script_code, resolver)


@pytest.mark.asyncio
async def test_doc_not_opened(resolver: _Resolver):
    with pytest.raises(TpyOperationError):
        await tpyi.execute(
            """\
T.use("sdoc")
T.read_node('sdoc//a')
""",
            resolver,
        )


@pytest.mark.asyncio
async def test_infer_doc_type(
    resolver: _Resolver, make_temp_file_name: Callable[[str], str]
):
    file_name = make_temp_file_name(".yaml")
    with open(file_name, "w+") as f:
        f.write("""a: 1""")

    await tpyi.execute(
        f"""\
T.use("sdoc")
T.open_document('sdoc//', path={file_name!r})
t = T.get_document_type('sdoc//')
assert t == 'application/yaml'
""",
        resolver,
    )


@pytest.mark.asyncio
async def test_write_node(resolver: _Resolver, make_temp_file_name: Callable[[], str]):
    file_name = make_temp_file_name()
    with open(file_name, "w+") as f:
        f.write("""a: 0""")

    script_code = f"""\
T.use("sdoc")
T.open_document('sdoc//', path={file_name!r}, doc_type="application/yaml")
T.write_node('sdoc//a', [1], {{}})
"""
    await tpyi.execute(script_code, resolver)
    with open(file_name, "r") as f:
        assert f.read() == "a:\n  - 1\n"

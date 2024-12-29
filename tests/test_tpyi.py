from contextlib import asynccontextmanager
from typing import Any, override

import pytest

from spaceport.subject import TSL, Handle, Subject
from spaceport.tpyi import execute
from spaceport.tpyi.errors import (
    TpyAssertionError,
    TpyOperationError,
    TpyRuntimeError,
    TpySubjectError,
)


class MockHandle(Handle):
    def __init__(self):
        self.counter = 0

    @override
    @asynccontextmanager
    async def bind(self):
        print("binding")
        self.counter += 1
        yield

    def size(self) -> int:
        return 1

    def is_collection(self) -> bool:
        return False

    def click(self) -> str:
        print("clicked")
        return "clicked"

    def increment(self, other: int) -> int:
        return 1 + other

    def stringify(self) -> str:
        return "mock handle"


class MockSubject(Subject[MockHandle]):
    def __init__(self):
        self.handle = MockHandle()

    @override
    async def search(self, tsl: TSL, op_name: str) -> MockHandle:
        return self.handle


class MockResolver:
    def __init__(self):
        self.subject = MockSubject()

    async def resolve(self, name: str | None, **kwargs: Any) -> MockSubject:
        if name is None:
            raise ValueError("name is required")
        return self.subject


@pytest.mark.asyncio
async def test_execute():
    resolver = MockResolver()
    ret = await execute(
        """\
T.use("subj")
x = T.target("gui//button")
assert T.size(x) == 1
y = T.click(x)
z = y[1:]
assert T.stringify(x) == "mock handle"
""",
        resolver,
    )
    assert ret["y"] == "clicked"
    assert ret["z"] == "licked"

    ret = await execute(
        """\
T.use("subj")
x = T.increment("//", 1)
""",
        resolver,
    )
    assert ret["x"] == 2
    assert resolver.subject.handle.counter == 5


@pytest.mark.asyncio
async def test_execute_error_lineno():
    resolver = MockResolver()
    with pytest.raises(TpyRuntimeError) as exc:
        await execute("x", resolver)
    assert exc.value.lineno == 1

    with pytest.raises(TpyAssertionError) as exc:
        await execute("x = 1\nassert x == 2", resolver)
    assert exc.value.lineno == 2

    with pytest.raises(TpySubjectError) as exc:
        await execute("T.use(None)", resolver)
    assert exc.value.lineno == 1

    with pytest.raises(TpyOperationError) as exc:
        await execute("# comment\nT.use('//')\nT.add('//', 1)", resolver)
    assert exc.value.lineno == 3


@pytest.mark.asyncio
async def test_execute_error_message():
    resolver = MockResolver()
    with pytest.raises(TpySubjectError) as exc:
        await execute("T.use(None, x=1)", resolver)
    assert str(exc.value) == "T.use(None, x=1): name is required"

    with pytest.raises(TpyOperationError) as exc:
        await execute("T.use('subj')\nT.add('//', 1)", resolver)
    assert str(exc.value) == "T.add('//', 1): Operation 'add' not found on handle"

    with pytest.raises(TpyOperationError) as exc:
        await execute("T.use('subj')\nT.increment('//', other='a')", resolver)
    assert str(exc.value).startswith("T.increment('//', other='a'): ")

    with pytest.raises(TpyAssertionError) as exc:
        await execute("T.use('subj')\nassert 1 == 2", resolver)
    assert str(exc.value) == "Cannot assert 1 == 2"

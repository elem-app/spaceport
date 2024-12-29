from contextlib import asynccontextmanager
from typing import override

from spaceport.subject import TSL, Handle, Subject


class DummyHandle(Handle):
    @override
    @asynccontextmanager
    async def bind(self):
        yield

    @override
    async def size(self) -> int:
        return 1

    @override
    def is_collection(self) -> bool:
        return False


class DummySubject(Subject[DummyHandle]):
    @override
    async def search(self, tsl: TSL, op_name: str) -> DummyHandle:
        return DummyHandle()

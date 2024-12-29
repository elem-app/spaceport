from typing import Any, Protocol

from spaceport.subject import Handle, Subject


class Resolver[T: Handle](Protocol):
    async def resolve(self, name: str | None, **kwargs: Any) -> Subject[T] | None: ...

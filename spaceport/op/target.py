"""Operations on targets that are components of the test subject."""

from abc import ABC, abstractmethod
from typing import Self


class Target(ABC):
    def target(self) -> Self:
        """Return the target itself.

        Usage: `x = T.target("term//input")` assigns `x` to the target designated by `term//input`.
        Usage: `T.click(T.target("gui//button"))` is equivalent to `T.click("gui//button")`.
        """
        return self

    @abstractmethod
    async def size(self) -> int:
        """Return the number of components in the target.

        If the target's cardinality is not collection-like, always return 1.

        Fails: if the target's cardinality is not collection-like yet the target does not exist.

        Usage: `assert T.size("gui//button") == 1` checks that there is exactly one button.
        """

    @abstractmethod
    def is_collection(self) -> bool:
        """Return whether the target is a collection of components.

        Usage: `assert T.is_collection("all:gui//button")` passes since the cardinality is ``all``.
        Usage: `assert not T.is_collection("unique:table//user/id=1")` passes since the cardinality is ``unique``.
        """

    async def has_some(self) -> bool:
        """Check if the TSL matches at least one target component.

        If the TSL asks for a collection, this method returns `True` if there is at least one component that matches the TSL. Otherwise, always returns `True`.

        Usage: `T.has_some("all:gui//button")` returns `True` if there are any buttons.
        Usage: `T.has_some("unique:gui//button")` returns `True` if there is uniquely one button.
        """
        return (await self.size()) > 0

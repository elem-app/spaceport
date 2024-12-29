"""Types for working with test subjects."""

import ast
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Self

from spaceport.op import target


class TSLError(Exception):
    """An error parsing a TSL."""


class CardinalityError(Exception):
    """An error in the cardinality of the target identified by a TSL."""

    def __init__(
        self,
        expected: str,
        *,
        actual_count: str | int | None = None,
        reason: str | None = None,
    ):
        if actual_count is not None:
            super().__init__(f"Expected '{expected}' but found {actual_count} targets")
        elif reason is not None:
            super().__init__(f"Expected '{expected}' but {reason}")
        else:
            super().__init__(f"Expected '{expected}' but got an error")


class TSL(str):
    """A TSL expression that describes a target.

    A TSL expression is a slash-separated path that starts with ``//``, optionally
    prefixed by a cardinality marker and a header.

    The cardinality marker specifies how to handle the case when multiple targets match
    the query. When it is included, it must be followed by a ``:``. For example,
    ``all://...`` indicates that the target is a collection of items.

    The header specifies the type of subject. For example, ``gui//...`` indicates that
    the target is an element of a graphical user interface.
    """

    def __new__(cls, value: object) -> Self:
        if isinstance(value, cls):
            return value
        s = super().__new__(cls, value)
        dslash_pos = s.find("//")
        if dslash_pos == -1:
            raise ValueError("Invalid target format: '//' not found")
        return s

    def __init__(self, value: object) -> None:
        super().__init__()
        self._dslash_pos = self.index("//")
        self._colon_pos = self.find(":", 0, self._dslash_pos)

    @property
    def cardinality(self) -> str:
        """The cardinality marker of the target.

        The cardinality marker is the part of the target before ``:``.
        """
        return self[: self._colon_pos] if self._colon_pos != -1 else ""

    @property
    def header(self) -> str:
        """The header of the target.

        The header is the part of the target between ``:`` and ``//``.
        """
        return self[self._colon_pos + 1 : self._dslash_pos]

    @property
    def body(self) -> str:
        """The body of the target.

        The body is the part of the target after the header and ``//``.
        """
        return self[self._dslash_pos + 2 :]

    def body_parts(self) -> list[str]:
        """The parts of the target's body split by '/'.

        For example, ``//table/column/condition`` would be split into ``["table",
        "column", "condition"]``.

        An empty body is split into ``[""]``. Also, if a part is a string literal inside
        quotes, it is unquoted and unescaped, so ``//"table \\"users\\""`` would be split
        into ``['table "users"']``.
        """
        parts = self.body.split("/")
        return [
            # Unquote string literals
            ast.literal_eval(f"{part}")
            if (part.startswith('"') and part.endswith('"'))
            or (part.startswith("'") and part.endswith("'"))
            else part
            for part in parts
        ]


class Handle(target.Target):
    """A handle to one or more target components that are identified by a TSL."""

    @abstractmethod
    @asynccontextmanager
    async def bind(self) -> AsyncGenerator[None, None]:
        """Bind the handle to the target component(s).

        This method binds the handle to the underlying component(s). It is called before
        each operation.

        .. Important::

            It is expected that calling this method at different times may yield
            different results, so long as the subject may have been mutated between
            the calls.

        :raises CardinalityError: If the bound handle does not have the expected
            cardinality as specified by the TSL.
        """
        ...


class Subject[T: Handle](ABC):
    """Base class for test subjects.

    A subject implementation is responsible for:
    * defining a handle type that implements proper operation interfaces to interact
      with the subject's components for testing
    * parsing a TSL expression and providing a handle to the target component(s)
    """

    @abstractmethod
    async def search(self, tsl: TSL, op_name: str) -> T:
        """Search for the target component(s) described by a TSL and return a handle.

        :param tsl: The TSL expression that describes the target component(s).
        :param op_name: The operation that triggered this target search, provided as a
            hint to help optimize the search process.

        :returns: A handle constructed from the TSL.

        :raises TSLError: If the TSL is not parseable by this subject.
        """

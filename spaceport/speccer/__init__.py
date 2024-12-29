"""Spec and code generation."""

from abc import ABC, abstractmethod
from typing import override


class Postprocessor(ABC):
    @abstractmethod
    async def process(self, code: str) -> str:
        """Postprocess a code snippet."""

    @staticmethod
    def chain(*postprocessors: "Postprocessor") -> "Postprocessor":
        """Chain multiple postprocessors together.

        The postprocessors will be applied in the order they are given.

        :returns: A single postprocessor that applies all the given postprocessors.
        """
        return _PostprocessorSeq(*postprocessors)


class _PostprocessorSeq(Postprocessor):
    def __init__(self, *postprocessors: Postprocessor) -> None:
        self._postprocessors = postprocessors

    @override
    async def process(self, code: str) -> str:
        for p in self._postprocessors:
            code = await p.process(code)
        return code

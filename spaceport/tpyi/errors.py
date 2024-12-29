from typing import Any


class TpyError(Exception):
    """A base class for all test code errors."""

    def __init__(
        self,
        message: str,
        lineno: int | None = None,
        locals: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.lineno = lineno
        self.locals = locals


class TpySubjectError(TpyError):
    """An error in a `T.use()` call."""


class TpyOperationError(TpyError):
    """An error in an operation."""


class TpyAssertionError(TpyError):
    """An error in an assertion."""


class TpyRuntimeError(TpyError):
    """A runtime error that occurs during test script execution.

    This error is raised when there is a problem that doesn’t fall in any of the other
    categories.
    """

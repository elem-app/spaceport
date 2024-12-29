from typing import Literal, cast


class NoneValueError(ValueError):
    """Error raised when an optional value is None."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


def unwrap[T](opt: T | None, err: str | Exception | None = None) -> T:
    """Unwrap an optional value, otherwise raise an error."""

    if opt is not None:
        return opt

    if isinstance(err, Exception):
        raise err
    else:
        raise NoneValueError(err or "Optional value is None")


class NotGiven:
    """A marker class to indicate that a value is not given."""

    _instance: "NotGiven"
    STR_REPR: str = "<NOT_GIVEN>"

    def __new__(cls) -> "NotGiven":
        if not hasattr(cls, "_instance"):
            cls._instance = super().__new__(cls)
        return cls._instance

    def __bool__(self) -> Literal[False]:
        return False

    def dump(self) -> str:
        return self.STR_REPR


NOT_GIVEN = NotGiven()


def assume_given[T](value: T | NotGiven) -> T:
    """Assume that the value is given.

    NOTE: This should only be used in cases where the caller can guarantee that the
    value is indeed given.
    """
    return cast(T, value)

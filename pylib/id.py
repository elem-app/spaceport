import uuid
from typing import Any, ClassVar, Self, cast


class TypedID[T]:
    type_name: ClassVar[str]
    """The name of the type of ID."""

    def __init__(self, raw: T, /, *args: Any, **kwargs: Any) -> None:
        self.raw = raw

    def __str__(self) -> str:
        return f"{self.type_name}::{self.raw}"

    def __repr__(self) -> str:
        return f"{self.type_name}::{self.raw}"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, TypedID):
            return False
        other = cast(TypedID[T], other)
        return self.raw == other.raw and self.type_name == other.type_name

    def __hash__(self) -> int:
        return hash((self.raw, self.type_name))


class TypedUUID(TypedID[uuid.UUID]):
    @classmethod
    def random(cls, *args: Any, **kwargs: Any) -> Self:
        return cls(uuid.uuid4(), *args, **kwargs)

    @classmethod
    def from_int(cls, value: int, *args: Any, **kwargs: Any) -> Self:
        return cls(uuid.UUID(int=value), *args, **kwargs)

    @classmethod
    def from_hex(cls, value: str, *args: Any, **kwargs: Any) -> Self:
        return cls(uuid.UUID(hex=value), *args, **kwargs)

    @classmethod
    def uuid5(cls, ns: uuid.UUID, name: str, *args: Any, **kwargs: Any) -> Self:
        return cls(uuid.uuid5(ns, name), *args, **kwargs)


class TypedStrID(TypedID[str]):
    pass


class TypedIntID(TypedID[int]):
    def __lt__(self, other: object) -> bool:
        if not isinstance(other, TypedIntID):
            return NotImplemented
        return self.raw < other.raw

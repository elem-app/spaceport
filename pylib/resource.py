"""Classes for representing file system resources."""

import glob
from abc import ABC, abstractmethod
from pathlib import Path, PurePath
from typing import Iterator


class Resource(ABC):
    """A resource is a file or directory on the local file system or a remote server."""

    @property
    @abstractmethod
    def location(self) -> str:
        pass

    @abstractmethod
    def is_dir(self) -> bool:
        pass


class LocalFile(Resource):
    def __init__(self, path: str | PurePath) -> None:
        self.path = Path(path)
        if self.path.is_dir():
            raise ValueError("Path is a directory")

    @property
    def location(self) -> str:
        return str(self.path)

    def is_dir(self) -> bool:
        return False


class LocalDir(Resource):
    def __init__(self, path: str | PurePath) -> None:
        self.path = Path(path)
        if not self.path.is_dir():
            raise ValueError("Path is not a directory")

    @property
    def location(self) -> str:
        return str(self.path)

    def list_files(
        self, *, include_hidden: bool = False, recursive: bool = False
    ) -> Iterator[LocalFile]:
        pattern = self.path / ("**/*" if recursive else "*")
        for p in glob.glob(
            str(pattern), recursive=recursive, include_hidden=include_hidden
        ):
            try:
                yield LocalFile(p)
            except ValueError:
                pass

    def is_dir(self) -> bool:
        return True


def local(path: str | PurePath) -> LocalFile | LocalDir:
    p = Path(path)
    if p.is_dir():
        return LocalDir(p)
    return LocalFile(p)


class RemoteFile(Resource):
    def __init__(self, url: str) -> None:
        self._url = url

    @property
    def location(self) -> str:
        return self._url

    def is_dir(self) -> bool:
        return False

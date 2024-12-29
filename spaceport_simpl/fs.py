import shutil
from abc import ABC
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator, Generic, TypeVar, cast, override

from pylib.optional import NOT_GIVEN
from spaceport.op import fs
from spaceport.subject import TSL, CardinalityError, Handle, Subject, TSLError
from spaceport.subject.factory import (
    ManagedSubject,
    Resource,
    SubjectFactory,
    managed_subject,
)

PathT_co = TypeVar("PathT_co", bound=Path, covariant=True)


class WorkdirHolder(ABC, Generic[PathT_co]):
    """An object that has a working directory."""

    workdir: PathT_co


class FileOrFolder(
    Generic[PathT_co],
    Handle,
    fs.CreateFile,
    fs.CreateDir,
    fs.Read,
    fs.Write,
    fs.Delete,
    fs.Move,
    fs.Copy,
    fs.List,
    fs.WorkingDir,
):
    def __init__(
        self, subject: WorkdirHolder[PathT_co], path_str: str, cardinality: str
    ):
        self.subject = subject
        self.path_str = path_str
        self.ending_slash = path_str.endswith("/")
        self.cardinality = cardinality

    @override
    @asynccontextmanager
    async def bind(self) -> AsyncIterator[None]:
        self._path = self.subject.workdir / self.path_str
        if self.ending_slash:
            if self.cardinality != "all":
                raise CardinalityError(
                    self.cardinality, reason="targeting content inside a directory"
                )
            if not self._path.is_dir():
                raise CardinalityError(self.cardinality, reason="path not a directory")
        elif self.cardinality == "all":
            raise CardinalityError(
                self.cardinality, reason="not targeting content inside a directory"
            )

        yield

    @override
    async def size(self) -> int:
        if self.ending_slash:
            return len(list(self._path.iterdir()))
        else:
            return 1 if self._path.exists() else 0

    @override
    def is_collection(self) -> bool:
        return self.ending_slash

    @override
    def create_file(self, data: str | bytes) -> None:
        if isinstance(data, str):
            data = data.encode("utf-8")
        self._path.write_bytes(data)

    @override
    def create_dir(self) -> None:
        self._path.mkdir(parents=True, exist_ok=True)

    @override
    def read_bytes(self) -> bytes:
        return self._path.read_bytes()

    @override
    def read_text(self, encoding: str) -> str:
        return self._path.read_text(encoding=encoding)

    @override
    def append_bytes(self, data: bytes) -> None:
        self._path.write_bytes(data)

    @override
    def move(self, dest: str) -> None:
        to_ending_slash = dest.endswith("/")
        dest_path = self.subject.workdir / dest
        if self.ending_slash and not to_ending_slash:
            raise ValueError("Cannot move all contents inside a folder to a file")
        if not self.ending_slash and to_ending_slash:
            # According to the docs, shutil.move will move the source _into_ the
            # dest if the latter exists. So we create the dest to ensure that
            # the source is moved into it.
            if not dest_path.exists():
                dest_path.mkdir(parents=True)
            shutil.move(self._path, dest_path)
            return
        if self.ending_slash and to_ending_slash:
            for p in self._path.iterdir():
                # According to the docs, shutil.move will move the source _into_ the
                # dest if the latter exists. But we want to avoid moving the entire
                # source path into the dest, so we move individual files under it
                shutil.move(p, dest_path / p.name)
            return

        self._path.rename(dest_path)

    @override
    def copy(self, dest: str) -> None:
        to_ending_slash = dest.endswith("/")
        dest_path = self.subject.workdir / dest
        if self.ending_slash and not to_ending_slash:
            raise ValueError("Cannot move all contents inside a folder to a file")
        if not self.ending_slash and to_ending_slash:
            if self._path.is_dir():
                shutil.copytree(self._path, dest_path / self._path.name)
            else:
                shutil.copy(self._path, dest_path / self._path.name)
            return
        if self.ending_slash and to_ending_slash:
            shutil.copytree(self._path, dest_path, dirs_exist_ok=True)
            return

        if self._path.is_dir():
            shutil.copytree(self._path, dest_path)
        else:
            shutil.copy(self._path, dest_path)

    @override
    def list(self) -> list[str]:
        return [str(p) for p in self._path.iterdir()]

    @override
    def set_working_dir(self, dest: str) -> None:
        if dest.startswith("/"):
            self.subject.workdir = type(self.subject.workdir)(dest).resolve()
        else:
            self.subject.workdir = (self.subject.workdir / dest).resolve()
        self.subject.workdir.mkdir(parents=True, exist_ok=True)

    @override
    def get_working_dir(self) -> str:
        return str(self.subject.workdir)

    @override
    def delete(self) -> None:
        if not self._path.exists():
            return
        if self.ending_slash and self._path.is_dir():
            for p in self._path.iterdir():
                if p.is_dir():
                    shutil.rmtree(p)
                else:
                    p.unlink()
            return
        if self._path.is_dir():
            shutil.rmtree(self._path)
        else:
            self._path.unlink()


class FS(Subject[FileOrFolder[Path]], WorkdirHolder[Path]):
    """A subject implementation that interacts with the file system.

    Acceptable TSL headers: ``fs``.
    """

    def __init__(self, workdir: str | Path = "."):
        """Initialize a file system subject.

        :param workdir: The working directory. Defaults to the current working
            directory.
        """
        if isinstance(workdir, Path):
            self.workdir = workdir.resolve()
        else:
            self.workdir = Path(workdir).resolve()

    @override
    async def search(self, tsl: TSL, op_name: str) -> FileOrFolder[Path]:
        if tsl.header != "fs":
            raise TSLError('FS expects a "fs" header')

        return FileOrFolder(self, tsl.body, tsl.cardinality or "unique")


ManagedFS = managed_subject(FS)


class _FSResource(Resource):
    def __init__(self, path: Path, deinit_policy: str):
        self.path = path.resolve()
        if not path.exists():
            path.mkdir(parents=True)
        self.deinit_policy = deinit_policy

    @override
    async def deinit(self) -> None:
        match self.deinit_policy:
            case "delete":
                shutil.rmtree(self.path)
            case "delete_contents":
                for p in self.path.iterdir():
                    if p.is_dir():
                        shutil.rmtree(p)
                    else:
                        p.unlink()
            case "keep":
                pass
            case _:
                raise ValueError(f"Unknown deinit policy: {self.deinit_policy}")


class FSFactory(SubjectFactory[FileOrFolder[Path]]):
    """A managed FS subject that supports file system operations with auto resource
    management.

    Acceptable TSL headers: ``fs``.
    """

    def __init__(self, root: str = "."):
        self.root = Path(root).resolve()
        assert self.root.exists()

    @override
    async def create(self, **kwargs: Any) -> ManagedSubject[FileOrFolder[Path]]:
        """Create a managed file system subject.

        :param workdir: The working directory. Can be either a path string or a
            dictionary with ``value`` and ``deinit`` keys. If a path string, it
            will be resolved relative to the factory's root and must be an existing
            directory. No auto setup or cleanup will be performed.
            If a dictionary, the ``value`` key is required and specifies the working
            directory path, and the ``deinit`` key specifies the deinitialization
            policy. Options for the ``deinit`` key are ``"delete"``,
            ``"delete_contents"``, and ``"keep"``.
            Recommended to use a dictionary with ``deinit`` set to ``"delete"``.
        """
        workdir = kwargs.get("workdir", NOT_GIVEN)
        if isinstance(workdir, dict):
            workdir_dict = cast(dict[Any, Any], workdir)
            deinit_policy = cast(str, workdir_dict["deinit"])
            value = cast(str, workdir_dict["value"])
            path = self.root / value
            return ManagedFS((_FSResource(path, deinit_policy),), workdir=path)
        elif workdir is NOT_GIVEN:
            return ManagedFS((), workdir=self.root)
        else:
            return ManagedFS((), workdir=self.root / workdir)

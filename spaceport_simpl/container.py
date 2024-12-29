import asyncio
import hashlib
import io
import tarfile
from contextlib import asynccontextmanager
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any, Literal, Self, Sequence, cast, override

from pydantic import BaseModel, Field
from ruamel.yaml import YAML

from pylib.optional import unwrap
from pylib.string import extract_tagged
from spaceport.op import fs, sdoc
from spaceport.subject import TSL, Handle, Subject, TSLError
from spaceport.subject.factory import (
    ManagedSubject,
    Resource,
    SubjectFactory,
    managed_subject,
)

from .fs import FileOrFolder, WorkdirHolder
from .repl import Buffer, Cursor, InputQuery, KeyboardEvent, OutputQuery, REPLSubject

if TYPE_CHECKING:
    from docker.models.containers import Container as DockerContainer

yaml = YAML()


class ContainerAbsolutePath(type(Path())):
    """A path to a file or folder in a Docker container."""

    def __init__(self, container: "DockerContainer", *path_parts: str):
        super().__init__(*path_parts)
        self.container = container
        # Convert to posix path since Docker containers use Linux-style paths
        self._posix = PurePosixPath(*path_parts)

    def __new__(cls, container: "DockerContainer", *path_parts: str):
        # Required for Path subclassing
        if not path_parts or not path_parts[0].startswith("/"):
            raise ValueError("Path must be absolute")
        return super().__new__(cls, *path_parts)

    def __str__(self) -> str:
        return str(self._posix)

    @override
    def with_segments(self, *parts: ...) -> Self:
        return type(self)(self.container, *self.parts, *parts)

    @override
    def __truediv__(self, key: ...) -> Self:
        return self.with_segments(self, key)

    @override
    def exists(self, *, follow_symlinks: bool = True) -> bool:
        exit_code, _ = self.container.exec_run(f"test -e {self._posix}")  # pyright: ignore[reportUnknownMemberType]
        return exit_code == 0

    @override
    def is_file(self) -> bool:
        exit_code, _ = self.container.exec_run(f"test -f {self._posix}")  # pyright: ignore[reportUnknownMemberType]
        return exit_code == 0

    @override
    def is_dir(self) -> bool:
        exit_code, _ = self.container.exec_run(f"test -d {self._posix}")  # pyright: ignore[reportUnknownMemberType]
        return exit_code == 0

    @override
    def read_text(self, encoding: str | None = None, errors: str | None = None) -> str:
        _, output = self.container.exec_run(f"cat {self._posix}")  # pyright: ignore[reportUnknownMemberType]
        return output.decode(encoding or "utf-8")

    @override
    def read_bytes(self) -> bytes:
        _, output = self.container.exec_run(f"cat {self._posix}")  # pyright: ignore[reportUnknownMemberType]
        return output

    @override
    def write_bytes(self, data: ...) -> int:
        _, _ = self.container.exec_run(  # pyright: ignore[reportUnknownMemberType]
            f"sh -c \"echo -n '{data.hex()}' | xxd -r -p > {self._posix}\""
        )
        return len(data)

    @override
    def mkdir(self, mode: int = 0o777, parents: bool = False, exist_ok: bool = False):
        self.container.exec_run(  # pyright: ignore[reportUnknownMemberType]
            f"mkdir {'-p' if parents or exist_ok else ''} {f'-m {mode}' if mode else ''} {self._posix}"
        )

    @override
    def iterdir(self):
        _, output = self.container.exec_run(f"ls -1 {self._posix}")  # pyright: ignore[reportUnknownMemberType]
        for name in output.decode().splitlines():
            yield self / name

    def move(self, to: str, contents: bool = False) -> None:
        if self.is_dir():
            if contents:
                if not to.endswith("/"):
                    raise ValueError(
                        "Cannot move directory contents to a non-directory"
                    )
                self.container.exec_run(f"mv -r {self._posix}/ {to}")  # pyright: ignore[reportUnknownMemberType]
            else:
                self.container.exec_run(f"mv {self._posix} {to}")  # pyright: ignore[reportUnknownMemberType]
        else:
            self.container.exec_run(f"mv {self._posix} {to}")  # pyright: ignore[reportUnknownMemberType]

    def copy(self, to: str, contents: bool = False) -> None:
        if self.is_dir():
            if contents:
                if not to.endswith("/"):
                    raise ValueError(
                        "Cannot copy directory contents to a non-directory"
                    )
                self.container.exec_run(f"cp -r {self._posix}/ {to}")  # pyright: ignore[reportUnknownMemberType]
            else:
                self.container.exec_run(f"cp -r {self._posix} {to}")  # pyright: ignore[reportUnknownMemberType]
        else:
            self.container.exec_run(f"cp {self._posix} {to}")  # pyright: ignore[reportUnknownMemberType]

    def delete(self, contents: bool = False) -> None:
        if self.is_dir():
            if contents:
                self.container.exec_run(f"rm -rf {self._posix}/")  # pyright: ignore[reportUnknownMemberType]
            else:
                self.container.exec_run(f"rm -rf {self._posix}")  # pyright: ignore[reportUnknownMemberType]
        else:
            self.container.exec_run(f"rm -f {self._posix}")  # pyright: ignore[reportUnknownMemberType]


class ContainerCursor(Cursor, fs.WorkingDir):
    def __init__(self, subject: "_Container", query: InputQuery | OutputQuery | None):
        super().__init__(query, subject.repl_delegate)
        self.workdir_holder = subject

    @override
    def get_working_dir(self) -> str:
        return str(self.workdir_holder.workdir)

    @override
    def set_working_dir(self, dest: str) -> None:
        self.workdir_holder.workdir /= dest
        self.workdir_holder.workdir.mkdir(parents=True, exist_ok=True)


class ContainerFileOrFolder(FileOrFolder[ContainerAbsolutePath]):
    def __init__(self, subject: "_Container", path_str: str, cardinality: str):
        super().__init__(subject, path_str, cardinality)
        self.workdir_holder = subject

    @override
    def get_working_dir(self) -> str:
        return str(self.workdir_holder.workdir)

    @override
    def set_working_dir(self, dest: str) -> None:
        self.workdir_holder.workdir /= dest
        self.workdir_holder.workdir.mkdir(parents=True, exist_ok=True)

    @override
    def move(self, dest: str) -> None:
        if self.ending_slash:
            self._path.move(dest, contents=True)
        else:
            self._path.move(dest)

    @override
    def copy(self, dest: str) -> None:
        if self.ending_slash:
            self._path.copy(dest, contents=True)
        else:
            self._path.copy(dest)

    @override
    def delete(self) -> None:
        if self.ending_slash:
            self._path.delete(contents=True)
        else:
            self._path.delete()


class ContainerStructuredDoc(Handle, sdoc.ReadDocument):
    def __init__(self, subject: "_Container", query: list[str | int]):
        self.subject = subject
        self.query = query

    @override
    @asynccontextmanager
    async def bind(self):
        if self.subject.opened_doc_path:
            self._doc_content = self.subject.opened_doc_path.read_text()
            yield
        else:
            yield

    @override
    async def size(self) -> int:
        return 1

    @override
    def is_collection(self) -> bool:
        return False

    @override
    def open_document(self, path: str, doc_type: str | None = None) -> None:
        p = self.subject.workdir / path
        self.subject.opened_doc_path = p
        if doc_type:
            self.subject.opened_doc_type = doc_type
        else:
            match p.suffix:
                case ".yaml" | ".yml":
                    self.subject.opened_doc_type = "application/yaml"
                case _:
                    raise ValueError(f"Unsupported file type: {path}")

    @override
    def get_document_type(self) -> str:
        return unwrap(self.subject.opened_doc_type)

    @override
    def read_node(self) -> tuple[Any, dict[str, Any]]:
        match unwrap(self.subject.opened_doc_type):
            case "application/yaml":
                return self._read_yaml()
            case _:
                raise NotImplementedError(
                    f"Unsupported document type: {self.subject.opened_doc_type}"
                )

    def _read_yaml(self) -> tuple[Any, dict[str, Any]]:
        content = cast(dict[str | int, Any], yaml.load(self._doc_content))  # pyright: ignore[reportUnknownMemberType]
        if not self.query:
            return content, {}

        n = content
        for sel in self.query:
            try:
                n = n[sel]
            except (KeyError, IndexError):
                return None, {}
        return n, {}


type ContainerHandle = ContainerCursor | ContainerFileOrFolder | ContainerStructuredDoc


class _REPLDelegate(REPLSubject):
    def __init__(self, subject: "_Container"):
        super().__init__()
        self.subject = subject
        self.container = subject.docker_container

    @override
    def try_execute(self, buf: Buffer) -> bool:
        # TODO handle Ctrl-C and other keyboard events
        # Only execute if the buffer ends with Enter
        if not isinstance(buf[-1], KeyboardEvent) or "Enter" not in buf[-1]:
            return False

        # Join all text and keyboard events into a single command string
        cmd = "".join(str(part) for part in buf[:-1])

        self.execution_complete.clear()
        try:
            exit_code, output = self.container.exec_run(  # pyright: ignore[reportUnknownMemberType]
                cmd, workdir=str(self.subject.workdir)
            )
            self.last_exit_code = exit_code
            self.outputs.append(output.decode())
        finally:
            self.execution_complete.set()

        return True


class _Container(Subject[ContainerHandle], WorkdirHolder[ContainerAbsolutePath]):
    def __init__(
        self,
        docker_container: "DockerContainer",
        copy_from_host: Sequence[str] | None = None,
    ):
        self.docker_container = docker_container

        self.workdir = ContainerAbsolutePath(
            docker_container, str(Path.cwd().resolve())
        )
        self.workdir.mkdir(parents=True, exist_ok=True)
        if copy_from_host:
            for src in copy_from_host:
                self._copy_from_host(src)

        self.opened_doc_path: ContainerAbsolutePath | None = None
        self.opened_doc_type: str | None = None

        self.repl_delegate = _REPLDelegate(self)

    def _copy_from_host(self, src: str) -> None:
        src_path = Path(src).resolve()
        stream = io.BytesIO()
        with tarfile.open(src_path.stem + ".tar", mode="w", fileobj=stream) as tar:
            tar.add(src_path)

        self.docker_container.put_archive(  # pyright: ignore[reportUnknownMemberType]
            "/", stream.getvalue()
        )

    @override
    async def search(self, tsl: TSL, op_name: str) -> ContainerHandle:
        match tsl.header:
            case "term" | "cli" | "repl":
                body_parts = iter(tsl.body_parts())
                query_cls_str = next(body_parts)
                match query_cls_str:
                    case "input":
                        query_cls = InputQuery
                    case "output":
                        query_cls = OutputQuery
                    case "":
                        # No query, return a cursor that represents the entire subject
                        return ContainerCursor(subject=self, query=None)
                    case _:
                        raise TSLError(f"Cannot get a cursor for {tsl}")

                query_idx_str = next(body_parts, "0")
                try:
                    query_idx = int(query_idx_str)
                except ValueError:
                    raise TSLError(f"Cannot get a cursor for {tsl}")
                if query_idx > 0:
                    raise TSLError(f"Cannot get a cursor for {tsl}")

                return ContainerCursor(subject=self, query=query_cls(query_idx))

            case "fs" | "filesystem":
                return ContainerFileOrFolder(self, tsl.body, tsl.cardinality)

            case "sdoc":
                query: list[str | int] = []
                for sel in tsl.body_parts():
                    try:
                        query.append(int(sel))
                    except ValueError:
                        pass
                    else:
                        continue
                    try:
                        complex_sel = extract_tagged(sel, "[", "]")
                    except ValueError:
                        query.append(sel)
                    else:
                        raise NotImplementedError(
                            f"Complex selection not supported: {complex_sel}"
                        )

                return ContainerStructuredDoc(self, query)

            case _:
                raise TSLError(f"Cannot get a handle for {tsl}")


Container = managed_subject(_Container)


class _DockerContainerResource(Resource):
    def __init__(self, docker_container: "DockerContainer", do_remove: bool = True):
        self.docker_container = docker_container
        self.do_remove = do_remove

    @override
    async def deinit(self) -> None:
        self.docker_container.stop()
        self.docker_container.wait()
        if self.do_remove:
            self.docker_container.remove()


class REPLContainerFactoryInitParams(BaseModel):
    auto_remove: Literal["all", "container", "none"] = Field(default="container")
    dockerfile: str | None = Field(default=None)


_LATEST_UBUNTU = """\
FROM ubuntu:latest
WORKDIR /
CMD ["tail", "-f", "/dev/null"]
"""


class ContainerFactory(SubjectFactory[ContainerHandle]):
    """A managed container subject that support file system operations,
    non-interactive terminal operations, and structured document editing.

    Acceptable TSL headers: ``fs``, ``sdoc``, ``term``, ``repl``.
    """

    docker: Any = None
    ImageNotFound: Any = None

    def __init__(self, **kwargs: Any):
        if self.docker is None:
            import importlib

            try:
                self.__class__.docker = importlib.import_module("docker")
                self.__class__.ImageNotFound = importlib.import_module(
                    "docker.errors"
                ).ImageNotFound

                # A hack to force docker to use a different build context than the dockerfile
                # See https://github.com/docker/docker-py/issues/2105#issuecomment-613685891
                docker_api_build = importlib.import_module("docker.api.build")
                docker_api_build.process_dockerfile = lambda dockerfile, path: (  # type: ignore
                    "Dockerfile",
                    dockerfile,
                )
            except ImportError:
                raise ImportError("Docker is not installed")

        self.params = REPLContainerFactoryInitParams.model_validate(kwargs)
        self.docker_client = self.docker.from_env()
        if self.params.dockerfile is None:
            dockerfile = _LATEST_UBUNTU
        else:
            dockerfile = Path(self.params.dockerfile).read_text()

        dockerfile_hash = hashlib.sha256(dockerfile.encode()).hexdigest()[:12]
        image_tag = f"spaceport-test:{dockerfile_hash}"

        try:
            self.image = self.docker_client.images.get(image_tag)
        except self.ImageNotFound:
            # dockerfile should be a path but is hacked to be the file content
            # See https://github.com/docker/docker-py/issues/2105#issuecomment-613685891
            self.image, _ = self.docker_client.images.build(
                path=".", dockerfile=dockerfile, rm=True, forcerm=True, tag=image_tag
            )
        self.container_count = 0

    @override
    async def create(self, **kwargs: Any) -> ManagedSubject[ContainerHandle]:
        """Create a managed REPL container subject.

        :param copy_from_host: An optional list of strings where each string is a
            path to a file or directory on the host. The file or directory will be
            copied into the container under the same path.
        """
        docker_container = self.docker_client.containers.run(self.image, detach=True)
        while docker_container.status != "running":
            await asyncio.sleep(0.1)
            docker_container.reload()

        container_resource = _DockerContainerResource(
            docker_container, do_remove=self.params.auto_remove in ("all", "container")
        )
        try:
            return Container(
                [container_resource],
                docker_container=docker_container,
                copy_from_host=kwargs.get("copy_from_host"),
            )
        except Exception:
            await container_resource.deinit()
            raise

    @override
    async def destroy(self) -> None:
        if self.params.auto_remove == "all":
            self.image.remove()

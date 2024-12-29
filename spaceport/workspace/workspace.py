import asyncio
import datetime
from pathlib import Path
from typing import Any, Iterable, Iterator, NamedTuple, Sequence, cast

from spaceport import tpyi
from spaceport.speccer import Postprocessor
from spaceport.speccer.arranger import SubjectArranger

from . import _yaml
from ._filenames import artifact_dir, workspace_manifest_file
from .artifact import Artifact
from .env import Env
from .manifest import (
    ArtifactProjectMetadata,
    ProjectSourcesMetadata,
    RawProjectMetadata,
    WorkspaceManifest,
)


class SpecInfo(NamedTuple):
    name: str
    code_status: str
    """The status of the code generation for the spec.

    May be '*' (fully transpiled) or ' ' (some blocks are not transpiled).
    """


class ListProjectInfo(NamedTuple):
    name: str
    artifact: str | None
    sources: list[str] | None
    specs: list[SpecInfo] | None


class TestError(NamedTuple):
    filename: str
    type_: str
    lineno: int | None
    message: str
    locals: dict[str, Any] | None


class TestReport(NamedTuple):
    spec: str
    err: TestError | None
    timestamp: datetime.datetime
    time: float


class Workspace:
    def __init__(self, root_dir: Path = Path()):
        self._root_dir = root_dir
        self._art_dir = root_dir / artifact_dir()
        if not self._root_dir.exists() or not self._root_dir.is_dir():
            raise ValueError("Root directory does not exist")
        self._env: Env | None = None
        self._postprocessor: Postprocessor | None = None

    @property
    def env(self) -> Env:
        if self._env is None:
            self._env = Env.from_workspace(self._root_dir)
        return self._env

    @property
    def postprocessor(self) -> Postprocessor:
        if self._postprocessor is None:
            self._postprocessor = Postprocessor.chain(SubjectArranger(self.env))
        return self._postprocessor

    @staticmethod
    def dump_new_manifest(root_dir: Path) -> None:
        """Create a new workspace manifest.

        If a manifest file already exists, it will not be overwritten.
        """
        try:
            _ = Workspace._load_manifest(root_dir)
        except FileNotFoundError:
            default_name = root_dir.name
            manifest = WorkspaceManifest(name=default_name, projects=[])
            Workspace._write_manifest(root_dir, manifest)

    @staticmethod
    def _load_manifest(root_dir: Path) -> WorkspaceManifest:
        if (yaml_path := root_dir / workspace_manifest_file()).exists():
            with yaml_path.open("rb") as f:
                return WorkspaceManifest.model_validate(_yaml.load(f))

        else:
            raise FileNotFoundError("No Spaceport manifest file found")

    @staticmethod
    def _write_manifest(root_dir: Path, manifest: WorkspaceManifest) -> None:
        with (root_dir / workspace_manifest_file()).open("wb") as f:
            _yaml.dump(manifest.model_dump(), f)

    def _artifact_path(
        self, proj: ArtifactProjectMetadata | RawProjectMetadata
    ) -> Path:
        match proj:
            case ArtifactProjectMetadata(name=name, artifact=True):
                return self._art_dir / f"{name}.md"
            case ArtifactProjectMetadata(artifact=artifact):
                return self._root_dir / cast(str, artifact)
            case RawProjectMetadata(name=name):
                return self._art_dir / f"{name}.md"

    def add_project(
        self,
        name: str,
        *,
        artifact: str | bool = False,
        sources: Sequence[str] | None = None,
    ) -> None:
        """Add a project to the workspace.

        Use either `artifact` or `sources` but not both. The first item in `sources`
        will be used as the primary source.
        """
        if artifact:
            assert (
                sources is None
            ), "Cannot specify sources when adding an artifact project"
            manifest = self._load_manifest(self._root_dir)
            if any(p.name == name for p in manifest.projects):
                raise ValueError(f"Project {name} already exists")
            manifest.projects.append(
                ArtifactProjectMetadata(name=name, artifact=artifact)
            )
            self._write_manifest(self._root_dir, manifest)

        elif sources:
            manifest = self._load_manifest(self._root_dir)
            if any(p.name == name for p in manifest.projects):
                raise ValueError(f"Project {name} already exists")
            manifest.projects.append(
                RawProjectMetadata(
                    name=name,
                    sources=ProjectSourcesMetadata(
                        primary=sources[0], other=list(sources[1:])
                    ),
                )
            )
            self._write_manifest(self._root_dir, manifest)

        else:
            raise ValueError("No artifact or sources provided")

    def rename_project(self, old: str, new: str) -> None:
        """Rename a project."""
        manifest = self._load_manifest(self._root_dir)
        for p in manifest.projects:
            if p.name == old:
                old_artifact_path = self._artifact_path(p)
                p.name = new
                if old_artifact_path.exists():
                    new_artifact_path = self._artifact_path(p)
                    old_artifact_path.rename(new_artifact_path)
                    artifact = Artifact(old, new_artifact_path)
                    artifact.metadata.project = new
                    artifact.save()
                break
        else:
            raise ValueError(f"Project {old} not found")

        self._write_manifest(self._root_dir, manifest)

    def list_projects(
        self, projects: Iterable[str] | None = None
    ) -> Iterator[ListProjectInfo]:
        """List the given projects.

        If no projects are given, will list all projects in the workspace.

        :returns: An iterator of tuples, where the first element is the project name and the
            second element is a list of specs in the project.
        """
        manifest = self._load_manifest(self._root_dir)

        includes_all = projects is None
        for p in manifest.projects:
            if includes_all or p.name in projects:
                path = self._artifact_path(p)
                if path.exists():
                    artifact = Artifact(p.name, path)
                    specs: list[SpecInfo] = []
                    for s_name, s_blocks in artifact.specs.items():
                        code_missing = len([b for b in s_blocks if not b.code_lines])
                        if code_missing == 0:
                            code_status = "*"
                        else:
                            code_status = " "
                        specs.append(SpecInfo(name=s_name, code_status=code_status))
                    yield ListProjectInfo(
                        name=p.name,
                        artifact=str(path.relative_to(self._root_dir)),
                        sources=[p.sources.primary, *p.sources.other]
                        if isinstance(p, RawProjectMetadata)
                        else None,
                        specs=specs,
                    )
                else:
                    yield ListProjectInfo(
                        name=p.name,
                        artifact=None,
                        sources=[p.sources.primary, *p.sources.other]
                        if isinstance(p, RawProjectMetadata)
                        else None,
                        specs=None,
                    )

    async def rewrite(
        self, projects: Iterable[str] | None = None
    ) -> Sequence[tuple[Path, Path | None]]:
        """Rewrite the given projects into artifacts.

        :returns: A list of tuples, where the first element is the save path of the
            artifact and the second element is the path of the renamed old artifact, if
            it exists.
        """

        manifest = self._load_manifest(self._root_dir)
        if projects is None:
            projs = (p for p in manifest.projects if isinstance(p, RawProjectMetadata))
        else:
            projs = (
                p
                for p in manifest.projects
                if p.name in projects and isinstance(p, RawProjectMetadata)
            )

        async with asyncio.TaskGroup() as tg:
            tasks = [
                tg.create_task(
                    Artifact.rewrite_and_save(
                        p.name,
                        p.sources.primary_as_resource(),
                        p.sources.other_as_resources(),
                        self._artifact_path(p),
                    )
                )
                for p in projs
            ]

        return [t.result() for t in tasks]

    async def transpile(self, projects: Iterable[str] | None = None) -> None:
        """Transpile the given projects."""

        def _get_artifact(proj: ArtifactProjectMetadata | RawProjectMetadata):
            if projects is None or proj.name in projects:
                return Artifact(proj.name, self._artifact_path(proj))
            return None

        manifest = self._load_manifest(self._root_dir)
        projs = (p for proj in manifest.projects if (p := _get_artifact(proj)))

        async with asyncio.TaskGroup() as tg:
            for proj in projs:
                tg.create_task(proj.transpile_and_save(post=self.postprocessor))

    async def transpile_specs(self, project: str, specs: Iterable[str]) -> None:
        """Transpile the given specs into test code."""

        manifest = self._load_manifest(self._root_dir)
        try:
            proj = next(p for p in manifest.projects if p.name == project)
        except StopIteration:
            raise ValueError(f"Project {project} not found")

        artifact = Artifact(project, self._artifact_path(proj))
        await artifact.transpile_and_save(spec_names=specs, post=self.postprocessor)

    async def test(
        self, project: str, specs: Iterable[str] | None = None
    ) -> Sequence[TestReport]:
        """Test the given specs of a project.

        If no specs are given, will test all executable specs in the project.
        """
        manifest = self._load_manifest(self._root_dir)

        try:
            proj = next(p for p in manifest.projects if p.name == project)
        except StopIteration:
            raise ValueError(f"Project {project} not found")

        artifact = Artifact(project, self._artifact_path(proj))
        artifact.save()  # clean up formatting for easier lineno lookup
        async with asyncio.TaskGroup() as tg:
            reports = [
                tg.create_task(self._test_spec(artifact, spec_name))
                for spec_name in specs or artifact.specs
            ]

        return [t.result() for t in reports]

    async def _test_spec(self, artifact: Artifact, spec_name: str) -> TestReport:
        """Test a spec."""
        code = artifact.get_code(spec_name)
        start_time = datetime.datetime.now()
        try:
            async with self.env.resolver() as r:
                await tpyi.execute(code, r)
        except tpyi.TpyError as e:
            lineno = (
                artifact.find_code_lineno(spec_name, e.lineno)
                if e.lineno is not None
                else None
            )
            err = TestError(
                filename=artifact.path.name,
                type_=type(e).__name__,
                lineno=lineno,
                message=str(e),
                locals=e.locals,
            )
        except Exception:
            # TODO handle other exceptions (probably bugs in tpyi)
            raise
        else:
            err = None

        end_time = datetime.datetime.now()
        execution_time = (end_time - start_time).total_seconds()

        return TestReport(
            spec=spec_name, timestamp=start_time, time=execution_time, err=err
        )

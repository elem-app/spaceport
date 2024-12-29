import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, override
from unittest.mock import Mock

import pytest

from spaceport.subject import TSL, Handle, Subject
from spaceport.workspace import Workspace
from spaceport.workspace._filenames import (
    artifact_dir,
    env_manifest_file,
    workspace_manifest_file,
)
from spaceport.workspace.artifact import Artifact
from spaceport.workspace.env import Env


class MockHandle(Handle):
    def __init__(self):
        self.counter = 0

    @override
    @asynccontextmanager
    async def bind(self):
        print("binding")
        self.counter += 1
        yield

    def size(self) -> int:
        return 1

    def is_collection(self) -> bool:
        return False

    def click(self) -> str:
        print("clicked")
        return "clicked"

    def increment(self, other: int) -> int:
        return 1 + other

    def stringify(self) -> str:
        return "mock handle"


class MockSubject(Subject[MockHandle]):
    def __init__(self):
        self.handle = MockHandle()

    @override
    async def search(self, tsl: TSL, op_name: str) -> MockHandle:
        return self.handle


class MockResolver:
    def __init__(self):
        self.subject = MockSubject()

    async def __aenter__(self) -> "MockResolver":
        return self

    async def __aexit__(
        self, exc_type: type | None, exc_value: Any, traceback: Any
    ) -> None:
        pass

    async def resolve(self, name: str | None, **kwargs: Any) -> MockSubject:
        if name is None:
            raise ValueError("name is required")
        return self.subject


@pytest.fixture
def env():
    e = Mock(spec=Env)
    e.resolver.return_value = MockResolver()
    return e


workspace_manifest = """\
name: test-build
projects:
  - name: test-project
    artifact: test-spec.md
"""

artifact = """\
---
project: test-project
created_at: 2024-01-01T00:00:00Z
---
>> Test build
>- USE _homepage_
>- Click the _build_ button
"""


@pytest.mark.asyncio
async def test_build_and_test(env: Mock):
    with tempfile.TemporaryDirectory() as temp_dir:
        (Path(temp_dir) / workspace_manifest_file()).write_text(workspace_manifest)
        (Path(temp_dir) / env_manifest_file()).write_text("subjects: []")
        (Path(temp_dir) / "test-spec.md").write_text(artifact)
        workspace = Workspace(Path(temp_dir))
        await workspace.transpile(("test-project",))
        workspace._env = env  # pyright: ignore[reportPrivateUsage]
        await workspace.test("test-project")


def test_add_and_rename_project():
    # add project and explicitly set artifact path
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir = Path(temp_dir)
        artifact_file = temp_dir / "test.md"
        content_lines = "random\ndata\n"
        artifact_file.write_text(content_lines)
        Artifact("test-project", artifact_file).save()

        Workspace.dump_new_manifest(temp_dir)
        workspace = Workspace(temp_dir)
        workspace.add_project("test-project", artifact=str(artifact_file))

        # reload
        workspace = Workspace(temp_dir)
        assert len(list(workspace.list_projects(projects="test-project"))) == 1
        workspace.rename_project("test-project", "test-project-2")

        # reload
        workspace = Workspace(temp_dir)
        assert len(list(workspace.list_projects(projects="test-project"))) == 0
        assert len(list(workspace.list_projects("test-project-2"))) == 1
        artifact = Artifact("test-project-2", artifact_file)
        assert artifact.metadata.project == "test-project-2"
        assert artifact.content_lines == content_lines.splitlines()

    # add project and use default artifact path
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir = Path(temp_dir)
        artifact_file = temp_dir / artifact_dir() / "test-project.md"
        content_lines = "random\ndata\n"
        artifact_file.parent.mkdir(parents=True)
        artifact_file.write_text(content_lines)
        Artifact("test-project", artifact_file).save()

        Workspace.dump_new_manifest(temp_dir)
        workspace = Workspace(temp_dir)
        workspace.add_project("test-project", artifact=True)

        # reload
        workspace = Workspace(temp_dir)
        assert len(list(workspace.list_projects(projects="test-project"))) == 1
        workspace.rename_project("test-project", "test-project-2")

        # reload
        workspace = Workspace(temp_dir)
        assert len(list(workspace.list_projects(projects="test-project"))) == 0
        assert len(list(workspace.list_projects("test-project-2"))) == 1
        artifact = Artifact(
            "test-project-2", temp_dir / artifact_dir() / "test-project-2.md"
        )
        assert artifact.metadata.project == "test-project-2"
        assert artifact.content_lines == content_lines.splitlines()

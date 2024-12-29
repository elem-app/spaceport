import tempfile
from pathlib import Path
from typing import Any

import pytest

from spaceport.workspace._filenames import env_manifest_file
from spaceport.workspace.env import Env, ManifestTemplates
from spaceport_simpl.dummy import DummySubject


@pytest.fixture
def workspace_path():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d)
        p.joinpath(env_manifest_file()).write_text("""---
impl_pkgs: []
subjects:
  - name: dummy
    impl:
      class: DummySubject
""")

        yield p


@pytest.mark.asyncio
async def test_resolve(workspace_path: Path):
    env = Env.from_workspace(workspace_path)
    async with env.resolver() as resolver:
        subject = await resolver.resolve("dummy")
        assert isinstance(subject, DummySubject)


def test_env_default_manifest():
    with tempfile.TemporaryDirectory() as temp_dir:
        Env.from_workspace(Path(temp_dir))
        assert (Path(temp_dir) / env_manifest_file()).exists()

        from ruamel.yaml import YAML

        yaml = YAML()
        with open(Path(temp_dir) / env_manifest_file(), "rb") as f:
            manifest: Any = yaml.load(f)  # type: ignore
            print(manifest)
        assert len(manifest["subjects"]) > 0


def test_env_add_manifest():
    with tempfile.TemporaryDirectory() as temp_dir:
        Env.load_and_add_template(Path(temp_dir), ("local",))
        assert (Path(temp_dir) / env_manifest_file()).exists()
        manifest = Env.load_manifest(Path(temp_dir))
        assert manifest == ManifestTemplates.local
        Env.load_and_add_template(Path(temp_dir), ("browser",))
        manifest = Env.load_manifest(Path(temp_dir))
        expected = ManifestTemplates.local.merge(ManifestTemplates.browser)
        assert manifest == expected

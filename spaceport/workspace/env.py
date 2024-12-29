import importlib
from pathlib import Path
from typing import Any

import spaceport_simpl
from pylib.optional import NOT_GIVEN
from spaceport.subject import Subject
from spaceport.subject.factory import ManagedSubject, SubjectFactory
from spaceport.subject.impl_pkg import IMPL_PKG_REGISTRY_FUNC, ImplDocs, ImplRegistry

from . import _yaml
from ._filenames import env_manifest_file
from .manifest import (
    EnvManifest,
    SubjectFactoryMetadata,
    SubjectImplClassMetadata,
    SubjectImplFactoryMetadata,
    SubjectMetadata,
)


class SubjectResolver:
    """Resolver of subject references."""

    def __init__(self, env: "Env"):
        self._env = env

    async def __aenter__(self) -> "SubjectResolver":
        self.resolved_subjects: dict[str, Subject[Any]] = {}
        self.factories: dict[str, SubjectFactory[Any]] = {}
        return self

    async def __aexit__(
        self, exc_type: type | None, exc_value: Any, traceback: Any
    ) -> None:
        await self.destroy_subjects()
        await self.destroy_factories()

    async def resolve(self, name: str | None, **kwargs: Any) -> Subject[Any] | None:
        """Resolve a subject reference."""

        if name is None:
            return None
        else:
            if name in self.resolved_subjects:
                return self.resolved_subjects[name]

            if name not in self._env.subject_metadatas:
                raise ValueError(f"Subject {name} not found in env manifest")

            subject_metadata = self._env.subject_metadatas[name]
            subject_metadata.impl.params.update(kwargs)
            subject = await self._resolve_subject(subject_metadata)
            self.resolved_subjects[name] = subject
            return subject

    async def _resolve_subject(self, metadata: SubjectMetadata) -> Subject[Any]:
        """Resolve a subject based on its metadata."""
        match metadata.impl:
            case SubjectImplClassMetadata(class_=class_name, pkg=pkg, params=params):
                if pkg is None:
                    impl_cls = self._env.default_registry[class_name]
                else:
                    self._env.load_registry(pkg)
                    impl_cls = self._env.loaded_registries[pkg][class_name]
                if not issubclass(impl_cls, Subject):
                    raise ValueError(
                        f"Impl class {class_name} is not a subclass of Subject"
                    )
                return impl_cls(**params)
            case SubjectImplFactoryMetadata(factory=factory_name, params=params):
                if factory_name in self.factories:
                    factory = self.factories[factory_name]
                else:
                    factory_metadata = self._env.factory_metadatas[factory_name]
                    pkg = factory_metadata.pkg
                    class_name = factory_metadata.class_
                    factory_params = factory_metadata.params
                    if pkg is None:
                        factory_cls = self._env.default_registry[class_name]
                    else:
                        self._env.load_registry(pkg)
                        factory_cls = self._env.loaded_registries[pkg][class_name]
                    if not issubclass(factory_cls, SubjectFactory):
                        raise ValueError(
                            f"Impl factory class {factory_name} is not a subclass of "
                            "SubjectFactory"
                        )
                    factory = factory_cls(**factory_params)
                    self.factories[factory_name] = factory
                return await factory.create(**params)

    async def destroy_subjects(self) -> None:
        """Destroy all managed subjects."""
        # Destroy managed subjects in reverse order
        for subject in reversed(self.resolved_subjects.values()):
            if isinstance(subject, ManagedSubject):
                await subject.destroy()
        del self.resolved_subjects

    async def destroy_factories(self) -> None:
        """Destroy all managed factories."""
        for factory in reversed(self.factories.values()):
            await factory.destroy()
        del self.factories


class ManifestTemplates:
    local = EnvManifest.model_construct(
        subjects=[
            SubjectMetadata.model_construct(
                name="term",
                impl=SubjectImplClassMetadata.model_construct(class_="BashREPL"),
            ),
            SubjectMetadata.model_construct(
                name="fs",
                impl=SubjectImplClassMetadata.model_construct(class_="FS"),
            ),
            SubjectMetadata.model_construct(
                name="sdoc-editor",
                impl=SubjectImplClassMetadata.model_construct(class_="SDocEditor"),
            ),
        ]
    )

    container = EnvManifest.model_construct(
        factories=[
            SubjectFactoryMetadata.model_construct(
                name="container-factory",
                class_="ContainerFactory",
                params=dict(
                    dockerfile=NOT_GIVEN.dump(),
                    auto_remove="all",
                ),
            ),
        ],
        subjects=[
            SubjectMetadata.model_construct(
                name="container",
                impl=SubjectImplFactoryMetadata.model_construct(
                    factory="container-factory"
                ),
            ),
        ],
    )

    browser = EnvManifest.model_construct(
        factories=[
            SubjectFactoryMetadata.model_construct(
                name="browser-factory",
                class_="BrowserFactory",
            ),
        ],
        subjects=[
            SubjectMetadata.model_construct(
                name="browser",
                impl=SubjectImplFactoryMetadata.model_construct(
                    factory="browser-factory"
                ),
            ),
        ],
    )


def find_not_given_values(data: dict[str, Any]) -> list[str]:
    """Find all values that are NOT_GIVEN.

    Returns:
        list[str]: List of field paths that contain NOT_GIVEN values.
        For example: ['factories[0].params.dockerfile', 'subjects[1].impl.params.image']
    """

    def _check_dict(d: dict[str, Any], path: str = "") -> list[str]:
        not_given_paths: list[str] = []
        for key, value in d.items():
            current_path = f"{path}.{key}" if path else key

            if value == NOT_GIVEN.STR_REPR:
                not_given_paths.append(current_path)
            elif isinstance(value, dict):
                not_given_paths.extend(_check_dict(value, current_path))  # type: ignore
            elif isinstance(value, list):
                not_given_paths.extend(_check_list(value, current_path))  # type: ignore
        return not_given_paths

    def _check_list(lst: list[Any], path: str) -> list[str]:
        not_given_paths: list[str] = []
        for i, item in enumerate(lst):
            current_path = f"{path}[{i}]"

            if item == NOT_GIVEN.STR_REPR:
                not_given_paths.append(current_path)
            elif isinstance(item, dict):
                not_given_paths.extend(_check_dict(item, current_path))  # type: ignore
            elif isinstance(item, list):
                not_given_paths.extend(_check_list(item, current_path))  # type: ignore
        return not_given_paths

    return _check_dict(data)


class Env:
    def __init__(self, manifest: EnvManifest):
        self.impl_pkgs = manifest.impl_pkgs
        self.factory_metadatas = {f.name: f for f in manifest.factories}
        self.subject_metadatas = {s.name: s for s in manifest.subjects}
        self.default_registry: ImplRegistry = getattr(
            spaceport_simpl, IMPL_PKG_REGISTRY_FUNC
        )()
        self.loaded_registries: dict[str, ImplRegistry] = {}

    @staticmethod
    def load_manifest(workspace_dir: Path) -> EnvManifest:
        """Load the env manifest from a workspace directory.

        :raises FileNotFoundError: If no env manifest is found.
        :raises ValueError: If the env manifest contains not-given values.
        """
        if (yaml_path := workspace_dir / env_manifest_file()).exists():
            with yaml_path.open("rb") as f:
                manifest = _yaml.load(f)
                if not_given_values := find_not_given_values(manifest):
                    raise ValueError(
                        f"The following fields are not given: \n  - "
                        f"{'  - \n'.join(not_given_values)}"
                    )
                return EnvManifest.model_validate(manifest)

        else:
            raise FileNotFoundError("No env manifest found")

    @classmethod
    def from_workspace(cls, workspace_dir: Path) -> "Env":
        """Create an environment from a workspace directory.

        If no env manifest is found, it will create one with the local template.

        :param workspace_dir: The workspace directory.
        """
        manifest = cls.load_and_add_template(workspace_dir, tuple())
        if manifest.is_empty():
            manifest = cls.load_and_add_template(workspace_dir, "local")
        return cls(manifest)

    @classmethod
    def load_and_add_template(
        cls, workspace_dir: Path, template: str | tuple[str, ...]
    ) -> EnvManifest:
        """Load and add one or more templates to the workspace.

        :param workspace_dir: The workspace directory.
        :param template: The template(s) to add.
            - If a string, it will be added as a single template.
            - If a tuple, it will be added as multiple templates.

        :returns: The updated env manifest.
        """
        try:
            manifest = cls.load_manifest(workspace_dir)
            if isinstance(template, str):
                manifest = manifest.merge(getattr(ManifestTemplates, template))
            else:
                for t in template:
                    manifest = manifest.merge(getattr(ManifestTemplates, t))
        except FileNotFoundError:
            if isinstance(template, str):
                manifest = getattr(ManifestTemplates, template)
            else:
                manifest = EnvManifest(subjects=[])
                for t in template:
                    manifest = manifest.merge(getattr(ManifestTemplates, t))
        with (workspace_dir / env_manifest_file()).open("wb") as f:
            _yaml.dump(
                manifest.model_dump(
                    by_alias=True, exclude_none=True, exclude_defaults=True
                ),
                f,
            )
        return manifest

    def resolver(self) -> SubjectResolver:
        return SubjectResolver(self)

    def _resolve_package(self, pkg_uri: str) -> None:
        """Resolve package URI to an importable Python package."""
        if pkg_uri.startswith("git+"):
            self._clone_git_package(pkg_uri)
        elif pkg_uri.startswith("file://"):
            self._resolve_local_package(pkg_uri)

    def _clone_git_package(self, pkg_uri: str) -> None:
        """Clone a git package and resolve it to a local directory."""
        ...

    def _resolve_local_package(self, pkg_uri: str) -> None:
        """Resolve a local package to an importable Python package."""
        ...

    def load_registry(self, pkg: str) -> None:
        """Load and register implementations from a package."""
        if pkg in self.loaded_registries:
            return
        try:
            module = importlib.import_module(pkg)
            self.loaded_registries[pkg] = getattr(module, IMPL_PKG_REGISTRY_FUNC)()
        except ImportError as e:
            raise ValueError(f"Invalid implementation package {pkg}: {e}")

    def provide_impl_docs(self) -> dict[str, ImplDocs]:
        """Provide subject implementation and factory class documentation.

        .. note::
            For subjects that use a factory, the factory class's documentation is
            provided instead of the subject class's documentation.
        """
        docs: dict[str, ImplDocs] = {}
        for subject_name, subject_metadata in self.subject_metadatas.items():
            impl = subject_metadata.impl
            if isinstance(impl, SubjectImplClassMetadata):
                if p := impl.pkg:
                    self.load_registry(p)
                    docs[subject_name] = self.loaded_registries[p].get_docs(impl.class_)
                else:
                    docs[subject_name] = self.default_registry.get_docs(impl.class_)
            else:
                factory_metadata = self.factory_metadatas[impl.factory]
                if p := factory_metadata.pkg:
                    self.load_registry(p)
                    docs[subject_name] = self.loaded_registries[p].get_docs(
                        factory_metadata.class_
                    )
                else:
                    docs[subject_name] = self.default_registry.get_docs(
                        factory_metadata.class_
                    )
        return docs

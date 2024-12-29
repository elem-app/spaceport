import re
from pathlib import Path
from typing import Any, Literal, Sequence

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationInfo,
    field_validator,
    model_validator,
)

from pylib import resource


class ImplPkgMetadata(BaseModel):
    """Setting up a subject implementation package that can be used."""

    name: str
    """The in-workspace name to refer to the subject implementation package."""

    uri: str
    """The URI of the subject implementation package.
    
    If omitted, the package will be loaded from PyPI.
    """

    type_: Literal["git", "local", "pypi"] = Field(..., alias="type")

    version: str | None = Field(None)

    @model_validator(mode="before")
    def parse_uri(cls, values: dict[str, Any]) -> dict[str, Any]:
        uri = values.get("uri", "")
        if uri.startswith("git+"):
            values["type"] = "git"
            # Extract version from git URI if present
            if "@" in uri:
                values["version"] = uri.split("@")[1]
        elif uri.startswith("file://"):
            values["type"] = "local"
        elif not uri:
            values["uri"] = values["name"]
            values["type"] = "pypi"
        return values

    @field_validator("version", mode="before")
    def validate_version(cls, value: str | None, info: ValidationInfo) -> str | None:
        if info.data.get("type") in ("git", "pypi") and not value:
            raise ValueError(f"Version is required for {info.data['type']} packages")
        if value and not re.match(r"^v?\d+\.\d+\.\d+", value):
            raise ValueError(f"Invalid version format: {value}")
        return value

    @field_validator("uri", mode="before")
    def validate_uri(cls, value: str, info: ValidationInfo) -> str:
        if info.data.get("type") == "git":
            if not value.startswith("git+https://"):
                raise ValueError("Git URI must start with git+https://")
        elif info.data.get("type") == "local":
            if not value.startswith("file://"):
                raise ValueError("Local URI must start with file://")
            path = Path(value[7:])
            if not path.exists():
                raise ValueError(f"Local package path does not exist: {path}")
        return value


class SubjectImplClassMetadata(BaseModel):
    """Specifying the subject implementation for a subject."""

    class_: str = Field(..., alias="class")
    """The subject implementation class name."""

    pkg: str | None = Field(default=None)
    """The in-workspace name of the package to load the subject implementation class 
    from.
    
    If omitted, the default implementation package spaceport_simpl will be used.
    """

    params: dict[str, Any] = Field(default_factory=dict)
    """The parameters for initializing the subject implementation."""


class SubjectImplFactoryMetadata(BaseModel):
    """Specifying the subject factory for a subject."""

    factory: str
    """The in-workspace name of the subject factory."""

    params: dict[str, Any] = Field(default_factory=dict)
    """The parameters for initializing the subject implementation factory."""


class SubjectMetadata(BaseModel):
    """Setting up a subject."""

    model_config = ConfigDict(extra="forbid")

    name: str
    """The in-workspace name to refer to the subject.
    
    This name can be used in `T.use()` calls.
    """

    impl: SubjectImplClassMetadata | SubjectImplFactoryMetadata = Field(
        ..., union_mode="left_to_right"
    )
    """The subject's implementation."""


class SubjectFactoryMetadata(BaseModel):
    """Setting up a subject factory that can be used by a subject."""

    model_config = ConfigDict(extra="forbid")

    name: str
    """The in-workspace name to refer to the subject factory."""

    class_: str = Field(..., alias="class")
    """The subject factory class name."""

    pkg: str | None = Field(default=None)
    """The in-workspace name of the package to load the subject factory class from.
    
    If omitted, the default implementation package spaceport_simpl will be used.
    """

    params: dict[str, Any] = Field(default_factory=dict)
    """The parameters for initializing the subject factory."""


class EnvManifest(BaseModel):
    """Env manifest."""

    impl_pkgs: list[ImplPkgMetadata] = Field(default_factory=list)
    """The metadata for subject implementation packages."""

    factories: list[SubjectFactoryMetadata] = Field(default_factory=list)
    """The metadata for subject factories."""

    subjects: list[SubjectMetadata]
    """The metadata for subjects."""

    def is_empty(self) -> bool:
        """Check if the manifest is empty.

        A manifest is considered empty if it has no factories or subjects.
        """
        return not self.factories and not self.subjects

    def merge(self, other: "EnvManifest") -> "EnvManifest":
        """Merge two env manifests into a new one."""
        return EnvManifest(
            impl_pkgs=self.impl_pkgs + other.impl_pkgs,
            factories=self.factories + other.factories,
            subjects=self.subjects + other.subjects,
        )


def _is_local(path: str) -> bool:
    """Check if a string is a local file or directory.

    :returns: True if the string is a local file or directory, False otherwise.
    """
    from urllib.parse import urlparse

    try:
        return urlparse(path, "file").scheme == "file"
    except ValueError:
        return True


class ProjectSourcesMetadata(BaseModel):
    """Specifying the sources for a project."""

    primary: str
    """The primary source of the project."""

    other: list[str] = Field(default_factory=list)
    """The other sources for the project."""

    def primary_as_resource(self) -> resource.Resource:
        if _is_local(self.primary):
            return resource.local(self.primary)
        return resource.RemoteFile(self.primary)

    def other_as_resources(self) -> Sequence[resource.Resource]:
        return [
            resource.local(r) if _is_local(r) else resource.RemoteFile(r)
            for r in self.other
        ]


class RawProjectMetadata(BaseModel):
    """Setting up a project that needs to be rewritten from source documents."""

    name: str
    """The in-workspace name to refer to the project."""

    sources: ProjectSourcesMetadata
    """The source documents for the project."""


class ArtifactProjectMetadata(BaseModel):
    """Setting up a project that has an artifact as its source."""

    name: str
    """The in-workspace name to refer to the project."""

    artifact: Literal[True] | str
    """The path to the artifact file.
    
    If set to `True`, the default path will be used.
    """


class WorkspaceManifest(BaseModel):
    """Workspace manifest."""

    name: str
    """The name of the workspace."""

    projects: list[ArtifactProjectMetadata | RawProjectMetadata] = Field(
        default_factory=list
    )
    """The metadata for the projects in the workspace."""

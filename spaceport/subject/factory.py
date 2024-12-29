from abc import ABC, abstractmethod
from typing import Any, Sequence

from . import Handle, Subject


class Resource(ABC):
    """A resource managed by a subject factory."""

    @abstractmethod
    async def deinit(self) -> None:
        """Deinitialize the resource."""


class ManagedSubject[T: Handle](Subject[T]):
    """A subject that is managed by a factory."""

    def __init__(self, resources: Sequence[Resource], /, **kwargs: Any): ...

    @abstractmethod
    async def destroy(self) -> None:
        """Destroy the subject and its resources."""


def managed_subject[T: Handle](base_class: type[Subject[T]]) -> type[ManagedSubject[T]]:
    """Create a managed subject class that inherits from a specific Subject subclass."""

    class DynamicManagedSubject(ManagedSubject[T], base_class):
        def __init__(self, resources: Sequence[Resource], /, **kwargs: Any):
            """Do not call this directly; use the factory to create a managed subject."""
            base_class.__init__(self, **kwargs)
            self._resources: Sequence[Resource] = resources

        async def destroy(self) -> None:
            """Destroy the subject.

            The resources are deinitialized in reverse order as they were defined and
            initialized.
            """
            # Deinitialize resources in reverse order
            for resource in reversed(self._resources):
                await resource.deinit()

            # Prevent double deinitialization
            self._resources = []

    return DynamicManagedSubject


class SubjectFactory[T: Handle](ABC):
    """A factory for creating subject instances.

    .. important::
        Subclasses should handle failures of subject creation in the `create()` method.
        If a subject cannot be created, the factory should manually release resources
        that would be deinited if the subject were successfully created and later
        destroyed.
    """

    @abstractmethod
    async def create(self, **kwargs: Any) -> ManagedSubject[T]:
        """Create a managed subject instance."""

    async def destroy(self) -> None:
        """Destroy the factory."""
        pass

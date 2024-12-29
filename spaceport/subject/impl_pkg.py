from typing import Any, NamedTuple

from . import Subject
from .factory import SubjectFactory


class ImplDocs(NamedTuple):
    """Documentation of a subject implementation or factory."""

    class_doc: str
    """The documentation of the subject implementation or factory class."""

    method_doc: str
    """The documentation of the subject creation method (``__init__()`` for
    implementations, ``create()`` for factories).
    """


class ImplRegistry:
    """A registry of subject implementations.

    The registry maps class names to either a subject implementation class or a subject
    factory class. When creating a test subject, Spaceport looks up the class name in the
    registry and instantiates the appropriate class.
    """

    def __init__(self, *impls: type[Subject[Any]] | type[SubjectFactory[Any]]):
        self._inner = {cls.__name__: cls for cls in impls}

    def __getitem__(self, key: str) -> type[Subject[Any]] | type[SubjectFactory[Any]]:
        return self._inner[key]

    def get_docs(self, key: str) -> ImplDocs:
        """Get the documentation of a subject implementation or factory.

        :param key: The name of the subject implementation or factory class.

        :returns: A tuple of the class documentation and the subject creation method
            documentation.
        """
        impl = self._inner[key]
        class_doc = impl.__doc__ or ""

        if issubclass(impl, Subject):
            method_doc = impl.__init__.__doc__ or ""
        else:
            method_doc = impl.create.__doc__ or ""

        return ImplDocs(class_doc, method_doc)


IMPL_PKG_REGISTRY_FUNC = "__impl_pkg_registry__"
"""The name of the function that is set on the root package to supply an ``ImplRegistry``."""


def declare_impl_pkg(
    *impls: type[Subject[Any]] | type[SubjectFactory[Any]],
    registry: ImplRegistry | None = None,
) -> None:
    """Declare an implementation package.

    Using this function makes its residing root package an implementation package.

    Spaceport projects create test subjects by looking for subject implementations inside
    the implementation packages loaded by the project. As such, each implementation
    package needs to export a list of subject implementations or factories by calling
    this function.

    For example, a package providing a ``RestAPISubject`` can declare itself as an
    implementation package by including in its ``__init__.py`` file:

    .. code-block:: python
        from spaceport.subject.impl_pkg import declare_impl_pkg

        declare_impl_pkg(RestAPISubject)

    :param impls: Subject implementations or factories to be exported by the
        implementation package.
    :param registry: An ``ImplRegistry`` instance that will contains all the subject
        implementations or factories to be exported by the implementation package.

    :raises ValueError: If both ``impls`` and ``registry`` are provided.
    :raises RuntimeError: If unable to determine the package context
    """

    if impls and registry:
        raise ValueError("`impls` and `registry` cannot be both provided")

    import inspect
    import sys

    # Get the caller's root package
    frame = inspect.currentframe()
    caller_frame = None
    try:
        if frame is None:
            raise RuntimeError("Could not determine caller frame")

        # Get caller's frame (one level up)
        caller_frame = frame.f_back
        if caller_frame is None:
            raise RuntimeError("Could not determine caller module")

        # Get caller's module name
        caller_name = caller_frame.f_globals.get("__name__")
        if caller_name is None:
            raise RuntimeError("Could not determine caller module name")

        # Get package name (first component of the module path)
        package_name = caller_name.split(".")[0]

        # Get package module
        root_pkg = sys.modules.get(package_name)
        if root_pkg is None:
            raise RuntimeError(f"Could not find package {package_name}")
    finally:
        del frame
        if caller_frame is not None:
            del caller_frame

    if hasattr(root_pkg, IMPL_PKG_REGISTRY_FUNC):
        raise RuntimeError(
            f"Package {package_name} is already declared as an implementation package"
        )

    def registry_func() -> ImplRegistry:
        return registry or ImplRegistry(*impls)

    setattr(root_pkg, IMPL_PKG_REGISTRY_FUNC, registry_func)

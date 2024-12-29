"""Helper module for extracting operation signatures and documentation."""

import inspect
from abc import ABC
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from types import ModuleType
from typing import Iterator


@dataclass
class OpDoc:
    """Documentation for an operation signature."""

    name: str
    """The operation name."""

    signature: str
    """The method signature."""

    doc: str
    """The docstring describing the operation."""

    module: ModuleType
    """The module containing the operation."""


def _get_op_modules() -> list[ModuleType]:
    """Get all modules in the spaceport.op package."""
    op_dir = Path(__file__).parent.parent / "op"
    modules: list[ModuleType] = []

    for file in op_dir.glob("*.py"):
        if file.stem == "__init__":
            continue
        module_name = f"spaceport.op.{file.stem}"
        modules.append(import_module(module_name))

    return modules


def get_op_docs() -> Iterator[OpDoc]:
    """Extract documentation for all operation methods in ABC subclasses.

    Yields:
        Documentation for each operation method found in spaceport.op modules.
    """
    for module in _get_op_modules():
        # Find all ABC subclasses in the module
        for _, cls in inspect.getmembers(
            module, lambda x: inspect.isclass(x) and issubclass(x, ABC) and x != ABC
        ):
            # Get all methods defined in the ABC
            for name, method in inspect.getmembers(cls, inspect.isfunction):
                if name.startswith("_"):
                    continue

                doc = inspect.getdoc(method) or ""
                signature = str(inspect.signature(method)).replace("(self", "(tsl")
                yield OpDoc(name=name, signature=signature, doc=doc, module=module)


def format_op_docs() -> str:
    """Format operation signatures documentation for the transpiler template.

    Returns:
        Markdown formatted documentation of all operations.
    """
    sections: list[str] = []

    # Group by module
    by_module: dict[str, list[OpDoc]] = {}
    modules: dict[str, ModuleType] = {}

    for op_doc in get_op_docs():
        module_name = op_doc.module.__name__.split(".")[-1]
        if module_name not in by_module:
            by_module[module_name] = []
        by_module[module_name].append(op_doc)
        modules[module_name] = op_doc.module

    # Format each module's operations
    for module_name, ops in sorted(by_module.items()):
        sections.append(f"### {module_name.replace('_', ' ').title()} Operations")
        if module_doc := inspect.getdoc(modules[module_name]):
            sections.append(module_doc.splitlines()[0])

        for op in ops:
            if not op.doc:
                raise ValueError(f"Operation {op.name} has no docstring")

            doc_lines = op.doc.splitlines()
            sections.append(f"* `T.{op.name}{op.signature}` - {doc_lines[0]}")
            for line in doc_lines[1:]:
                if line := line.strip():
                    sections.append(f"\t- {line}")
        sections.append("")

    return "\n".join(sections)

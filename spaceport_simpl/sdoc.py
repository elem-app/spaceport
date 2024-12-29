from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, cast, override

from ruamel.yaml import YAML

from pylib.optional import unwrap
from pylib.string import extract_tagged
from spaceport.op import sdoc
from spaceport.subject import TSL, Handle, Subject, TSLError

yaml = YAML()
yaml.indent(mapping=2, sequence=4, offset=2)  # type: ignore


class StructuredDoc(Handle, sdoc.ReadDocument, sdoc.WriteDocument):
    def __init__(self, query: list[str | int], subject: "SDocEditor"):
        self.query = query
        self.subject = subject

    @override
    @asynccontextmanager
    async def bind(self):
        if self.subject.opened_doc_path:
            with self.subject.opened_doc_path.open("r+") as f:
                self._doc_file = f
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
        p = Path(path)
        self.subject.opened_doc_path = p
        if doc_type:
            self.subject.opened_doc_type = doc_type
        else:
            match p.suffix:
                case ".yaml" | ".yml":
                    self.subject.opened_doc_type = "application/yaml"
                case ".json":
                    self.subject.opened_doc_type = "application/json"
                case ".toml":
                    self.subject.opened_doc_type = "application/toml"
                case ".html":
                    self.subject.opened_doc_type = "text/html"
                case ".xml":
                    self.subject.opened_doc_type = "application/xml"
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
        content = cast(dict[str | int, Any], yaml.load(self._doc_file))  # pyright: ignore[reportUnknownMemberType]
        if not self.query:
            return content, {}

        n = content
        for sel in self.query:
            try:
                n = n[sel]
            except (KeyError, IndexError):
                return None, {}
        return n, {}

    @override
    def write_node(self, content: Any, metadata: dict[str, Any]) -> None:
        match unwrap(self.subject.opened_doc_type):
            case "application/yaml":
                return self._write_yaml(content, metadata)
            case _:
                raise NotImplementedError(
                    f"Unsupported document type: {self.subject.opened_doc_type}"
                )

    def _write_yaml(self, content: Any, metadata: dict[str, Any]) -> None:
        doc = self._doc_file
        if not self.query:
            # Overwrite entire document
            doc.seek(0)
            yaml.dump(content, doc)  # pyright: ignore[reportUnknownMemberType]
            doc.truncate()
            return

        # Read current content
        doc.seek(0)
        doc_content = cast(dict[str | int, Any], yaml.load(doc))  # pyright: ignore[reportUnknownMemberType]

        # Navigate to and update the target node
        n = doc_content
        for sel in self.query[:-1]:
            n = n[sel]

        if (last_sel := self.query[-1]) == "*":
            n = cast(list[Any], n)
            n.append(content)
        else:
            n[last_sel] = content

        # Write back the modified document
        doc.seek(0)
        yaml.dump(doc_content, doc)  # pyright: ignore[reportUnknownMemberType]
        doc.truncate()


class SDocEditor(Subject[StructuredDoc]):
    """A subject for reading and writing structured documents.

    A structured document is one that encodes a tree-shaped data structure. Each node
    may contain a sub-tree of nodes, or a literal value. A node may also contain
    additional metadata.

    Acceptable TSL headers: ``sdoc``.
    """

    def __init__(self):
        """Initialize a structured document editor subject."""
        self.opened_doc_path: Path | None = None
        self.opened_doc_type: str | None = None

    @override
    async def search(self, tsl: TSL, op_name: str) -> StructuredDoc:
        if tsl.header != "sdoc":
            raise TSLError(f"TSL header must be 'sdoc', got {tsl.header}")

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

        return StructuredDoc(query, self)

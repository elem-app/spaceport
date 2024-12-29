"""Operations on structured or semi-structured documents."""

from abc import ABC, abstractmethod
from typing import Any


class ReadDocument(ABC):
    @abstractmethod
    def open_document(self, path: str, doc_type: str | None = None) -> None:
        """Open the document for editing.

        Args: path - the path to the document. doc_type - the MIME type of the document; if not provided, the document type is inferred from the path.

        Usage: `T.open_document("sdoc//", "package.json")` opens package.json for editing.
        Usage: `T.open_document("sdoc//", "doc1.docx", "application/xml")` opens doc1.docx as an XML document.
        """

    @abstractmethod
    def get_document_type(self) -> str:
        """Get the type of the document as an MIME type.

        Fails: If no document is open.

        Usage: `T.get_document_type("sdoc//")` returns `"application/json"` if the file is a JSON document.
        Usage: `T.get_document_type("sdoc//")` returns `"text/html"` if the file is an HTML document.
        """

    @abstractmethod
    def read_node(self) -> tuple[Any, dict[str, Any]]:
        """Read a node from the file's content based on the TSL.

        Fails: If no document is open.
        Returns: A tuple whose first element is the canonical content of the node, and the second element is a dictionary of it properties or attributes, if any.

        Usage: `T.read_node("sdoc//0/name")` regards the file's content as an unnamed list of items, and returns the "name" field of the first item.
        Usage: `T.read_node("sdoc//html/body/[first 'h1']")` regards the file's content as an HTML document, and returns the inner HTML plus props of the first `<h1>` tag inside `<body>`.
        """


class WriteDocument(ABC):
    @abstractmethod
    def write_node(self, content: Any, metadata: dict[str, Any]) -> None:
        """Write a node to the document. Overwrite the existing node at the position specified by the TSL.

        Args: content - the content of the node. metadata - the properties or attributes of the node.
        Fails: If no document is open.

        Usage: `T.write_node("sdoc//users/*", {"name": "John"}, {})` when the subject is a JSON document, appends `{"name": "John"}` to the array under `users`.
        Usage: `T.write_node("sdoc//html/body/[first 'li']", "John", {"class": "name"})` when the subject is an HTML document, replaces the first `<li>` tag inside `<body>` with `<li class="name">John</li>`.
        """

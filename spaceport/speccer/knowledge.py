import asyncio
import sqlite3
from typing import Any, Iterable, NamedTuple, Sequence

import numpy as np
from openai import AsyncOpenAI

from pylib.resource import LocalDir, LocalFile, RemoteFile, Resource
from spaceport.globals import globals

from ._langchain_text_splitter import MarkdownHeaderTextSplitter

client = AsyncOpenAI(api_key=globals.envvars.openai_api_key)


def _should_ignore(path: str) -> bool:
    # TODO: Implement this
    return False


class Context(NamedTuple):
    location: str
    content: str


class IndexedContext(NamedTuple):
    id: int
    location: str
    content: str
    embedding: np.ndarray[Any, Any] | None = None


class KnowledgeRepo:
    def __init__(self):
        self._unprocessed_sources: list[Resource] = []
        self._unprocessed_contents: list[str | Context] = []
        self._retrieved: set[int] = set()

        self._db = sqlite3.connect(":memory:")
        self._init_db()

        self._markdown_splitter = MarkdownHeaderTextSplitter(
            [
                ("#", "Header 1"),
                ("##", "Header 2"),
                ("###", "Header 3"),
            ],
            strip_headers=False,
        )

    def clear(self) -> None:
        self._unprocessed_sources.clear()
        self._unprocessed_contents.clear()
        self._retrieved.clear()
        self._db.executescript("DELETE FROM repo")
        self._db.commit()

    @property
    def is_indexed(self) -> bool:
        return not (self._unprocessed_sources or self._unprocessed_contents)

    def _init_db(self):
        self._db.executescript("""\
BEGIN TRANSACTION;
CREATE TABLE IF NOT EXISTS repo (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT,
    title TEXT,
    content TEXT,
    embedding BLOB
);
CREATE INDEX IF NOT EXISTS idx_path ON repo (path);
COMMIT;""")

    async def _embed(self, content: str) -> np.ndarray[Any, Any]:
        resp = await client.embeddings.create(
            model="text-embedding-3-small",
            input=content,
            encoding_format="float",
        )
        return np.array(resp.data[0].embedding)

    def add_source(self, source: Resource | Iterable[Resource]) -> None:
        if isinstance(source, Resource):
            self._unprocessed_sources.append(source)
        else:
            self._unprocessed_sources.extend(source)

    def add_content(self, content: str | Context | Iterable[str | Context]) -> None:
        if isinstance(content, (str, Context)):
            self._unprocessed_contents.append(content)
        else:
            self._unprocessed_contents.extend(content)

    async def index(self) -> None:
        unprocessed = [c for c in self._unprocessed_contents]

        for src in self._unprocessed_sources:
            if _should_ignore(src.location):
                continue

            match src:
                case LocalFile():
                    with open(src.location, "r") as f:
                        c = f.read()
                        unprocessed.append(Context(location=src.location, content=c))

                case LocalDir():
                    for file in src.list_files():
                        loc = file.location
                        if _should_ignore(loc):
                            continue
                        with open(loc, "r") as f:
                            c = f.read()
                            unprocessed.append(Context(location=loc, content=c))

                case RemoteFile():
                    raise NotImplementedError("Remote file indexing is not implemented")
                case _:
                    raise ValueError(f"Unknown source type: {type(src)}")

        if unprocessed:
            async with asyncio.TaskGroup() as tg:
                # Tuple: optional path, content, embedding task
                tasks: list[tuple[str | None, str, asyncio.Task[Any]]] = []

                for c in unprocessed:
                    if isinstance(c, str):
                        chunks = self._markdown_splitter.split_text(c)
                        tasks.extend(
                            (
                                None,
                                ch.content,
                                tg.create_task(self._embed(ch.content)),
                            )
                            for ch in chunks
                        )
                    else:
                        chunks = self._markdown_splitter.split_text(c.content)
                        tasks.extend(
                            (
                                c.location,
                                ch.content,
                                tg.create_task(self._embed(ch.content)),
                            )
                            for ch in chunks
                        )

            self._db.executemany(
                "DELETE FROM repo WHERE path = ?", ((p,) for p, _, _ in tasks)
            )
            self._db.executemany(
                "INSERT INTO repo (path, content, embedding) VALUES (?, ?, ?)",
                ((p, c, t.result().tobytes()) for p, c, t in tasks),
            )
            self._db.commit()
            self._unprocessed_contents.clear()
            self._unprocessed_sources.clear()

    async def retrieve(self, queries: Iterable[str]) -> Sequence[IndexedContext]:
        if not self.is_indexed:
            await self.index()

        async with asyncio.TaskGroup() as tg:
            tasks = [tg.create_task(self._embed(q)) for q in queries]

        results: dict[int, IndexedContext] = {}
        for t in tasks:
            hits = self._semantic_search(t.result())
            results.update({h.id: h for h in hits if h.id not in self._retrieved})

        self._retrieved.update(results)
        return list(results.values())

    def _semantic_search(
        self, query_embedding: np.ndarray[Any, Any], *, threshold: float = 0.75
    ) -> list[IndexedContext]:
        cursor = self._db.execute("SELECT id, path, content, embedding FROM repo")

        # Tuple: score, id, path, content
        results: list[tuple[float, int, str, str]] = []

        for id, path, content, emb_bytes in cursor:
            emb = np.frombuffer(emb_bytes)
            similarity = np.dot(query_embedding, emb)
            results.append((similarity, id, path, content))

        results.sort(reverse=True)
        return [
            IndexedContext(id=i, location=p, content=c)
            for score, i, p, c in results
            if score > threshold
        ]

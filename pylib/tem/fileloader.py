import glob
import hashlib
import logging
import os
import sqlite3
from typing import Iterable, NamedTuple, Self, cast

import aiofiles

logger = logging.getLogger(__name__)


class ParseError(Exception):
    def __eq__(self, other: object) -> bool:
        return type(self) is type(other) and self.args == cast(Self, other).args


class ParsedTemplate(NamedTuple):
    module: str
    name: str
    content: str


def parse(lines: Iterable[str]) -> Iterable[ParsedTemplate | ParseError]:
    module = None
    name = None
    content: list[str] = []
    for lineno, line in enumerate(lines, start=1):
        line = line.rstrip()
        if line.startswith("%mod "):
            if (module is not None) or (name is not None) or content:
                yield ParseError(f"Unexpected %mod directive at line {lineno}")
                return
            else:
                module = line[len("%mod ") :]
        elif line.startswith("%tem "):
            if (module is None) or (name is not None) or content:
                yield ParseError(f"Unexpected %tem directive at line {lineno}")
                return
            else:
                name = line[len("%tem ") :]
        elif line == "%end":
            if (module is None) or (name is None) or not content:
                yield ParseError(f"Unexpected %end directive at line {lineno}")
                return
            else:
                yield ParsedTemplate(module, name, "\n".join(content))
                name = None
                content = []
        elif line == "%endmod":
            if (module is None) or (name is not None) or content:
                yield ParseError(f"Unexpected %endmod directive at line {lineno}")
                return
            else:
                module = None
        else:
            if module is None or name is None:
                if line:
                    yield ParseError(f"Unexpected content at line {lineno}")
                    return
                else:
                    continue
            else:
                content.append(line)
    if (module is not None) or (name is not None) or content:
        yield ParseError("Unexpected end of file")


class FileLoader:
    _CREATE_TABLE = """BEGIN;
    CREATE TABLE IF NOT EXISTS template (
        module TEXT NOT NULL,
        name TEXT NOT NULL,
        content TEXT NOT NULL,
        PRIMARY KEY (module, name)
    );
    COMMIT;
    """

    def __init__(self, template_dir: str) -> None:
        self.template_dir = template_dir

        self.hashes: dict[str, bytes] = {}
        """Hashes of the files that have been loaded."""

        self._conn = sqlite3.connect(":memory:")
        self._conn.executescript(self._CREATE_TABLE)

    def _save_template(self, module: str, name: str, content: str) -> None:
        self._conn.execute(
            "INSERT INTO template VALUES (:module, :name, :content) "
            "ON CONFLICT (module, name) DO UPDATE SET content = :content",
            {"module": module, "name": name, "content": content},
        )
        self._conn.commit()

    def get_template(self, module: str, name: str) -> str:
        cur = self._conn.execute(
            "SELECT content FROM template WHERE module = :module AND name = :name",
            {"module": module, "name": name},
        )
        try:
            return cur.fetchone()[0]
        except (IndexError, TypeError):
            raise FileNotFoundError(f"Template {module}::{name} not found")

    def get_module(self, module: str) -> dict[str, str]:
        cur = self._conn.execute(
            "SELECT name, content FROM template WHERE module = :module",
            {"module": module},
        )
        return {name: content for name, content in cur}

    async def load(self, *, recursive: bool = False) -> list[tuple[str, str]]:
        """Load templates from files in the template directory.

        :returns: A list of tuples, each containing the module and name of the loaded template.
        """
        if recursive:
            paths = glob.glob(
                os.path.join(self.template_dir, "**", "*.tem"), recursive=True
            )
            logger.debug(
                f"Loading templates from {len(paths)} files inside {self.template_dir}"
            )
        else:
            paths = glob.glob(os.path.join(self.template_dir, "*.tem"))
        updated: list[tuple[str, str]] = []
        for path in paths:
            try:
                async with aiofiles.open(path) as f:
                    s = await f.read()
                    h = hashlib.sha1(s.encode(), usedforsecurity=False).digest()
                    if self.hashes.get(path) == h:
                        continue
                    self.hashes[path] = h

                    await f.seek(0)
                    lines = await f.readlines()
                    for parsed in parse(lines):
                        match parsed:
                            case ParsedTemplate(module, name, content):
                                self._save_template(module, name, content)
                                updated.append((module, name))
                            case ParseError():
                                logger.error(f"Error parsing {path}: {parsed}")

            except FileNotFoundError:
                continue
            except ValueError:
                pass

        logger.debug(f"Loaded {len(updated)} templates")
        return updated

import asyncio
import datetime
import itertools
from pathlib import Path
from typing import Iterable, Iterator, NamedTuple, Sequence, TextIO

from pydantic import BaseModel, Field

from pylib.resource import LocalFile, Resource
from spaceport.speccer import Postprocessor
from spaceport.speccer.rewriter import SpecRewriter
from spaceport.speccer.transpiler import SpecTranspiler

from . import _yaml
from .manifest import ProjectSourcesMetadata


class ArtifactMetadata(BaseModel):
    project: str
    sources: ProjectSourcesMetadata | None = Field(default=None)
    created_at: datetime.datetime


class Block(NamedTuple):
    name: str
    spec_lines: list[str]
    code_lines: list[str]

    def count_lines(self) -> int:
        return len(self.spec_lines) + len(self.code_lines)


class CodeOnlyBlock(NamedTuple):
    name: str
    code_lines: list[str]

    def count_lines(self) -> int:
        return len(self.code_lines)


class _SpecVisitor:
    def __init__(self):
        self.in_spec_block = False

    @property
    def is_in_block(self) -> bool:
        return self.in_spec_block

    def detect(self, line: str) -> bool:
        if line[:3] == ">- " or line[:4] == "> - ":
            self.in_spec_block = True
            return True
        elif line[:1] == ">" and self.in_spec_block:
            return True

        self.in_spec_block = False
        return False


class _CodeVisitor:
    def __init__(self):
        self.opening_fence: str | None = None

    @property
    def is_in_block(self) -> bool:
        return self.opening_fence is not None

    def detect(self, line: str) -> bool:
        stripped = line.strip()
        if stripped[:12] == "```py .test":
            self.opening_fence = "```"
        elif stripped[:13] == "````py .test":
            self.opening_fence = "````"
        elif stripped == self.opening_fence:
            self.opening_fence = None
        elif self.opening_fence:
            return True

        return False


class Artifact:
    """A class for working with artifact files."""

    _transpiler = SpecTranspiler()
    _rewriter = SpecRewriter()

    def __init__(self, project: str, path: Path) -> None:
        self.path = path
        assert self.path.exists(), f"Artifact file {self.path} does not exist"

        self.content_lines, metadata = self._lines()
        self.specs = {
            k: list(g)
            for k, g in itertools.groupby(
                self._organize(iter(self.content_lines)), lambda x: x.name
            )
        }
        self._metadata_line_count = len(metadata) + 2  # a trailing '---' and a newline
        if metadata:
            try:
                yaml = _yaml.load("".join(metadata))
            except Exception as e:
                raise ValueError("Failed to load metadata") from e
            self.metadata = ArtifactMetadata.model_validate(yaml)
        else:
            self.metadata = ArtifactMetadata(
                project=project, created_at=datetime.datetime.now(datetime.UTC)
            )
        if self.metadata.project != project:
            raise ValueError(
                f"Project mismatch: expected {project}, got {self.metadata.project} in artifact"
            )

    def _lines(self) -> tuple[list[str], list[str]]:
        metadata: list[str] = []

        def _lines_iter():
            with self.path.open() as f:
                metadata_finished = False
                content_started = False
                for line in f:
                    stripped = line.rstrip()
                    if content_started:
                        yield stripped
                    elif metadata_finished:
                        if stripped:
                            content_started = True
                            yield stripped
                    elif stripped == "---":
                        if not metadata:
                            metadata.append(line)
                        else:
                            metadata_finished = True
                    elif metadata:
                        metadata.append(line)
                    elif stripped:
                        content_started = True
                        yield stripped

        return list(_lines_iter()), metadata

    def _organize(self, lines: Iterator[str]) -> Iterator[Block | CodeOnlyBlock]:
        """Organize lines into blocks.

        The method works with the following logic:
        1. If a line starts with `>>`, it is considered a spec start; spec starts cannot
           immediately follow another spec line nor can its content be empty.
        2. Otherwise, perform the following:
           - Only check if a line is a code line if the previous line is a spec line or
             already in a code block. If so, add the line to the code collection.
           - Only check if a line is a spec line if not in a code block. If so, add
             the line to the spec collection.
        3. If the last line is a spec and the current line is not in a code block, or if
           the last line is code but the current line is not, yield the collected lines.
        """

        spec_name: str | None = None
        spec_coll: list[str] = []
        code_coll: list[str] = []
        spec_visitor = _SpecVisitor()
        code_visitor = _CodeVisitor()

        # Add a trailing empty line to ensure the last block is yielded
        for line in itertools.chain(lines, [""]):
            if line[:2] == ">>":
                if spec_visitor.is_in_block:
                    raise ValueError(
                        f"Spec name cannot immediately follow another spec: {line}; "
                        "add a blank line before"
                    )
                spec_name = line[2:].strip()
                if not spec_name:
                    raise ValueError("No spec name has been given")
            elif spec_name is not None:
                last_line_in_code_block = code_visitor.is_in_block
                last_line_in_spec_block = spec_visitor.is_in_block
                if code_visitor.detect(line):  # A code line
                    code_coll.append(line)
                elif code_visitor.is_in_block:  # An opening fence
                    pass
                elif last_line_in_code_block:  # An ending fence
                    if spec_coll:
                        yield Block(spec_name, spec_coll, code_coll)
                    else:
                        yield CodeOnlyBlock(spec_name, code_coll)
                    spec_coll = []
                    code_coll = []
                elif spec_visitor.detect(line):  # A spec line
                    spec_coll.append(line)
                elif last_line_in_spec_block and spec_coll:  # End of a spec block
                    yield Block(spec_name, spec_coll, code_coll)
                    spec_coll = []
                    code_coll = []

        if spec_name is not None:
            if code_visitor.is_in_block:
                raise ValueError("Hanging block without closing code fence")

    def _save_metadata(self, stream: TextIO) -> None:
        """Save metadata to a stream.

        :param stream: The stream to save the metadata to.
        """
        stream.write("---\n")
        _yaml.dump(self.metadata.model_dump(exclude_none=True), stream)
        stream.write("---\n\n")

    async def transpile(
        self, spec_names: Iterable[str] | None = None, post: Postprocessor | None = None
    ) -> Iterator[str]:
        """Transpile the project's specs into test code.

        The method works with the following logic:
        1. Transpile each spec block into a test code block.
        2. Iterate over and yield the original lines until a spec block ends:
           - If there is a paired code block in the original content, skip the code block.
           - Yield the transpiled code block.
        3. After yielding the transpiled code block, go back to step 2.

        .. note::

            The method works under the assumption that the original content is valid.
            Normally, it should be, since the original content has gone through the
            ``organize()`` method.

        :returns: An iterator over an artifact's content by combining original content
            with transpiled code.
        """
        tr_tasks: dict[str, asyncio.Task[Iterator[str]]] = {}
        spec_names = list(self.specs.keys() if spec_names is None else spec_names)
        async with asyncio.TaskGroup() as tg:
            for name in spec_names:
                tr_tasks[name] = tg.create_task(
                    self._transpiler.transpile_blocks(
                        [
                            b.code_lines
                            if isinstance(b, CodeOnlyBlock)
                            else b.spec_lines
                            for b in self.specs[name]
                        ]
                    )
                )
        scripts: dict[str, list[str]] = {}
        post = post or Postprocessor.chain()
        for name in spec_names:
            orig_blocks = self.specs[name]
            transpiled = tr_tasks[name].result()

            new_blocks: list[str] = []
            # Add code only blocks to the generated ones to facilitate postprocessing
            for blk, code in zip(orig_blocks, transpiled):
                if isinstance(blk, CodeOnlyBlock):
                    new_blocks.append("\n".join(blk.code_lines))
                else:
                    new_blocks.append(code)

            sep = "\n########\n# XSEPX\n########\n"
            concatenated_code = sep.join(new_blocks)
            processed = (await post.process(concatenated_code)).split(sep)
            if len(processed) != len(orig_blocks):
                raise RuntimeError(
                    f"Failed to transpile spec {name}; expected "
                    f"{len(orig_blocks)} code blocks, got {len(processed)}:\n"
                    f"{processed}"
                )

            scripts[name] = []
            # Remove code only blocks from processed--those will be left untouched
            for blk, code in zip(orig_blocks, processed):
                if not isinstance(blk, CodeOnlyBlock):
                    scripts[name].append(code)

        return self.combine_code(scripts)

    def combine_code(self, scripts: dict[str, list[str]]) -> Iterator[str]:
        """Iterate over the document's content combined with the new scripts.

        This method looks for specs in the original content and replaces their paired
        code blocks with the new ones.

        :param scripts: A dict of spec names to its code blocks.
        """
        spec_visitor = _SpecVisitor()
        code_visitor = _CodeVisitor()
        spec_name: str | None = None
        cb_iter = iter([])
        for line in self.content_lines:
            if line[:2] == ">>":
                new_name = line[2:].strip()
                if new_name in scripts:
                    cb_iter = map(
                        lambda x: f"````py .test\n{x}\n````\n",
                        scripts[new_name],
                    )
                    spec_name = new_name
                else:
                    spec_name = None
            elif spec_name is not None:
                # Only check for code lines if after a spec block
                # i.e., we ignore code-only blocks
                last_line_in_code_block = code_visitor.is_in_block
                if spec_visitor.is_in_block or last_line_in_code_block:
                    if (
                        code_visitor.detect(line) or code_visitor.is_in_block
                    ):  # A code line or an opening fence
                        continue
                    elif last_line_in_code_block:  # An ending fence
                        yield next(cb_iter)

                        # Also we must force the spec_visitor to reset in order to
                        # NOT detect the next line as code.
                        spec_visitor.detect(line)
                        continue
                    elif not spec_visitor.detect(line):  # End of a spec block
                        yield next(cb_iter)

                else:
                    spec_visitor.detect(line)

            yield line.rstrip()
            yield "\n"
        yield from cb_iter

    def save(self, save_path: Path | None = None) -> None:
        """Save the artifact to a file."""
        save_path = save_path or self.path
        with save_path.open("w") as f:
            self._save_metadata(f)
            for t in self.combine_code({}):
                f.write(t)

    async def transpile_and_save(
        self,
        *,
        spec_names: Iterable[str] | None = None,
        post: Postprocessor | None = None,
        save_path: Path | None = None,
    ) -> None:
        """Transpile the artifact and save the result to a file.

        :param spec_names: The names of the specs to transpile. If not provided, all
            specs will be transpilied.
        :param post: The postprocessor to use.
        :param save_path: The path to save the transpiled result to. If not provided,
            the original file will be overwritten.
        """
        save_path = save_path or self.path
        text_iter = await self.transpile(spec_names, post)
        with save_path.open("w") as f:
            self._save_metadata(f)
            for t in text_iter:
                f.write(t)

    def get_code(self, spec_name: str) -> str:
        return "\n".join(
            itertools.chain.from_iterable(b.code_lines for b in self.specs[spec_name])
        )

    def find_code_lineno(self, spec: str, script_lineno: int) -> int:
        found_spec = False
        code_visitor = _CodeVisitor()
        spec_code_line_cnt = 0

        for lineno, line in enumerate(self.content_lines, 1):
            if line[:2] == ">>":
                spec_name = line[2:].strip()
                if spec_name == spec:
                    found_spec = True
                elif found_spec:
                    raise ValueError(f"Line {script_lineno} not found in spec {spec}")
            elif found_spec:
                if code_visitor.detect(line):  # A code line
                    spec_code_line_cnt += 1
                    if spec_code_line_cnt == script_lineno:
                        return lineno + self._metadata_line_count
        else:
            raise ValueError(f"Spec {spec} not found")

    @classmethod
    async def rewrite_and_save(
        cls,
        project_name: str,
        primary_source: Resource,
        references: Sequence[Resource] | None = None,
        save_path: Path | None = None,
    ) -> tuple[Path, Path | None]:
        """Generate the artifact using Rewriter and save it to a file.

        :returns: A tuple of the new save path and the path of the renamed old file, if
            the a file with the same name exists.
        """
        renamed_path = None
        if save_path is None:
            save_path = Path(
                f"{project_name}.{datetime.datetime.now(datetime.UTC).strftime('%Y%m%dT%H%M%SZ')}.md"
            )
        if save_path.exists():
            existing = Artifact(project_name, save_path)
            time = existing.metadata.created_at.strftime("%Y%m%dT%H%M%SZ")
            renamed_path = save_path.rename(
                save_path.with_name(f"{save_path.name}.{time}")
            )
        else:
            save_path.parent.mkdir(parents=True, exist_ok=True)
            save_path.touch()

        cls._rewriter.clear_knowledge()
        if references:
            cls._rewriter.add_source(references)
        else:
            references = []
        match primary_source:
            case LocalFile():
                primary = Path(primary_source.location).read_text()
            case _:
                raise ValueError("Primary source must be a local file")

        output = await cls._rewriter.rewrite(primary)
        artifact = Artifact(project_name, save_path)
        artifact.metadata = ArtifactMetadata.model_validate(
            {
                "project": project_name,
                "sources": {
                    "primary": primary_source.location,
                    "other": [str(r.location) for r in references],
                },
                "created_at": datetime.datetime.now(datetime.UTC),
            }
        )
        with save_path.open("w") as f:
            artifact._save_metadata(f)
            f.write(output.artifact)
            f.write("\n")
        return save_path, renamed_path

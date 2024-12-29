import asyncio
import itertools
from typing import Iterator, NamedTuple, Sequence

from pylib.string import extract_tagged
from spaceport.globals import globals
from spaceport.llm import LLM, UserMessage, Vendor
from spaceport.speccer.op_docs import format_op_docs
from spaceport.subject import TSL

tem = globals.templates.for_module(__name__)


class TargetTSL(NamedTuple):
    """A target and its corresponding TSL."""

    text: str
    """The text referring to the target in the natural language sentence."""

    tsl: str
    """The TSL corresponding to the target."""

    def as_llm_input(self) -> str:
        return f"""[MAPPING]
  [TARGET]{self.text}[/TARGET]
  [TSL]{self.tsl}[/TSL]
[/MAPPING]"""


class SpecTranspiler:
    """Provides functionality to transpile executable specs into test code."""

    def __init__(self) -> None:
        self._op_docs = format_op_docs()
        self._block_sep = "===SP_BLOCK_SEP==="
        self.system_preamble = tem(
            "transpile preamble v5", op_docs=self._op_docs, block_sep=self._block_sep
        )
        self._llm = LLM(
            "spec-transpiler",
            Vendor.from_str(globals.envvars.speccer_llm_vendor),
            globals.envvars.speccer_llm_model,
            preamble=self.system_preamble,
        )
        self.tsl_system_preamble = tem("tsl preamble")
        self._tsl_llm = LLM(
            "tsl-transpiler",
            Vendor.from_str(globals.envvars.speccer_llm_vendor),
            globals.envvars.speccer_llm_model,
            preamble=self.tsl_system_preamble,
        )

    async def extract_tsls(self, sentence: str) -> list[TargetTSL]:
        resp = await self._tsl_llm.chat([UserMessage(content=sentence)])
        mappings = extract_tagged(resp, "<TSL-MAPPINGS>").split("</MAPPING>")
        return [
            TargetTSL(extract_tagged(m, "<TARGET>"), TSL(extract_tagged(m, "<TSL>")))
            for m in mappings
            if m.strip()
        ]

    async def transpile(self, spec: str) -> str:
        """Transpile an executable spec into test code.

        :param spec: The executable spec to transpile.
        :returns: The test code.
        """
        tsl_tasks: list[asyncio.Task[list[TargetTSL]]] = []
        async with asyncio.TaskGroup() as tg:
            given_indent = -1
            for line in spec.splitlines():
                line = line.strip()
                if not line:
                    continue
                if line[0] != ">":  # code block
                    break
                if "USE" in line[:12]:
                    continue
                if (idx := line.find("GIVEN")) != -1:
                    given_indent = line.index("- ", 0, idx)
                    continue
                if given_indent != -1 and "- " not in line[: given_indent + 2]:
                    continue
                given_indent = -1
                task = tg.create_task(self.extract_tsls(line))
                tsl_tasks.append(task)

        tsl_results: list[TargetTSL] = []
        for task in tsl_tasks:
            tsl_results.extend(task.result())
        tsl_mappings = (
            "[TSL-MAPPINGS]\n"
            f"{'\n'.join(tsl.as_llm_input() for tsl in tsl_results)}\n"
            "[/TSL-MAPPINGS]"
        )

        resp = await self._llm.chat(
            [UserMessage(content=f"[TEXT]\n{spec}\n[/TEXT]\n{tsl_mappings}")],
        )
        return extract_tagged(resp, "[SCRIPT]")

    async def transpile_blocks(self, blocks: Sequence[Sequence[str]]) -> Iterator[str]:
        """Transpile a list of executable spec blocks into test code.

        :param blocks: The blocks to transpile. A block comprises a sequence of lines.
        :returns: An iterator of test code, each item corresponding to an input block.
        """
        if not blocks:
            return iter([])
        tsl_tasks: list[asyncio.Task[list[TargetTSL]]] = []
        async with asyncio.TaskGroup() as tg:
            given_indent = -1
            for block in blocks:
                for line in block:
                    if not line:
                        continue
                    if line[0] != ">":  # code block
                        break
                    if "USE" in line[:12]:
                        continue
                    if (idx := line.find("GIVEN")) != -1:
                        given_indent = line.index("- ", 0, idx)
                        continue
                    if given_indent != -1 and "- " not in line[: given_indent + 2]:
                        continue
                    given_indent = -1
                    task = tg.create_task(self.extract_tsls(line))
                    tsl_tasks.append(task)

        tsl_results: list[TargetTSL] = []
        for task in tsl_tasks:
            tsl_results.extend(task.result())
        tsl_mappings = (
            "[TSL-MAPPINGS]\n"
            f"{'\n'.join(tsl.as_llm_input() for tsl in tsl_results)}\n"
            "[/TSL-MAPPINGS]"
        )

        # TODO check if block separator is in the text
        sep = self._block_sep
        joined_text = "\n".join(
            itertools.chain.from_iterable(itertools.chain(b, (sep,)) for b in blocks)
        )
        resp = await self._llm.chat(
            [UserMessage(content=f"[TEXT]\n{joined_text}\n[/TEXT]\n{tsl_mappings}")]
        )
        code_blocks = extract_tagged(resp, "[SCRIPT]")
        return (c for b in code_blocks.split(sep) if (c := b.strip()))

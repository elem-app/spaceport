from typing import Protocol, override

from pylib.string import extract_tagged
from spaceport.globals import globals
from spaceport.llm import LLM, UserMessage, Vendor
from spaceport.subject.impl_pkg import ImplDocs

from . import Postprocessor

tem = globals.templates.for_module(__name__)


class ImplDocsProvider(Protocol):
    def provide_impl_docs(self) -> dict[str, ImplDocs]: ...


def _format_docs(docs: dict[str, ImplDocs]) -> str:
    return str({k: v._asdict() for k, v in docs.items()})


class SubjectArranger(Postprocessor):
    def __init__(self, docs_provider: ImplDocsProvider) -> None:
        self.docs_provider = docs_provider
        self.system_preamble = tem(
            "arrange preamble v1", docs=_format_docs(docs_provider.provide_impl_docs())
        )
        self._llm = LLM(
            "subject-arranger",
            Vendor.from_str(globals.envvars.speccer_llm_vendor),
            globals.envvars.speccer_llm_model,
            preamble=self.system_preamble,
        )

    @override
    async def process(self, code: str) -> str:
        resp = await self._llm.chat([UserMessage(code)])
        stmts = extract_tagged(resp, "<STMTS>").split("</USE>")
        replacements = [
            (extract_tagged(s, "<ORIG>"), extract_tagged(s, "<NEW>"))
            for s in stmts
            if s.strip()
        ]
        # The following string replacement algorithm is based on the assumption that the
        # LLM-generated use statements are in the same order as they appear in the code.
        result: list[str] = []
        pos = 0
        for old, new in replacements:
            next_pos = code.find(old, pos)
            if next_pos == -1:
                raise ValueError(f"{old} not found in code")

            result.append(code[pos:next_pos])
            result.append(new)

            # Update position to after the pattern
            pos = next_pos + len(old)

        if pos < len(code):
            result.append(code[pos:])

        return "".join(result)

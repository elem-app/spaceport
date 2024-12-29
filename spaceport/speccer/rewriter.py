from typing import Iterable, NamedTuple

from pylib.resource import Resource
from pylib.string import extract_tagged, extract_tagged_all
from spaceport.globals import globals
from spaceport.llm import LLM, UserMessage, Vendor

from .knowledge import IndexedContext, KnowledgeRepo

tem = globals.templates.for_module(__name__)


class RewriteOutput(NamedTuple):
    artifact: str
    queries: list[str]
    contexts: list[IndexedContext]


class SpecRewriter:
    """Rewrites source documents into artifacts."""

    def __init__(self) -> None:
        self.collected_content: list[dict[str, str]] = []
        self.qa_prompt_name = "qa prompt"
        self.system_preamble = tem("rewrite preamble v1")
        self._llm = LLM(
            "spec-rewriter",
            Vendor.from_str(globals.envvars.speccer_llm_vendor),
            globals.envvars.speccer_llm_model,
            preamble=self.system_preamble,
            options={"max_tokens": 8192, "temperature": 0.5},
        )
        self._knowledge_repo = KnowledgeRepo()

    def add_source(self, source: Resource | Iterable[Resource]) -> None:
        self._knowledge_repo.add_source(source)

    def add_content(self, content: str | Iterable[str]) -> None:
        self._knowledge_repo.add_content(content)

    def clear_knowledge(self) -> None:
        self._knowledge_repo.clear()

    async def rewrite(self, source: str, *, max_queries: int = 5) -> RewriteOutput:
        await self._knowledge_repo.index()
        queries: list[str] = []
        contexts: list[IndexedContext] = []
        messages = [UserMessage(content=source)]
        for _ in range(max_queries + 1):
            resp = await self._llm.chat(messages)
            try:
                artifact = extract_tagged(resp, "<ARTIFACT>")
                return RewriteOutput(artifact, queries, contexts)
            except ValueError:
                try:
                    qs = list(extract_tagged_all(resp, "<QUERY>"))
                except ValueError:
                    raise ValueError(
                        "Could not find a query or a generated artifact in response"
                    )

            queries.extend(qs)
            ctxs = await self._knowledge_repo.retrieve(qs)
            contexts.extend(ctxs)
            messages.append(
                UserMessage(content=tem(self.qa_prompt_name, contexts=ctxs))
            )
        else:
            raise ValueError(
                f"Could not generate an artifact within {max_queries} queries"
            )

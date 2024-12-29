import os
import pprint

import pytest

from spaceport.speccer.op_docs import format_op_docs, get_op_docs
from spaceport.speccer.transpiler import SpecTranspiler


@pytest.mark.skipif(
    not os.environ.get("PRINT_TEST"),
    reason="Only run with PRINT_TEST",
)
@pytest.mark.asyncio
async def test_transpiler_preamble():
    from spaceport.llm import UserMessage

    llm = SpecTranspiler()._llm  # type: ignore
    spec_text = """\
>- Fill in the Search box with "squirrel".
>- The Search box should contain the text "squirrel".
>- Click the Search button.
>- There should be at least 1 search result in the search results list.
"""

    resp = await llm.chat(
        [UserMessage(spec_text)],
    )
    print(resp)
    assert False


@pytest.mark.skipif(
    not os.environ.get("PRINT_TEST"),
    reason="Only run with PRINT_TEST",
)
@pytest.mark.asyncio
async def test_transpile_tsl():
    from spaceport.globals import globals
    from spaceport.llm import LLM, UserMessage, Vendor

    tem = globals.templates.for_module("spaceport.speccer.transpiler")
    llm = LLM(
        "test-tsl",
        Vendor.from_str(globals.envvars.speccer_llm_vendor),
        globals.envvars.speccer_llm_model,
        preamble=tem("tsl preamble"),
    )
    text = "Input 'squirrels' in the search box"
    resp = await llm.chat([UserMessage(text)])
    print(resp)
    assert False


@pytest.mark.skipif(
    not os.environ.get("PRINT_TEST"),
    reason="Only run with PRINT_TEST",
)
@pytest.mark.asyncio
async def test_transpile():
    """Test ``spaceport.spec.transpiler.SpecTranspiler.transpile``."""

    text = """\
>- Fill in the Search box with "squirrel".
>- Click the Search button.
>- Check that the search results appear in the search panel.
>- Assert that the number of search results is at least 1.
>- Bring the search result to John and ask for his opinion.
"""

    transpiler = SpecTranspiler()
    code = await transpiler.transpile(text)
    assert len(code) >= 5
    print(code)
    assert False


@pytest.mark.skipif(
    not os.environ.get("PRINT_TEST"),
    reason="Only run with PRINT_TEST",
)
def test_op_docs():
    """Test ``spaceport.speccer.op_docs.get_op_docs``."""

    op_docs = list(get_op_docs())
    assert len(op_docs) > 0
    pprint.pprint(op_docs)
    assert False


@pytest.mark.skipif(
    not os.environ.get("PRINT_TEST"),
    reason="Only run with PRINT_TEST",
)
def test_format_op_docs():
    """Test ``spaceport.speccer.op_docs.format_op_docs``."""

    op_docs = format_op_docs()
    print(op_docs)
    assert False

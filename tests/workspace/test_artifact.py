import os
import tempfile
import time
from pathlib import Path
from typing import Callable

import pytest

from pylib.resource import LocalFile
from spaceport.workspace.artifact import Artifact, Block, CodeOnlyBlock


@pytest.fixture
def temp_file(make_temp_file_name: Callable[[], str]):
    p = Path(make_temp_file_name())
    return p


@pytest.fixture(name="make_temp_file_name")
def make_temp_file_name_():
    created: list[str] = []

    def make_temp_file_name():
        name = f"tmp-{time.time()}"
        created.append(name)
        return name

    yield make_temp_file_name

    if not os.environ.get("TEST_NO_CLEANUP"):
        for name in created:
            try:
                os.remove(name)
            except FileNotFoundError:
                pass


@pytest.mark.parametrize(
    "text",
    [
        # Illegal metadata
        """\
---
project: test
>- TO BE IGNORED
""",
        # Mismatching project name
        """\
---
project: not-test
created_at: 2024-01-01T00:00:00Z
---
""",
        # Block not closed
        """\
---
project: test
created_at: 2024-01-01T00:00:00Z
---

>> block
>- spec
```py .test
print()
""",
        # Spec name after another spec
        """\
---
project: test
created_at: 2024-01-01T00:00:00Z
---
>> block

>- spec
>> another block
""",
    ],
)
def test_organize_errors(temp_file: Path, text: str) -> None:
    temp_file.write_text(text)
    with pytest.raises(ValueError):
        artifact = Artifact("test", temp_file)
        print(artifact.metadata)


def test_multiple_dividers(temp_file: Path) -> None:
    text = """\
---
project: test
created_at: 2024-01-01T00:00:00Z
---

---
project: test
---

>> spec
```py .test
print()
```

"""
    temp_file.write_text(text)
    artifact = Artifact("test", temp_file)
    assert len(artifact.content_lines) == 9
    assert artifact.content_lines[0] == "---"


def test_organize_corner_cases(temp_file: Path) -> None:
    text = """\
---
project: test
created_at: 2024-01-01T00:00:00Z
---
### Code only block
>> spec
```py .test
print()
```

### Spec only block
>- spec

### No block spec
>> nonexistent spec

### False-positive spec + consecutive code + no trailing new line
>> another spec
>- another spec
```py .test
>- false spec
```
```py .test
another code
```"""
    temp_file.write_text(text)
    artifact = Artifact("test", temp_file)
    assert artifact.specs == {
        "spec": [CodeOnlyBlock("spec", ["print()"]), Block("spec", [">- spec"], [])],
        "another spec": [
            Block("another spec", [">- another spec"], [">- false spec"]),
            CodeOnlyBlock("another spec", ["another code"]),
        ],
    }


def test_replace_code(temp_file: Path) -> None:
    text = """\
---
project: test
created_at: 2024-01-01T00:00:00Z
---
>> another spec
>- another spec
```py .test
code to be kept
```

>> spec
```py .test
code to be kept
```

>- spec
```py .test
code to be overridden
```
```py .test
code to be kept
```
"""

    new_text = """\
>> another spec
>- another spec
```py .test
code to be kept
```

>> spec
```py .test
code to be kept
```

>- spec
````py .test
code to be inserted
````
```py .test
code to be kept
```
"""

    temp_file.write_text(text)
    artifact = Artifact("test", temp_file)
    assert "".join(artifact.combine_code({"spec": ["code to be inserted"]})) == new_text


@pytest.mark.skipif(
    not os.environ.get("TEST_LLM"),
    reason="Only run with TEST_LLM",
)
@pytest.mark.asyncio
async def test_transpile(temp_file: Path) -> None:
    text = """\
---
project: test
created_at: 2024-01-01T00:00:00Z
---
>- TO BE IGNORED

>> test
```py .test
print()
```

>- USE `home-page`

>- Click the _Search button_

>> another test
>- USE `home-page-2`
>- Check if there are multiple _search buttons_

"""
    temp_file.write_text(text)
    artifact = Artifact("test", temp_file)
    print(artifact.metadata)
    print(artifact.specs)
    await artifact.transpile_and_save(spec_names=["test"])
    artifact = Artifact("test", temp_file)
    assert len([b for b in artifact.specs["test"] if b.code_lines]) == 3
    assert artifact.specs["test"][0].code_lines == ["print()"]
    assert artifact.get_code("test")
    assert not artifact.get_code("another test")


@pytest.mark.skipif(
    not os.environ.get("TEST_LLM"),
    reason="Only run with TEST_LLM",
)
@pytest.mark.asyncio
async def test_transpile_overriding_code(temp_file: Path) -> None:
    # The last line is deliberatley not a new line
    text = """\
---
project: test
created_at: 2024-01-01T00:00:00Z
---
>- TO BE IGNORED

>> test

>- USE `home-page`

>- Click the _Search button_

>> nonexistent spec

>> another test
>- USE `home-page-2`

>- Check if there are multiple _search buttons_
````py .test
````"""
    temp_file.write_text(text)
    artifact = Artifact("test", temp_file)
    print(repr(artifact.specs))
    assert "nonexistent spec" not in artifact.specs
    assert not artifact.get_code(spec_name="test")
    assert not artifact.get_code(spec_name="another test")
    await artifact.transpile_and_save(spec_names=["another test"])
    artifact = Artifact("test", temp_file)
    assert "nonexistent spec" not in artifact.specs
    assert not artifact.get_code(spec_name="test")
    assert artifact.get_code("another test")
    assert len([b for b in artifact.specs["another test"] if b.code_lines]) == 2


@pytest.mark.skipif(
    not os.environ.get("TEST_LLM"),
    reason="Only run with TEST_LLM",
)
@pytest.mark.asyncio
async def test_rewrite_and_save(make_temp_file_name: Callable[[], str]) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        primary_source_text = """\
## ohce
Display message on screen, writes each given STRING to standard output, with a space between each and a newline after the last one.

Syntax
     ohce [options]... [String]...

Options
   -n   Do not output a trailing newline.
   -E   Disable the interpretation of the following backslash-escaped characters.
"""
        temp_file = Path(temp_dir) / make_temp_file_name()
        temp_file.write_text(primary_source_text)

        out_file = Path(temp_dir) / make_temp_file_name()
        out_file.touch()

        await Artifact.rewrite_and_save(
            "test", LocalFile(temp_file), save_path=out_file
        )
        artifact = Artifact("test", out_file)
        assert artifact.metadata.project == "test"
        assert artifact.metadata.created_at
        print(list(out_file.parent.iterdir()))
        year = artifact.metadata.created_at.year
        assert any(
            f"{out_file.name}.{year}" in p.name for p in out_file.parent.iterdir()
        )

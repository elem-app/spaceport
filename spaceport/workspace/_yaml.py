from typing import IO, Any

from ruamel.yaml import YAML
from ruamel.yaml.scalarstring import PreservedScalarString

yaml = YAML()
yaml.indent(mapping=2, sequence=4, offset=2)  # type: ignore


def dump(data: Any, stream: IO[str] | IO[bytes], **kwargs: Any) -> None:
    yaml.dump(data, stream, **kwargs)  # type: ignore


def load(stream: str | bytes | IO[str] | IO[bytes]) -> Any:
    return yaml.load(stream)  # type: ignore


def preserved(data: str) -> PreservedScalarString:
    """Preserve a string as a YAML literal scalar for dumping.

    For example, given a string ``s = "Hello,\nworld!"``, the following code:

    .. code-block:: python
        dump({"key": preserved(s)})

    will produce the following YAML:

    .. code-block:: yaml
        key: |-
            Hello,
            world!
    """
    return PreservedScalarString(data)

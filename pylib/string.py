from typing import Iterator


def _extract(
    source: str, start_tag: str, end_tag: str | None = None, strip: bool = True
) -> tuple[str, str]:
    end_tag = end_tag or (
        f"[/{start_tag[1:-1]}]"
        if start_tag.startswith("[")
        else f"</{start_tag[1:-1]}>"
        if start_tag.startswith("<")
        else None
    )
    if end_tag is None:
        raise ValueError(f"Could not infer end tag for '{start_tag}'")
    try:
        start = source.index(start_tag) + len(start_tag)
        end = source.index(end_tag, start)
    except ValueError:
        raise ValueError(f"Could not find tags '{start_tag}'/'{end_tag}' in '{source}'")

    return source[start:end].strip() if strip else source[start:end], source[
        end + len(end_tag) :
    ]


def extract_tagged(
    source: str, start_tag: str, end_tag: str | None = None, *, strip: bool = True
) -> str:
    """Extract text between the start and end tags.

    :param source: The source text to extract from.
    :param start_tag: The start tag to extract from.
    :param end_tag: The end tag to extract to. If not provided, it will be inferred
        from the start tag. For example, ``[TSL]`` will be matched with ``[/TSL]``,
        and ``<TARGET>`` will be matched with ``</TARGET>``.
    :param strip: If ``True``, the extracted text will be stripped of leading and
        trailing whitespace. Defaults to ``True``.

    :returns: The extracted text.

    :raises ValueError: If the start or end tag is not found in the source; or if the
        end tag is cannot be inferred from the start tag.
    """
    extracted, _ = _extract(source, start_tag, end_tag, strip=strip)
    return extracted


def extract_tagged_all(
    source: str, start_tag: str, end_tag: str | None = None, *, strip: bool = True
) -> Iterator[str]:
    """Extract all texts between each pair of start and end tags."""
    while True:
        try:
            extracted, source = _extract(source, start_tag, end_tag, strip=strip)
            yield extracted
        except ValueError:
            break

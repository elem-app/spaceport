import asyncio
import os
from typing import NamedTuple


class FetchResult(NamedTuple):
    content: bytes
    content_updated_at: float


async def fetch(url: str) -> FetchResult:
    async with asyncio.TaskGroup() as tg:
        content = tg.create_task(fetch_content(url))
        content_updated_at = tg.create_task(fetch_updated_at(url))

    return FetchResult(content.result(), content_updated_at.result())


async def fetch_content(url: str) -> bytes:
    with open(url, "rb") as f:
        return f.read()


async def fetch_updated_at(url: str) -> float:
    return os.path.getmtime(url)

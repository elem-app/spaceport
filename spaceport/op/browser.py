"""Operations on browsers."""

from abc import ABC, abstractmethod


class Navigate(ABC):
    @abstractmethod
    async def goto_url(self, url: str) -> None:
        """Visit the given URL."""

    @abstractmethod
    def get_current_url(self) -> str:
        """Get the current URL."""

    @abstractmethod
    async def go_back(self) -> None:
        """Go back to the previous page."""

    @abstractmethod
    async def go_forward(self) -> None:
        """Go forward to the next page."""

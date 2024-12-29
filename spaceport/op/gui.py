"""Operations on generic graphical user interfaces."""

from abc import ABC, abstractmethod
from typing import Sequence


class Mouse(ABC):
    @abstractmethod
    async def mouse_move(self) -> None:
        """Move the mouse to the target.

        Usage: `T.mouse_move('one:gui//button[label is "Click me"]')` moves the mouse to the button with text "Click me".
        """

    @abstractmethod
    async def mouse_move_coords(self, x: int, y: int) -> None:
        """Move the mouse to the given coordinates in CSS pixels.

        Args: x - the x coordinate to move to; y - the y coordinate to move to.

        Usage: `T.mouse_move_coords('//gui', x=100, y=200)` moves the mouse to the coordinates (100, 200).
        """

    @abstractmethod
    async def mouse_down(self, button: str = "left") -> None:
        """Send a mouse down event to the target.

        Args: button - the button to send a down event for, one of "left", "middle", "right".

        Usage: `T.mouse_down('gui//', button="left")` imitates a mouse down at its current position.
        """

    @abstractmethod
    async def mouse_up(self, button: str = "left") -> None:
        """Send a mouse up event to the target.

        Args: button - the button to send an up event for, one of "left", "middle", "right".

        Usage: `T.mouse_up('gui//', button="left")` imitates a mouse up at its current position.
        """


class MouseClick(Mouse):
    async def click(self, button: str = "left") -> None:
        """Click the target.

        Args: button - the button to click, one of "left", "middle", "right".

        Usage: `T.click('one:gui//button[label is "Click me"]', button="left")` clicks the button with text "Click me".
        """
        await self.mouse_move()
        await self.mouse_down(button)
        await self.mouse_up(button)


class Keyboard(ABC):
    @abstractmethod
    async def keydown(self, keys: Sequence[str]) -> None:
        """Send a keydown event to the target.

        Args: keys - a list of Web API `KeyboardEvent.key` values representing the pressed keys

        Usage: `T.keydown('gui//', keys=["a"])` sends the "a" key down event to the current focus.
        Usage: `T.keydown('gui//', keys=["Ctrl", "r"])` sends the "Ctrl" and "r" key down events to the current focus.
        """

    @abstractmethod
    async def keyup(self, keys: Sequence[str]) -> None:
        """Send a keyup event to the target.

        Args: keys - a list of Web API `KeyboardEvent.key` values representing the released keys

        Usage: `T.keyup('gui//', keys=["a"])` sends the "a" key up event to the current focus.
        Usage: `T.keyup('gui//', keys=["Ctrl", "r"])` sends the "Ctrl" and "r" key up events to the current focus.
        """


class TypeText(Keyboard):
    async def type_text(self, text: str) -> None:
        """Type the given text.

        Usage: `T.type_text('gui//', text="John Doe")` types "John Doe" into the current focus.
        """

        for key in text:
            await self.keydown((key,))
            await self.keyup((key,))


class ReadText(ABC):
    @abstractmethod
    async def read_text(self) -> str:
        """Read the text of the target. If the target is a collection, read the text of all items in the collection.

        Usage: `T.read_text('gui//input[role is "textbox"]')` reads the text of the input with role "textbox".
        """

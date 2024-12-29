"""Operations on REPLs."""

from abc import ABC, abstractmethod


class CheckState(ABC):
    @abstractmethod
    def is_alive(self) -> bool:
        """Check if the target is alive.

        Usage: `T.is_alive("term//")` returns whether the terminal is alive.
        """


class Input(ABC):
    @abstractmethod
    def input_keys(self, keys: list[str]) -> None:
        """Input a key down event with one or more keys. Does not work on collections.

        Args: keys - a list of Web API `KeyboardEvent.key` values representing the pressed keys

        Usage: `T.input_keys("term//input", ["Q"])` inputs the "Q" key into the terminal input buffer.
        Usage: `T.input_keys("term//input", ["Shift", "Tab"])` inputs the "Shift" key and the "Tab" key into the terminal input buffer.
        """

    @abstractmethod
    def input_text(self, text: str) -> None:
        """Input text into the target. Does not work on collections.

        Args: text - a string representing the text to input

        Usage: `T.input_text("term//input", "Hello, world!")` inputs "Hello, world!" into the terminal input buffer.
        """

    @abstractmethod
    def input_enter(self) -> None:
        """Input an enter event into the target. Does not work on collections.

        Usage: `T.input_enter("term//input")` inputs an enter event into the terminal input buffer.
        """


class Read(ABC):
    @abstractmethod
    def read_text(self, encoding: str = "utf-8") -> str:
        """Read the target.

        Args: encoding - the encoding to use when reading the target

        Usage: `T.read_text("term//input")` reads the content of the terminal input buffer as a utf-8 string.
        Usage: `T.read_text("term//output/-1", encoding="utf-16")` reads the latest output buffer as a utf-16 string.
        """

    @abstractmethod
    def read_bytes(self) -> bytes:
        """Read the target as bytes.

        Usage: `T.read_bytes("term//input")` reads the content of the terminal input buffer as bytes.
        Usage: `T.read_bytes("term//output/-1")` reads the last output buffer as bytes.
        Usage: `T.read_bytes("term//output/-2", encoding="utf-16")` reads the second to last output buffer as a utf-16 string.
        """


class Wait(ABC):
    @abstractmethod
    def wait_till_complete(
        self, timeout: float | None = None, return_error: bool = False
    ) -> None | Exception:
        """Wait till the previous command has completed.

        Args: timeout - a number representing the number of seconds to wait before giving up; if None, wait indefinitely. return_error - whether to return the error if the command fails; if False, the operation will fail silently; if True, the operation will always return the error it encountered, if any
        Fails: Only when return_error is False and either 1) the timeout is reached or 2) the command fails
        Returns: None if return_error is False; the error it encountered, if any, if return_error is True

        Usage: `T.wait_till_complete("term//", timeout=1)` waits till the previous command has completed, or fails if 1 second has passed.
        Usage: `T.wait_till_complete("term//", return_error=True)` waits till the previous command has completed, and returns the error it encountered, if any.
        """

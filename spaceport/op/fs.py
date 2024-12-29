"""Operations on file systems."""

from abc import ABC, abstractmethod


class CreateFile(ABC):
    @abstractmethod
    def create_file(self, data: str | bytes) -> None:
        """Create a file with the given data.

        Args: data - the string or bytes to write to the file.

        Usage: `T.create_file("fs//file.txt", "Hello, world!")` creates a file with the contents "Hello, world!".
        Usage: `T.create_file("fs//file.txt", b"Hello, world!")` creates a file with the contents "Hello, world!".
        """


class CreateDir(ABC):
    @abstractmethod
    def create_dir(self) -> None:
        """Create a directory.

        Usage: `T.create_dir("fs//dir")` creates a directory named "dir".
        Usage: `T.create_dir("fs///tmp")` creates a directory named "tmp" in the root directory.
        """


class Read(ABC):
    @abstractmethod
    def read_text(self, encoding: str) -> str:
        """Read the file as a string.

        Args: encoding - the encoding to use when reading the file.

        Usage: `T.read_text("fs//file.txt", "utf-8")` reads the contents of "file.txt" as a string.
        """

    @abstractmethod
    def read_bytes(self) -> bytes:
        """Read the file as bytes.

        Usage: `T.read_bytes("fs//file.txt")` reads the contents of "file.txt" as bytes.
        """


class Write(ABC):
    @abstractmethod
    def append_bytes(self, data: bytes) -> None:
        """Append bytes to the file.

        Args: data - the bytes to append to the file.

        Usage: `T.append_bytes("fs//file.txt", b"Hello, world!")` appends "Hello, world!" to "file.txt".
        """


class Move(ABC):
    @abstractmethod
    def move(self, dest: str) -> None:
        """Move a file or directory to the given destination.

        Args: dest - the destination path.
        Fails: If the target does not exist.

        Usage: `T.move("fs//a", dest="/tmp/")` moves file or directory "a" in the current directory into the "/tmp/" directory.
        Usage: `T.move("fs//a", dest="b")` renames file or directory "a" in the current directory to "b".
        Usage: `T.move("all:fs//a/", dest="/tmp/")` moves all files inside the "a" directory into the "/tmp/" directory.
        """


class Copy(ABC):
    @abstractmethod
    def copy(self, dest: str) -> None:
        """Copy a file or directory to the given destination.

        Args: dest - the destination path.

        Usage: `T.copy("fs//a", dest="/tmp/")` copies file or directory "a" in the current directory into the "/tmp/" directory.
        Usage: `T.copy("fs//a", dest="b")` copies file or directory "a" in the current directory to "b".
        Usage: `T.copy("all:fs//a/", dest="/tmp/")` copies all files inside the "a" directory into the "/tmp/" directory.
        """


class Delete(ABC):
    @abstractmethod
    def delete(self) -> None:
        """Delete a file or directory.

        Usage: `T.delete("fs//a")` deletes file or directory "a" in the current directory.
        Usage: `T.delete("all:fs//a/")` deletes all files inside the "a" directory.
        """


class List(ABC):
    @abstractmethod
    def list(self) -> list[str]:
        """List the contents of a directory.

        Fails: If the target is not a directory.

        Usage: `T.list("fs//dir")` lists the contents of the "dir" directory.
        """


class WorkingDir(ABC):
    @abstractmethod
    def get_working_dir(self) -> str:
        """Get the current working directory.

        Usage: `T.get_working_dir("fs//")` gets the current working directory as a string.
        """

    @abstractmethod
    def set_working_dir(self, dest: str) -> None:
        """Set the current working directory.

        IMPORTANT: If the subject is a shell/terminal, NEVER USE `cd` and ALWAYS USE THIS OPERATION to change the working directory.
        Args: dest - the destination directory.
        Fails: If the target does not exist or is not a directory.

        Usage: `T.set_working_dir("fs//", dest="/tmp")` sets the current working directory to "/tmp".
        """

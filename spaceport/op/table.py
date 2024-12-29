"""Operations on table-like targets."""

from abc import ABC, abstractmethod
from typing import Any


class TableView(ABC):
    @abstractmethod
    def count_rows(self) -> int:
        """Return the number of rows in the table.

        Use this method over `T.size()` when you need to check the number of rows in the table.

        Usage: `assert T.count_rows() == 10` checks that there are exactly 10 rows in the table.
        """

    @abstractmethod
    def get_value(self, row: int, col: int | str) -> Any:
        """Get the value of a cell.

        Args: row - the row index (0-based); col - the column index or name.
        Fails: if the row or column is not found.

        Usage: `T.get_value("table//user", 1, "name")` gets the value of the second row, "name" column.
        Usage: `T.get_value("table//user", 1, 2)` gets the value of the second row, third column.
        """

    @abstractmethod
    def get_row(self, row: int) -> dict[str, Any]:
        """Get a row as a dictionary.

        Args: row - the row index (0-based).
        Fails: if the row is not found.

        Usage: `T.get_row("table//user", 1)` gets the second row.
        """

    @abstractmethod
    def get_column(self, col: int | str) -> list[Any]:
        """Get a column as a list.

        Args: col - the column index or name.
        Fails: if the column is not found.

        Usage: `T.get_column("table//user", "name")` gets the "name" column.
        Usage: `T.get_column("table//user", 4)` gets the fifth column.
        """

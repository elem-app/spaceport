"""Test code interpreter."""

from .errors import TpyError
from .exec import execute
from .resolver import Resolver

__all__ = ["execute", "Resolver", "TpyError"]

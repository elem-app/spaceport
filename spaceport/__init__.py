from .globals import copy_package_data, initialize_global_dirs
from .logging import enable_logging

initialize_global_dirs()
if __debug__:
    # Only enable logging in debug mode
    enable_logging(__name__, "DEBUG")

    # Copy package data to the global data directory every time to ensure its contents
    # are always up to date
    copy_package_data()

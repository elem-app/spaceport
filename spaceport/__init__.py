from .globals import copy_package_data, initialize_global_dirs
from .logging import enable_logging

initialize_global_dirs()


def is_editable_install():
    import pathlib

    pkg_path = pathlib.Path(__file__).parent

    # If we're in site-packages and not in a .egg-link or .pth related path
    # then it's not an editable install
    return (
        "site-packages" not in str(pkg_path)
        or ".egg-link" in str(pkg_path)
        or any(p.suffix == ".pth" for p in pkg_path.parents)
    )


if is_editable_install():
    # Only enable logging in debug mode
    enable_logging(__name__, "DEBUG")

    # Copy package data to the global data directory every time to ensure its contents
    # are always up to date
    copy_package_data()

import logging
import logging.config
import os
from typing import Literal

log_dir = "logs"
_configured = False

LoggingLevel = Literal["INFO", "DEBUG", "WARN", "FATAL"]

# disable logging by default unless enabled
logging.disable()


def enable_logging(
    pkg: str, level: LoggingLevel = "INFO", other: LoggingLevel = "WARN"
) -> None:
    """Enable logging for a package.

    This function configures logging for a specific package so that logs emitted by
    other loggers are suppressed unless explicitly configured. This helps reduce
    noise in the logs.

    .. note::
        - This function is idempotent and can be called multiple times without
          causing additional configuration.
        - This function also sets a special config for the "llm" loggers so that LLM
          logs at INFO or above are always kept in a rotating file.

    :param pkg: Name of the package to log for.
    :param level: Minimum logging level of loggers within the given package.
    :param other: Minimum logging level of loggers for other packages.
    """
    global _configured
    if _configured:
        logger = logging.getLogger(__name__)
        logger.warning("Logging already configured elsewhere; ignoring")
        return
    _configured = True
    os.makedirs(log_dir, exist_ok=True)
    _logging_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "loggers": {
            pkg: {
                "level": level,
                "handlers": ["file"],
                "propagate": False,
            },
            "llm": {
                "level": "INFO",
                "handlers": ["llm_file"],
                "propagate": False,
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": "DEBUG",
                "formatter": "standard",
                "stream": "ext://sys.stdout",
            },
            "file": {
                "class": "logging.handlers.TimedRotatingFileHandler",
                "level": "DEBUG",
                "formatter": "standard",
                "filename": f"{log_dir}/{pkg}.log",
                "when": "midnight",
            },
            "llm_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "INFO",
                "formatter": "multiline",
                "filename": f"{log_dir}/llm.log",
                "maxBytes": 1024 * 1024,
            },
        },
        "formatters": {
            "standard": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            },
            "multiline": {
                "format": "%(asctime)s - %(name)s\n  %(message)s\n",
            },
        },
        "root": {
            "level": "WARNING",
            "handlers": ["file"],
        },
    }
    _logging_config["root"]["level"] = other  # type: ignore
    _logging_config["loggers"][pkg]["level"] = level  # type: ignore
    logging.config.dictConfig(_logging_config)
    logging.disable(logging.NOTSET)

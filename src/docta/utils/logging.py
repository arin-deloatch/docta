"""Centralized logging configuration for docta."""

import logging
import sys

import structlog


def configure_logging(verbose: bool = False) -> None:
    """
    Configure structlog for the application.

    Sets up structured logging with appropriate processors, formatters,
    and log levels based on the verbose flag.

    Args:
        verbose: If True, set log level to DEBUG, otherwise INFO
    """
    min_level = logging.DEBUG if verbose else logging.INFO

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(min_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=True,
    )

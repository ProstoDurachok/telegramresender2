import logging

from rich.logging import RichHandler


def configure_logging():
    DATE_FORMAT = '[%d.%m %H:%M:%S]'
    LOGGER_FORMAT = '%(asctime)s %(message)s'

    logging.basicConfig(
        level=logging.INFO,
        format=LOGGER_FORMAT,
        datefmt=DATE_FORMAT,
        handlers=[RichHandler(show_time=False, rich_tracebacks=True)],
    )

    logging.getLogger('httpx').setLevel(logging.WARNING)

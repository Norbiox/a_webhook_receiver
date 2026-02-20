import logging
import sys


def configure_logging(log_level: str) -> None:
    logging.basicConfig(
        stream=sys.stdout,
        level=log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

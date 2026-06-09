"""CodingCat – Logger utility."""

from __future__ import annotations

import logging
import os
import sys


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        level = logging.DEBUG if os.getenv("CODINGCAT_DEBUG") else logging.INFO
        logger.setLevel(level)
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                              datefmt="%H:%M:%S")
        )
        logger.addHandler(handler)
    return logger

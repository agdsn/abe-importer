import logging
import sys

import colorama


class ColoredFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        # breakpoint()
        style = ""
        msg = super().format(record)
        if record.levelno >= logging.ERROR:
            style = colorama.Style.BRIGHT + colorama.Fore.RED
        if record.levelno == logging.WARNING:
            style = colorama.Style.BRIGHT + colorama.Fore.YELLOW
        if record.levelno == logging.INFO:
            style = colorama.Style.BRIGHT
        if record.levelno <= logging.DEBUG:
            style = colorama.Style.NORMAL
        return f"{style}{msg}{colorama.Style.RESET_ALL}"


def setup_logger(logger_name, verbose):
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    log_format = "[%(levelname).4s] %(name)s:%(funcName)s:%(message)s"
    h = logging.StreamHandler(sys.stdout)
    h.setFormatter(ColoredFormatter(log_format))
    h.setLevel(logging.DEBUG)
    logger.addHandler(h)
    return logger

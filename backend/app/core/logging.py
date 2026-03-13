import logging
import sys

from loguru import logger


class InterceptHandler(logging.Handler):
    """Forward all stdlib logging records (aiogram, uvicorn, sqlalchemy) to loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level: str | int = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = sys._getframe(6), 6
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back  # type: ignore[assignment]
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def setup_logging() -> None:
    logger.remove()
    logger.add(
        sys.stdout,
        format=(
            "{time:YYYY-MM-DDTHH:mm:ss.SSSZ} | {level} | "
            "{name}:{function}:{line} | {message}"
        ),
        level="INFO",
        serialize=False,
        colorize=False,
        backtrace=True,
        diagnose=False,
    )
    # Bridge stdlib logging → loguru (captures aiogram, uvicorn, sqlalchemy, etc.)
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

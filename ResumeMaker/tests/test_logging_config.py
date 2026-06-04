import logging
from logging.handlers import RotatingFileHandler

from core.logging_config import get_logger


def test_backend_logger_uses_rotating_file_handler():
    logger = get_logger("test")
    root_logger = logging.getLogger("resumemaker")

    assert root_logger.handlers
    assert any(isinstance(handler, RotatingFileHandler) for handler in root_logger.handlers)
    assert logger.name == "resumemaker.test"

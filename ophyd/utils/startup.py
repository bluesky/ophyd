import logging

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

__all__ = ['setup', 'logger']


def setup():
    from ..control_layer import setup as _setup
    return _setup(logger)

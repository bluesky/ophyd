import logging
import warnings

logger = logging.getLogger(__name__)

__all__ = ["setup", "logger"]


def setup():
    from .. import get_cl

    warnings.warn(
        "This function is deprecated in ophyd 1.2 "
        "and will be removed in ophyd 1.3. "
        "setup is now automatically called."
    )
    return get_cl().setup(logger)

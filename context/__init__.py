'''

'''

import logging

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


def get_session_manager():
    return None

    # TODO: Session manager singleton
    try:
        return SessionManager.instance
    except AttributeError:
        return None

'''

'''

import logging

# from .sessionmgr import SessionManager


logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


def get_session_manager():
    return None

    # TODO: Session manager singleton
    try:
        return SessionManager.instance
    except AttributeError:
        return None


def register_object(obj, set_vars=True):
    '''
    Register the object with the current running ophyd session.

    :param object obj: The object to register
    :param bool set_vars: If set, obj._session and obj._ses_logger
        are set to the current session and its associated logger.
    :return: The current session
    :rtype: :class:`SessionManager` or None
    '''
    ses = get_session_manager()

    if ses is None:
        # TODO setup additional logger when no session present?
        ses_logger = logger
    else:
        ses_logger = ses.register(obj)

    if set_vars:
        obj._session = ses
        obj._ses_logger = ses_logger

    return ses

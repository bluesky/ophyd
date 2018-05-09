import threading

from caproto.threading.pyepics_compat import get_pv, caput, caget


thread_class = threading.Thread
pv_form = 'time'


def setup(logger):
    ...

import threading
from caproto.threading.client import caget, caput, get_pv

thread_class = threading.Thread
pv_form = 'time'


def setup(logger):
    ...

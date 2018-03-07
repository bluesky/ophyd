import threading

thread_class = threading.Thread
pv_form = 'time'


def setup(logger):
    ...

def caget(*args, **kwargs):
    raise NotImplemented

def caput(*args, **kwargs):
    raise NotImplemented

def get_pv(*args, **kwargs):
    raise NotImplemented

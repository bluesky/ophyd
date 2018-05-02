import threading

thread_class = threading.Thread
pv_form = 'time'


def setup(logger):
    ...

def caget(*args, **kwargs):
    raise NotImplementedError

def caput(*args, **kwargs):
    raise NotImplementedError

def get_pv(*args, **kwargs):
    raise NotImplementedError

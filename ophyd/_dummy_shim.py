import threading

thread_class = threading.Thread
pv_form = 'time'
name = 'dummy'


def setup(logger):
    ...


def caget(*args, **kwargs):
    raise NotImplementedError


def caput(*args, **kwargs):
    raise NotImplementedError


def get_pv(*args, **kwargs):
    raise NotImplementedError


def release_pvs(*args, **kwargs):
    raise NotImplementedError

import threading


class DummyDispatcherThreadContext:
    dispatcher = None
    event_type = None
    event_thread = None

    def run(self, *args, **kwargs):
        ...

    __call__ = run


class DummyDispatcher:
    context = None
    logger = None
    stop_event = None
    timeout = 0.1
    threads = {}

    def stop(self):
        ...

    def schedule_utility_task(self, callback, *args, **kwargs):
        ...

    def get_thread_context(self, name):
        return DummyDispatcherThreadContext()


thread_class = threading.Thread
pv_form = "time"
name = "dummy"
_dispatcher = DummyDispatcher()


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


def get_dispatcher():
    return _dispatcher

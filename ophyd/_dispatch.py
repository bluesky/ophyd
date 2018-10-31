import functools
import queue
import threading


class _CallbackThread(threading.Thread):
    'A queue-based callback dispatcher thread'

    def __init__(self, name, *, dispatcher):
        super().__init__(name=name)
        self.daemon = True
        self.stop_event = dispatcher._stop_event
        self.context = dispatcher.context
        self._timeout = dispatcher._timeout
        self.logger = dispatcher.logger
        self.queue = queue.Queue()

    def __repr__(self):
        return '<{} qsize={}>'.format(self.__class__.__name__,
                                      self.queue.qsize())

    def run(self):
        '''The dispatcher itself'''
        self.attach_context(self.context)
        self.logger.debug('Callback thread %s started', self.name)
        while not self.stop_event.is_set():
            try:
                callback, args, kwargs = self.queue.get(True, self._timeout)
            except queue.Empty:
                ...
            else:
                try:
                    callback(*args, **kwargs)
                except Exception as ex:
                    self.logger.exception(
                        'Exception occurred during callback %r', callback
                    )

        self.logger.debug('Callback thread %s exiting', self.name)
        self.detach_context()

    def attach_context(self, context):
        self.logger.debug('Callback thread %s attaching to context %s',
                          self.name, self.context)

    def detach_context(self):
        self.logger.debug('Callback thread %s detaching from context %s',
                          self.name, self.context)
        self.context = None


class EventDispatcher:
    def __init__(self, *, context, logger, timeout=0.1,
                 thread_class=_CallbackThread):
        self._threads = {}
        self._thread_class = thread_class
        self._timeout = timeout

        # The dispatcher thread will stop if this event is set
        self._stop_event = threading.Event()
        self.context = context
        self.logger = logger

        self._start_thread(name='metadata')
        self._start_thread(name='monitor')
        self._start_thread(name='get_put')

    def __repr__(self):
        threads = [repr(thread) for thread in self._threads.values()]
        return '<{} threads={}>'.format(self.__class__.__name__, threads)

    def is_alive(self):
        return any(thread.is_alive() for thread in self.threads.values()
                   if thread is not None)

    @property
    def threads(self):
        return dict(self._threads)

    def stop(self):
        '''Stop the dispatcher threads and re-enable normal callbacks'''
        self._stop_event.set()
        for attr, thread in list(self._threads.items()):
            if thread is not None:
                thread.join()

        self._threads.clear()

    def _start_thread(self, name):
        'Start dispatcher thread by name'
        self._threads[name] = self._thread_class(name=name, dispatcher=self)
        self._threads[name].start()


def wrap_callback(dispatcher, event_type, callback):
    'Wrap a callback for usage with the dispatcher'
    if callback is None:
        return

    assert event_type in dispatcher._threads

    @functools.wraps(callback)
    def wrapped(*args, **kwargs):
        queue = dispatcher._threads[event_type].queue
        queue.put((callback, args, kwargs))

    wrapped._wrapped_callback = True
    return wrapped

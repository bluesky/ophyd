import functools
import logging
import queue
import threading
import time


class _CallbackThread(threading.Thread):
    "A queue-based callback dispatcher thread"

    def __init__(
        self,
        name,
        *,
        dispatcher,
        logger,
        context,
        stop_event,
        timeout,
        callback_queue=None,
        daemon=True,
    ):
        super().__init__(name=name, daemon=daemon)
        self.context = context
        self.current_callback = None
        self.dispatcher = dispatcher
        self.logger = logger
        self.stop_event = stop_event
        self.timeout = timeout

        if callback_queue is None:
            callback_queue = queue.Queue()

        self.queue = callback_queue

    def __repr__(self):
        return "<{} qsize={}>".format(self.__class__.__name__, self.queue.qsize())

    def run(self):
        """The dispatcher itself"""
        self.logger.debug("Callback thread %s started", self.name)
        self.attach_context()

        while not self.stop_event.is_set():
            try:
                callback, args, kwargs = self.queue.get(True, self.timeout)
            except queue.Empty:
                ...
            else:
                try:
                    self.current_callback = (
                        getattr(callback, "__name__", "(unnamed)"),
                        kwargs.get("pvname"),
                    )
                    callback(*args, **kwargs)
                except Exception:
                    self.logger.exception(
                        "Exception occurred during callback %r (pvname=%r)",
                        callback,
                        kwargs.get("pvname"),
                    )

        self.detach_context()

    def attach_context(self):
        self.logger.debug(
            "Callback thread %s attaching to context %s", self.name, self.context
        )

    def detach_context(self):
        self.context = None


class DispatcherThreadContext:
    """
    A thread context associated with a single Dispatcher event type

    Parameters
    ----------
    dispatcher : Dispatcher
    event_type : str

    Attributes
    ----------
    dispatcher : Dispatcher
    event_type : str
    event_thread : _CallbackThread
    """

    def __init__(self, dispatcher, event_type):
        self.dispatcher = dispatcher
        self.event_type = event_type
        self.event_thread = None

    def run(self, func, *args, **kwargs):
        """
        If in the correct threading context, run func(*args, **kwargs) directly,
        otherwise schedule it to be run in that thread.
        """
        if self.event_thread is None:
            self.event_thread = self.dispatcher._threads[self.event_type]

        current_thread = threading.current_thread()
        if current_thread is self.event_thread:
            func(*args, **kwargs)
        else:
            self.event_thread.queue.put((func, args, kwargs))

    __call__ = run


debug_monitor_log = logging.getLogger("ophyd.event_dispatcher")


class EventDispatcher:
    def __init__(
        self,
        *,
        context,
        logger,
        timeout=0.1,
        thread_class=_CallbackThread,
        utility_threads=4,
    ):
        self._threads = {}
        self._thread_contexts = {}
        self._thread_class = thread_class
        self._timeout = timeout

        # The dispatcher thread will stop if this event is set
        self._stop_event = threading.Event()
        self.context = context
        self.logger = logger
        self.debug_monitor_interval = 1
        self._utility_threads = [f"util{i}" for i in range(utility_threads)]
        self._utility_queue = queue.Queue()

        self._start_thread(name="metadata")
        self._start_thread(name="monitor")
        self._start_thread(name="get_put")

        for name in self._utility_threads:
            self._start_thread(name=name, callback_queue=self._utility_queue)

        self._debug_monitor_thread = threading.Thread(
            target=self._debug_monitor, name="debug_monitor", daemon=True
        )
        self._debug_monitor_thread.start()

    def _debug_monitor(self):
        while not self._stop_event.is_set():
            queue_sizes = [
                (name, thread.queue.qsize(), thread.current_callback)
                for name, thread in sorted(self._threads.items())
            ]
            status = [
                "{name}={qsize} ({cb})".format(name=name, qsize=qsize, cb=cb)
                for name, qsize, cb in queue_sizes
                if qsize
            ]
            if status:
                debug_monitor_log.debug(" / ".join(status))
            # Else, all EventDispatch queues are empty.
            time.sleep(self.debug_monitor_interval)

    def __repr__(self):
        threads = [repr(thread) for thread in self._threads.values()]
        return "<{} threads={}>".format(self.__class__.__name__, threads)

    def is_alive(self):
        return any(
            thread.is_alive() for thread in self.threads.values() if thread is not None
        )

    @property
    def stop_event(self):
        return self._stop_event

    @property
    def timeout(self):
        return self._timeout

    @property
    def threads(self):
        return dict(self._threads)

    def stop(self):
        """Stop the dispatcher threads and re-enable normal callbacks"""
        self._stop_event.set()
        for attr, thread in list(self._threads.items()):
            if thread is not None:
                thread.join()

        self._threads.clear()
        self._debug_monitor_thread.join()

    def schedule_utility_task(self, callback, *args, **kwargs):
        "Schedule `callback` with the given args and kwargs in a util thread"
        self._utility_queue.put((callback, args, kwargs))

    def get_thread_context(self, name):
        "Get the DispatcherThreadContext for the given thread name"
        return self._thread_contexts[name]

    def _start_thread(self, name, *, callback_queue=None):
        "Start dispatcher thread by name"
        self._threads[name] = self._thread_class(
            name=name,
            dispatcher=self,
            stop_event=self._stop_event,
            timeout=self.timeout,
            context=self.context,
            logger=self.logger,
            daemon=True,
            callback_queue=callback_queue,
        )
        self._thread_contexts[name] = DispatcherThreadContext(self, name)
        self._threads[name].start()


def wrap_callback(dispatcher, event_type, callback):
    "Wrap a callback for usage with the dispatcher"
    if callback is None or getattr(callback, "_wrapped_callback", False):
        return callback

    assert event_type in dispatcher._threads
    callback_queue = dispatcher._threads[event_type].queue

    @functools.wraps(callback)
    def wrapped(*args, **kwargs):
        callback_queue.put((callback, args, kwargs))

    wrapped._wrapped_callback = True
    return wrapped

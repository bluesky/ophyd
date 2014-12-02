# vi: ts=4 sw=4 sts=4 expandtab
'''
:mod:`ophyd.utils.threads` - Ophyd threading utilities
======================================================

.. module:: ophyd.utils.threads
   :synopsis:

'''

from __future__ import print_function
import logging
import threading
import Queue as queue

import epics


class FThread(epics.ca.CAThread):

    def __init__(self, name, stop_event,
                 timeout=0.1, logger=None,
                 queue_class=queue.Queue, **kwargs):
        '''
        A thread created by the ThreadFunnel, which calls callbacks
        in its own context.
        '''
        epics.ca.CAThread.__init__(self, name=name)
        self.daemon = True

        self._timeout = timeout
        self._logger = logger
        self.queue = queue_class(**kwargs)
        self._stop_event = stop_event

    def main_loop(self):
        '''
        Grab events on the queue and call them in this FThread
        '''
        while not self._stop_event.is_set():
            try:
                callback, args, kwargs = self.queue.get(True, self._timeout)
            except queue.Empty:
                pass
            else:
                try:
                    callback(*args, **kwargs)
                except Exception as ex:
                    if self._logger is not None:
                        self._logger.error('Callback error: %s' % ex, exc_info=ex)

    def setup(self):
        pass

    def teardown(self):
        pass

    def run(self):
        '''
        The dispatcher itself
        '''

        self.setup()

        try:
            self.main_loop()
        finally:
            self.teardown()


class ThreadFunnel(object):
    def __init__(self, logger=None, name='thread_funnel',
                 categories=None, timeout=0.1, thread_class=FThread,
                 single_thread=False, locked=False, **kwargs):
        '''
        Funnels all events that are queued into the single "funnel" thread
        (or optionally multiple threads identified by name).

        :param str name: Name of the thread pool
        :param list categories: Categories to add, each representing one FThread
        :param float timeout: Timeout to use in busy-loops
        :param logger: Logger to use for callback exceptions
        :param bool single_thread: If set, only one category is used (and one thread).
        :param class thread_class: The class to use for the threads
        :param dict kwargs: Keyword arguments to pass to add_category()
        :param bool locked: Lock categories after initialization

        .. note:: categories is ignored if single_thread is set.
        '''
        self.daemon = True

        # The dispatcher thread will stop if this event is set
        self._name = name
        self._stop_event = threading.Event()
        self._timeout = timeout
        self._categories = {}
        self._thread_class = FThread
        self._logger = logger
        self._initialized = False

        if single_thread:
            self.add_event = self._add_single_event
            self.add_category('main', **kwargs)
        else:
            self.add_event = self._add_category_event
            if categories is not None:
                for category in categories:
                    self.add_category(category, **kwargs)

        self._locked = bool(locked)

    @property
    def name(self):
        return self._name

    @property
    def locked(self):
        return self._locked

    @property
    def categories(self):
        return tuple(sorted(self._categories.keys()))

    def __str__(self):
        return 'ThreadFunnel(name={0._name}, categories={0.categories})'.format(self)

    __repr__ = __str__

    def add_category(self, name, class_=None, start=True, **kwargs):
        if name in self._categories:
            raise ValueError('Category already exists')
        elif self._locked:
            raise RuntimeError('Categories locked')

        if class_ is None:
            class_ = self._thread_class

        thread = class_('%s.%s' % (self.name, name),
                        self._stop_event,
                        timeout=self._timeout,
                        logger=self._logger,
                        **kwargs)

        if not self._initialized:
            self.setup()
            self._initialized = True

        if start:
            thread.start()

        self._categories[name] = thread
        return thread

    def stop(self):
        '''
        Stop the dispatcher thread and re-enable normal callbacks
        '''
        self._stop_event.set()
        self._initialized = False
        self.teardown()

    def _add_single_event(self, fcn, *args, **kwargs):
        self._add_category_event('main', fcn, *args, **kwargs)

    def _add_category_event(self, category, fcn, *args, **kwargs):
        try:
            ft = self._categories[category]
        except KeyError:
            raise KeyError('Invalid FThread category "%s"' % category)

        ft.queue.put((fcn, args, kwargs))

    @property
    def threads(self):
        return self._categories.values()

    def join(self, timeout=1.0):
        self.stop()

        for thread in self.threads:
            thread.join(timeout)

    def setup(self):
        pass

    def teardown(self):
        pass


def test():
    import time
    import sys

    logger = logging.Logger('test')
    if False:
        logger.addHandler(logging.NullHandler())
    else:
        logger.setLevel(logging.DEBUG)

        handler = logging.StreamHandler(sys.stdout)
        fmt = logging.Formatter("** CB exception ** %(asctime)-15s [%(name)5s:%(levelname)s] %(message)s")
        handler.setFormatter(fmt)
        logger.addHandler(handler)

    funnel = ThreadFunnel(logger=logger, single_thread=True)

    def callback(*args, **kwargs):
        print('%s %s %s' % (threading.currentThread(), args, kwargs))

    print('main thread: %s' % threading.currentThread())

    funnel.add_event(callback, 'test', 'testing', kw='test')
    time.sleep(0.1)
    print('Funnel: %s' % funnel)
    funnel.join()
    print('done')

    categ = ['a', 'b', 'c']
    funnel = ThreadFunnel(logger=logger, categories=categ)
    print('Funnel: %s' % funnel)

    def callback_fail(*args, **kwargs):
        print('(exception cb) %s %s %s' % (threading.currentThread(), args, kwargs))
        raise ValueError('foobar')

    print('main thread: %s' % threading.currentThread())

    for i in range(3):
        for cat in categ:
            funnel.add_event(cat, callback, i, 'testing', kw='test')

    funnel.add_event(cat, callback_fail, 0, 'testing', kw='test')
    time.sleep(0.1)

    funnel.join()
    print('done')


if __name__ == '__main__':
    test()

*********************
Debugging and Logging
*********************

.. versionchanged:: 1.4.0

   Ophyd's use of Python's logging framework has been completely reworked to
   follow Python's documented best practices for libraries.

Ophyd uses Python's logging framework, which enables sophisticated log
management. For common simple cases, including viewing logs in the terminal or
writing them to a file, the next section illustrates streamlined,
copy/paste-able examples. Users who are familiar with that framework or who
need to route logs to multiple destinations may wish to skip ahead to
:ref:`logger_api`.

Useful Snippets
===============

Log warnings
------------

This is the recommended standard setup.

.. code-block:: python

   from ophyd.log import config_ophyd_logging
   config_ophyd_logging()

It will display ``'ophyd'`` log records of ``WARNING`` level or higher in the
terminal (standard out) with a format tailored to ophyd.

Maximum verbosity
-----------------

If operations are "hanging," running slowly, or repeatedly encountering an
error, increasing the logging verbosity can help identify the underlying issue.

.. code-block:: python

   from ophyd.log import config_ophyd_logging
   config_ophyd_logging(level='DEBUG')

Log to a file
-------------

This will direct all log messages to a file instead of the terminal (standard
out).

.. code-block:: python

    from ophyd.log import config_ophyd_logging
    config_ophyd_logging(file='/tmp/ophyd.log', level='DEBUG')

.. _logger_api:

Ophyd's Logging-Related API
=============================

Logger Names
------------

Here are the primary loggers used by ophyd.

* ``'ophyd'`` --- the logger to which all ophyd log records propagate
* ``'ophyd.objects'`` --- logs records from all devices and signals
  (that is, :class:`~ophyd.OphydObject` subclasses)
* ``'ophyd.control_layer'`` --- logs requests issued to the underlying control
  layer (e.g. pyepics, caproto)
* ``'ophyd.event_dispatcher'`` --- issues regular summaries of the backlog of
  updates from the control layer that are being processed on background threads

There are also many module-level loggers for specific features.

Formatter
---------

.. autoclass:: ophyd.log.LogFormatter

Global Handler
---------------

Following Python's recommendation, ophyd does not install any handlers at
import time, but it provides a function to set up a basic useful configuration
in one line, similar to Python's :py:func:`logging.basicConfig` but with some
additional options---and scoped to the ``'ophyd'`` logger with ophyd's
:class:`ophyd.log.LogFormatter`. It streamlines common use cases without
interfering with more sophisticated use cases.

We recommend that facilities using ophyd leave this function for users and
configure any standardized, facility-managed logging handlers separately, as
described in the next section.

.. autofunction:: ophyd.log.config_ophyd_logging
.. autofunction:: ophyd.log.get_handler

Advanced Example
================

The flow of log event information in loggers and handlers is illustrated in the
following diagram:

.. image:: https://docs.python.org/3/_images/logging_flow.png

For further reference, see the Python 3 logging howto:
https://docs.python.org/3/howto/logging.html#logging-flow

As an illustrative example, we will set up two handlers using the Python
logging framework directly, ignoring ophyd's convenience function.

Suppose we set up a handler aimed at a file:

.. code-block:: python

    import logging
    file_handler = logging.FileHandler('ophyd.log')

And another aimed at `Logstash <https://www.elastic.co/products/logstash>`_:

.. code-block:: python

    import logstash  # requires python-logstash package
    logstash_handler = logstash.TCPLogstashHandler(<host>, <port>, version=1)

We can attach the handlers to the ophyd logger, to which all log records
created by ophyd propagate:

.. code-block:: python

    logger = logging.getLogger('ophyd')
    logger.addHandler(logstash_handler)
    logger.addHandler(file_filter)

We can set the verbosity of each handler. Suppose want maximum verbosity in the
file but only medium verbosity in logstash.

.. code-block:: python

    logstash_handler.setLevel('INFO')
    file_handler.setLevel('DEBUG')

Finally, ensure that "effective level" of ``logger`` is at least as verbose as
the most verbose handler---in this case, ``'DEBUG'``. By default, at import,
its level is not set

.. ipython:: python
   :verbatim:

    logging.getLevelName(logger.level)
    'NOTSET'

and so it inherits the level of Python's default
"handler of last resort," :py:obj:`logging.lastResort`, which is ``'WARNING'``.

.. ipython:: python
   :verbatim:

    logging.getLevelName(logger.getEffectiveLevel())
    'WARNING'

In this case we should set it to ``'DEBUG'``, to match the most verbose level
of the handler we have added.

.. code-block:: python

   logger.setLevel('DEBUG')

This makes DEBUG-level records *available* to all handlers. Our logstash
handler, set to ``'INFO'``, will filter out DEBUG-level records.

To globally disable the generation of any log records at or below a certain
verbosity, which may be helpful for optimizing performance, Python provides
:py:func:`logging.disable`.

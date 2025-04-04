import json
import time
from re import search

import redis
from ophyd.ophydobj import Kind, OphydObject
from ophyd.status import Status
from ophyd.utils.epics_pvs import data_shape, data_type


class NoKey(KeyError): ...


class NoEventNotifications(EnvironmentError): ...


class RedisSignal(OphydObject):
    """Redis backed Ophyd Signal

    Handles:

      * Store and retrieving from redis database.
      * Setting up subscription thread.


    Parameters
    ----------
    key: str
        The redis key for this signal.
    r: redis.StrictRedis instance or parameters to redis.StrictRedis to create redis connection
        The redis instance or parameters.
    name : str, optional
        The name of the object. Default name is the key.
    inital_value : serializable, optional
        Value to set redis signal if not already initialised in Redis. If
    serializer_deserializer : tuple of callables, optional
        A pair of serializer/deserializer callables. Default is json.dumps/json.loads.

    """

    SUB_VALUE = "value"
    SUB_META = "meta"
    _default_sub = SUB_VALUE
    _metadata_keys = None
    _core_metadata_keys = ("connected", "timestamp")

    def __init__(
        self,
        key,
        *,
        r,
        initial_value=None,
        serializer_deserializer=None,
        name=None,
        timestamp=None,
        **kwargs,
    ):
        if name is None:
            name = key
        super().__init__(name=name, **kwargs)
        if not isinstance(r, redis.StrictRedis):
            r = redis.StrictRedis(**r)
        self._r = r
        self._key = key
        self._subscription_thread = None
        self._pubsub = None

        self._last_read = {"value": None, "timestamp": None}
        self._default_sub = self.SUB_VALUE

        if serializer_deserializer is None:
            self._serializer = json.dumps
            self._deserializer = json.loads
        else:
            self._serializer = serializer_deserializer[0]
            self._deserializer = serializer_deserializer[1]

        if initial_value is not None:
            if not self._r.exists(self._key):
                self.set(initial_value)

        if timestamp is None:
            timestamp = time.time()

        try:
            connected = self._r.ping()
        except redis.ConnectionError:
            connected = False

        self._metadata = dict(
            connected=connected,
            # read_access=True,
            # write_access=True,
            timestamp=timestamp,
            # status=None,
            # severity=None,
            # precision=None,
        )

    @property
    def timestamp(self):
        """Timestamp of the readback value"""
        return self._metadata["timestamp"]

    @property
    def connected(self):
        "Is the signal connected to its associated hardware, and ready to use?"
        return self._metadata["connected"]  # and not self._destroyed

    def set(self, value):
        """Set value of signal. Sets value of redis key to the serialized dictionary of value and timestamp.

        Returns
        -------
        st : Status
            The status object is set to finished on successful write to redis, or an exception is set if redis.ConnectionError is raised.
        """
        st = Status(self)
        try:
            server_time = self._r.time()
            ts = server_time[0] + server_time[1] / 1000000
            self._r.set(
                self._key,
                self._serializer({"value": value, "timestamp": ts}),
            )
        except redis.ConnectionError as e:
            st.set_exception(e)
        st.set_finished()
        return st

    def get(self):
        return self.read()[self.name]["value"]

    def put(self, value):
        self.set(value)

    def read(self):
        v = self._r.get(self._key)
        if v is None:
            raise NoKey

        self._last_read = self._deserializer(v)

        return {
            self.name: self._last_read,
        }

    def describe(self):
        val = self.read()
        return {
            k: {
                "source": f"redis://{self._r.connection_pool.connection_kwargs['host']}:{self._key}",
                "dtype": data_type(v["value"]),
                "shape": data_shape(v["value"]),
            }
            for k, v in val.items()
        }

    def read_configuration(self):
        return {}

    def describe_configuration(self):
        return {}

    @property
    def hints(self):
        if self.kind == Kind.hinted:
            return {"fields": [self.name]}
        else:
            return {}

    def subscribe(self, *args, **kwargs):
        """Subscribe to redis signal. If key is updated in redis, subscription callback(s) will be fired.

        Handles:

            * Starting subscription thread if not already running.

        Raises
        -------
        NoEventNotifications
            If notify-keyspace-events is not set to AK or $K on the redis server.

        Returns
        -------
        cid : int
            id of callback, can be passed to `unsubscribe` to remove the
            callback
        """
        events = self._r.config_get()["notify-keyspace-events"]
        if not search(r"^(?=.*(A|\$))(?=.*K)", events):
            raise NoEventNotifications

        if self._pubsub is None:
            self._pubsub = self._r.pubsub(ignore_subscribe_messages=True)

        self._pubsub.subscribe(**{f"__keyspace@0__:{self._key}": self._callback})
        if self._subscription_thread is not None:
            if self._subscription_thread.is_alive():
                return
        self._subscription_thread = self._pubsub.run_in_thread(
            sleep_time=None, daemon=True
        )

        cid = super().subscribe(self._callback, *args, **kwargs)

        return cid

    def clear_sub(self, cb, event_type=None):
        super().clear_sub(cb, event_type=event_type)
        if len(self._cid_to_event_mapping) == 0:
            self._delete_subscription()

    def unsubscribe(self, cid):
        super().unsubscribe(cid)
        if len(self._cid_to_event_mapping) == 0:
            self._delete_subscription()

    def unsubscribe_all(self):
        super().unsubscribe_all()
        self._delete_subscription()

    def _delete_subscription(self):
        self._pubsub.unsubscribe(f"__keyspace@0__:{self._key}")
        self._subscription_thread.stop()

    def _callback(self, *args, **kwargs):
        read = self.read()[self._key]
        self._run_subs(
            sub_type=self.SUB_VALUE,
            old_value=self._last_read["value"],
            value=read["value"],
            timestamp=read["timestamp"],
        )


class RedisSignalFactory:
    """Factory to return RedisSignals"""

    def __init__(self, r):
        if not isinstance(r, redis.StrictRedis):
            r = redis.StrictRedis(**r)
        self._redis = r

    def __getattr__(self, key, initial_value=None):
        return RedisSignal(key, r=self._redis, initial_value=initial_value)

    def get(self, key, initial_value=None):
        return self.__getattr__(key, initial_value)

    def get_signals_pattern(self, pattern: str):
        """Returns dictionary of signals with keys matching pattern"""
        return {
            k.decode("utf-8"): self.get(k.decode("utf-8"))
            for k in self._redis.scan_iter(pattern)
        }


# class StructuredRedisSignal(RedisSignal):
#     def __init__(self, channel, *, schema, **kwargs):
#         super().__init__(channel, **kwargs)
#         # TODO do more with schema!
#         self._allowed_keys = set(schema)

#     def set(self, **kwargs):
#         # TODO also check types etc
#         if set(kwargs) - self._allowed_keys:
#             raise ValueError("not allowed keys")
#         # TODO use a pipeline here so we can use watch!
#         try:
#             reading = self.read()
#         except NoKey:
#             current = {}
#         else:
#             current = {k[len(self.name) + 1 :]: v for k, v in reading.items()}

#         ts = time.time()

#         current.update({k: {"value": v, "timestamp": ts} for k, v in kwargs.items()})

#         st = Status(self)
#         self._r.set(
#             self._channel, self._serializer({"payload": current}),
#         )
#         st.set_finished()
#         return st

#     def read(self):
#         v = self._r.get(self._channel)
#         if v is None:
#             raise NoKey

#         return {
#             f"{self.name}_{k}": v for k, v in self._deserializer(v)["payload"].items()
#         }

# @property
# def hints(self):
#     # TODO sort out controlling internal kind state
#     if self.kind == Kind.hinted:
#         return {"fields": [f"{self.name}_{k}" for k in self._allowed_keys]}
#     else:
#         return {}

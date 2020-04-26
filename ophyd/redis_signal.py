import redis
import json
from ophyd.ophydobj import OphydObject, Kind
from ophyd.status import Status
from ophyd.utils.epics_pvs import data_type, data_shape
import time


class NoKey(KeyError):
    ...


class RedisSignal(OphydObject):
    def __init__(self, channel, *, r, name=None, **kwargs):
        if name is None:
            name = channel
        super().__init__(name=name, **kwargs)
        if not isinstance(r, redis.Redis):
            r = redis.Redis(**r)
        self._r = r
        self._channel = channel
        # TODO make this configurable
        self._serializer = json.dumps
        self._deserializer = json.loads

    def set(self, value):
        st = Status(self)
        ts = time.time()
        self._r.set(
            self._channel,
            self._serializer({"payload": {"value": value, "timestamp": ts}}),
        )
        st.set_finished()
        return st

    def read(self):
        v = self._r.get(self._channel)
        if v is None:
            raise NoKey
        return {
            self.name: self._deserializer(v)["payload"],
        }

    def describe(self):
        val = self.read()
        return {
            k: {
                # TODO make this better?
                "source": f"redis://{self._r.connection_pool.connection_kwargs['host']}:{self._channel}",
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
        raise TypeError("redis signals don't support subscriptions")


class StructuredRedisSignal(RedisSignal):
    def __init__(self, channel, *, schema, **kwargs):
        super().__init__(channel, **kwargs)
        # TODO do more with schema!
        self._allowed_keys = set(schema)

    def set(self, **kwargs):
        # TODO also check types etc
        if set(kwargs) - self._allowed_keys:
            raise ValueError("not allowed keys")
        # TODO use a pipeline here so we can use watch!
        try:
            reading = self.read()
        except NoKey:
            current = {}
        else:
            current = {k[len(self.name) + 1 :]: v for k, v in reading.items()}

        ts = time.time()

        current.update({k: {"value": v, "timestamp": ts} for k, v in kwargs.items()})

        st = Status(self)
        self._r.set(
            self._channel, self._serializer({"payload": current}),
        )
        st.set_finished()
        return st

    def read(self):
        v = self._r.get(self._channel)
        if v is None:
            raise NoKey

        return {
            f"{self.name}_{k}": v for k, v in self._deserializer(v)["payload"].items()
        }

    @property
    def hints(self):
        # TODO sort out controlling internal kind state
        if self.kind == Kind.hinted:
            return {"fields": [f"{self.name}_{k}" for k in self._allowed_keys]}
        else:
            return {}

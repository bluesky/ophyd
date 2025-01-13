import pymongo
import json
from ophyd.ophydobj import OphydObject, Kind
from ophyd.status import Status
from ophyd.utils.epics_pvs import data_type, data_shape
import time


class NoKey(KeyError):
    ...


class MongoSignal(OphydObject):
    database = "_OHPYD_SIGNAL_"
    collection = "_signal_"

    def __init__(self, key, *, mongo_client, name=None, **kwargs):
        if name is None:
            name = key
        super().__init__(name=name, **kwargs)
        if not isinstance(mongo_client, pymongo.MongoClient):
            mongo_client = pymongo.MongoClient(**mongo_client)
        self._mc = mongo_client
        self._db = mongo_client.get_database(self.database)
        self._col = self._db.get_collection(self.collection)
        self._key = key
        # TODO make this configurable
        self._serializer = json.dumps
        self._deserializer = json.loads

    def set(self, value):
        st = Status(self)
        ts = time.time()

        self._col.replace_one(
            {"key": self._key},
            {"payload": {"value": value, "timestamp": ts}, "key": self._key},
            upsert=True,
        )
        st.set_finished()
        return st

    def read(self):
        v = self._col.find_one({"key": self._key})
        if v is None:
            raise NoKey
        return {
            self.name: v["payload"],
        }

    def describe(self):
        val = self.read()
        return {
            k: {
                # TODO make this better?
                "source": f"mongo://{self._col}:{self._key}",
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
        raise TypeError("mongo signals don't support subscriptions")


class StructuredMongoSignal(MongoSignal):
    def __init__(self, key, *, schema, **kwargs):
        super().__init__(key, **kwargs)
        # TODO do more with schema!
        self._allowed_keys = set(schema)

    def set(self, **kwargs):
        # TODO also check types etc
        if set(kwargs) - self._allowed_keys:
            raise ValueError("not allowed keys")
        try:
            reading = self.read()
        except NoKey:
            current = {}
        else:
            current = {k[len(self.name) + 1 :]: v for k, v in reading.items()}

        ts = time.time()

        current.update({k: {"value": v, "timestamp": ts} for k, v in kwargs.items()})

        st = Status(self)
        self._col.replace_one(
            {"key": self._key}, {"payload": current, "key": self._key}, upsert=True,
        )
        st.set_finished()
        return st

    def read(self):
        v = self._col.find_one({"key": self._key})
        if v is None:
            raise NoKey

        return {f"{self.name}_{k}": v for k, v in v["payload"].items()}

    @property
    def hints(self):
        # TODO sort out controlling internal kind state
        if self.kind == Kind.hinted:
            return {"fields": [f"{self.name}_{k}" for k in self._allowed_keys]}
        else:
            return {}

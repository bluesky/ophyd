import time
import fakeredis

from ophyd.redis_signal import RedisSignal
from unittest.mock import MagicMock


def test_redis_signal():

    start_t = time.time()

    r = fakeredis.FakeStrictRedis()

    key = "test_key"
    value = "test_value"

    signal = RedisSignal(key, r=r, initial_value=value, timestamp=start_t)

    assert signal.connected
    assert signal.name == key
    assert signal.get() == value
    assert signal.timestamp == start_t


def test_redis_put():
    start_t = time.time()

    r = fakeredis.FakeStrictRedis()

    key = "test_key"
    value = "test_value"
    new_value = 10

    signal = RedisSignal(key, r=r, initial_value=value, timestamp=start_t)

    # test put method
    signal.put(new_value)
    assert signal.get() == new_value

    # reset value
    signal.put(value)
    assert signal.read()[key]["value"] == value
    signal.describe()

    # ensure configuration is readable and describable
    signal.read_configuration()
    signal.describe_configuration()


def test_redis_subscribe():
    start_t = time.time()

    r = fakeredis.FakeStrictRedis()

    key = "test_key"
    value = "test_value"

    signal = RedisSignal(key, r=r, initial_value=value, timestamp=start_t)

    # Mock the `config_get` method to simulate the presence of `notify-keyspace-events`
    r.config_get = MagicMock(return_value={"notify-keyspace-events": "AK"})

    cid = signal.subscribe()
    assert cid is not None

    signal.unsubscribe(cid)


if __name__ == "__main__":

    print(f"Testing: test_redis_signal")
    test_redis_signal()
    print("Done.")

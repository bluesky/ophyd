import time
import fakeredis

from ophyd import RedisSignal

def test_redis_signal():

    start_t = time.time()

    r = fakeredis.FakeStrictRedis()

    key = 'test_key'
    value = 'test_value'
    new_value = 10

    signal = RedisSignal(name, r=r, timestamp=start_t)

    assert signal.connected
    assert signal.name == name
    assert signal.get() == value
    assert signal.timestamp == start_t

    # test put method
    signal.put(new_value)
    assert signal.get() == new_value
    # reset value
    signal.put(value)
    assert signal.read()['value'] == value
    # signal.describe()
    # signal.read_configuration()
    # signal.describe_configuration()

    # eval(repr(signal))

    # Need a way to test subscriptions. Look at other redis mocking options.


if __name__ == "__main__":

    print(f'Testing: test_redis_signal')
    test_redis_signal()
    print('Done.')
from ophyd.sim import make_fake_device
from ophyd.areadetector.plugins import StatsPlugin, copy_plugin


def test_copy_plugin_values_all():
    # Create a fake StatsPlugin device class
    FakeStats1 = make_fake_device(StatsPlugin)
    FakeStats2 = make_fake_device(StatsPlugin)

    # Instantiate two fake plugin devices
    src = FakeStats1("SRC:", name="src")
    tgt = FakeStats2("TGT:", name="tgt")

    # Set a value on the source device
    src.compute_centroid.put(1)
    src.hist_max.put(123)
    src.hist_min.put(10)

    # Target should have different values before copy
    tgt.compute_centroid.put(0)
    tgt.hist_max.put(0)
    tgt.hist_min.put(0)

    # Copy all values from src to tgt
    copy_plugin(src, tgt)

    # Assert that values have been copied
    assert tgt.compute_centroid.get() == '1'
    assert tgt.hist_max.get() == 123
    assert tgt.hist_min.get() == 10


def test_copy_plugin_include():
    FakeStats_INC = make_fake_device(StatsPlugin)

    # Instantiate two fake plugin devices
    src_inc = FakeStats_INC("SRC:", name="src")
    tgt_inc = FakeStats_INC("TGT:", name="tgt")

    # Set a value on the source device
    src_inc.compute_centroid.sim_put(1)
    src_inc.hist_max.sim_put(123)
    src_inc.hist_min.sim_put(10)

    # Target should have different values before copy
    tgt_inc.compute_centroid.sim_put(0)
    tgt_inc.hist_max.sim_put(0)
    tgt_inc.hist_min.sim_put(0)

    # Test include/exclude
    src_inc.hist_max.sim_put(555)
    copy_plugin(src_inc, tgt_inc, include={src_inc.hist_max})
    assert tgt_inc.hist_max.get() == 555
    # hist_min and compute_centroid should remain unchanged
    assert tgt_inc.hist_min.get() == 0
    assert tgt_inc.compute_centroid.get() == '0'


def test_copy_plugin_exclude():
    FakeStat2 = make_fake_device(StatsPlugin)

    # Instantiate two fake plugin devices
    src_exc = FakeStat2("SRC:", name="src")
    tgt_exc = FakeStat2("TGT:", name="tgt")

    # Set a value on the source device
    src_exc.compute_centroid.sim_put(1)
    src_exc.hist_max.sim_put(123)
    src_exc.hist_min.sim_put(999)

    # Target should have different values before copy
    tgt_exc.compute_centroid.sim_put(0)
    tgt_exc.hist_max.sim_put(0)
    tgt_exc.hist_min.sim_put(0)

    copy_plugin(src_exc, tgt_exc, exclude={src_exc.hist_max})
    # hist_max should remain unchanged
    assert tgt_exc.hist_max.get() == 0
    # hist_min and compute_centroid should be updated
    assert tgt_exc.hist_min.get() == 999
    assert tgt_exc.compute_centroid.get() == '1'

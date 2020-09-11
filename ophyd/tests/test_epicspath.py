import pytest

from ..areadetector.paths import EpicsPathSignal
from ..areadetector.plugins import FilePlugin
from .. import wait, SingleTrigger, SimDetector
from ..device import (Component as Cpt,)


def test_path_semantics_exception():
    with pytest.raises(ValueError):
        EpicsPathSignal('TEST', path_semantics='not_a_thing')


# @pytest.mark.adsim
# @pytest.mark.parametrize()
# def test_epicspath(cleanup, ad_prefix):
#     class MyDetector(SingleTrigger, SimDetector):
#         fp1 = Cpt(FilePlugin, '')
#
#     det = MyDetector(ad_prefix, name='test')
#     print(det.fp1.plugin_type)
#     cleanup.add(det)
#
#     det.wait_for_connection()
#
#     # try passing in a bunch of unix/windows paths
#     # and make sure they are fine or break?
#     windows_path_list = ['']
#     unix_path_list = ['/path/to/a/thing']
#
#     det.cam.path_semantics = 'posix'
#     det.cam.file_path.put('/path/to/a/thing')
#     det.stage()
#     st = det.trigger()
#     wait(st, timeout=5)
#     det.unstage()

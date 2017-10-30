import os

__all__ = ['setup',
           'caput', 'caget',
           'get_pv',
           'pv_form',
           'thread_class']

if os.environ.get('CAPROTO', False):
    from ._caproto_shim import setup, caput, caget, get_pv, pv_form, thread_class
else:
    from ._pyepics_shim import setup, caput, caget, get_pv, pv_form, thread_class

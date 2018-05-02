import os
import warnings


warnings.warn("This module is deprecated in ophyd 1.1 and "
              "will be removed in 1.2. "
              "use the cl attribute at the top level instead",
              stacklevel=2)

__all__ = ['setup',
           'caput', 'caget',
           'get_pv',
           'pv_form',
           'thread_class']
_cl = os.environ.get('OPHYD_CONTROL_LAYER', '').lower()

if _cl == 'caproto':
    from ._caproto_shim import setup, caput, caget, get_pv, pv_form, thread_class
elif '_cl' == 'dummy':
    from ._dummy_shim import setup, caput, caget, get_pv, pv_form, thread_class
else:
    try:
        from ._pyepics_shim import setup, caput, caget, get_pv, pv_form, thread_class
    except ImportError:
        from ._dummy_shim import setup, caput, caget, get_pv, pv_form, thread_class
del _cl

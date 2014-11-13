'''
'''

import sys
import logging

try:
    import ophyd
except ImportError:
    sys.path.insert(0, '..')
    import ophyd


LOG_FORMAT = "%(asctime)-15s [%(name)5s:%(levelname)s] %(message)s"
EXAMPLE_LOGGER = 'ophyd_examples'


def setup_loggers(logger_names, fmt=LOG_FORMAT):
    fmt = logging.Formatter(LOG_FORMAT)
    for name in logger_names:
        logger = logging.getLogger(name)
        logger.setLevel(logging.DEBUG)

        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(fmt)
        logger.addHandler(handler)


session = ophyd.get_session_manager()

setup_loggers((EXAMPLE_LOGGER, ))
logger = logging.getLogger(EXAMPLE_LOGGER)

motor_recs = ['XF:31IDA-OP{Tbl-Ax:X1}Mtr',
              'XF:31IDA-OP{Tbl-Ax:X2}Mtr',
              'XF:31IDA-OP{Tbl-Ax:X3}Mtr',
              'XF:31IDA-OP{Tbl-Ax:X4}Mtr',
              'XF:31IDA-OP{Tbl-Ax:X5}Mtr',
              'XF:31IDA-OP{Tbl-Ax:X6}Mtr',
              ]

fake_motors = [{'readback': 'XF:31IDA-OP{Tbl-Ax:FakeMtr}-I',
                'setpoint': 'XF:31IDA-OP{Tbl-Ax:FakeMtr}-SP',
                'moving': 'XF:31IDA-OP{Tbl-Ax:FakeMtr}Sts:Moving-Sts',
                'actuate': 'XF:31IDA-OP{Tbl-Ax:FakeMtr}Cmd:Go-Cmd.PROC',
                'stop': 'XF:31IDA-OP{Tbl-Ax:FakeMtr}Cmd:Stop-Cmd.PROC',
                },

               ]

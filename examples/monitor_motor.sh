#!/bin/bash
# Monitor the motor status as you run the example scripts

camonitor XF:31IDA-OP{Tbl-Ax:X1}Mtr.VAL XF:31IDA-OP{Tbl-Ax:X1}Mtr.RBV XF:31IDA-OP{Tbl-Ax:FakeMtr}-I  XF:31IDA-OP{Tbl-Ax:X1}Mtr.VAL  XF:31IDA-OP{Tbl-Ax:FakeMtr}-SP

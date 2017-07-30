#!/bin/bash

# Usage: coverage_single.sh tests/test_pvpositioner.py [ophyd/pv_positioner.py]

py.test -v --cov=ophyd --cov-report term-missing --cov-report html $1
if [ "$2" != "" ]; then
    $EDITOR $2 -c ":Coveragepy report"
fi

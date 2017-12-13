#!/usr/bin/bash

export DOCKER0_IP="172.17.0.1"
export EPICS_CA_ADDR_LIST=$( echo $DOCKER0_IP | sed -e 's/^\([0-9]\+\)\.\([0-9]\+\)\..*$/\1.\2.255.255/' )
export EPICS_CA_AUTO_ADDR_LIST="no"
export EPICS_CA_MAX_ARRAY_BYTES=10000000


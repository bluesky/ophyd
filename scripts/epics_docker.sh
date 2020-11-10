#!/bin/bash

systemctl status docker.service > /dev/null
if ! [ $? -eq 0 ]; then
    echo $?
    systemctl restart docker.service
fi

SCRIPTS_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
source $SCRIPTS_DIR/epics_exports.sh

DOCKERIMAGE="nsls2/epics-docker:latest"
PE_DOCKERIMAGE="nsls2/pyepics-docker:latest"

docker pull ${DOCKERIMAGE}
docker pull ${PE_DOCKERIMAGE}
mkdir -p /tmp/data
# this is required because the images use a version of AD which
# does not create missing directories.
python $SCRIPTS_DIR/create_directories.py /tmp/ophyd_AD_test/data1
python $SCRIPTS_DIR/create_directories.py /tmp/ophyd_AD_test/data2
docker run -d -p $DOCKER0_IP:7000-9000:5064/tcp -v /tmp/data:/data ${DOCKERIMAGE}
docker run -d -p $DOCKER0_IP:7000-9000:5064/tcp ${PE_DOCKERIMAGE}


#!/bin/bash

systemctl status docker.service > /dev/null
if ! [ $? -eq 0 ]; then
    echo $?
    systemctl restart docker.service
fi

SCRIPTS_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
source $SCRIPTS_DIR/epics_exports.sh

MOTOR_DOCKERIMAGE="nsls2/epics-docker:latest"
PE_DOCKERIMAGE="nsls2/pyepics-docker:latest"
AD_DOCKERIMAGE="prjemian/synapps-6.1-ad-3.7:latest"

docker pull ${MOTOR_DOCKERIMAGE}
docker pull ${PE_DOCKERIMAGE}
docker pull ${AD_DOCKERIMAGE}

mkdir -p /tmp/ophyd_AD_test/

# Create YYYY/MM/DD subdirectories.
# This is required because the images use a version of AD which
# does not create missing directories.
python $SCRIPTS_DIR/create_directories.py /tmp/ophyd_AD_test/data1

docker run --rm -d -p $DOCKER0_IP:7000-9000:5064/tcp -v /tmp/ophyd_AD_test:/tmp/ophyd_AD_test/ ${MOTOR_DOCKERIMAGE}
docker run --rm -dit -p $DOCKER0_IP:7000-9000:5064/tcp -v /tmp/ophyd_AD_test:/tmp/ophyd_AD_test/ -e AD_PREFIX="ADSIM:" ${AD_DOCKERIMAGE} iocSimDetector/simDetector.sh start
docker run --rm -d -p $DOCKER0_IP:7000-9000:5064/tcp ${PE_DOCKERIMAGE}


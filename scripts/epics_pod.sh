#! /usr/bin/bash
set -e
set -o xtrace


SCRIPTS_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

MOTOR_DOCKERIMAGE="docker.io/nsls2/epics-docker:latest"
PE_DOCKERIMAGE="docker.io/nsls2/pyepics-docker:latest"
AD_DOCKERIMAGE="docker.io/prjemian/synapps-6.1-ad-3.7:latest"

podman pull ${MOTOR_DOCKERIMAGE}
podman pull ${PE_DOCKERIMAGE}
podman pull ${AD_DOCKERIMAGE}

podman pod stop ophyd_testing || true
podman pod rm ophyd_testing || true

# create the testing pod, do not expose anything
podman pod create -n ophyd_testing

# TODO do this with volumes
# set up directories for AD
mkdir -p /tmp/ophyd_AD_test/
# Create YYYY/MM/DD subdirectories.
# This is required because the images use a version of AD which
# does not create missing directories.
python $SCRIPTS_DIR/create_directories.py /tmp/ophyd_AD_test/data1

podman run --pod ophyd_testing --name=sim_motor  --rm -d ${MOTOR_DOCKERIMAGE}
podman run --pod ophyd_testing --name=area-detector --rm -dit -v /tmp/ophyd_AD_test:/tmp/ophyd_AD_test/ -e AD_PREFIX="ADSIM:" ${AD_DOCKERIMAGE} /bin/bash
sleep 1  # Probably not needed?
podman exec area-detector iocSimDetector/simDetector.sh start
podman run --pod ophyd_testing --name=pyepics-container --rm -d ${PE_DOCKERIMAGE}

# make testing container
podman run --pod ophyd_testing --name test_target --rm -dit -v `pwd`:'/app' -w '/app' fedora bash
# make testing env
podman exec test_target python3 -m venv /test
podman exec test_target /test/bin/python -m pip install --upgrade pip
# install system deps
podman exec test_target yum install python3-devel gcc -y
# install python testing deps
podman exec test_target /test/bin/python -m pip install -r requirements-test.txt
# install (editable) ophyd
podman exec test_target /test/bin/python -m pip install -ve .

#!/bin/bash

SCRIPTS_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
source $SCRIPTS_DIR/epics_exports.sh

# Override the deprecation warning of V1 images
# Remove when images are updated
sudo mkdir -p /etc/systemd/system/docker.service.d
file="/etc/systemd/system/docker.service.d/extra_env.conf"
sudo cp $SCRIPTS_DIR/docker.conf $file
sudo systemctl daemon-reload
sudo systemctl restart docker

AD_DOCKERIMAGE="prjemian/synapps-6.1-ad-3.7:latest"

docker pull ${AD_DOCKERIMAGE}

mkdir -p /tmp/ophyd_AD_test/

# Create YYYY/MM/DD subdirectories.
# This is required because the images use a version of AD which
# does not create missing directories.
python $SCRIPTS_DIR/create_directories.py /tmp/ophyd_AD_test/data1

docker run --name=area-detector --rm -dit -v /tmp/ophyd_AD_test:/tmp/ophyd_AD_test/ -e AD_PREFIX="ADSIM:" ${AD_DOCKERIMAGE} /bin/bash
sleep 1  # Probably not needed?
docker exec area-detector iocSimDetector/simDetector.sh start

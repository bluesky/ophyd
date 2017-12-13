#!/usr/bin/bash

systemctl status docker.service > /dev/null
if ! [ $? -eq 0 ]; then
    echo $?
    systemctl restart docker.service
fi

source epics_exports.sh

DOCKERIMAGE="klauer/epics-docker"
PE_DOCKERIMAGE="klauer/simioc-docker"
PE_DOCKERTAG="pyepics-docker"

docker pull ${DOCKERIMAGE}
docker pull ${PE_DOCKERIMAGE}:${PE_DOCKERTAG}
mkdir -p /tmp/data
# this is required because the images use a version of AD which
# does not create missing directories.
python -c "import ophyd.utils.paths as oup; import datetime; now = datetime.datetime.now(); [oup.make_dir_tree(now.year + j, base_path='/tmp/data') for j in [-1, 0, 1]]"
docker run -d -p $DOCKER0_IP:7000-9000:5064/tcp -v /tmp/data:/data ${DOCKERIMAGE}
docker run -d -p $DOCKER0_IP:7000-9000:5064/tcp ${PE_DOCKERIMAGE}:${PE_DOCKERTAG}


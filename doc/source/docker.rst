Docker setup
============

.. highlight:: bash


You can use Docker to run test IOCs that are convenient for testing without
having to locally build and install EPICS IOCs. Please use the following
Docker links to install and configure Docker:

  - `Installing Docker on ubuntu <https://docs.docker.com/engine/installation/linux/docker-ce/ubuntu/#uninstall-docker-ce>`_
  - `Configuring Docker (allowing to run as non-root, running at startup, etc.) <https://docs.docker.com/engine/installation/linux/linux-postinstall/>`_

To communicate with the Docker you have set up some environmental variables: ::

   #!/bin/bash

   export DOCKER0_IP="172.17.0.1"
   export EPICS_CA_ADDR_LIST=$( echo $DOCKER0_IP | sed -e 's/^\([0-9]\+\)\.\([0-9]\+\)\..*$/\1.\2.255.255/' )
   export EPICS_CA_AUTO_ADDR_LIST="no"
   export EPICS_CA_MAX_ARRAY_BYTES=10000000


and to run docker with the correct images (assuming the preceding code block is
saved in :file:`epics_exports.sh`): ::

   #!/bin/bash

   systemctl status docker.service > /dev/null
   if ! [ $? -eq 0 ]
   then
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

Running this multiple times will lead to multiple instances of the
images running.

For EPICS to know where to search for the IOCs you will need to do ::

  source epics_exports.sh


to setup the EPICS environmental variables. To check that it is setup
correctly ::

  $ env | grep -i epics
  EPICS_CA_ADDR_LIST=172.17.255.255
  EPICS_CA_AUTO_ADDR_LIST=no
  EPICS_CA_MAX_ARRAY_BYTES=10000000

To check if it is working, try ::

  $ caget XF:31IDA-OP{Tbl-Ax:X1}Mtr

.. note::

  You may need to install ``pyepics``, which installs ``epics-base``
  and the corresponding ``caget`` executable: ::

    conda install -c lightsource2-tag pyepics


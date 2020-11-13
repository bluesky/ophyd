Docker setup
============

.. highlight:: bash


You can use Docker to run test IOCs that are convenient for testing without
having to locally build and install EPICS IOCs. Please use the following
Docker links to install and configure Docker:

  - `Installing Docker on Ubuntu <https://docs.docker.com/engine/installation/linux/docker-ce/ubuntu/>`_
  - `Configuring Docker <https://docs.docker.com/engine/installation/linux/linux-postinstall/>`_
    (allowing to run as non-root, running at startup, etc.)

To communicate with the Docker you have set up some environmental variables:

.. literalinclude:: ../../scripts/epics_exports.sh

and to run docker with the correct images (assuming the preceding code block is
saved in :file:`epics_exports.sh`):

.. literalinclude:: ../../scripts/epics_docker.sh

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


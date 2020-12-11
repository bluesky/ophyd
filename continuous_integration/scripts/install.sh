#!/bin/bash
set -vxeuo pipefail

sudo apt install graphviz procserv libhdf5-dev
# These packages are installed in the base environment but may be older
# versions. Explicitly upgrade them because they often create
# installation problems if out of date.
python -m pip install --upgrade pip setuptools numpy
pip install .
pip install -r requirements-docs.txt
pip list

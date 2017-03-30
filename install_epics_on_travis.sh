#!/bin/sh
set -e
sudo apt-get update
sudo apt-get install -yq wget
wget --quiet http://epics.nsls2.bnl.gov/debian/repo-key.pub -O - | apt-key add -
echo "deb http://epics.nsls2.bnl.gov/debian/ jessie/staging main contrib" | tee /etc/apt/sources.list.d/nsls2.list
sudo apt-get update
sudo apt-get install -yq epics-dev

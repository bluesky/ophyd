#! /usr/bin/bash
set -e
set -o xtrace

podman exec -it test_target /test/bin/python -m pytest $@

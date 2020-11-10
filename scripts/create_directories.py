#!/usr/bin/env python
"Create directories where Area Detector will save its data during tests."
from ophyd.utils.paths import make_dir_tree
import datetime


def main(args):
    base_path = args[1]  # e.g. "/tmp/data"
    now = datetime.datetime.now()
    # Make YYYY/MM/DD/ directories for yesterday, today, and tomorrow.
    for offset in (-1, 0, 1):
        make_dir_tree(now.year + j, base_path=base_path)


if __name__ == "__main__":
    import sys

    main(sys.argv)

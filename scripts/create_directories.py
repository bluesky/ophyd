#!/usr/bin/env python
"Create directories where Area Detector will save its data during tests."
import datetime

from ophyd.utils.paths import make_dir_tree


def main(args):
    base_path = args[1]  # e.g. "/tmp/data"
    now = datetime.datetime.now()
    # Make YYYY/MM/DD/ directories for last year, this year, next year.
    for offset in (-1, 0, 1):
        make_dir_tree(now.year + offset, base_path=base_path)


if __name__ == "__main__":
    import sys

    main(sys.argv)

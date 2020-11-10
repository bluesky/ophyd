#!/usr/bin/env python
from ophyd.utils.paths import make_dir_tree
import datetime


def main(args):
    base_path = args[1]  # e.g. "/tmp/data"
    now = datetime.datetime.now()
    for offset in (-1, 0, 1):
        make_dir_tree(now.year + j, base_path=base_path)


if __name__ == "__main__":
    import sys

    main(sys.argv)

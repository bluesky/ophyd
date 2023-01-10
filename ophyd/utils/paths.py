import calendar
import os


def makedirs(path, *, mode=0o755, mode_base=None):
    """Recursively make directories and set permissions

    Parameters
    ----------
    path : str
        Full path to create, including all parent directories
    mode : int, optional
        Mode to set
    mode_base : str, optional
        If specified, only try to set mode after this directory
        Full base path
    """
    # Permissions not working with os.makedirs -
    # See: http://stackoverflow.com/questions/5231901
    if not path or os.path.exists(path):
        return []

    head, tail = os.path.split(path)

    # Recurse on all directories above:
    ret = makedirs(head, mode=mode, mode_base=mode_base)

    # Then try to make the last directory:
    os.makedirs(path, mode=mode, exist_ok=True)

    # And set its permissions if after mode_base:
    if not mode_base or os.path.commonprefix((mode_base, path)) == mode_base:
        os.chmod(path, mode)

    ret.append(path)
    return ret


def make_dir_tree(year, *, base_path=None, mode=0o755):
    """Make full directory tree for the year

    Parameters
    ----------
    year : int
    base_path : str, optional
        If unspecified, defaults to the current directory
    mode : int, optional
        File mode to set for permissions (default: 0o755)

    Returns
    -------
    paths : list
        List of directories created
    """
    if base_path is None:
        base_path = os.getcwd()

    year_dir = os.path.join(base_path, str(year))
    paths = []

    for month in range(1, 13):
        month_dir = os.path.join(year_dir, "%02d" % month)

        _, num_days = calendar.monthrange(year, month)
        for day in range(1, 1 + num_days):
            day_path = os.path.join(month_dir, "%02d" % day)
            paths.append(day_path)

    for path in paths:
        makedirs(path, mode=mode, mode_base=base_path)

    return paths

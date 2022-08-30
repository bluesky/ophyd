import subprocess
import sys

from ophyd import __version__


def test_cli_version():
    cmd = [sys.executable, "-m", "ophyd", "--version"]
    assert subprocess.check_output(cmd).decode().strip() == __version__

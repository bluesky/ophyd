import logging  # noqa: F401
import os
import subprocess
import sys

logger = logging.getLogger(__name__)


def subprocess_run_for_testing(
    command,
    env=None,
    timeout=60,
    stdout=None,
    stderr=None,
    check=False,
    text=True,
    capture_output=False,
):
    """
    Create and run a subprocess.

    Thin wrapper around `subprocess.run`, intended for testing.  Will
    mark fork() failures on Cygwin as expected failures: not a
    success, but not indicating a problem with the code either.

    Borrowed from
    https://github.com/matplotlib/matplotlib/blob/e1887b8d0d44d66103f0e3c787cfe7281daa7c63/lib/matplotlib/testing/__init__.py#L55

    Parameters
    ----------
    command : list of str
    env : dict[str, str]
    timeout : float
    stdout, stderr
    check : bool
    text : bool
        Also called ``universal_newlines`` in subprocess.  I chose this
        name since the main effect is returning bytes (`False`) vs. str
        (`True`), though it also tries to normalize newlines across
        platforms.
    capture_output : bool
        Set stdout and stderr to subprocess.PIPE

    Returns
    -------
    proc : subprocess.Popen

    See Also
    --------
    subprocess.run

    Raises
    ------
    pytest.xfail
        If platform is Cygwin and subprocess reports a fork() failure.
    """
    if capture_output:
        stdout = stderr = subprocess.PIPE
    try:
        proc = subprocess.run(
            command,
            env=env,
            timeout=timeout,
            check=check,
            stdout=stdout,
            stderr=stderr,
            text=text,
        )
    except BlockingIOError:
        if sys.platform == "cygwin":
            # Might want to make this more specific
            import pytest

            pytest.xfail("Fork failure")
        raise
    except subprocess.CalledProcessError as e:
        if e.stdout:
            logger.info(f"Subprocess output:\n{e.stdout}")
        if e.stderr:
            logger.error(f"Subprocess error:\n{e.stderr}")
        raise e
    if proc.stdout:
        logger.info(f"Subprocess output:\n{proc.stdout}")
    if proc.stderr:
        logger.error(f"Subprocess error:\n{proc.stderr}")
    return proc


def subprocess_run_helper(func, *args, timeout, extra_env=None):
    """
    Run a function in a sub-process.

    Borrowed from
    https://github.com/matplotlib/matplotlib/blob/e1887b8d0d44d66103f0e3c787cfe7281daa7c63/lib/matplotlib/testing/__init__.py#L111

    Parameters
    ----------
    func : function
        The function to be run.  It must be in a module that is importable.
    *args : str
        Any additional command line arguments to be passed in
        the first argument to ``subprocess.run``.
    extra_env : dict[str, str]
        Any additional environment variables to be set for the subprocess.
    """
    target = func.__name__
    module = func.__module__
    file = func.__code__.co_filename
    proc = subprocess_run_for_testing(
        [
            sys.executable,
            "-c",
            f"import importlib.util;"
            f"_spec = importlib.util.spec_from_file_location({module!r}, {file!r});"
            f"_module = importlib.util.module_from_spec(_spec);"
            f"_spec.loader.exec_module(_module);"
            f"_module.{target}()",
            *args,
        ],
        env={**os.environ, "SOURCE_DATE_EPOCH": "0", **(extra_env or {})},
        timeout=timeout,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return proc

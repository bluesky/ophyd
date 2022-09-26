"""IPython magics wrapping some RunEngine plans"""

from typing import Any, List

from bluesky import RunEngine
from bluesky import plan_stubs as bps
from IPython.core.magic import Magics, line_magic, magics_class


def _print_rd(obj):
    value = yield from bps.rd(obj)
    print(repr(value))


@magics_class
class _OphydMagics(Magics):
    """IPython magics for ophyd."""

    @property
    def RE(self) -> RunEngine:
        return self.shell.user_ns["RE"]

    def eval(self, arg: str) -> Any:
        return eval(arg, self.shell.user_ns)

    def eval_args(self, line: str) -> List:
        return [eval(arg, self.shell.user_ns) for arg in line.split()]

    @line_magic
    def mov(self, line: str):
        self.RE(bps.mov(*self.eval_args(line)))

    @line_magic
    def movr(self, line: str):
        self.RE(bps.movr(*self.eval_args(line)))

    @line_magic
    def rd(self, line: str):
        self.RE(_print_rd(self.eval(line)))


def register():
    """Register magics with IPython so they can be used.

    They consist of:

    - ``mov device pos`` will move device to absolute position pos
    - ``movr device pos`` will move device to relative position pos
    - ``rd device`` will print the position of device
    """
    from IPython import get_ipython

    get_ipython().register_magics(_OphydMagics)

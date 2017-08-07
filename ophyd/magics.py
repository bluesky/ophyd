from IPython.core.magic import Magics, magics_class, line_magic
from operator import attrgetter
from ophyd.utils import DisconnectedError

@magics_class
class SPECMagics(Magics):

    positioners = []

    @line_magic
    def wa(self, line):
        "List positioner info. 'wa' stands for 'where all'."
        if line.split():
            raise TypeError("No parameters expected, just %wa")
        positioners = sorted(set(self.positioners), key=attrgetter('name'))
        lines = []
        LINE_FMT = '{: <30} {: <15} {: <15} {: <15}'
        headers = ['Positioner', 'Value', 'Low Limit', 'High Limit']
        lines.append(LINE_FMT.format(*headers))
        for p in positioners:
            try:
                pos = p.position
            except DisconnectedError:
                pos = '<DISCONNECTED>'
            except Exception:
                pos = '<ERROR>'
            try:
                low_limit, high_limit = p.limits
            except DisconnectedError:
                low_limit = high_limit = '<DISCONNECTED>'
            except Exception:
                low_limit = high_limit = '<ERROR>'
            line = LINE_FMT.format(p.name, pos, low_limit, high_limit)
            lines.append(line)
        print('\n'.join(lines))

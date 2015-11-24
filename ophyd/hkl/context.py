class UsingEngine(object):
    """Context manager that uses a calculation engine temporarily"""
    def __init__(self, calc, engine):
        self.calc = calc
        self.engine = engine
        self.old_engine = None

    def __enter__(self):
        self.old_engine = self.calc.engine
        if self.engine is not None:
            self.calc.engine = self.engine

    def __exit__(self, type_, value, traceback):
        if self.engine is not None:
            self.calc.engine = self.old_engine


class TemporaryGeometry(object):
    """Context manager that restores physical geometry after a block of code"""

    def __init__(self, calc):
        self.calc = calc

    def __enter__(self):
        self.geometry = self.calc._geometry.copy()

    def __exit__(self, type_, value, traceback):
        self.calc._geometry = self.geometry
        self.calc._re_init()

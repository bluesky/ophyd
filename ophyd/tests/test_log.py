import pytest

import ophyd.log as log


def test_validate_level():
    log.validate_level("CRITICAL")
    log.validate_level("ERROR")
    log.validate_level("WARNING")
    log.validate_level("INFO")
    log.validate_level("DEBUG")
    log.validate_level("NOTSET")

    with pytest.raises(ValueError):
        log.validate_level("TRACE")

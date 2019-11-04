#!/usr/bin/env python
from setuptools import (setup, find_packages)
import sys
import versioneer

with open('requirements.txt') as f:
    requirements = f.read().split()

# Temporary hack until databroker is on PyPI, needed because
# `pip install -r requirements.txt` works with git URLs, but `install_requires`
# does not.
requirements = [r for r in requirements if not r.startswith('git+')]
print("User must install https://github.com/NSLS-II/databroker manually")

with open('test-requirements.txt') as f:
    test_requirements = f.read().split()

if sys.version_info < (3, 6):
    caproto_warning = """
Python 3.6 or above is required for caproto.
The caproto tests will not be run.
"""
    print('*'*45)
    print(caproto_warning)
    print('*'*45)

    # remove caproto from test_requirements
    test_requirements = [r for r in test_requirements if not r.startswith('caproto')]

extras_require = {
    'test': test_requirements,
}

setup(name='ophyd',
      version=versioneer.get_version(),
      cmdclass=versioneer.get_cmdclass(),
      license='BSD',
      install_requires=requirements,
      packages=find_packages(),
      extras_require=extras_require)

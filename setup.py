#!/usr/bin/env python
import os
from setuptools import (setup, find_packages)
import sys
import versioneer

here = os.path.abspath(os.path.dirname(__file__))

# Get the requirements from requirements.txt
with open(os.path.join(here, 'requirements.txt'), 'rt') as f:
    requirements = [r.strip() for r in f.readlines() if not r.startswith('git+')]

with open('test-requirements.txt') as f:
    test_requirements = [r.strip() for r in f.readlines()]

if sys.version_info < (3, 6):
    caproto_warning = """
Python 3.6 or above is required for caproto.
The caproto tests will not be run.
"""
    print('*' * 45)
    print(caproto_warning)
    print('*' * 45)

    # remove caproto from test_requirements
    test_requirements = [r for r in test_requirements if not r.startswith('caproto')]

extras_require = {
    'test': test_requirements,
}

# Get the long description from the README file
with open(os.path.join(here, 'README.md'), 'rt', encoding='utf-8') as f:
    long_description = f.read()

setup(name='ophyd',
      version=versioneer.get_version(),
      cmdclass=versioneer.get_cmdclass(),
      long_description=long_description,
      long_description_content_type='text/markdown',
      license='BSD',
      install_requires=requirements,
      packages=find_packages(),
      extras_require=extras_require,
      classifiers=[
          "Development Status :: 5 - Production/Stable",
          "Programming Language :: Python :: 3.6",
          "Programming Language :: Python :: 3.7",
      ])

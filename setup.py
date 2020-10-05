#!/usr/bin/env python
import os
import sys

from setuptools import find_packages, setup

import versioneer

# NOTE: This file must remain Python 2 compatible for the foreseeable future,
# to ensure that we error out properly for people with outdated setuptools
# and/or pip.
min_version = (3, 6)
if sys.version_info < min_version:
    error = """
ophyd does not support Python {0}.{1}.
Python {2}.{3} and above is required. Check your Python version like so:

python3 --version

This may be due to an out-of-date pip. Make sure you have pip >= 9.0.1.
Upgrade pip like so:

pip install --upgrade pip
""".format(*(sys.version_info[:2] + min_version))
    sys.exit(error)


here = os.path.abspath(os.path.dirname(__file__))

# Get the requirements from requirements.txt
with open(os.path.join(here, 'requirements.txt'), 'rt') as f:
    requirements = f.read().split()

# Get the long description from the README file
with open(os.path.join(here, 'README.md'), 'rt', encoding='utf-8') as f:
    long_description = f.read()

setup(name='ophyd',
      version=versioneer.get_version(),
      cmdclass=versioneer.get_cmdclass(),
      long_description=long_description,
      long_description_content_type='text/markdown',
      license='BSD',
      python_requires='>={}'.format('.'.join(str(n) for n in min_version)),
      install_requires=requirements,
      packages=find_packages(),
      entry_points={
          'databroker.handlers': [
              'NPY_SEQ = ophyd.sim:NumpySeqHandler',
          ]},
      include_package_data=True,
      package_data={
          # NOTE: this is required in addition to MANIFEST.in, as that only
          # applies to source distributions

          # Include our documentation helpers:
          '': ['*.rst'],
      },
      classifiers=[
          "Development Status :: 5 - Production/Stable",
          "Programming Language :: Python :: 3.6",
          "Programming Language :: Python :: 3.7",
      ])

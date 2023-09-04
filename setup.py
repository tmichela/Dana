#!/usr/bin/env python
from pathlib import Path
import re
from setuptools import setup, find_packages


def read(*parts):
    return Path(__file__).parent.joinpath(*parts).read_text()


def find_version(*parts):
    vers_file = read(*parts)
    match = re.search(r'^__version__ = "(\d+\.\d+\.\d+)"', vers_file, re.M)
    if match is not None:
        return match.group(1)
    raise RuntimeError("Unable to find version string.")


setup(
    name="Dana",
    version=find_version("src", "dana", "__init__.py"),
    author="Thomas Michelat",
    author_email="thomas.michelat@gmail.com",
    maintainer="Thomas Michelat",
    url="https://github.com/tmichela/Dana",
    description=("Zulip bot"),
    long_description=read("README.md"),
    license="BSD-3-Clause",
    python_requires='>=3.7',
    install_requires=[
        'apscheduler',
        'holidays',
        'loguru',
        'numpy',
    ],
    package_dir={"": "src"},
    packages=find_packages('src'),
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Console',
        'License :: OSI Approved :: BSD License',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python :: 3',
    ]
)

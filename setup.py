import os

from setuptools import setup, find_packages


with open("requirements.txt") as f:
    required = f.read().splitlines()


setup(
    name="wampapi", version="0.1", packages=["wampapi"], install_requires=["autobahn", "pydantic"]
)

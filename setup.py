#!/usr/bin/env python3
"""Setup for ReconPulse"""
from setuptools import setup, find_packages

with open("README.md", "r") as f:
    long_description = f.read()

setup(
    name="reconpulse",
    version="1.0.0",
    author="tadi",
    description="Automated Bug Bounty Reconnaissance Pipeline",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/itztadi/ReconPulse",
    packages=find_packages(),
    py_modules=["reconpulse"],
    install_requires=["requests", "rich", "click", "pyyaml", "colorama"],
    entry_points={
        "console_scripts": [
            "reconpulse=reconpulse:main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Topic :: Security",
    ],
    python_requires=">=3.8",
)

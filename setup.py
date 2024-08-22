from pathlib import Path

from setuptools import find_packages, setup


def get_long_description() -> str:
    return Path("README.md").read_text(encoding="utf8")


setup(
    name="RoffIO",
    author="Equinor",
    author_email="fg_sib-scout@equinor.com",
    description="A (lazy) parser and writer for the Roxar Open File Format (ROFF).",
    use_scm_version=True,
    url="https://github.com/equinor/roffio",
    long_description=get_long_description(),
    long_description_content_type="text/markdown",
    license="LGPL-3.0",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    install_requires=["dataclasses>=0.6;python_version<'3.7'", "numpy"],
    platforms="any",
    classifiers=[
        "Development Status :: 1 - Planning",
        "License :: OSI Approved :: GNU Lesser General Public License v3 or later (LGPLv3+)",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    setup_requires=["setuptools_scm"],
    include_package_data=True,
)

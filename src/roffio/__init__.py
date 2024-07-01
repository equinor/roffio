import roffio.version
from _roffio.reading import lazy_read, read
from _roffio.writing import Format, write

__author__ = """Equinor"""
__email__ = "fg_sib-scout@equinor.com"

__version__ = roffio.version.version

__all__ = [
    "Format",
    "lazy_read",
    "read",
    "write",
]

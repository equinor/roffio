import pytest

import roffio
from _roffio.exceptions import RoffWriteError


def test_write_disallows_double_quotation_marks(tmpdir):
    contents = {"tagname": [("keyname", '"')]}

    with tmpdir.as_cwd(), pytest.raises(RoffWriteError):
        roffio.write("file.roff", contents, roff_format=roffio.Format.ASCII)


def test_write_allows_single_quotation_marks(tmpdir):
    contents = {"tagname": [("keyname", "'")]}

    with tmpdir.as_cwd():
        roffio.write("file.roff", contents, roff_format=roffio.Format.ASCII)

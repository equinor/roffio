import io
import os

import numpy as np
import pytest
from hypothesis import HealthCheck, example, given, settings

import roffio

from .generators.roff_tag_data import roff_data


def test_write_adds_metadata():
    f = io.BytesIO()
    roffio.write(f, {})
    f.seek(0)
    read_contents = roffio.read(f)

    assert read_contents["version"]["major"] == 2
    assert read_contents["version"]["minor"] == 0
    assert read_contents["filedata"]["byteswaptest"] == 1


def test_overwrite_version_major_errors():
    with pytest.raises(ValueError, match="change roff file version"):
        roffio.write(io.BytesIO(), {"version": {"major": -1}})


def test_overwrite_version_minor_errors():
    with pytest.raises(ValueError, match="change roff file version"):
        roffio.write(io.BytesIO(), {"version": {"minor": -1}})


def test_overwrite_byteswaptest_errors():
    with pytest.raises(ValueError, match="not possible to set the byteswaptest"):
        roffio.write(io.BytesIO(), {"filedata": {"byteswaptest": -1}})


def test_overwrite_filetype():
    f = io.BytesIO()
    roffio.write(f, {"filedata": {"filetype": "surface"}})
    f.seek(0)
    assert roffio.read(f)["filedata"]["filetype"] == "surface"


def test_overwrite_creation_date():
    f = io.BytesIO()
    roffio.write(f, {"filedata": {"creationDate": "today"}})
    f.seek(0)
    assert roffio.read(f)["filedata"]["creationDate"] == "today"


def test_just_one_eof():
    f = io.BytesIO()
    roffio.write(f, {"eof": {}})
    f.seek(0)
    assert roffio.read(f)["eof"] == {}


@given(roff_data)
@example({"filedata": {"filetype": "generic"}, "tag": {"x": 1}})
def test_read_write_is_identity(roff_data):
    f = io.BytesIO()
    roffio.write(f, roff_data)
    f.seek(0)
    read_contents = roffio.read(f)

    read_contents.pop("version")
    read_contents.pop("filedata")
    read_contents.pop("eof")

    roff_data.pop("version", None)
    roff_data.pop("filedata", None)
    roff_data.pop("eof", None)

    assert read_contents == roff_data


@given(roff_data)
def test_binary_write_read_is_ascii_write_read(roff_contents):
    bf = io.BytesIO()
    af = io.StringIO()
    roffio.write(bf, roff_contents, roff_format=roffio.Format.BINARY)
    roffio.write(af, roff_contents, roff_format=roffio.Format.ASCII)
    bf.seek(0)
    af.seek(0)
    read_binary_contents = roffio.read(bf)
    read_ascii_contents = roffio.read(af)

    read_binary_contents.pop("filedata")
    read_ascii_contents.pop("filedata")

    assert read_binary_contents == read_ascii_contents


@pytest.mark.parametrize(
    "roff_format, buffer",
    [(roffio.Format.BINARY, io.BytesIO()), (roffio.Format.ASCII, io.StringIO())],
)
def test_read_write_multitag(roff_format, buffer):
    contents = [
        ("tagname", {"keyname": 1.0}),
        ("tagname", {"keyname": 2.0}),
    ]

    roffio.write(buffer, contents, roff_format=roff_format)

    buffer.seek(0)
    values = roffio.read(buffer)

    assert values["tagname"] == [{"keyname": 1.0}, {"keyname": 2.0}]


@pytest.mark.parametrize(
    "roff_format, buffer",
    [(roffio.Format.BINARY, io.BytesIO()), (roffio.Format.ASCII, io.StringIO())],
)
def test_read_write_multikey(roff_format, buffer):
    contents = {
        "tagname": [
            ("keyname", 1.0),
            ("keyname", 2.0),
        ],
    }

    roffio.write(buffer, contents, roff_format=roff_format)

    buffer.seek(0)
    values = roffio.read(buffer)

    assert values["tagname"] == {"keyname": [1.0, 2.0]}


def test_read_write_warn_cast():
    buff = io.BytesIO()
    contents = {"t": {"a": np.array([1, 2], dtype=np.int64)}}

    with pytest.warns(UserWarning, match="cast"):
        roffio.write(buff, contents)

    buff.seek(0)
    assert np.array_equal(roffio.read(buff)["t"]["a"], np.array([1, 2], dtype=np.int32))


@given(roff_data)
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_read_write_pathlib(tmp_path, roff_data):
    filepath = tmp_path / "data.roff"
    roffio.write(filepath, roff_data)

    read_contents = roffio.read(filepath)

    read_contents.pop("version")
    read_contents.pop("filedata")
    read_contents.pop("eof")

    roff_data.pop("version", None)
    roff_data.pop("filedata", None)
    roff_data.pop("eof", None)

    assert read_contents == roff_data


@given(roff_data)
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_read_write_filestr(tmpdir, roff_data):
    filepath = os.path.join(tmpdir, "data.roff")
    roffio.write(filepath, roff_data)

    read_contents = roffio.read(filepath)

    read_contents.pop("version")
    read_contents.pop("filedata")
    read_contents.pop("eof")

    roff_data.pop("version", None)
    roff_data.pop("filedata", None)
    roff_data.pop("eof", None)

    assert read_contents == roff_data


@pytest.mark.parametrize(
    "roff_format, filelike",
    [(roffio.Format.BINARY, io.BytesIO()), (roffio.Format.ASCII, io.StringIO())],
)
def test_read_write_list(roff_format, filelike):
    data = {"t": {"k": ["a", "b"]}}
    roffio.write(filelike, data, roff_format=roff_format)

    filelike.seek(0)
    read_contents = roffio.read(filelike)

    read_contents.pop("version")
    read_contents.pop("filedata")
    read_contents.pop("eof")

    read_contents["t"]["k"] = list(read_contents["t"]["k"])
    assert read_contents == data

import io

import _roffio.writing as roffwrite
import numpy as np
import pytest


@pytest.mark.parametrize(
    "value, expected",
    [
        (True, "bool"),
        (False, "bool"),
        (1, "int"),
        (1.0, "double"),
        (np.float32(1.0), "float"),
        (np.int8(1), "byte"),
        (np.bool_(1), "bool"),
        (np.array([1.0], dtype=np.float32), "array float"),
        (np.array([1.0], dtype=np.float64), "array double"),
        (np.array([1], dtype=np.int32), "array int"),
        (np.array([1], dtype=np.uint8), "array byte"),
        (b"\x01", "byte"),
        (b"\x01\x02", "array byte"),
    ],
)
def test_tagkey_type_prefix_ascii(value, expected):
    buf = io.StringIO()
    roffwrite.write_ascii_tagkey(buf, "x", value)
    assert buf.getvalue().startswith(expected)


@pytest.mark.parametrize(
    "value, expected",
    [
        (True, b"bool"),
        (False, b"bool"),
        (1, b"int"),
        (1.0, b"double"),
        (np.float32(1.0), b"float"),
        (np.int8(1), b"byte"),
        (np.bool_(1), b"bool"),
        (np.array([1.0], dtype=np.float32), b"array\0float"),
        (np.array([1.0], dtype=np.float64), b"array\0double"),
        (np.array([1], dtype=np.int32), b"array\0int"),
        (np.array([1], dtype=np.uint8), b"array\0byte"),
        (b"\x01", b"byte"),
        (b"\x01\x02", b"array\0byte"),
    ],
)
def test_tagkey_type_prefix_binary(value, expected):
    buf = io.BytesIO()
    roffwrite.write_binary_tagkey(buf, "x", value)
    assert buf.getvalue().startswith(expected)

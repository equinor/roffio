import contextlib
import io

import numpy as np
import pytest
from hypothesis import given

import _roffio.parser as roffparse
from _roffio.tokenizer import RoffTokenizer
from _roffio.tokenizer.binary_roff_body_tokenizer import BinaryRoffBodyTokenizer
from _roffio.tokenizer.text_roff_body_tokenizer import TextRoffBodyTokenizer
from _roffio.tokenizer.token import Token
from _roffio.tokenizer.token_kind import TokenKind

from .generators.roff_file_contents import ascii_file_contents, binary_file_contents


def test_parse_numeric_value_type_error():
    tokens = iter([Token(TokenKind.STRING_LITERAL, 0, 0)])
    stream = io.StringIO()
    parser = roffparse.RoffTagKeyParser(tokens, stream, None)
    with pytest.raises(roffparse.RoffTypeError):
        next(parser.parse_numeric_value(np.int32))


def test_parse_numeric_value_syntax_error():
    tokens = iter([Token(TokenKind.NUMERIC_VALUE, 0, 0)])
    stream = io.StringIO("ERR")
    parser = roffparse.RoffTagKeyParser(tokens, stream, None)
    with pytest.raises(roffparse.RoffSyntaxError):
        next(parser.parse_numeric_value(np.int32))


@pytest.mark.parametrize(
    "valuestr, valuetype, expected",
    [
        ("1.0", np.float32, 1.0),
        ("1.0E+4", np.float32, 10000.0),
        ("-1", np.int32, -1),
        ("20", int, 20),
        ("1", bool, True),
        ("1", np.int8, 1),
    ],
)
def test_parse_numeric_ascii_value(valuestr, valuetype, expected):
    tokens = iter([Token(TokenKind.NUMERIC_VALUE, 0, len(valuestr))])
    stream = io.StringIO(valuestr)
    parser = roffparse.RoffTagKeyParser(tokens, stream, None)
    assert next(parser.parse_numeric_value(valuetype)) == expected


@pytest.mark.parametrize(
    "dtype, bytevalue, expected",
    [
        (np.int32, b"\x01\x00\x00\x00", 1),
        (np.dtype(np.int32).newbyteorder(">"), b"\x00\x00\x00\x01", 1),
        (np.float32, b"\x00" * 4, 0.0),
        (np.float64, b"\x00" * 8, 0.0),
        (np.int8, b"\x01", 1),
        (np.bool_, b"\x01", True),
        (np.bool_, b"\x00", False),
    ],
)
def test_parse_numeric_binary_value(dtype, bytevalue, expected):
    tokens = iter([Token(TokenKind.BINARY_NUMERIC_VALUE, 0, len(bytevalue))])
    stream = io.BytesIO(bytevalue)
    parser = roffparse.RoffTagKeyParser(tokens, stream, None)
    assert next(parser.parse_numeric_value(dtype)) == expected


def test_parse_binary_string_Literal():
    tokens = iter([Token(TokenKind.STRING_LITERAL, 0, 5)])
    stream = io.BytesIO(b"hello\0")
    parser = roffparse.RoffTagKeyParser(tokens, stream, None)
    assert next(parser.parse_string_literal()) == "hello"


def test_parse_ascii_string_literal():
    tokens = iter([Token(TokenKind.STRING_LITERAL, 1, 6)])
    stream = io.StringIO('"hello"')
    parser = roffparse.RoffTagKeyParser(tokens, stream, None)
    assert next(parser.parse_string_literal()) == "hello"


def test_parse_one_of():
    assert (
        next(
            roffparse.parse_one_of(TokenKind.TAG)(
                iter([Token(TokenKind.TAG, 0, 3)]),
            )
        )
        == TokenKind.TAG
    )
    with pytest.raises(roffparse.RoffSyntaxError):
        next(
            roffparse.parse_one_of(
                TokenKind.INT,
            )(iter([Token(TokenKind.TAG, 0, 3)]))
        )


@pytest.mark.parametrize(
    "typestr, expected",
    [(TokenKind.keywords()[st], st) for st in TokenKind.simple_types()],
)
def test_parse_simple_type(typestr, expected):
    stream = io.StringIO(typestr)
    tokenizer = TextRoffBodyTokenizer(stream)
    assert (
        next(roffparse.parse_simple_type(tokenizer.tokenize_keyword[expected]()))
        == expected
    )


@pytest.mark.parametrize(
    "inp_str, expected",
    [
        ("int x 3", ("x", 3)),
        ("float var 1.0", ("var", 1.0)),
        ("bool flag 1", ("flag", True)),
        ('char str "hello world"', ("str", "hello world")),
    ],
)
def test_parse_simple_tagkey(inp_str, expected):
    stream = io.StringIO(inp_str)
    tokenizer = TextRoffBodyTokenizer(stream)
    tokens = tokenizer.tokenize_simple_tagkey()
    parser = roffparse.RoffParser(tokens, stream)
    tagkey_parser = roffparse.RoffTagKeyParser(tokens, stream, parser)
    assert next(tagkey_parser.parse_tagkey()) == expected


@pytest.mark.parametrize(
    "inp_str, expected",
    [
        ("array int x 1 3", ("x", np.array([3]))),
        ("array float var 4 1.0 2.0 3.0 4.0", ("var", np.array([1.0, 2.0, 3.0, 4.0]))),
        ("array bool flag 1 1", ("flag", np.array([True]))),
        ('array char str 1 "hello world"', ("str", np.array(["hello world"]))),
    ],
)
def test_parse_array_tagkey(inp_str, expected):
    stream = io.StringIO(inp_str)
    tokenizer = TextRoffBodyTokenizer(stream)
    tokens = tokenizer.tokenize_array_tagkey()
    parser = roffparse.RoffParser(tokens, stream)
    tagkey_parser = roffparse.RoffTagKeyParser(tokens, stream, parser)
    varname, array = next(tagkey_parser.parse_tagkey())

    assert expected[0] == varname
    assert np.array_equal(expected[1], array)


@given(ascii_file_contents())
def test_parse_ascii_file(ascii_str):
    stream = io.StringIO(ascii_str)
    tokens = iter(RoffTokenizer(stream))
    parser = roffparse.RoffParser(tokens, stream)
    with contextlib.suppress(roffparse.RoffTypeError):
        {t: dict(tags) for t, tags in iter(parser)}


@given(binary_file_contents())
def test_parse_binary_file(binary_str):
    stream = io.BytesIO(binary_str)
    tokens = iter(RoffTokenizer(stream, endianess="little"))
    parser = roffparse.RoffParser(tokens, stream)
    with contextlib.suppress(roffparse.RoffTypeError):
        {t: dict(tags) for t, tags in iter(parser)}


@pytest.mark.parametrize(
    "input_str, expected, expected_type",
    [
        ("int x 3", ("x", 3), np.int32),
        ("float x 3.0", ("x", 3.0), np.float32),
        ("double x 3.0", ("x", 3.0), np.float64),
        ("byte x 1", ("x", b"\x01"), bytes),
        ("bool x 1", ("x", True), bool),
    ],
)
def test_parse_tagkey_ascii_types(input_str, expected, expected_type):
    stream = io.StringIO(input_str)
    tokenizer = TextRoffBodyTokenizer(stream)
    tokens = tokenizer.tokenize_tagkey()
    parser = roffparse.RoffTagKeyParser(
        tokens, stream, roffparse.RoffParser(stream, tokens)
    )
    val = next(iter(parser))
    assert val == expected
    assert isinstance(val[1], expected_type)


@pytest.mark.parametrize(
    "input_str, expected, expected_type",
    [
        (b"int\0x\0\x03\x00\x00\x00", ("x", 3), np.int32),
        (b"float\0x\0\x00\x00\x00\x00", ("x", 0.0), np.float32),
        (b"double\0x\0" + b"\x00" * 8, ("x", 0.0), np.float64),
        (b"byte\0x\0\x01", ("x", b"\x01"), bytes),
        (b"bool\0x\0\x01", ("x", True), bool),
    ],
)
def test_parse_tagkey_binary_types(input_str, expected, expected_type):
    stream = io.BytesIO(input_str)
    tokenizer = BinaryRoffBodyTokenizer(stream)
    tokens = tokenizer.tokenize_simple_tagkey()
    parser = roffparse.RoffParser(tokens, stream)
    parser.is_binary_file = True
    parser = roffparse.RoffTagKeyParser(tokens, stream, parser)
    val = next(iter(parser))
    assert val == expected
    assert isinstance(val[1], expected_type)


@pytest.mark.parametrize(
    "input_str, expected",
    [
        (
            b"array\0int\0x\0\x01\x00\x00\x00\x03\x00\x00\x00",
            ("x", np.array([3], dtype=np.int32)),
        ),
        (
            b"array\0float\0x\0\x01\x00\x00\x00\x00\x00\x00\x00",
            ("x", np.array([0.0], dtype=np.float32)),
        ),
        (
            b"array\0double\0x\0\x01\x00\x00\x00" + b"\x00" * 8,
            ("x", np.array([0.0], dtype=np.float64)),
        ),
        (b"array\0byte\0x\0\x02\x00\x00\x00\x01\x02", ("x", b"\x01\x02")),
        (
            b"array\0bool\0x\0\x01\x00\x00\x00\x01",
            ("x", np.array([True], dtype=np.bool_)),
        ),
    ],
)
def test_parse_tagkey_binary_array_types(input_str, expected):
    stream = io.BytesIO(input_str)
    tokens = BinaryRoffBodyTokenizer(stream).tokenize_array_tagkey()
    parser = roffparse.RoffParser(tokens, stream)
    parser.is_binary_file = True
    parser = roffparse.RoffTagKeyParser(tokens, stream, parser)
    val = next(iter(parser))
    assert val[0] == expected[0]
    assert np.array_equal(val[1], expected[1])


@pytest.mark.parametrize(
    "input_str, expected",
    [
        ("array int x 1 3", ("x", np.array([3], dtype=np.int32))),
        ("array float x 1 0.0", ("x", np.array([0.0], dtype=np.float32))),
        ("array double x 1 0.0", ("x", np.array([0.0], dtype=np.float64))),
        ("array byte x 2 1 2", ("x", b"\x01\x02")),
        ("array bool x 1 1", ("x", np.array([True], dtype=np.bool_))),
    ],
)
def test_parse_tagkey_ascii_array_types(input_str, expected):
    stream = io.StringIO(input_str)
    tokenizer = TextRoffBodyTokenizer(stream)
    tokens = tokenizer.tokenize_array_tagkey()
    parser = roffparse.RoffParser(tokens, stream)
    parser.is_binary_file = False
    parser = roffparse.RoffTagKeyParser(tokens, stream, parser)
    val = next(iter(parser))
    assert val[0] == expected[0]
    assert np.array_equal(val[1], expected[1])


def test_parse_boolean_values_typing():
    stream = io.StringIO("bool x 2")
    tokenizer = TextRoffBodyTokenizer(stream)
    tokens = tokenizer.tokenize_simple_tagkey()
    parser = roffparse.RoffParser(tokens, stream)
    parser.is_binary_file = False

    parser = roffparse.RoffTagKeyParser(tokens, stream, parser)
    with pytest.raises(roffparse.RoffTypeError, match="must be either 1 or 0"):
        next(iter(parser))


def test_parse_boolean_values():
    stream = io.StringIO("bool x 1")
    tokenizer = TextRoffBodyTokenizer(stream)
    tokens = tokenizer.tokenize_simple_tagkey()
    parser = roffparse.RoffParser(tokens, stream)
    parser.is_binary_file = False

    parser = roffparse.RoffTagKeyParser(tokens, stream, parser)
    assert next(iter(parser)) == ("x", True)


def test_parse_byten_values():
    stream = io.StringIO("byte x 1")
    tokenizer = TextRoffBodyTokenizer(stream)
    tokens = tokenizer.tokenize_simple_tagkey()
    parser = roffparse.RoffParser(tokens, stream)
    parser.is_binary_file = False

    parser = roffparse.RoffTagKeyParser(tokens, stream, parser)
    assert next(iter(parser)) == ("x", b"\x01")


def test_parse_byte_array_values():
    stream = io.StringIO("array byte x 2 255 0")
    tokenizer = TextRoffBodyTokenizer(stream)
    tokens = tokenizer.tokenize_array_tagkey()
    parser = roffparse.RoffParser(tokens, stream)
    parser.is_binary_file = False

    parser = roffparse.RoffTagKeyParser(tokens, stream, parser)
    assert next(iter(parser)) == ("x", b"\xff\x00")


def test_endianess_swap():
    stream = io.BytesIO(
        b"roff-bin\0tag\0t\0int\0x\0\x01\0\0\0int\0y\0\0\0\0\xffendtag\0"
    )
    tokenizer = RoffTokenizer(stream)
    parser = roffparse.RoffParser(iter(tokenizer), stream)
    tag = next(iter(parser))
    assert tag[0] == "t"
    assert next(tag[1]) == ("x", 1)
    assert tokenizer.endianess == "little"
    assert parser.endianess == "little"
    tokenizer.swap_endianess()
    parser.swap_endianess()
    assert tokenizer.endianess == "big"
    assert parser.endianess == "big"
    assert tag[0] == "t"
    assert next(tag[1]) == ("y", 255)

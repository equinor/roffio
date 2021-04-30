import io

import numpy as np
import pytest
from hypothesis import given

import _roffio.parser as roffparse
import _roffio.tokenizer as rofftok

from .generators.roff_file_contents import (
    ascii_file_contents,
    binary_file_contents,
    whitespace,
)


def test_parse_numeric_value_type_error():
    tokens = iter([rofftok.Token(rofftok.TokenKind.STRING_LITERAL, 0, 0)])
    stream = io.StringIO()
    parser = roffparse.RoffTagKeyParser(tokens, stream, None)
    with pytest.raises(roffparse.RoffTypeError):
        next(parser.parse_numeric_value(np.int32))


def test_parse_numeric_value_syntax_error():
    tokens = iter([rofftok.Token(rofftok.TokenKind.NUMERIC_VALUE, 0, 0)])
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
    tokens = iter([rofftok.Token(rofftok.TokenKind.NUMERIC_VALUE, 0, len(valuestr))])
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
    tokens = iter(
        [rofftok.Token(rofftok.TokenKind.BINARY_NUMERIC_VALUE, 0, len(bytevalue))]
    )
    stream = io.BytesIO(bytevalue)
    parser = roffparse.RoffTagKeyParser(tokens, stream, None)
    assert next(parser.parse_numeric_value(dtype)) == expected


def test_parse_binary_string_Literal():
    tokens = iter([rofftok.Token(rofftok.TokenKind.STRING_LITERAL, 0, 5)])
    stream = io.BytesIO(b"hello\0")
    parser = roffparse.RoffTagKeyParser(tokens, stream, None)
    assert next(parser.parse_string_literal()) == "hello"


def test_parse_ascii_string_literal():
    tokens = iter([rofftok.Token(rofftok.TokenKind.STRING_LITERAL, 1, 6)])
    stream = io.StringIO('"hello"')
    parser = roffparse.RoffTagKeyParser(tokens, stream, None)
    assert next(parser.parse_string_literal()) == "hello"


def test_parse_one_of():
    assert (
        next(
            roffparse.parse_one_of(rofftok.TokenKind.TAG)(
                iter([rofftok.Token(rofftok.TokenKind.TAG, 0, 3)]),
            )
        )
        == rofftok.TokenKind.TAG
    )
    with pytest.raises(roffparse.RoffSyntaxError):
        next(
            roffparse.parse_one_of(
                rofftok.TokenKind.INT,
            )(iter([rofftok.Token(rofftok.TokenKind.TAG, 0, 3)]))
        )


@pytest.mark.parametrize(
    "typestr, expected",
    [(rofftok.TokenKind.keywords()[st], st) for st in rofftok.TokenKind.simple_types()],
)
def test_parse_simple_type(typestr, expected):
    assert (
        next(
            roffparse.parse_simple_type(
                rofftok.tokenize_keyword[expected](io.StringIO(typestr))
            )
        )
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
    tokens = rofftok.tokenize_simple_ascii_tagkey(stream)
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
    tokens = rofftok.tokenize_ascii_array_tagkey(stream)
    parser = roffparse.RoffParser(tokens, stream)
    tagkey_parser = roffparse.RoffTagKeyParser(tokens, stream, parser)
    varname, array = next(tagkey_parser.parse_tagkey())

    assert expected[0] == varname
    assert np.array_equal(expected[1], array)


@given(ascii_file_contents())
def test_tokenize_ascii_file(ascii_str):
    stream = io.StringIO(ascii_str)
    tokens = iter(rofftok.RoffTokenizer(stream))
    parser = roffparse.RoffParser(tokens, stream)
    try:
        {t: {tk: v for tk, v in tags} for t, tags in iter(parser)}
    except roffparse.RoffTypeError:
        pass


@given(binary_file_contents())
def test_tokenize_binary_file(binary_str):
    stream = io.BytesIO(binary_str)
    tokens = iter(rofftok.RoffTokenizer(stream, endianess="little"))
    parser = roffparse.RoffParser(tokens, stream)
    try:
        {t: {tk: v for tk, v in tags} for t, tags in iter(parser)}
    except roffparse.RoffTypeError:
        pass

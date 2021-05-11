import io

import pytest
from hypothesis import given

import _roffio.tokenizer as rofftok
from _roffio.parser import as_ascii
from _roffio.tokenizer.binary_roff_body_tokenizer import (
    BinaryRoffBodyTokenizer,
    tokenlen,
)
from _roffio.tokenizer.combinators import bind, repeated
from _roffio.tokenizer.errors import TokenizationError
from _roffio.tokenizer.token_kind import TokenKind

from .generators.roff_file_contents import binary_file_contents

test_comment = "# A comment #"


@pytest.fixture(
    params=[
        lambda x: x + test_comment.encode("ascii") + b"\0",
        lambda x: test_comment.encode("ascii") + b"\0" + x,
        lambda x: x,
    ]
)
def pad_with_binary_comment(request):
    return request.param


@pytest.fixture
def roff_binary_body_tokenizer(pad_with_binary_comment):
    def make_body_tokenizer(contents):
        contents = pad_with_binary_comment(contents)
        stream = io.BytesIO(contents)
        return BinaryRoffBodyTokenizer(stream)

    return make_body_tokenizer


@pytest.mark.parametrize(
    "expected_kind, token_word",
    TokenKind.keywords().items(),
)
def test_tokenize_binary_keywords(
    roff_binary_body_tokenizer, token_word, expected_kind
):
    tokenizer = roff_binary_body_tokenizer(token_word.encode("ascii") + b"\0")
    tok = next(tokenizer.tokenize_keyword[expected_kind]())
    assert tok.kind == expected_kind
    assert as_ascii(tok.get_value(tokenizer.stream)) == token_word


def test_tokenize_binary_string(roff_binary_body_tokenizer):
    tokenizer = roff_binary_body_tokenizer(b"Aroffstring\0")
    token = next(
        bind(
            repeated(tokenizer.tokenize_comment),
            tokenizer.tokenize_string(TokenKind.STRING_LITERAL),
        )()
    )
    assert token.kind == TokenKind.STRING_LITERAL
    assert token.get_value(tokenizer.stream) == b"Aroffstring"


def test_tokenlen_raises():
    with pytest.raises(TokenizationError, match="non-fixed"):
        tokenlen(TokenKind.CHAR)


def test_take_one_binary_delimiter():
    stream = io.BytesIO(b"\0a")
    tokenizer = BinaryRoffBodyTokenizer(stream)
    tokenizer.tokenize_delimiter()
    with pytest.raises(TokenizationError):
        tokenizer.tokenize_delimiter()
    assert stream.read(1) == b"a"


def test_tokenize_binary_numeric_value():
    value_string = b"\x01\x00\x00\x00"
    tokenizer = BinaryRoffBodyTokenizer(io.BytesIO(value_string))
    token = next(tokenizer.tokenize_numeric_value(TokenKind.INT)())
    assert token.kind == TokenKind.BINARY_NUMERIC_VALUE
    assert token.get_value(tokenizer.stream) == value_string


def test_tokenize_comment():
    comment_buffer = io.BytesIO(b"#a comment#\x001")

    tokenizer = BinaryRoffBodyTokenizer(comment_buffer)

    with pytest.raises(StopIteration):
        next(tokenizer.tokenize_comment())

    assert comment_buffer.read(1) == b"1"


def test_drop_comment_eof():
    comment_buffer = io.BytesIO(b"#a comment")

    tokenizer = BinaryRoffBodyTokenizer(comment_buffer)

    with pytest.raises(TokenizationError, match="Reached end of stream"):
        next(tokenizer.tokenize_comment())


@pytest.mark.parametrize(
    "varname, typename, typekind, value, valuekind",
    [
        ("x", "int", TokenKind.INT, b"\x03" * 4, TokenKind.BINARY_NUMERIC_VALUE),
        ("str", "char", TokenKind.CHAR, b"a string\0", TokenKind.STRING_LITERAL),
        ("foo", "float", TokenKind.FLOAT, b"\x00" * 4, TokenKind.BINARY_NUMERIC_VALUE),
        ("str", "char", TokenKind.CHAR, b"\x00", TokenKind.STRING_LITERAL),
    ],
)
def test_tokenize_simple_binary_tagkey(
    roff_binary_body_tokenizer, varname, typename, typekind, value, valuekind
):
    tokenizer = roff_binary_body_tokenizer(
        f"{typename}\0{varname}\0".encode("ascii") + value
    )
    tokens = list(tokenizer.tokenize_simple_tagkey())

    assert tokens[0].kind == typekind
    assert tokens[1].kind == TokenKind.NAME
    assert tokens[2].kind == valuekind

    read_var_name = tokens[1].get_value(tokenizer.stream)

    assert read_var_name.decode("ascii") == varname


@pytest.mark.parametrize(
    "varname, typename, typekind, values, valuekind",
    [
        ("x", "int", TokenKind.INT, b"\0" * 12, TokenKind.ARRAYBLOB),
        ("foo", "float", TokenKind.FLOAT, b"\0" * 12, TokenKind.ARRAYBLOB),
        ("str", "char", TokenKind.CHAR, b"a\0b\0c\0", TokenKind.STRING_LITERAL),
        ("str", "char", TokenKind.CHAR, b"a string\0b\0c\0", TokenKind.STRING_LITERAL),
    ],
)
def test_tokenize_binary_array_tagkey(
    roff_binary_body_tokenizer, varname, typename, typekind, values, valuekind
):
    tokenizer = roff_binary_body_tokenizer(
        f"array\0{typename}\0{varname}\0".encode("ascii") + b"\x03\0\0\0" + values
    )
    tokens = list(tokenizer.tokenize_array_tagkey())

    assert tokens[0].kind == TokenKind.ARRAY
    assert tokens[1].kind == typekind
    assert tokens[2].kind == TokenKind.NAME
    assert tokens[3].kind == TokenKind.BINARY_NUMERIC_VALUE
    all(t.kind == valuekind for t in tokens[3:])

    read_var_name = tokens[2].get_value(tokenizer.stream)

    assert read_var_name.decode("ascii") == varname


def test_tokenize_tag_group(roff_binary_body_tokenizer):
    tokenizer = roff_binary_body_tokenizer(
        b"tag\0"
        b"# A tag comment #\0"
        b"tag_name\0"
        b"int\0x\0\x03\0\0\0"
        b"char\0str\0a string\0"
        b"float\0y\0\0\0\0\0"
        b"endtag\0"
    )
    tokens = list(tokenizer.tokenize_tag_group())

    assert [t.kind for t in tokens] == [
        TokenKind.TAG,
        TokenKind.NAME,
        TokenKind.INT,
        TokenKind.NAME,
        TokenKind.BINARY_NUMERIC_VALUE,
        TokenKind.CHAR,
        TokenKind.NAME,
        TokenKind.STRING_LITERAL,
        TokenKind.FLOAT,
        TokenKind.NAME,
        TokenKind.BINARY_NUMERIC_VALUE,
        TokenKind.ENDTAG,
    ]

    assert tokens[1].get_value(tokenizer.stream) == b"tag_name"
    assert tokens[3].get_value(tokenizer.stream) == b"x"
    assert tokens[4].get_value(tokenizer.stream) == b"\x03\0\0\0"
    assert tokens[6].get_value(tokenizer.stream) == b"str"
    assert tokens[7].get_value(tokenizer.stream) == b"a string"
    assert tokens[9].get_value(tokenizer.stream) == b"y"
    assert tokens[10].get_value(tokenizer.stream) == b"\0\0\0\0"


@given(binary_file_contents())
def test_tokenize_binary_file(binary_str):
    buff = io.BytesIO(binary_str)
    tokenizer = rofftok.RoffTokenizer(buff)
    for t in tokenizer:
        if t.kind in TokenKind.keywords():
            assert as_ascii(t.get_value(buff)) == TokenKind.keywords()[t.kind]

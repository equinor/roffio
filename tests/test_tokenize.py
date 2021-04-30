import io

import hypothesis.strategies as st
import pytest
from hypothesis import given

import _roffio.tokenizer as rofftok
from _roffio.parser import as_ascii
from _roffio.tokenizer import TokenKind

from .generators.roff_file_contents import (
    ascii_file_contents,
    binary_file_contents,
    whitespace,
)


@pytest.fixture(params=[lambda x: x + " ", lambda x: " " + x, lambda x: x])
def pad_with_space(request):
    return request.param


test_comment = "# A comment #"


@pytest.fixture(
    params=[lambda x: x + test_comment, lambda x: test_comment + x, lambda x: x]
)
def pad_with_ascii_comment(request):
    return request.param


@pytest.fixture(params=["strings", "bytes"])
def roff_ascii_buffer(request, pad_with_space, pad_with_ascii_comment):
    def make_char_stream(contents):
        contents = pad_with_space(pad_with_ascii_comment(contents))
        return io.StringIO(contents)

    def make_byte_stream(contents):
        contents = pad_with_space(pad_with_ascii_comment(contents))
        return io.BytesIO(contents.encode("ascii"))

    if request.param == "strings":
        return make_char_stream

    if request.param == "bytes":
        return make_byte_stream


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
def roff_binary_buffer(pad_with_binary_comment):
    def make_byte_stream(contents):
        contents = pad_with_binary_comment(contents.encode("ascii"))
        return io.BytesIO(contents)

    return make_byte_stream


@pytest.mark.parametrize(
    "token, tokenizer, expected_kind",
    [
        (kw, rofftok.tokenize_keyword[kw_kind], kw_kind)
        for kw_kind, kw in TokenKind.keywords().items()
    ],
)
def test_tokenize_ascii_keywords(roff_ascii_buffer, token, tokenizer, expected_kind):
    buf = roff_ascii_buffer(token)
    tok = next(rofftok.ascii_delimited(tokenizer)(buf))
    assert tok.kind == expected_kind
    assert as_ascii(tok.get_value(buf)) == token


@pytest.mark.parametrize(
    "token, tokenizer, expected_kind",
    [
        (kw, rofftok.tokenize_keyword[kw_kind], kw_kind)
        for kw_kind, kw in TokenKind.keywords().items()
    ],
)
def test_tokenize_binary_keywords(roff_binary_buffer, token, tokenizer, expected_kind):
    buf = roff_binary_buffer(token)
    tok = next(rofftok.binary_delimited(tokenizer)(buf))
    assert tok.kind == expected_kind
    assert as_ascii(tok.get_value(buf)) == token


def test_tokenize_ascii_string(roff_ascii_buffer):
    buf = roff_ascii_buffer('"A string"')
    token = next(
        rofftok.ascii_delimited(rofftok.tokenize_ascii_string_literal)(
            roff_ascii_buffer('"A string"')
        )
    )
    assert token.kind == TokenKind.STRING_LITERAL
    assert as_ascii(token.get_value(buf)) == "A string"


@pytest.mark.parametrize("value_string", ["321", "1", "1.0", "1.0E+1", "-1.0"])
def test_tokenize_ascii_numeric_value(roff_ascii_buffer, value_string):
    buf = roff_ascii_buffer(value_string)
    token = next(rofftok.ascii_delimited(rofftok.tokenize_ascii_numeric_value)(buf))
    assert token.kind == TokenKind.NUMERIC_VALUE
    assert as_ascii(token.get_value(buf)) == value_string


def test_one_of_combinator():
    float_value = io.StringIO("123.0")
    string_literal = io.StringIO('"A string"')
    name = io.StringIO("variable")

    test_tokenizer = rofftok.one_of(
        rofftok.tokenize_ascii_numeric_value,
        rofftok.tokenize_ascii_string_literal,
    )

    assert next(test_tokenizer(float_value)).kind == TokenKind.NUMERIC_VALUE
    assert next(test_tokenizer(string_literal)).kind == TokenKind.STRING_LITERAL
    with pytest.raises(rofftok.TokenizationError):
        next(test_tokenizer(name))


def test_repeated_combinator():
    float_values = io.StringIO("123.0 " * 6)

    test_tokenizer = rofftok.repeated(
        rofftok.ascii_delimited(rofftok.tokenize_ascii_numeric_value)
    )

    tokens = list(test_tokenizer(float_values))
    assert len(tokens) == 6
    assert all(t.kind == TokenKind.NUMERIC_VALUE for t in tokens)


def test_tokenlen_raises():
    with pytest.raises(rofftok.TokenizationError, match="non-fixed"):
        rofftok.tokenlen(TokenKind.CHAR)


@given(
    st.characters(blacklist_categories=("C", "Z")),
    whitespace,
)
def test_dropwhile_space(character, whitespace):
    starts_with_space = io.StringIO(whitespace + character)

    did_drop = rofftok.drop_while_space(starts_with_space)

    assert did_drop == (len(whitespace) > 0)

    assert starts_with_space.read(1) == character


def test_drop_comment():
    comment_buffer = io.StringIO("#a comment#1")

    assert rofftok.drop_comment(comment_buffer)
    assert comment_buffer.read(1) == "1"


def test_drop_comment_eof():
    comment_buffer = io.StringIO("#a comment")

    with pytest.raises(rofftok.TokenizationError, match="Reached end of stream"):
        rofftok.drop_comment(comment_buffer)


def test_tokenize_empty_name():
    name_buffer = io.StringIO("  ")
    with pytest.raises(rofftok.TokenizationError, match="could not tokenize name"):
        next(rofftok.ascii_delimited(rofftok.tokenize_name)(name_buffer))


def test_take_one_binary_delimiter():
    stream = io.BytesIO(b"\0a")
    rofftok.take_one_binary_delimiter(stream)
    with pytest.raises(rofftok.TokenizationError):
        rofftok.take_one_binary_delimiter(stream)
    assert stream.read(1) == b"a"


def test_drop_til_next_ascii_token():
    comment_buffer = io.StringIO(" #a comment# #another comment#1")

    rofftok.drop_til_next_ascii_token(comment_buffer)
    assert comment_buffer.read(1) == "1"


def test_drop_til_next_binary_token():
    comment_buffer = io.BytesIO(b"#a comment#\0#another comment#\x001")

    rofftok.drop_til_next_binary_token(comment_buffer)
    assert comment_buffer.read(1) == b"1"


def test_tokenize_word():
    word_buffer = io.StringIO("foobar")
    token = next(rofftok.tokenize_word("foo", 1)(word_buffer))
    assert token.kind == 1
    with pytest.raises(rofftok.TokenizationError):
        next(rofftok.tokenize_word("baz", 1)(word_buffer))

    assert word_buffer.read(1) == "b"


@pytest.mark.parametrize(
    "varname, typename, typekind, value, valuekind",
    [
        ("x", "int", TokenKind.INT, 3, TokenKind.NUMERIC_VALUE),
        ("str", "char", TokenKind.CHAR, '"a string"', TokenKind.STRING_LITERAL),
        ("foo", "float", TokenKind.FLOAT, 10.0, TokenKind.NUMERIC_VALUE),
        ("str", "char", TokenKind.CHAR, 10.0, TokenKind.NUMERIC_VALUE),
    ],
)
def test_tokenize_simple_ascii_tagkey(
    roff_ascii_buffer, varname, typename, typekind, value, valuekind
):
    tagkey_buffer = roff_ascii_buffer(f"{typename} {varname} {value}")
    tokens = list(rofftok.tokenize_simple_ascii_tagkey(tagkey_buffer))

    assert tokens[0].kind == typekind
    assert tokens[1].kind == TokenKind.NAME
    assert tokens[2].kind == valuekind

    read_var_name = tokens[1].get_value(tagkey_buffer)

    assert as_ascii(read_var_name) == varname


@pytest.mark.parametrize(
    "varname, typename, typekind, values, valuekind",
    [
        ("x", "int", TokenKind.INT, "1 2 3", TokenKind.NUMERIC_VALUE),
        ("str", "char", TokenKind.CHAR, "1 2 3", TokenKind.NUMERIC_VALUE),
        ("foo", "float", TokenKind.FLOAT, "1 2 3", TokenKind.NUMERIC_VALUE),
        ("str", "char", TokenKind.CHAR, "1 2 3", TokenKind.NUMERIC_VALUE),
        ("x", "int", TokenKind.INT, '"a" "b"', TokenKind.STRING_LITERAL),
        ("str", "char", TokenKind.CHAR, '"a" "b" "c"', TokenKind.STRING_LITERAL),
        ("foo", "float", TokenKind.FLOAT, '"a"', TokenKind.STRING_LITERAL),
        ("str", "char", TokenKind.CHAR, '"a string" "b"', TokenKind.STRING_LITERAL),
    ],
)
def test_tokenize_array_ascii_tagkey(
    roff_ascii_buffer, varname, typename, typekind, values, valuekind
):
    tagkey_buffer = roff_ascii_buffer(f"array {typename} {varname} 3 {values}")
    tokens = list(rofftok.tokenize_ascii_array_tagkey(tagkey_buffer))

    assert tokens[0].kind == TokenKind.ARRAY
    assert tokens[1].kind == typekind
    assert tokens[2].kind == TokenKind.NAME
    assert tokens[3].kind == TokenKind.NUMERIC_VALUE
    all(t.kind == valuekind for t in tokens[3:])

    read_var_name = tokens[2].get_value(tagkey_buffer)

    assert as_ascii(read_var_name) == varname


def test_tokenize_tag_group(roff_ascii_buffer):
    tag_group_buffer = roff_ascii_buffer(
        "tag\n"
        "# A tag comment #\n"
        "tag_name\n"
        "int x 3\n"
        'char str "a string"\n'
        "float y 4.0\n"
        "endtag\n"
    )
    tokens = list(rofftok.tokenize_ascii_tag_group(tag_group_buffer))

    assert [t.kind for t in tokens] == [
        TokenKind.TAG,
        TokenKind.NAME,
        TokenKind.INT,
        TokenKind.NAME,
        TokenKind.NUMERIC_VALUE,
        TokenKind.CHAR,
        TokenKind.NAME,
        TokenKind.STRING_LITERAL,
        TokenKind.FLOAT,
        TokenKind.NAME,
        TokenKind.NUMERIC_VALUE,
        TokenKind.ENDTAG,
    ]

    assert as_ascii(tokens[1].get_value(tag_group_buffer)) == "tag_name"
    assert as_ascii(tokens[3].get_value(tag_group_buffer)) == "x"
    assert as_ascii(tokens[4].get_value(tag_group_buffer)) == "3"
    assert as_ascii(tokens[6].get_value(tag_group_buffer)) == "str"
    assert as_ascii(tokens[7].get_value(tag_group_buffer)) == "a string"
    assert as_ascii(tokens[9].get_value(tag_group_buffer)) == "y"
    assert as_ascii(tokens[10].get_value(tag_group_buffer)) == "4.0"


def test_tokenize_binary_string(roff_binary_buffer):
    string_stream = roff_binary_buffer("A roff string\0")
    token = next(
        rofftok.binary_delimited(
            rofftok.tokenize_binary_string(TokenKind.STRING_LITERAL)
        )(string_stream)
    )
    assert token.kind == TokenKind.STRING_LITERAL
    assert token.get_value(string_stream) == b"A roff string"


@given(ascii_file_contents())
def test_tokenize_ascii_file(ascii_str):
    buff = io.StringIO(ascii_str)
    tokenizer = rofftok.RoffTokenizer(buff)
    for t in tokenizer:
        if t.kind in TokenKind.keywords():
            assert t.get_value(buff) == TokenKind.keywords()[t.kind]


@given(binary_file_contents())
def test_tokenize_binary_file(binary_str):
    buff = io.BytesIO(binary_str)
    tokenizer = rofftok.RoffTokenizer(buff, endianess="little")
    for t in tokenizer:
        if t.kind in TokenKind.keywords():
            assert as_ascii(t.get_value(buff)) == TokenKind.keywords()[t.kind]

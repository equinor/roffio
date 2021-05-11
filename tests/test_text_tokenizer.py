import io

import hypothesis.strategies as st
import pytest
from hypothesis import given

from _roffio.tokenizer import RoffTokenizer
from _roffio.tokenizer.errors import TokenizationError
from _roffio.tokenizer.text_roff_body_tokenizer import TextRoffBodyTokenizer
from _roffio.tokenizer.token_kind import TokenKind

from .generators.roff_file_contents import ascii_file_contents, whitespace


@pytest.fixture(params=[lambda x: x + " ", lambda x: " " + x, lambda x: x])
def pad_with_space(request):
    return request.param


test_comment = "# A comment #"


@pytest.fixture(
    params=[lambda x: x + test_comment, lambda x: test_comment + x, lambda x: x]
)
def pad_with_ascii_comment(request):
    return request.param


@pytest.fixture
def roff_text_body_tokenizer(pad_with_space, pad_with_ascii_comment):
    def make_body_tokenizer(contents):
        contents = pad_with_space(pad_with_ascii_comment(contents))
        stream = io.StringIO(contents)
        return TextRoffBodyTokenizer(stream)

    return make_body_tokenizer


@pytest.mark.parametrize(
    "expected_kind, token_word",
    TokenKind.keywords().items(),
)
def test_tokenize_ascii_keywords(roff_text_body_tokenizer, token_word, expected_kind):
    tokenizer = roff_text_body_tokenizer(token_word)
    tok = next(tokenizer.tokenize_keyword[expected_kind]())
    assert tok.kind == expected_kind
    assert tok.get_value(tokenizer.stream) == token_word


def test_tokenize_ascii_string(roff_text_body_tokenizer):
    tokenizer = roff_text_body_tokenizer('"A string"')
    token = next(tokenizer.tokenize_string_literal())
    assert token.kind == TokenKind.STRING_LITERAL
    assert token.get_value(tokenizer.stream) == "A string"


@pytest.mark.parametrize("value_string", ["321", "1", "1.0", "1.0E+1", "-1.0"])
def test_tokenize_ascii_numeric_value(roff_text_body_tokenizer, value_string):
    tokenizer = roff_text_body_tokenizer(value_string)
    token = next(tokenizer.tokenize_numeric_value())
    assert token.kind == TokenKind.NUMERIC_VALUE
    assert token.get_value(tokenizer.stream) == value_string


@given(
    st.characters(blacklist_categories=("C", "Z")),
    whitespace,
)
def test_tokenize_space(character, whitespace):
    starts_with_space = io.StringIO(whitespace + character)

    tokenizer = TextRoffBodyTokenizer(starts_with_space)

    test_tokenizer = tokenizer.tokenize_delimiter()

    with pytest.raises(StopIteration):
        next(test_tokenizer)

    assert starts_with_space.read(1) == character


def test_tokenize_comment():
    comment_buffer = io.StringIO("#a comment#1")

    tokenizer = TextRoffBodyTokenizer(comment_buffer)

    with pytest.raises(StopIteration):
        next(tokenizer.tokenize_comment())

    assert comment_buffer.read(1) == "1"


def test_drop_comment_eof():
    comment_buffer = io.StringIO("#a comment")

    tokenizer = TextRoffBodyTokenizer(comment_buffer)

    with pytest.raises(TokenizationError, match="Reached end of stream"):
        next(tokenizer.tokenize_comment())


def test_tokenize_empty_name(roff_text_body_tokenizer):
    tokenizer = roff_text_body_tokenizer("")
    with pytest.raises(TokenizationError):
        next(tokenizer.tokenize_name())


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
    roff_text_body_tokenizer, varname, typename, typekind, value, valuekind
):
    tokenizer = roff_text_body_tokenizer(f"{typename} {varname} {value}")
    tokens = list(tokenizer.tokenize_simple_tagkey())

    assert tokens[0].kind == typekind
    assert tokens[1].kind == TokenKind.NAME
    assert tokens[2].kind == valuekind

    read_var_name = tokens[1].get_value(tokenizer.stream)

    assert read_var_name == varname


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
    roff_text_body_tokenizer, varname, typename, typekind, values, valuekind
):
    tokenizer = roff_text_body_tokenizer(f"array {typename} {varname} 3 {values}")
    tokens = list(tokenizer.tokenize_array_tagkey())

    assert tokens[0].kind == TokenKind.ARRAY
    assert tokens[1].kind == typekind
    assert tokens[2].kind == TokenKind.NAME
    assert tokens[3].kind == TokenKind.NUMERIC_VALUE
    all(t.kind == valuekind for t in tokens[3:])

    read_var_name = tokens[2].get_value(tokenizer.stream)

    assert read_var_name == varname


def test_tokenize_tag_group(roff_text_body_tokenizer):
    tokenizer = roff_text_body_tokenizer(
        "tag\n"
        "# A tag comment #\n"
        "tag_name\n"
        "int x 3\n"
        'char str "a string"\n'
        "float y 4.0\n"
        "endtag\n"
    )
    tokens = list(tokenizer.tokenize_tag_group())

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

    assert tokens[1].get_value(tokenizer.stream) == "tag_name"
    assert tokens[3].get_value(tokenizer.stream) == "x"
    assert tokens[4].get_value(tokenizer.stream) == "3"
    assert tokens[6].get_value(tokenizer.stream) == "str"
    assert tokens[7].get_value(tokenizer.stream) == "a string"
    assert tokens[9].get_value(tokenizer.stream) == "y"
    assert tokens[10].get_value(tokenizer.stream) == "4.0"


@given(ascii_file_contents())
def test_tokenize_ascii_file(ascii_str):
    buff = io.StringIO(ascii_str)
    tokenizer = RoffTokenizer(buff)
    for t in tokenizer:
        if t.kind in TokenKind.keywords():
            assert t.get_value(buff) == TokenKind.keywords()[t.kind]

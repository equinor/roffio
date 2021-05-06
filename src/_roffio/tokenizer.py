"""
In the following a tokenizer is a generator that takes a stream and generates
tokens. If an error occurs, the function winds back the stream to the position
to where it started generating and raises an Error.

Token combinator is any function which returns a tokenizer.

As the ROFF format is simple (LL(1)), we only require backtracking capabilities
when errors occurr for at most one token. This means that there is no
bookkeeping of backtracking points.

The roff format does not specify endianess although the filedata tag contains
the byteswaptest tagkey which can be used to determine what endianess the file
was created with. In order to correctly tokenize arrays, the correct ednianess
has to be given to RoffTokenizer. However, RoffTokenizer does not parse the
byteswaptest tagkey, instead it is possible to at any time change the endianess
used for tokenization, see RoffTokenizer.

For binary roff files, the tokenizers have to be given a byte stream. For ascii
roff files, both text and binary streams can be given.


"""
from dataclasses import dataclass
from enum import Enum, unique


@unique
class TokenKind(Enum):
    ROFF_ASC = 1
    ROFF_BIN = 2
    TAG = 3
    ENDTAG = 4
    STRING_LITERAL = 5
    NUMERIC_VALUE = 6
    BINARY_NUMERIC_VALUE = 7
    NAME = 8
    CHAR = 10
    BOOL = 11
    BYTE = 12
    INT = 13
    FLOAT = 14
    DOUBLE = 15
    ARRAY = 16
    ARRAYBLOB = 17

    @classmethod
    def simple_types(cls):
        return (
            cls.CHAR,
            cls.BOOL,
            cls.BYTE,
            cls.INT,
            cls.FLOAT,
            cls.DOUBLE,
        )

    @classmethod
    def keywords(cls):
        return {
            cls.ROFF_BIN: "roff-bin",
            cls.ROFF_ASC: "roff-asc",
            cls.TAG: "tag",
            cls.ENDTAG: "endtag",
            cls.CHAR: "char",
            cls.BOOL: "bool",
            cls.BYTE: "byte",
            cls.INT: "int",
            cls.FLOAT: "float",
            cls.DOUBLE: "double",
            cls.ARRAY: "array",
        }


@dataclass
class Token:
    """
    A token in a roff file. See README.md for description of roff format.
    """

    kind: TokenKind
    start: int
    end: int

    def get_value(self, stream):
        """
        :returns: The value (either as a string or byte string) in a token. For
            keyword tokens, such as kind=TokenKind.TAG, the string returned should
            be 'tag'. For value tokens such as kind=TokenKind.NUMERIC_VALUE, the
            string returned could be e.g. "1.5".
        """
        go_back = stream.tell()
        stream.seek(self.start)
        value = stream.read(self.end - self.start)
        stream.seek(go_back)
        return value


class TokenizationError(Exception):
    """
    A tokenizer will throw a TokenizationError if the expected token
    is not found at the start of the stream (however, it could be that
    any other valid roff token not covered by that tokenizer is at the
    start of the stream).
    """

    pass


def read_ascii(bytes_stream, num_characters):
    """
    Given any byte-like or string like stream, read
    the given number of characters from it. If given
    a byte-like stream, treat it as if it is ascii
    encoded.
    """
    read_bytelike = bytes_stream.read(num_characters)
    read_char = read_bytelike
    if hasattr(read_char, "decode"):
        read_char = read_char.decode("ascii")
    return read_char


def one_of(*tokenizers):
    """
    Combinator for tokenizers.

    :param tokenizers: List of tokenizers.
    :returns: A tokenizer that yields tokens from the
    first tokenizer in tokenizers that succeeds.
    """

    def one_of_tokenizer(stream):
        did_yield = False
        for tok in tokenizers:
            try:
                yield from tok(stream)
                did_yield = True
                break
            except TokenizationError:
                pass

        if not did_yield:
            raise TokenizationError(f"Could not match any token at {stream.tell()}")

    return one_of_tokenizer


def repeated(tokenizer):
    """
    Combinator for tokenizer.
    :param tokenizer: Any tokenizer.
    :returns: Tokenizer that applies the tokenizer zero or more times, until it
        fails.
    """

    def repeated_tokenizer(stream):
        try:
            while True:
                yield from tokenizer(stream)
        except TokenizationError:
            pass

    return repeated_tokenizer


def drop_while_space(stream):
    """
    Takes any number of whitespace from stream.
    Ends with stream at the first character that
    is not whitespace.
    """
    did_drop = False
    first_non_space = stream.tell()
    read_char = read_ascii(stream, 1)
    while read_char.isspace():
        did_drop = True
        first_non_space = stream.tell()
        read_char = read_ascii(stream, 1)
    stream.seek(first_non_space)
    return did_drop


def drop_comment(stream):
    """
    Takes one or zero comments from the start of stream.
    Ends with stream at the first character after one
    comment from the stream.
    """
    did_drop = False
    start = stream.tell()
    read_char = stream.read(1)
    if read_char in ["#", b"#"]:
        did_drop = True
        read_char = stream.read(1)
        while read_char and read_char not in ["#", b"#"]:
            read_char = stream.read(1)
        if not read_char:
            stream.seek(start)
            raise TokenizationError("Reached end of stream while reading comment")
    else:
        stream.seek(start)
    return did_drop


def take_one_binary_delimiter(stream):
    """
    Take exactly one binary delimiter (zero character) from
    the stream. Throws TokenizationError if there is not a
    binary delimiter at the start of the stream.
    """
    start = stream.tell()
    read_char = stream.read(1)
    if read_char != b"\0":
        stream.seek(start)
        raise TokenizationError(f"Expected zero delimiter at {start}")


def drop_til_next_ascii_token(stream):
    """
    Drops delimiting ascii characters from the start of the
    stream (whitespace or comment)
    """
    while drop_while_space(stream) or drop_comment(stream):
        pass


def drop_til_next_binary_token(stream):
    """
    Drops delimiting binary characters from the start of the
    stream (zero character or comment)
    """
    while drop_comment(stream):
        take_one_binary_delimiter(stream)


def tokenize_word(word, kind):
    """
    Token combinator for fixed word tokens, ie. when the stream contains 'tag'
    tokenize_word('tag', TokenKind.TAG) will yield Token(kind=TokenKind.TAG, 0,
    3).

    :returns: Tokenizer for the given word, yielding a token
        of the given kind.
    :param word: Any ascii word to be matched by the tokenizer.
    :param kind: The kind of token yielded by the tokenizer.
    """
    word_len = len(word)

    def word_tokenizer(stream):
        start = stream.tell()

        token = read_ascii(stream, word_len)
        if token == word:
            end = stream.tell()
            yield Token(kind, end - word_len, end)
        else:
            stream.seek(start)
            raise TokenizationError(f"Token {repr(token)} did not match {word}")

    return word_tokenizer


def ascii_delimited(tokenizer):
    """
    Token combinator for tokenizing ascii delimited tokens. Ascii files are
    delimited by whitespace and comments.  Ie.
    ascii_delimited(tokenize_word('tag', TokenKind.TAG)) with "#a comment# tag"
    in the stream will yield Token(TokenKind.TAG, 12, 15).
    """

    def tok(stream):
        drop_til_next_ascii_token(stream)
        yield from tokenizer(stream)

    return tok


def binary_delimited(tokenizer):
    """
    Token combinator for tokenizing binary delimited tokens. Ascii files are
    delimited by comments only.  Ie.
    binary_delimited(tokenize_word('tag', TokenKind.TAG)) with b"#a comment#\0tag\0"
    in the stream will yield Token(TokenKind.TAG, 12, 15) and leave the stream
    at position 16 (next character read is b'\\0').
    """

    def tok(stream):
        drop_til_next_binary_token(stream)
        yield from tokenizer(stream)

    return tok


def binary_ended(tokenizer):
    """
    Token combinator for tokenizing binary delimited tokens which are ended by
    zero character. Ascii files are delimited by comments only.  Ie.
    ascii_delimited(tokenize_word('tag', TokenKind.TAG)) with b"#a
    comment#\\0tag\\0" in the stream will yield Token(TokenKind.TAG, 12, 15) and
    exhaust the stream.
    """

    def tok(stream):
        drop_til_next_binary_token(stream)
        res = next(tokenizer(stream))
        take_one_binary_delimiter(stream)
        yield res

    return tok


tokenize_keyword = {
    kw_kind: tokenize_word(kw, kw_kind) for kw_kind, kw in TokenKind.keywords().items()
}

tokenize_simple_type = one_of(
    *[tokenize_keyword[st] for st in TokenKind.simple_types()]
)


def tokenize_name(stream):
    start = stream.tell()
    last_alnum = start
    read_char = read_ascii(stream, 1)
    while read_char and not read_char.isspace():
        last_alnum = stream.tell()
        read_char = read_ascii(stream, 1)
    if last_alnum - start < 1:
        stream.seek(start)
        raise TokenizationError(f"could not tokenize name at {start}")
    else:
        yield Token(TokenKind.NAME, start, last_alnum)


def tokenize_binary_string(kind):
    """
    Combinator for tokenizing any binary string (any characters terminated by
    zero-character) and yielding a token of the given kind.
    :param kind: The TokenKind yielded by the resulting tokenizer.
    """

    def tokenizer(stream):
        start = stream.tell()
        last_alnum = start
        read_char = read_ascii(stream, 1)
        while read_char and not read_char == "\0":
            last_alnum = stream.tell()
            read_char = read_ascii(stream, 1)
        if read_char != "\0":
            stream.seek(start)
            raise TokenizationError(f"could not tokenize name at {start}")
        else:
            yield Token(kind, start, last_alnum)

    return tokenizer


def tokenize_ascii_numeric_value(stream):
    """
    Tokenize any ascii numeric value, yields
    Token(TokenKind.NUMERIC_VALUE, 0, 3) for stream
    containing "1.0".
    """
    start = stream.tell()
    end = start
    read_char = read_ascii(stream, 1)
    if read_char and read_char.isnumeric() or read_char == "-":
        while read_char and (read_char.isnumeric() or read_char in ".eE+-"):
            end = stream.tell()
            read_char = read_ascii(stream, 1)
    if end - start < 1:
        stream.seek(start)
        raise TokenizationError(f"Expected numeric value at {start}")
    else:
        stream.seek(end)
        yield Token(TokenKind.NUMERIC_VALUE, start, end)


def tokenize_ascii_string_literal(stream):
    """
    Tokenize a ascii string literal, yields
    Token(TokenKind.STRING_LITERAL, 1, 7) for stream
    containing '"string"'.
    """
    start = stream.tell()
    read_char = read_ascii(stream, 1)
    if read_char == '"':
        literal_start = stream.tell()
        read_char = read_ascii(stream, 1)
        literal_end = stream.tell()
        while read_char and read_char not in '"':
            literal_end = stream.tell()
            read_char = read_ascii(stream, 1)
        if not read_char:
            stream.seek(start)
            raise TokenizationError(
                "Reached end of stream while reading string literal"
            )
        yield Token(TokenKind.STRING_LITERAL, literal_start, literal_end)
    else:
        stream.seek(start)
        raise TokenizationError(f"Expected ascii string at {start}")


tokenize_ascii_value = one_of(
    tokenize_ascii_numeric_value, tokenize_ascii_string_literal
)


def tokenize_simple_ascii_tagkey(stream):
    """
    Tokenize a non-array ascii tag key, yields
    [Token(TokenKind.INT, 0, 4), Token(TokenKind.NAME, 5,6), Token(TokenKind.NUMERIC_VALUE, 7,8)] for
    stream containing "int x 1".
    """
    yield from ascii_delimited(tokenize_simple_type)(stream)
    yield from ascii_delimited(tokenize_name)(stream)
    yield from ascii_delimited(tokenize_ascii_value)(stream)


def tokenize_ascii_array_tagkey(stream):
    """
    Tokenize a non-array ascii tag key, yields
    [
      Token(TokenKind.ARRAY,0, 5),
      Token(TokenKind.INT, 6, 9),
      Token(TokenKind.NAME, 10,11),
      Token(TokenKind.NUMERIC_VALUE, 12,13)
    ]
    for stream containing "array int a 1".
    """
    yield from ascii_delimited(tokenize_keyword[TokenKind.ARRAY])(stream)
    yield from ascii_delimited(tokenize_simple_type)(stream)
    yield from ascii_delimited(tokenize_name)(stream)
    yield from ascii_delimited(tokenize_ascii_numeric_value)(stream)
    yield from repeated(ascii_delimited(tokenize_ascii_value))(stream)


tokenize_ascii_tagkey = one_of(
    tokenize_simple_ascii_tagkey,
    tokenize_ascii_array_tagkey,
)


def tokenlen(tokenkind):
    """
    For fixed bytesize types return the number of bytes used
    to store that type.

    :param tokenkind: A fixed bytesize type, eg. TokenKind.BOOL.
    :returns: The number of bytes used for that type.
    """
    if tokenkind == TokenKind.BOOL:
        return 1
    elif tokenkind == TokenKind.BYTE:
        return 1
    elif tokenkind == TokenKind.INT:
        return 4
    elif tokenkind == TokenKind.FLOAT:
        return 4
    elif tokenkind == TokenKind.DOUBLE:
        return 8
    else:
        raise TokenizationError(f"Attempted to read non-fixed size type {tokenkind}")


def tokenize_binary_numeric_value(tokenkind):
    """
    Tokenize any binary numeric value. Ie.
    tokenize_binary_numeric_value(TokenKind.INT) will skip 4 bytes ahead in the
    stream and yield Token(TokenKind.NUMERIC_VALUE, stream.tell(), stream.tell()+4).
    """

    def tok(stream):
        start = stream.tell()
        stream.seek(start + tokenlen(tokenkind))
        yield Token(TokenKind.BINARY_NUMERIC_VALUE, start, stream.tell())

    return tok


def tokenize_binary_value(kind):
    """
    Tokenize the binary value of the given simple type kind, ie. tokenizes a
    binary string if given TokenKind.CHAR and binary numeric value if given
    TokenKind.INT.
    :param kind: Any simple type kind, ie. TokenKind.INT, TokenKind.CHAR,
        TokenKind.BOOL, etc.
    """
    if kind == TokenKind.CHAR:
        return tokenize_binary_string(TokenKind.STRING_LITERAL)
    else:
        return tokenize_binary_numeric_value(kind)


def tokenize_simple_binary_tagkey(stream):
    """
    Tokenize a non-array binary tag key, yields
    [
      Token(TokenKind.ARRAY,0, 5),
      Token(TokenKind.BOOL, 6, 9),
      Token(TokenKind.NAME, 10,11),
      Token(TokenKind.NUMERIC_VALUE, 12,13)
    ]
    for stream containing b"array\\0bool\\0a\\0\\x01".
    """
    type_token = next(binary_ended(tokenize_simple_type)(stream))
    yield type_token
    yield from binary_delimited(tokenize_binary_string(TokenKind.NAME))(stream)
    # We do not use binary_delimited here because in the binary format it is
    # not possible to know whether you have a comment or a value starting with
    # b'#' Therefore we assume that no comments occur when we expect a value
    yield from tokenize_binary_value(type_token.kind)(stream)


def tokenize_ascii_tag_group(stream):
    """
    Tokenize an ascii tag group, yields
    [
        Token(TokenKind("tag")),
        tokenize_ascii_tag_key("bool a 1")
        Token(TokenKind("endtag")),
    ]
    for stream containing "tag bool a 1 endtag".
    """
    yield from ascii_delimited(tokenize_keyword[TokenKind.TAG])(stream)
    yield from ascii_delimited(tokenize_name)(stream)
    yield from repeated(tokenize_ascii_tagkey)(stream)
    yield from ascii_delimited(tokenize_keyword[TokenKind.ENDTAG])(stream)


def tokenize_ascii_body(stream):
    """
    Tokenize a roff ascii file body, that is, everything
    following the "roff-asc" header.
    """
    yield from repeated(tokenize_ascii_tag_group)(stream)


class RoffTokenizer:
    """
    The roff tokenizer is an iterable for tokens for a given
    stream of roff file contents, and raises TokenizationError
    as any other tokenizer.

    The endianess used to read the file can be changed while reading
    by setting the endianess field:

    >>> tokenizer = RoffTokenizer(stream, endianess="big")
    >>> token1 = next(tokenizer)
    >>> tokenizer.endianess = "little"
    >>> token2 = next(tokenizer)

    This makes it possible to implement byte swapping according to
    the filedata tagkey byteswaptest, however, the tokenizer does
    no such handling of byteswapping.
    """

    def __init__(self, stream, endianess="little"):
        """
        :param stream: A byte og text stream containing roff data.
        :param endianess: The endianess of the file, used only for
            determining the size of arrays in binary roff files.
        """
        self.stream = stream
        self._endianess = None
        self.endianess = endianess

    @property
    def endianess(self):
        return self._endianess

    @endianess.setter
    def endianess(self, value):
        if value not in ["little", "big"]:
            raise ValueError("endianess has to be either 'little' or 'big'")
        self._endianess = value

    def swap_endianess(self):
        if self.endianess == "little":
            self.endianess = "big"
        else:
            self.endianess = "little"

    def __iter__(self):
        return self.tokenize_roff_file(self.stream)

    def tokenize_roff_file(self, stream):
        """
        Tokenize a roff file.
        """
        start = stream.tell()
        header = next(
            one_of(
                tokenize_keyword[TokenKind.ROFF_ASC],
                binary_ended(tokenize_keyword[TokenKind.ROFF_BIN]),
            )(stream)
        )
        yield header
        if header.kind == TokenKind.ROFF_ASC:
            yield from tokenize_ascii_body(stream)
        elif header.kind == TokenKind.ROFF_BIN:
            yield from self.tokenize_binary_body(stream)
        else:
            stream.seek(start)
            raise TokenizationError("tokenizing header yielded unexpected token!")

    def tokenize_binary_body(self, stream):
        """
        Tokenize a roff binary file body, that is, everything
        following the b"roff-bin\\0" header.
        """
        yield from repeated(self.tokenize_binary_tag_group)(stream)

    def tokenize_binary_tag_group(self, stream):
        """
        Tokenize an binary tag group, yields
        [
            Token(TokenKind.TAG),
            tokenize_binary_tag_key(b"bool\\0a\\0\\x01")
            Token(TokenKind.ENDTAG),
        ]
        for stream containing b"tag\\0bool\\0a\\0\x01\\0endtag".
        """
        yield from binary_ended(tokenize_keyword[TokenKind.TAG])(stream)
        yield from binary_delimited(tokenize_binary_string(TokenKind.NAME))(stream)
        yield from repeated(self.tokenize_binary_tagkey())(stream)
        yield from binary_ended(tokenize_keyword[TokenKind.ENDTAG])(stream)

    def tokenize_binary_array_tagkey(self, stream):
        """
        Tokenize a binary array tagkey, yields
        [
          Token(TokenKind.ARRAY,0, 5),
          Token(TokenKind.INT, 6, 9),
          Token(TokenKind.NAME, 10,11),
          Token(TokenKind.NUMERIC_VALUE, 12,16)
        ]
        for stream containing b"array\\0int\\0a\\0\\x01\\x00\\x00\\x00".
        """
        yield from binary_ended(tokenize_keyword[TokenKind.ARRAY])(stream)
        element_type = next(binary_ended(tokenize_simple_type)(stream))
        yield element_type
        yield from binary_delimited(tokenize_binary_string(TokenKind.NAME))(stream)
        num_values = next(tokenize_binary_numeric_value(TokenKind.INT)(stream))
        yield num_values
        yield from self.tokenize_binary_array_data(
            stream, element_type.kind, num_values
        )

    def tokenize_binary_tagkey(self):
        """
        Tokenize stream containing either a binary simple or array tagkey see
        RoffTokenizer.tokenize_simple_binary_tagkey and
        RoffTokenizer.tokenize_binary_array_tagkey.
        """
        return one_of(
            tokenize_simple_binary_tagkey,
            self.tokenize_binary_array_tagkey,
        )

    def tokenize_binary_array_data(self, stream, element_type, num_values_token):
        """
        Tokenize binary array data of the given element type and with the given
        number of values. Yields the given number of string literal tokens for
        element_type == TokenKind.CHAR and one token of kind TokenKind.ARRAYBLOB
        for all other simple element types (for instance TokenKind.INT).
        :param element_type: TokenKind of a simple element type.
        :param num_values_token: The token for the number of values
            in the array.
        """
        num_values = int.from_bytes(num_values_token.get_value(stream), self.endianess)
        # We do not use binary_delimited here because in the binary format it is
        # not possible to know whether you have a comment or a value starting with
        # b'#' Therefore we assume that no comments occur when we expect a value.
        if element_type == TokenKind.CHAR:
            for _ in range(num_values):
                yield from tokenize_binary_string(TokenKind.STRING_LITERAL)(stream)
        else:
            start = stream.tell()
            stream.seek(start + tokenlen(element_type) * num_values)
            yield Token(TokenKind.ARRAYBLOB, start, stream.tell())

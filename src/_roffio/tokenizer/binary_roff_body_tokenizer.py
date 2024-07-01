from functools import cached_property

from _roffio.tokenizer.abstract_roff_body_tokenizer import AbstractRoffBodyTokenizer
from _roffio.tokenizer.combinators import bind, repeated
from _roffio.tokenizer.common import tokenize_word
from _roffio.tokenizer.errors import TokenizationError
from _roffio.tokenizer.token import Token
from _roffio.tokenizer.token_kind import TokenKind


def tokenlen(tokenkind):
    """
    For fixed bytesize types return the number of bytes used
    to store that type.

    :param tokenkind: A fixed bytesize type, eg. TokenKind.BOOL.
    :returns: The number of bytes used for that type.
    """
    if tokenkind in (TokenKind.BOOL, TokenKind.BYTE):
        return 1
    elif tokenkind in (TokenKind.INT, TokenKind.FLOAT):
        return 4
    elif tokenkind == TokenKind.DOUBLE:
        return 8
    else:
        raise TokenizationError(f"Attempted to read non-fixed size type {tokenkind}")


class BinaryRoffBodyTokenizer(AbstractRoffBodyTokenizer):
    def __init__(self, stream, endianess="little"):
        """
        :param stream: A byte stream containing roff data.
        :param endianess: The endianess of the file, used only for
            determining the size of arrays in binary roff files.
        """
        self._stream = stream
        self._endianess = None
        self.endianess = endianess

    @property
    def stream(self):
        return self._stream

    @cached_property
    def tokenize_keyword(self):
        return {
            kw_kind: bind(
                repeated(self.tokenize_comment),
                self.binary_ended(
                    tokenize_word(self.stream, kw.encode("ascii"), kw_kind)
                ),
            )
            for kw_kind, kw in TokenKind.keywords().items()
        }

    def binary_ended(self, tokenizer):
        def binary_ended_tokenizer():
            tok = next(tokenizer())
            start = self.stream.tell()
            read_char = self.stream.read(1)
            if read_char != b"\0":
                self.stream.seek(start)
                raise TokenizationError(f"Expected delimiter at {start}")
            yield tok

        return binary_ended_tokenizer

    @property
    def tokenize_array_size(self):
        return self.tokenize_numeric_value(TokenKind.INT)

    @property
    def tokenize_name(self):
        return bind(
            repeated(self.tokenize_comment), self.tokenize_string(TokenKind.NAME)
        )

    def tokenize_numeric_value(self, tokenkind):
        """
        Tokenize any binary numeric value. Ie.
        tokenize_binary_numeric_value(TokenKind.INT) will skip 4 bytes ahead in the
        stream and yield Token(TokenKind.NUMERIC_VALUE, stream.tell(), stream.tell()+4).
        """

        def tok():
            start = self.stream.tell()
            self.stream.seek(start + tokenlen(tokenkind))
            yield Token(TokenKind.BINARY_NUMERIC_VALUE, start, self.stream.tell())

        return tok

    def tokenize_string(self, kind):
        """
        Combinator for tokenizing any binary string (any characters terminated by
        zero-character) and yielding a token of the given kind.
        :param kind: The TokenKind yielded by the resulting tokenizer.
        """

        def tokenizer():
            start = self.stream.tell()
            last_alnum = start
            read_char = self.stream.read(1)
            while read_char and read_char != b"\x00":
                last_alnum = self.stream.tell()
                read_char = self.stream.read(1)
            if read_char != b"\0":
                self.stream.seek(start)
                raise TokenizationError(f"could not tokenize string at {start}")
            else:
                yield Token(kind, start, last_alnum)

        return tokenizer

    def tokenize_value(self, kind):
        """
        Tokenize the binary value of the given simple type kind, ie. tokenizes a
        binary string if given TokenKind.CHAR and binary numeric value if given
        TokenKind.INT.
        :param kind: Any simple type kind, ie. TokenKind.INT, TokenKind.CHAR,
            TokenKind.BOOL, etc.
        """
        if kind == TokenKind.CHAR:
            return self.tokenize_string(TokenKind.STRING_LITERAL)
        else:
            return self.tokenize_numeric_value(kind)

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

    def tokenize_comment(self):
        """
        Tokenize a comment from the start of stream.

        Note: does not actually yield a token for the comment,
        just raises StopIteration after taking a comment.

        """
        start = self.stream.tell()
        read_char = self.stream.read(1)
        if read_char == b"#":
            read_char = self.stream.read(1)
            while read_char and read_char != b"#":
                read_char = self.stream.read(1)
            if not read_char:
                self.stream.seek(start)
                raise TokenizationError("Reached end of stream while reading comment")
            yield from self.tokenize_delimiter()
        else:
            self.stream.seek(start)
            raise TokenizationError(f"Expected comment at {start}")

    def tokenize_array_data(self, element_type, num_values_token):
        """
        Tokenize binary array data of the given element type and with the given
        number of values. Yields the given number of string literal tokens for
        element_type == TokenKind.CHAR and one token of kind TokenKind.ARRAYBLOB
        for all other simple element types (for instance TokenKind.INT).
        :param element_type: TokenKind of a simple element type.
        :param num_values_token: The token for the number of values
            in the array.
        """
        num_values = int.from_bytes(
            num_values_token.get_value(self.stream), self.endianess
        )
        # We do not use binary_delimited here because in the binary format it is
        # not possible to know whether you have a comment or a value starting with
        # b'#' Therefore we assume that no comments occur when we expect a value.
        if element_type == TokenKind.CHAR:
            for _ in range(num_values):
                yield from self.tokenize_string(TokenKind.STRING_LITERAL)()
        else:
            start = self.stream.tell()
            self.stream.seek(start + tokenlen(element_type) * num_values)
            yield Token(TokenKind.ARRAYBLOB, start, self.stream.tell())

    def tokenize_simple_tagkey(self):
        """
        see AbstractRoffTokenizer.tokenize_simple_tagkey
        """
        type_token = next(self.tokenize_simple_type())

        yield type_token
        yield from repeated(self.tokenize_comment)()
        yield from self.tokenize_string(TokenKind.NAME)()
        # We do not use binary_delimited here because in the binary format it is
        # not possible to know whether you have a comment or a value starting with
        # b'#' Therefore we assume that no comments occur when we expect a value
        yield from self.tokenize_value(type_token.kind)()

    def tokenize_delimiter(self):
        start = self.stream.tell()
        read_char = self.stream.read(1)
        if read_char != b"\0":
            self.stream.seek(start)
            raise TokenizationError(f"Expected delimiter at {start}")
        return iter([])

    def tokenize_end_of_file(self):
        yield from repeated(self.tokenize_comment)()
        start = self.stream.tell()
        r = self.stream.read(1)
        if r:
            self.stream.seek(start)
            raise TokenizationError(
                f"Expected end of file or new tag at {start} got {r}"
            )
        return iter([])

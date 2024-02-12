from functools import cached_property

from _roffio.tokenizer.abstract_roff_body_tokenizer import AbstractRoffBodyTokenizer
from _roffio.tokenizer.combinators import bind, one_of, repeated
from _roffio.tokenizer.common import tokenize_word
from _roffio.tokenizer.errors import TokenizationError
from _roffio.tokenizer.token import Token
from _roffio.tokenizer.token_kind import TokenKind


class TextRoffBodyTokenizer(AbstractRoffBodyTokenizer):
    def __init__(self, stream):
        """
        :param stream: A byte stream containing roff data.
        """
        self._stream = stream

    @property
    def tokenize_delimiter(self):
        return repeated(one_of(self.tokenize_comment, self.tokenize_space))

    @property
    def stream(self):
        return self._stream

    @cached_property
    def tokenize_keyword(self):
        return {
            kw_kind: bind(
                self.tokenize_delimiter,
                tokenize_word(self.stream, kw, kw_kind),
            )
            for kw_kind, kw in TokenKind.keywords().items()
        }

    @property
    def tokenize_array_size(self):
        return self.tokenize_numeric_value

    @property
    def tokenize_value(self):
        return one_of(self.tokenize_numeric_value, self.tokenize_string_literal)

    def swap_endianess(self):
        pass

    def tokenize_numeric_value(self):
        """
        Tokenize any text numeric value, yields
        Token(TokenKind.NUMERIC_VALUE, 0, 3) for stream
        containing "1.0".
        """
        yield from self.tokenize_delimiter()
        start = self.stream.tell()
        end = start
        read_char = self.stream.read(1)
        if read_char and read_char.isnumeric() or read_char == "-":
            while read_char and (read_char.isnumeric() or read_char in ".eE+-"):
                end = self.stream.tell()
                read_char = self.stream.read(1)
        if end - start < 1:
            self.stream.seek(start)
            raise TokenizationError(f"Expected numeric value at {start}")
        else:
            self.stream.seek(end)
            yield Token(TokenKind.NUMERIC_VALUE, start, end)

    def tokenize_string_literal(self):
        """
        Tokenize a text string literal, yields
        Token(TokenKind.STRING_LITERAL, 1, 7) for stream
        containing '"string"'.
        """
        yield from self.tokenize_delimiter()
        start = self.stream.tell()
        read_char = self.stream.read(1)
        if read_char == '"':
            literal_start = self.stream.tell()
            read_char = self.stream.read(1)
            literal_end = self.stream.tell()
            while read_char and read_char not in '"':
                literal_end = self.stream.tell()
                read_char = self.stream.read(1)
            if not read_char:
                self.stream.seek(start)
                raise TokenizationError(
                    "Reached end of stream while reading string literal"
                )
            yield Token(TokenKind.STRING_LITERAL, literal_start, literal_end)
        else:
            self.stream.seek(start)
            raise TokenizationError(f"Expected string at {start}")

    def tokenize_comment(self):
        """
        Tokenize a comment from the start of stream.

        Note: does not actually yield a token for the comment,
        just raises StopIteration after taking a comment.

        """
        start = self.stream.tell()
        read_char = self.stream.read(1)
        if read_char == "#":
            read_char = self.stream.read(1)
            while read_char and read_char != "#":
                read_char = self.stream.read(1)
            if not read_char:
                self.stream.seek(start)
                raise TokenizationError("Reached end of stream while reading comment")
            return iter([])
        else:
            self.stream.seek(start)
            raise TokenizationError(f"Expected comment at {start}")

    def tokenize_array_data(self, element_type, num_values_token):
        """
        see AbstractRoffTokenizer.tokenize_array_data.
        """
        yield from repeated(self.tokenize_value)()

    def tokenize_simple_tagkey(self):
        """
        see AbstractRoffTokenizer.tokenize_simple_tagkey.
        """
        yield from self.tokenize_simple_type()
        yield from self.tokenize_name()
        yield from self.tokenize_value()

    def tokenize_name(self):
        yield from self.tokenize_delimiter()

        start = self.stream.tell()
        length = 0

        read_char = self.stream.read(1)
        while read_char and not read_char.isspace():
            length += 1
            read_char = self.stream.read(1)

        if length < 1:
            self.stream.seek(start)
            raise TokenizationError(f"could not tokenize name at {start}")

        yield Token(TokenKind.NAME, start, start + length)

    def tokenize_space(self):
        start = self.stream.tell()
        read_char = self.stream.read(1)
        if not read_char.isspace():
            self.stream.seek(start)
            raise TokenizationError(f"Expected space at start, got {read_char}")

        while read_char.isspace():
            first_non_space = self.stream.tell()
            read_char = self.stream.read(1)
        self.stream.seek(first_non_space)
        return iter([])

    def tokenize_end_of_file(self):
        yield from self.tokenize_delimiter()
        start = self.stream.tell()
        read_char = self.stream.read(1)
        if read_char:
            self.stream.seek(start)
            raise TokenizationError(
                f"Expected end of file or new tag at {start} got {read_char}"
            )

"""
A parser consumes from an iterator of tokens (see roffio.tokenizer) and
generates the corresponding roff data. For entire files, roff data is a two level
dictionary of tagname and tagkeyname to values, but for subsections of roff
files, the parser returns the corresponding subdata of the dictionary.
"""

from itertools import chain, dropwhile, tee

import numpy as np

from _roffio.lazy_tuple import LazyTuple
from _roffio.tokenizer.token_kind import TokenKind


# The token stream can contain string values or
# byte values, we need to convert them as ascii
# if given bytes.
def as_ascii(bytelike):
    """
    If a bytelike object, convert to ascii, otherwise do nothing.
    :param bytelike: A byte like string, or simply a string.
    :returns: If given a bytelike string object, then a that string decoded
        as ascii, otherwise just returns that string.
    """
    if hasattr(bytelike, "decode"):
        bytelike = bytelike.decode("ascii")
    return bytelike


class ParsingException(Exception):
    """
    Raised by the parser if the list of tokens is not of the expected section,
    but possibly some other valid section.
    """

    pass


class RoffTypeError(Exception):
    """
    Raised by the parser if there is a type error.
    """

    pass


class RoffSyntaxError(Exception):
    """
    Raised by the parser if the file has invalid syntax.
    """

    pass


def parse_one_of(*kinds):
    """
    Parser combinator for parser of one of the given token kinds
    :param kinds: list of token kinds to be accepted by the returned
        parser.
    """

    def parser(tokens):
        try:
            token = next(tokens)
        except StopIteration:
            return
        if token.kind in kinds:
            yield token.kind
        else:
            raise RoffSyntaxError(
                f"Expected {token.kind} to be one of {kinds} at {token.start}."
            )

    return parser


parse_simple_type = parse_one_of(*TokenKind.simple_types())


def parse_name(tokens, stream):
    """
    Takes a token with token.kind == TokenKind.NAME from the stream
    and yields the name as a string.
    """
    token = next(tokens)
    if token.kind != TokenKind.NAME:
        raise RoffTypeError(f"Expected name at {token.start} found {token.kind}")

    yield as_ascii(token.get_value(stream))


# Map from endianess and token kind to numpy dtype
# used for reading numeric values with
# a given type.
dtype_little = {
    TokenKind.BYTE: np.uint8,
    TokenKind.BOOL: np.bool_,
    TokenKind.INT: np.int32,
    TokenKind.FLOAT: np.float32,
    TokenKind.DOUBLE: np.float64,
}
dtype = {
    "little": dtype_little,
    "big": {tk: np.dtype(dt).newbyteorder(">") for tk, dt in dtype_little.items()},
}


class RoffTagKeyParser:
    """
    Parser for a tagkey, used by RoffParser to lazily
    generate data for a given tag. Therefore, belongs
    to a RoffParser in order to share parameters such
    as endianess.

    >>> buffer = io.StringIO("int x 3")
    >>> tokens = iter(RoffTokenizer(buffer))
    >>> parser = RoffParser(tokens, buffer)
    >>> rtkp = RoffTagKeyParser(tokens, buffer, parser)
    >>> next(iter(rtkp))
    ('x', 3)

    """

    def __init__(self, tokens, stream, roffparser):
        """
        :param tokens: iterator of tokens.
        :param stream: stream of characters the tokens
            refer to.
        :param roffparser: The roffparser used for
            shared parameters.
        """
        self.tokens = tokens
        self.stream = stream
        self.roffparser = roffparser

    def __iter__(self):
        first_tok = next(self.tokens)
        self.tokens = chain([first_tok], self.tokens)
        while first_tok.kind != TokenKind.ENDTAG:
            yield from self.parse_tagkey()
            first_tok = next(self.tokens)
            self.tokens = chain([first_tok], self.tokens)

    def parse_boolean_value(self):
        """
        Takes a boolean value token from the token generator and
        yields the boolean value.
        :param dtype: The numpy dtype of the numeric value.
        """
        num_token = next(self.tokens)
        val_str = num_token.get_value(self.stream)
        if len(val_str) != 1:
            raise RoffSyntaxError(f"too long boolean value, found: {val_str}")
        if self.roffparser.is_binary_file:
            value = int.from_bytes(val_str, self.roffparser.endianess)
        else:
            value = int(as_ascii(val_str))

        if value == 1:
            yield True
        elif value == 0:
            yield False
        else:
            raise RoffTypeError(f"boolean values must be either 1 or 0, found {value}")

    def parse_numeric_value(self, dtype):
        """
        Takes a numeric token from the token generator and
        yields the numeric value.
        :param dtype: The numpy dtype of the numeric value.
        """
        num_token = next(self.tokens)
        if num_token.kind == TokenKind.NUMERIC_VALUE:
            try:
                yield dtype(num_token.get_value(self.stream))
            except ValueError as err:
                raise RoffSyntaxError(f"Could not parse {dtype} got {err}") from err
        elif num_token.kind == TokenKind.BINARY_NUMERIC_VALUE:
            yield np.ndarray((1,), dtype, num_token.get_value(self.stream))[0]
        else:
            if num_token.kind == TokenKind.STRING_LITERAL:
                raise RoffTypeError(
                    f"Expected numeric value at {num_token.start} found string literal"
                )
            raise ParsingException(
                f"Expected numeric value, got {num_token.kind} at {num_token.start}"
            )

    def parse_string_literal(self):
        """
        Takes a string literal token from the token generator and
        yields the string.
        """
        token = next(self.tokens)
        if token.kind != TokenKind.STRING_LITERAL:
            raise RoffTypeError(
                f"Expected string literal at {token.start} found {token.kind}"
            )

        yield as_ascii(token.get_value(self.stream))

    def parse_value(self, typ):
        """
        Parse a value of the given type, where typ is the token kind of the
        token specifying type (ie. TokenKind.BYTE, TokenKind.FLOAT etc.)
        :param typ: one of TokenKind.simple_types.
        """
        if typ == TokenKind.CHAR:
            yield from self.parse_string_literal()
        elif typ == TokenKind.BOOL:
            yield from self.parse_boolean_value()
        elif typ == TokenKind.BYTE:
            val = next(self.parse_numeric_value(dtype[self.roffparser.endianess][typ]))
            yield val.tobytes()
        else:
            yield from self.parse_numeric_value(dtype[self.roffparser.endianess][typ])

    def parse_simple_tagkey_body(self, typ):
        """
        Parse a non-array tag key body, starting from the first
        token after the simple type.
        :param typ: The kind of the simple type token
        """
        name = next(parse_name(self.tokens, self.stream))
        value = next(self.parse_value(typ))
        yield (name, value)

    def parse_array_values(self, typ, name, number):
        """
        Parse array values, ie. tokens directly following
        the number of values in an array tagkey.
        :param typ: the TokenKind describing the type of
            elements in the array, eg. TokenKind.INT.
        :param name: The name of the array tagkey.
        :param number: The number of elements in the array.
        """
        first_tok = next(self.tokens)
        if first_tok.kind == TokenKind.ARRAYBLOB:
            if typ == TokenKind.BYTE:
                yield (lambda: first_tok.get_value(self.stream))
            else:
                yield (
                    lambda: np.ndarray(
                        number,
                        dtype[self.roffparser.endianess][typ],
                        first_tok.get_value(self.stream),
                    )
                )
        else:
            self.tokens = chain([first_tok], self.tokens)
            try:
                vals = np.array([next(self.parse_value(typ)) for _ in range(number)])
                if typ == TokenKind.BYTE:
                    yield vals.tobytes()
                else:
                    yield vals
            except StopIteration as stop_it:
                raise RoffSyntaxError(
                    f"Expected {number} values to follow array {name} at {first_tok.start}"
                ) from stop_it

    def parse_array_tagkey_body(self):
        """
        Parses the contents of an array tag key following the Array token.
        """
        typ = next(parse_simple_type(self.tokens))
        name = next(parse_name(self.tokens, self.stream))
        number = next(
            self.parse_numeric_value(dtype[self.roffparser.endianess][TokenKind.INT])
        )
        values = next(self.parse_array_values(typ, name, number))
        if isinstance(values, (np.ndarray, bytes)):
            yield (name, values)
        else:
            yield LazyTuple(lambda: name, values)

    def parse_tagkey(self):
        """
        Parse a tagkey, yields tuple of tagkey name and tagkey
        value.
        """
        first_tok = next(self.tokens)
        if first_tok.kind == TokenKind.ARRAY:
            yield from self.parse_array_tagkey_body()
        elif first_tok.kind in TokenKind.simple_types():
            yield from self.parse_simple_tagkey_body(first_tok.kind)
        else:
            raise RoffSyntaxError(
                f"expected tag key type at {first_tok.start} got {first_tok.kind}: {first_tok.get_value(self.stream)}"
            )


class RoffParser:
    """
    A lazy parser of the ROFF file format, ie. consumes the
    output of the roffio.tokenizer and is an iterable of
    tag name to generator of tag key name to tag key value.
    >>> buffer = io.StringIO("roff-asc tag y int x 3 endtag")
    >>> tokens = iter(RoffTokenizer(buffer))
    >>> parser = RoffParser(tokens, buffer)
    >>> t, k = next(iter(parser))
    >>> t
    "y"
    >>> next(k)
    ("x", 3)

    Note: The parser does not handle the "byteswaptest" tag key
    in the "filedata" tag. Instead, endianess used for
    parsing can be changed at any time.

    """

    def __init__(self, tokens, stream, endianess="little"):
        """
        :param tokens: iterator of tokens, ie. RoffTokenizer.
        :param stream: The stream of characters or bytes
            the tokens refer to.
        :param endianess: Either "little" or "big" for little
            endian and big endian, respectivly.
        """
        self.tokens = tokens
        self.stream = stream
        self.is_binary_file = False

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

    def parse_tag(self):
        try:
            next(parse_one_of(TokenKind.TAG)(self.tokens))
        except StopIteration:
            return
        name = next(parse_name(self.tokens, self.stream))

        self.tokens, tag_tokens = tee(self.tokens)

        tagkey_generator = iter(RoffTagKeyParser(tag_tokens, self.stream, self))
        self.tokens = dropwhile(lambda t: t.kind != TokenKind.ENDTAG, self.tokens)
        yield (name, tagkey_generator)

    def __iter__(self):
        header = next(parse_one_of(TokenKind.ROFF_BIN, TokenKind.ROFF_ASC)(self.tokens))
        if header == TokenKind.ROFF_BIN:
            self.is_binary_file = True
        while True:
            try:
                tag = next(self.parse_tag())
                try:
                    next(parse_one_of(TokenKind.ENDTAG)(self.tokens))
                except StopIteration as err:
                    raise RoffSyntaxError(
                        f"did not find closing endtag for tag {tag[0]}"
                    ) from err
                yield tag
            except StopIteration:
                break
        try:
            t = next(self.tokens)
            raise RoffSyntaxError(f"Parsing ended with trailing tokens at {t.start}")
        except StopIteration:
            return

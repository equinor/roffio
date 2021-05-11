from dataclasses import dataclass

from _roffio.tokenizer.token_kind import TokenKind


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

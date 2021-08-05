from abc import ABC, abstractmethod, abstractproperty

from _roffio.tokenizer.combinators import one_of, repeated
from _roffio.tokenizer.errors import TokenizationError
from _roffio.tokenizer.token_kind import TokenKind


class AbstractRoffBodyTokenizer(ABC):
    """
    The roff tokenizer is an iterable for tokens for a given stream of roff
    file contents, and raises TokenizationError as any other tokenizer.

    This is an abstract class which doesn't implement the specifics of
    delimiters and values. The documentation use ascii delimiters and values for
    simplicity, but it is up to the implementing class how these are actually
    represented.

    """

    @abstractproperty
    def stream(self):
        pass

    @abstractproperty
    def tokenize_keyword(self):
        pass

    def __iter__(self):
        return self.tokenize_roff_file()

    def tokenize_roff_file(self):
        """
        Tokenize a roff file.
        """
        yield from self.tokenize_body()
        yield from self.tokenize_end_of_file()

    def tokenize_body(self):
        """
        Tokenize a roff binary file body, that is, everything
        following the b"roff-bin" or "roff-asc" header.
        """
        yield from repeated(self.tokenize_tag_group)()

    def tokenize_tag_group(self):
        """
        Tokenize an binary tag group, yields
        [
            Token(TokenKind.TAG),
            tokenize_tag_key("bool a 1")
            Token(TokenKind.ENDTAG),
        ]
        for stream containing "tag bool a 1 endtag".
        """
        yield from self.tokenize_keyword[TokenKind.TAG]()
        yield from self.tokenize_name()
        yield from repeated(self.tokenize_tagkey)()
        yield from self.tokenize_keyword[TokenKind.ENDTAG]()

    def tokenize_array_tagkey(self):
        """
        Tokenize a array tagkey, yields
        [
          Token(TokenKind.ARRAY,0, 5),
          Token(TokenKind.INT, 6, 9),
          Token(TokenKind.NAME, 10,11),
          Token(TokenKind.NUMERIC_VALUE, 12,16)
        ]
        for stream containing "int a 1 0".
        """
        yield from self.tokenize_keyword[TokenKind.ARRAY]()
        try:
            element_type = next(self.tokenize_simple_type())
        except StopIteration:
            return
        yield element_type
        yield from self.tokenize_name()
        try:
            num_values = next(self.tokenize_array_size())
        except StopIteration:
            return
        yield num_values

        yield from self.tokenize_array_data(element_type.kind, num_values)

    @abstractmethod
    def tokenize_array_size(self):
        pass

    @abstractmethod
    def tokenize_array_data(self, typ, num_values):
        """
        :param element_type: TokenKind of a simple element type.
        :param num_values_token: The token for the number of values
            in the array.
        """
        pass

    @property
    def tokenize_simple_type(self):
        return one_of(*[self.tokenize_keyword[st] for st in TokenKind.simple_types()])

    @property
    def tokenize_tagkey(self):
        """
        Tokenize stream containing either a simple or array tagkey see
        RoffTokenizer.tokenize_simple_tagkey and
        RoffTokenizer.tokenize_array_tagkey.
        """
        return one_of(
            self.tokenize_simple_tagkey,
            self.tokenize_array_tagkey,
        )

    @abstractmethod
    def tokenize_simple_tagkey(self):
        """
        Tokenize a non-array binary tag key, yields
        [
          Token(TokenKind.BOOL, 6, 9),
          Token(TokenKind.NAME, 10,11),
          Token(TokenKind.NUMERIC_VALUE, 12,13)
        ]
        for stream containing "bool a 1".
        """
        pass

    @abstractmethod
    def tokenize_name(self):
        pass

    @abstractmethod
    def tokenize_end_of_file(self):
        start = self.stream.tell()
        r = self.stream.read(1)
        if r:
            self.stream.seek(start)
            raise TokenizationError(
                f"Expected end of file or new tag at {start} got {r}"
            )
        return iter([])

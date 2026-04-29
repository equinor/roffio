from _roffio.tokenizer.binary_roff_body_tokenizer import BinaryRoffBodyTokenizer
from _roffio.tokenizer.errors import TokenizationError, WrongFileModeError
from _roffio.tokenizer.text_roff_body_tokenizer import TextRoffBodyTokenizer
from _roffio.tokenizer.token import Token
from _roffio.tokenizer.token_kind import TokenKind


def tokenize_header(stream):
    start = stream.tell()

    header = stream.read(8)
    if header == b"roff-bin":
        read_char = stream.read(1)
        if read_char != b"\0":
            stream.seek(start)
            raise TokenizationError(
                f"Expected delimiter after header token got {read_char}"
            )
        yield Token(TokenKind.ROFF_BIN, start, start + 8)
    elif header == "roff-asc":
        yield Token(TokenKind.ROFF_ASC, start, start + 8)
    elif header == b"roff-asc":
        raise WrongFileModeError("Ascii formatted roff file was opened in binary mode!")
    elif header == "roff-bin":
        raise WrongFileModeError("Binary formatted roff file was opened in text mode!")
    else:
        stream.seek(start)
        raise TokenizationError(f"Did not find roff header, got {header}.")


class RoffTokenizer:
    def __init__(self, stream, endianness="little"):
        """
        :param stream: A byte stream containing roff data.
        """
        self.stream = stream
        self.body_tokenizer = None
        self.endianness = endianness

    def swap_endianness(self):
        if self.endianness == "little":
            self.endianness = "big"
        else:
            self.endianness = "little"
        if self.body_tokenizer is not None:
            self.body_tokenizer.endianness = self.endianness

    def initialize_body_tokenizer(self, header_kind):
        if header_kind == TokenKind.ROFF_BIN:
            self.body_tokenizer = BinaryRoffBodyTokenizer(
                self.stream, endianness=self.endianness
            )
        elif header_kind == TokenKind.ROFF_ASC:
            self.body_tokenizer = TextRoffBodyTokenizer(self.stream)
        else:
            raise ValueError(f"Unexpected header kind {header_kind}")

    def __iter__(self):
        header = next(tokenize_header(self.stream))
        self.initialize_body_tokenizer(header.kind)
        yield header
        yield from iter(self.body_tokenizer)

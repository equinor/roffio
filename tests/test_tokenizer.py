import io

import pytest

from _roffio.tokenizer import RoffTokenizer
from _roffio.tokenizer.errors import WrongFileModeError
from _roffio.tokenizer.token_kind import TokenKind


def test_swap_endianness():
    stream = io.BytesIO(b"roff-bin\0")
    tokenizer = RoffTokenizer(stream)
    assert tokenizer.endianness == "little"
    tokens = iter(tokenizer)
    assert next(tokens).kind == TokenKind.ROFF_BIN
    assert tokenizer.body_tokenizer.endianness == "little"
    tokenizer.swap_endianness()
    assert tokenizer.endianness == "big"
    assert tokenizer.body_tokenizer.endianness == "big"


def test_swap_endianness_ascii():
    stream = io.StringIO("roff-asc ")
    tokenizer = RoffTokenizer(stream)
    assert tokenizer.endianness == "little"
    tokens = iter(tokenizer)
    assert next(tokens).kind == TokenKind.ROFF_ASC
    tokenizer.swap_endianness()
    assert tokenizer.endianness == "big"


def test_wrong_mode_error_binary():
    stream = io.StringIO("roff-bin\0")
    tokenizer = RoffTokenizer(stream)
    tokens = iter(tokenizer)
    with pytest.raises(WrongFileModeError):
        next(tokens).kind  # noqa: B018


def test_wrong_mode_error_ascii():
    stream = io.BytesIO(b"roff-asc ")
    tokenizer = RoffTokenizer(stream)
    tokens = iter(tokenizer)
    with pytest.raises(WrongFileModeError):
        next(tokens).kind  # noqa: B018

import io

import pytest

from _roffio.tokenizer import RoffTokenizer
from _roffio.tokenizer.errors import WrongFileModeError
from _roffio.tokenizer.token_kind import TokenKind


def test_swap_endianess():
    stream = io.BytesIO(b"roff-bin\0")
    tokenizer = RoffTokenizer(stream)
    assert tokenizer.endianess == "little"
    tokens = iter(tokenizer)
    assert next(tokens).kind == TokenKind.ROFF_BIN
    assert tokenizer.body_tokenizer.endianess == "little"
    tokenizer.swap_endianess()
    assert tokenizer.endianess == "big"
    assert tokenizer.body_tokenizer.endianess == "big"


def test_swap_endianess_ascii():
    stream = io.StringIO("roff-asc ")
    tokenizer = RoffTokenizer(stream)
    assert tokenizer.endianess == "little"
    tokens = iter(tokenizer)
    assert next(tokens).kind == TokenKind.ROFF_ASC
    tokenizer.swap_endianess()
    assert tokenizer.endianess == "big"


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

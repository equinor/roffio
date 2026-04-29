from unittest.mock import MagicMock

import pytest

from _roffio.endianness_handler import EndiannessHandler, RoffFormatError


def test_no_filedata_warning():
    tokenizer = MagicMock()
    parser = MagicMock()
    parser.__iter__.return_value = iter([("tagname", [])])

    with pytest.warns(UserWarning):
        next(iter(EndiannessHandler(parser, tokenizer)))


def test_no_byteswaptest_error():
    tokenizer = MagicMock()
    parser = MagicMock()
    parser.__iter__.return_value = iter([("filedata", [])])

    with pytest.raises(RoffFormatError):
        next(iter(EndiannessHandler(parser, tokenizer)))


def test_double_filedata_error():
    tokenizer = MagicMock()
    parser = MagicMock()
    input_data = ("filedata", [("byteswaptest", 1)])
    parser.__iter__.return_value = iter([input_data] * 2)

    data_iter = iter(EndiannessHandler(parser, tokenizer))
    output_data = next(data_iter)

    assert (output_data[0], list(output_data[1])) == input_data

    with pytest.raises(RoffFormatError):
        next(data_iter)


def test_filedata_swaps():
    tokenizer = MagicMock()
    parser = MagicMock()
    parser.__iter__.return_value = iter([("filedata", [("byteswaptest", -1)])])

    data = next(iter(EndiannessHandler(parser, tokenizer)))

    assert data[0] == "filedata"
    assert list(data[1]) == [("byteswaptest", 1)]

    parser.swap_endianness.assert_called_once()
    tokenizer.swap_endianness.assert_called_once()

import io

import pytest

from _roffio.tokenizer.combinators import one_of, repeated
from _roffio.tokenizer.common import tokenize_word


@pytest.mark.parametrize("inp_str", ["foo foo foo", "foo foo foobar"])
def test_combinators(inp_str):
    stream = io.StringIO(inp_str)

    foo_tokenizer = tokenize_word(stream, "foo", "foo")
    space_tokenizer = tokenize_word(stream, " ", " ")

    test_tokenizer = repeated(one_of(foo_tokenizer, space_tokenizer))()

    assert next(test_tokenizer).kind == "foo"
    assert next(test_tokenizer).kind == " "
    assert next(test_tokenizer).kind == "foo"
    assert next(test_tokenizer).kind == " "
    assert next(test_tokenizer).kind == "foo"
    with pytest.raises(StopIteration):
        next(test_tokenizer)

import hypothesis.strategies as st
from hypothesis import given

from _roffio.lazy_tuple import LazyTuple


@given(st.integers(), st.integers())
def test_values(a, b):
    lt = LazyTuple(lambda: a, lambda: b)

    assert len(lt) == 2

    c, d = lt

    assert c == a
    assert d == b

    assert lt[0] == a
    assert lt[1] == b

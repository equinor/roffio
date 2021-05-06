import hypothesis.strategies as st

keys = st.text(min_size=1, alphabet=st.characters(min_codepoint=36, max_codepoint=126))

tag_contents = st.dictionaries(
    keys,
    st.one_of(
        st.binary(min_size=1, max_size=1),
        st.booleans(),
        st.integers(min_value=-(2 ** 29), max_value=2 ** 29),
        st.floats(allow_infinity=False, allow_nan=False),
        keys,
    ),
)
roff_data = st.dictionaries(keys, tag_contents)

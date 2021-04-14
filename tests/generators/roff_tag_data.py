import hypothesis.strategies as st

keys = st.text(alphabet=st.characters(whitelist_categories=("Lu",)))

tag_contents = st.dictionaries(
    keys,
    st.one_of(
        st.binary(min_size=1, max_size=1),
        st.booleans(),
        st.integers(),
        st.floats(),
        keys,
    ),
)
roff_data = st.dictionaries(keys, tag_contents)

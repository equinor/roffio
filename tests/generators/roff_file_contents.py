import hypothesis.strategies as st

keywords = st.text(
    alphabet=st.characters(whitelist_categories=("Lu",)), min_size=1, max_size=10
)

simple_types = st.sampled_from(["char", "bool", "byte", "int", "float", "double"])


def tokenlen(kindstr):
    if kindstr == "bool":
        return 1
    elif kindstr == "byte":
        return 1
    elif kindstr == "int":
        return 4
    elif kindstr == "float":
        return 4
    elif kindstr == "double":
        return 8


@st.composite
def string_literals(draw):
    return '"' + draw(keywords) + '"'


@st.composite
def binary_string(draw, min_size=0, max_size=10, min_char=32, max_char=126):
    size = draw(st.integers(min_value=min_size, max_value=max_size))
    result = b""
    for _ in range(size):
        # Printable non-extended ascii characters are between 32 and 126
        result += draw(st.integers(min_value=min_char, max_value=max_char)).to_bytes(
            1, "little"
        )
    result += b"\0"
    return result


@st.composite
def binary_values(draw, kindstr):
    if kindstr == "char":
        return draw(binary_string())
    else:
        num_bytes = tokenlen(kindstr)
        return draw(st.binary(min_size=num_bytes, max_size=num_bytes))


ascii_values = st.builds(
    str,
    st.one_of(
        st.integers(min_value=-(2 ** 30), max_value=2 ** 30),
        st.floats(allow_infinity=False, allow_nan=False),
        string_literals(),
    ),
)


def typed_ascii_values(kindstr):
    if kindstr == "bool":
        return st.integers(min_value=0, max_value=1)
    elif kindstr == "byte":
        return st.integers(min_value=0, max_value=127)
    elif kindstr == "int":
        return st.integers(min_value=-(2 ** 30), max_value=2 ** 30)
    elif kindstr == "float":
        return st.floats(allow_infinity=False, allow_nan=False)
    elif kindstr == "double":
        return st.floats(allow_infinity=False, allow_nan=False)
    elif kindstr == "char":
        return string_literals()


whitespace = st.text(alphabet=st.characters(whitelist_categories="Z"), min_size=1)


@st.composite
def binary_simple_tag_keys(draw):
    element_type = draw(simple_types)
    tag_key_str = element_type.encode("ascii") + b"\0"
    tag_key_str += draw(binary_string(min_size=1, min_char=36))
    tag_key_str += draw(binary_values(element_type))
    return tag_key_str


@st.composite
def ascii_simple_tag_keys(draw):
    typ = draw(simple_types)
    tag_key_str = typ + draw(whitespace)
    tag_key_str += draw(keywords) + draw(whitespace)
    tag_key_str += str(draw(typed_ascii_values(typ)))
    return tag_key_str


@st.composite
def ascii_array_tag_keys(draw):
    tag_key_str = "array" + draw(whitespace)
    typ = draw(simple_types)
    tag_key_str += typ + draw(whitespace)
    tag_key_str += draw(keywords) + draw(whitespace)
    array_size = draw(st.integers(min_value=0, max_value=5))
    tag_key_str += str(array_size) + draw(whitespace)
    tag_key_str += " ".join(
        map(
            str,
            draw(
                st.lists(
                    typed_ascii_values(typ), min_size=array_size, max_size=array_size
                )
            ),
        )
    )
    return tag_key_str


@st.composite
def binary_array_tag_keys(draw):
    tag_key_str = b"array\0"
    element_type = draw(simple_types)
    tag_key_str += element_type.encode("ascii") + b"\0"
    tag_key_str += draw(binary_string(min_size=1, min_char=36))
    num_elements = draw(st.integers(min_value=0, max_value=25))
    tag_key_str += num_elements.to_bytes(4, "little")
    if element_type == "char":
        tag_key_str += b"".join(
            draw(
                st.lists(binary_string(), min_size=num_elements, max_size=num_elements)
            )
        )
    else:
        num_bytes = num_elements * tokenlen(element_type)
        tag_key_str += draw(st.binary(min_size=num_bytes, max_size=num_bytes))
    return tag_key_str


ascii_tag_keys = st.one_of(ascii_simple_tag_keys(), ascii_array_tag_keys())
binary_tag_keys = st.one_of(binary_simple_tag_keys(), binary_array_tag_keys())


@st.composite
def ascii_tag_groups(draw):
    tag_group_str = "tag" + draw(whitespace)
    if draw(st.booleans()):
        tag_group_str += "# comment #" + draw(whitespace)

    tag_group_str += draw(keywords) + draw(whitespace)
    tag_group_str += " ".join(draw(st.lists(ascii_tag_keys, max_size=5)))

    tag_group_str += draw(whitespace) + "endtag"
    return tag_group_str


@st.composite
def binary_tag_groups(draw):
    tag_group_str = b"tag\0"
    if draw(st.booleans()):
        tag_group_str += b"# comment #\0"

    tag_group_str += draw(binary_string(min_size=1, min_char=36))
    tag_group_str += b"".join(draw(st.lists(binary_tag_keys, max_size=5)))

    tag_group_str += b"endtag\0"
    return tag_group_str


@st.composite
def ascii_bodies(draw):
    return " ".join(draw(st.lists(ascii_tag_groups(), max_size=5)))


@st.composite
def binary_bodies(draw):
    return b"".join(draw(st.lists(binary_tag_groups(), max_size=5)))


@st.composite
def ascii_file_contents(draw):
    file_str = "roff-asc" + draw(whitespace)
    if draw(st.booleans()):
        file_str += "# comment #" + draw(whitespace)
    file_str += draw(ascii_bodies())
    return file_str


@st.composite
def binary_file_contents(draw):
    file_str = b"roff-bin\0"
    if draw(st.booleans()):
        file_str += b"# comment #\0"
    file_str += draw(binary_bodies())
    return file_str

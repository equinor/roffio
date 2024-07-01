import pathlib
import warnings
from collections import OrderedDict
from datetime import datetime
from enum import Enum, unique
from functools import wraps

import numpy as np

from roffio.version import version as roffio_version


class RoffWriteError(Exception):
    pass


def type_string(value):
    if isinstance(value, str):
        return "char"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, bytes):
        return "byte"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "double"
    try:
        return numpy_to_roff_dtype(value.dtype)
    except AttributeError as err:
        raise ValueError(f"Could not find suitable roff type for {value}") from err


def numpy_to_roff_dtype(dtyp):
    if np.issubdtype(dtyp, np.bool_):
        return "bool"
    if np.issubdtype(dtyp, np.int8) or np.issubdtype(dtyp, np.uint8):
        return "byte"
    if np.issubdtype(dtyp, np.integer):
        return "int"
    if np.issubdtype(dtyp, np.float32):
        return "float"
    if np.issubdtype(dtyp, np.double):
        return "double"
    raise ValueError(f"Could not find suitable roff type for numpy type {dtyp}")


def takes_stream(i, mode):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if (
                len(args) > i
                and args[i] is not None
                and isinstance(args[i], (str, pathlib.Path))
            ):
                with open(args[i], mode) as f:
                    return func(*args[:i], f, *args[i + 1 :], **kwargs)
            else:
                return func(*args, **kwargs)

        return wrapper

    return decorator


def cast_to_roff(value, type_str):
    if type_str == "bool":
        return np.byte(value)
    if type_str == "byte":
        return value
    if type_str == "int":
        return np.int32(value)
    if type_str == "float":
        return np.float32(value)
    if type_str == "double":
        return np.float64(value)


def cast_array_to_roff(value):
    if value.dtype in [np.bool_, np.int32, np.uint8, np.float32, np.float64]:
        return value
    elif value.dtype == np.int8:
        result_dtype = np.uint8
    elif np.issubdtype(value.dtype, np.integer):
        result_dtype = np.int32
    elif np.issubdtype(value.dtype, np.floating):
        result_dtype = np.float64
    else:
        raise ValueError(f"Cannot cast {value.dtype} to a roff type")

    warnings.warn(
        f"casting array dtype {value.dtype} to {result_dtype}",
        stacklevel=1,
    )
    return value.astype(result_dtype)


def write_binary_string(stream, string):
    if "\0" in string:
        raise RoffWriteError(
            "char values, tag names and key names "
            "cannot contain zero-character in binary roff-format.\n"
            f"Found {string}"
        )
    stream.write(string.encode("ascii"))
    stream.write(b"\0")


def write_binary_value(stream, value, type_str):
    if isinstance(value, str):
        write_binary_string(stream, value)
    elif type_str == "byte" and isinstance(value, bytes):
        stream.write(value)
    else:
        stream.write(cast_to_roff(value, type_str).tobytes())


def write_ascii_value(stream, value, type_str):
    if isinstance(value, str):
        stream.write(f'"{value}"')
    elif type_str == "byte" and isinstance(value, bytes):
        if len(value) != 1:
            raise RoffWriteError(
                "Bytes in roff format must have length 1 " f"found {value}"
            )
        stream.write(str(int.from_bytes(value, "little")))
    elif type_str == "bool" and isinstance(value, bool):
        stream.write(str(int(value)))
    else:
        stream.write(str(value))


def write_binary_tagkey(file_stream, tagkey_name, value):
    if type(value) is np.ndarray:
        file_stream.write(b"array\0")
        value = cast_array_to_roff(value)
        file_stream.write(numpy_to_roff_dtype(value.dtype).encode("ascii"))
        file_stream.write(b"\0")
        write_binary_string(file_stream, tagkey_name)
        file_stream.write(len(value).to_bytes(4, "little"))
        file_stream.write(value.tobytes())
    elif isinstance(value, bytes) and len(value) > 1:
        # Iterating over bytes gives ints so
        # becomes a special case
        file_stream.write(b"array\0byte\0")
        write_binary_string(file_stream, tagkey_name)
        file_stream.write(len(value).to_bytes(4, "little"))
        file_stream.write(value)
    elif is_array_type(value):
        iterator = iter(value)
        try:
            first_value = next(iterator)
        except StopIteration:
            file_stream.write(b"array\0byte\0")
            write_binary_string(file_stream, tagkey_name)
            file_stream.write(b"\x00\x00\x00\x00")
        else:
            type_str = type_string(first_value)
            file_stream.write(b"array\0")
            file_stream.write(type_str.encode("ascii"))
            file_stream.write(b"\0")
            write_binary_string(file_stream, tagkey_name)
            file_stream.write(len(value).to_bytes(4, "little"))
            write_binary_value(file_stream, first_value, type_str)
            for val in iterator:
                if type_str != type_string(val):
                    raise RoffWriteError(
                        "Roff only allows homogenous arrays"
                        f", found {type_string(value)} in {type_str} array"
                    )
                write_binary_value(file_stream, val, type_str)
    else:
        type_str = type_string(value)
        file_stream.write(type_str.encode("ascii"))
        file_stream.write(b"\0")
        write_binary_string(file_stream, tagkey_name)
        write_binary_value(file_stream, value, type_str)


@takes_stream(0, "wb")
def write_binary_roff(file_stream, values):
    file_stream.write(b"roff-bin\0")
    file_stream.write(b"#ROFF file#\0")
    file_stream.write(f"#Creator: roffio, version {roffio_version}#".encode("ascii"))
    file_stream.write(b"\0")

    values_list = values.items() if hasattr(values, "items") else iter(values)

    for tag_name, tag_keys in values_list:
        file_stream.write(b"tag\0")
        write_binary_string(file_stream, tag_name)

        if hasattr(tag_keys, "items"):
            tag_keys_list = tag_keys.items()
        else:
            tag_keys_list = iter(tag_keys)

        for tagkey_name, value in tag_keys_list:
            write_binary_tagkey(file_stream, tagkey_name, value)

        file_stream.write(b"endtag\0")


def is_array_type(value):
    return (
        not (isinstance(value, bytes) and len(value) == 1)
        and not isinstance(value, str)
        and hasattr(value, "__iter__")
    )


def check_valid_ascii_name(name):
    if len(name) == 0:
        raise RoffWriteError("Names in roff ascii format cannot have 0 length.")
    if any(c.isspace() for c in name):
        raise RoffWriteError(
            f"Names in roff ascii format cannot contain space. found '{name}'"
        )
    if any(c == "#" for c in name):
        raise RoffWriteError(
            f"Names in roff ascii format cannot contain '#'. found '{name}'"
        )


def write_ascii_tagkey(file_stream, tagkey_name, value):
    check_valid_ascii_name(tagkey_name)
    if is_array_type(value):
        iterator = iter(value)
        try:
            first_value = next(iterator)
        except StopIteration:
            file_stream.write(f"array byte {tagkey_name} 0\n")
        else:
            typ_str = type_string(first_value)
            if isinstance(value, bytes):
                typ_str = "byte"
            file_stream.write(f"array {typ_str} {tagkey_name} {len(value)}\n")
            write_ascii_value(file_stream, first_value, typ_str)
            file_stream.write("\n")
            for v in iterator:
                if typ_str != type_string(v) and not isinstance(value, bytes):
                    raise RoffWriteError(
                        "Roff only allows homogenous arrays"
                        f", found {type_string(v)} in {typ_str} array"
                    )
                write_ascii_value(file_stream, v, typ_str)
                file_stream.write("\n")
    else:
        typ_str = type_string(value)
        file_stream.write(f"{typ_str} {tagkey_name} ")
        write_ascii_value(file_stream, value, typ_str)
        file_stream.write("\n")


@takes_stream(0, "w")
def write_ascii_roff(file_stream, values):
    file_stream.write("roff-asc\n")
    file_stream.write("#ROFF file#\n")
    file_stream.write(f"#Creator: roffio, version {roffio_version}#\n")

    values_list = values.items() if hasattr(values, "items") else iter(values)

    for tag_name, tag_keys in values_list:
        file_stream.write(f"tag {tag_name}\n")
        check_valid_ascii_name(tag_name)

        if hasattr(tag_keys, "items"):
            tag_keys_list = tag_keys.items()
        else:
            tag_keys_list = iter(tag_keys)

        for tagkey_name, value in tag_keys_list:
            write_ascii_tagkey(file_stream, tagkey_name, value)

        file_stream.write("endtag\n")


@unique
class Format(Enum):
    BINARY = 1
    ASCII = 2


def roff_metadata():
    return OrderedDict(
        [
            (
                "filedata",
                {
                    "byteswaptest": 1,
                    "creationDate": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                },
            ),
            ("version", {"major": 2, "minor": 0}),
        ]
    )


def write(filelike, values, roff_format=Format.BINARY):
    """
    Writes the given values to the file.
    :param filelike: A file-like object, (string to path, pathlib.Path or opened stream).
    :param roff_format: The roff-format for the file, defaults to Format.BINARY.
    :param values: Double level dictionary of tag-names and tag-key to values. Can
        also be given iterable of touples (both for tag and tag-keys) which
        enables multiple keys with same name.
    """
    metadata_values = roff_metadata()

    values_list = list(values.items()) if hasattr(values, "items") else list(values)

    for k, v in values_list:
        if k in metadata_values:
            metadata_values[k].update(v)

    values_list = list(
        filter(lambda p: p[0] not in metadata_values and p[0] != "eof", values_list)
    )

    if (
        metadata_values["version"]["major"] != 2
        or metadata_values["version"]["minor"] != 0
    ):
        raise ValueError(
            "Cannot change roff file version in values given to roffio.write!"
        )

    if set(metadata_values["version"].keys()) != {"major", "minor"}:
        raise ValueError(
            "No additional fields in the version tag is permitted, "
            f"found {values['filedata']['version'].keys()}"
        )

    if metadata_values["filedata"]["byteswaptest"] != 1:
        raise ValueError(
            "It is not possible to set the byteswaptest value in roffio.write"
            f", found value {values['filedata']['byteswaptest']}."
            "\nUse the endianess parameter to set endianess."
        )

    if roff_format == Format.BINARY:
        write_binary_roff(
            filelike, list(metadata_values.items()) + values_list + [("eof", {})]
        )
    else:
        write_ascii_roff(
            filelike, list(metadata_values.items()) + values_list + [("eof", {})]
        )

import pathlib
from collections import defaultdict
from contextlib import contextmanager

import _roffio.parser as roffparse
import _roffio.tokenizer as rofftok
from _roffio.endianess_handler import EndianessHandler
from _roffio.tokenizer.errors import WrongFileModeError


def read(filelike):
    """
    Reads a roff file and returns a dictionary of values,
    ie. values = read("/my/file.roff")

    The value of in the tag 'tag-name' and tag-key 'key-name'
    is found at values['tag-name']['key-name']. Note that at
    any level the value can be a list signifying that there was
    more than one tag/key with that value.

    """
    result = defaultdict(list)
    with lazy_read(filelike) as roff_iter:
        for tag_name, tag_group in roff_iter:
            result_tagkey = defaultdict(list)
            for tagkey_name, value in tag_group:
                result_tagkey[tagkey_name].append(value)
            result[tag_name].append(result_tagkey)

    for tag_name, tag_groups in list(result.items()):
        for i, tag_group in enumerate(list(tag_groups)):
            for key_name, values in list(tag_group.items()):
                if len(values) == 1:
                    tag_group[key_name] = values[0]
            result[tag_name][i] = dict(tag_group)
        if len(tag_groups) == 1:
            result[tag_name] = tag_groups[0]

    return dict(result)


def make_filestream(filelike):
    file_stream = open(filelike, "rb")
    tokenizer = rofftok.RoffTokenizer(file_stream)
    try:
        next(iter(tokenizer))
        file_stream.seek(0)
    except WrongFileModeError:
        file_stream.close()
        file_stream = open(filelike, "rt")

    return file_stream


@contextmanager
def lazy_read(filelike):
    file_stream = filelike
    did_open = False
    if isinstance(filelike, (str, pathlib.Path)):
        did_open = True

        file_stream = make_filestream(filelike)

    tokenizer = rofftok.RoffTokenizer(file_stream)
    parser = roffparse.RoffParser(iter(tokenizer), file_stream)

    yield iter(EndianessHandler(parser, tokenizer))

    if did_open:
        file_stream.close()

import warnings


class RoffFormatError(Exception):
    """
    Raised when reading a roff file with unexpected contents.
    """

    pass


class EndianessHandler:
    """
    An iterator that consumes from RoffParser and handles setting
    the endianess according to the byteswaptest tagkey in the
    filedata tag.

    If filedata tag is not first tag, a warning is emitted.
    """

    def __init__(self, roff_parser, roff_tokenizer):
        self.roff_parser = roff_parser
        self.roff_tokenizer = roff_tokenizer
        self.found_byteswaptest = False
        self.has_warned = False

    def check_endianess(self, tag):
        """
        If given the filedata tag, check for byteswaptest tagkey
        and set endianess of parser and tokenizer accordingly.
        """
        if tag[0] == "filedata":
            if self.found_byteswaptest:
                raise RoffFormatError("Roff file has duplicate filedata tags.")

            tagkeys = dict(list(tag[1]))
            if "byteswaptest" not in tagkeys:
                raise RoffFormatError(
                    "Roff file tag filedata is missing byteswapttest tagkey."
                )

            self.found_byteswaptest = True
            if tagkeys["byteswaptest"] != 1:
                self.roff_parser.swap_endianess()
                self.roff_tokenizer.swap_endianess()
                tagkeys["byteswaptest"] = 1
            return (tag[0], tagkeys.items())
        if (
            not self.found_byteswaptest
            and not self.has_warned
            and self.roff_parser.is_binary_file
        ):
            self.has_warned = True
            warnings.warn(
                "First tag of file is not filedata, "
                f"default endianess {self.roff_parser.endianess}-endian is used "
                "without checking 'byteswaptest' field."
            )
        return tag

    def __iter__(self):
        roff_iterator = iter(self.roff_parser)
        while True:
            try:
                tag = next(roff_iterator)
                new_tag = self.check_endianess(tag)
                yield new_tag
            except StopIteration:
                return

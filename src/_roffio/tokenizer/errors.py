class TokenizationError(Exception):
    """
    A tokenizer will throw a TokenizationError if the expected token
    is not found at the start of the stream (however, it could be that
    any other valid roff token not covered by that tokenizer is at the
    start of the stream).
    """

    pass


class WrongFileModeError(Exception):
    """
    Thrown when a binary roff file is opened in text mode or
    a ascii roff file is opened in binary mode.
    """

    pass

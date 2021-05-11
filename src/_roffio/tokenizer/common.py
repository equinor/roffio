from _roffio.tokenizer.errors import TokenizationError
from _roffio.tokenizer.token import Token


def tokenize_word(stream, word, kind):
    """
    Token combinator for fixed word tokens, ie. when the stream contains 'tag'
    tokenize_word('tag', TokenKind.TAG) will yield Token(kind=TokenKind.TAG, 0,
    3).

    :returns: Tokenizer for the given word, yielding a token
        of the given kind.
    :param word: Any word to be matched by the tokenizer.
    :param kind: The kind of token yielded by the tokenizer.
    """
    word_len = len(word)

    def word_tokenizer():
        start = stream.tell()

        token = stream.read(word_len)
        if token == word:
            end = stream.tell()
            yield Token(kind, end - word_len, end)
        else:
            stream.seek(start)
            raise TokenizationError(f"Token {repr(token)} did not match {word}")

    return word_tokenizer

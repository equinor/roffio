from _roffio.tokenizer.errors import TokenizationError


def bind(*tokenizers):
    def result():
        for tok in tokenizers:
            yield from tok()

    return result


def one_of(*tokenizers):
    """
    Combinator for tokenizers.

    :param tokenizers: List of tokenizers.
    :returns: A tokenizer that yields tokens from the
    first tokenizer in tokenizers that succeeds.
    """

    def one_of_tokenizer():
        did_yield = False
        errors = []
        for tok in tokenizers:
            try:
                yield from tok()
                did_yield = True
                break
            except TokenizationError as err:
                errors.append(str(err))

        if not did_yield:
            raise TokenizationError(
                "Tokenization failed, due to one of\n*" + ("\n*".join(errors))
            )

    return one_of_tokenizer


def repeated(tokenizer):
    """
    Combinator for tokenizer.
    :param tokenizer: Any tokenizer.
    :returns: Tokenizer that applies the tokenizer zero or more times, until it
        fails.
    """

    def repeated_tokenizer():
        try:
            while True:
                yield from tokenizer()
        except TokenizationError:
            pass

    return repeated_tokenizer

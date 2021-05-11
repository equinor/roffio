"""
In this module, a tokenizer is a generator that takes a stream and generates
tokens. If an error occurs, the function winds back the stream to the position
to where it started generating and raises an Error.

Token combinator is any function which returns a tokenizer.

As the ROFF format is simple (LL(1)), we only require backtracking capabilities
when errors occurr for at most one token. This means that there is no
bookkeeping of backtracking points.

The roff format does not specify endianess although the filedata tag contains
the byteswaptest tagkey which can be used to determine what endianess the file
was created with. In order to correctly tokenize arrays, the correct ednianess
has to be given to RoffTokenizer. However, RoffTokenizer does not parse the
byteswaptest tagkey, instead it is possible to at any time change the endianess
used for tokenization, see RoffTokenizer.

For binary roff files, the tokenizers have to be given a byte stream. For ascii
roff files, both text streams has to be given.
"""

from .roff_tokenizer import RoffTokenizer

__all__ = ["RoffTokenizer"]

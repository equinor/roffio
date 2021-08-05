from enum import Enum, auto, unique


@unique
class TokenKind(Enum):
    ROFF_ASC = auto()
    ROFF_BIN = auto()
    TAG = auto()
    ENDTAG = auto()
    STRING_LITERAL = auto()
    NUMERIC_VALUE = auto()
    BINARY_NUMERIC_VALUE = auto()
    NAME = auto()
    CHAR = auto()
    BOOL = auto()
    BYTE = auto()
    INT = auto()
    FLOAT = auto()
    DOUBLE = auto()
    ARRAY = auto()
    ARRAYBLOB = auto()

    @classmethod
    def simple_types(cls):
        return (
            cls.CHAR,
            cls.BOOL,
            cls.BYTE,
            cls.INT,
            cls.FLOAT,
            cls.DOUBLE,
        )

    @classmethod
    def keywords(cls):
        return {
            cls.ROFF_BIN: "roff-bin",
            cls.ROFF_ASC: "roff-asc",
            cls.TAG: "tag",
            cls.ENDTAG: "endtag",
            cls.CHAR: "char",
            cls.BOOL: "bool",
            cls.BYTE: "byte",
            cls.INT: "int",
            cls.FLOAT: "float",
            cls.DOUBLE: "double",
            cls.ARRAY: "array",
        }

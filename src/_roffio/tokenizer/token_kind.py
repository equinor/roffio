from enum import Enum, unique


@unique
class TokenKind(Enum):
    ROFF_ASC = 1
    ROFF_BIN = 2
    TAG = 3
    ENDTAG = 4
    STRING_LITERAL = 5
    NUMERIC_VALUE = 6
    BINARY_NUMERIC_VALUE = 7
    NAME = 8
    CHAR = 10
    BOOL = 11
    BYTE = 12
    INT = 13
    FLOAT = 14
    DOUBLE = 15
    ARRAY = 16
    ARRAYBLOB = 17

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

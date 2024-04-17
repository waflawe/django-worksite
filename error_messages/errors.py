from enum import EnumMeta, StrEnum
from typing import NamedTuple


class E(NamedTuple):
    message: str
    code: str


class ErrorsMeta(EnumMeta):
    def __getitem__(self, item: str):
        attribute = f"INVALID_{item.upper()}"
        message: str = getattr(self, attribute, None)
        return E(message, attribute)


class BaseErrorsEnum(StrEnum, metaclass=ErrorsMeta):
    pass

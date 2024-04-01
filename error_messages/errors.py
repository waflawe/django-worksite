from enum import EnumMeta, StrEnum
from typing import NamedTuple


class E(NamedTuple):
    message: str
    code: str


class ErrorsMeta(EnumMeta):
    def __getitem__(self, item):
        attribute = f"INVALID_{item.upper()}"
        return E(getattr(self, attribute, None), attribute)


class BaseErrorsEnum(StrEnum, metaclass=ErrorsMeta):
    pass

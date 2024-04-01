from enum import EnumMeta
from typing import NamedTuple


class E(NamedTuple):
    message: str
    code: str


class ErrorsMeta(EnumMeta):
    def __getitem__(self, item):
        attribute = f"INVALID_{item.upper()}"
        return E(getattr(self, attribute, None), attribute)

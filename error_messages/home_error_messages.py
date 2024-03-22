from enum import StrEnum
from error_messages.errors_meta import ErrorsMeta


class SettingsErrors(StrEnum, metaclass=ErrorsMeta):
    INVALID_TIMEZONE = "Неверная временная зона."
    INVALID_APPLICANT_AVATAR = "Неверная аватарка."
    INVALID_COMPANY_LOGO = "Неверный логотип компании."
    INVALID_COMPANY_DESCRIPTION = "Неверная длина описания компании."
    INVALID_COMPANY_SITE = "Неверный сайт компании."

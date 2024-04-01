from error_messages.errors import BaseErrorsEnum


class SettingsErrors(BaseErrorsEnum):
    INVALID_TIMEZONE = "Неверная временная зона."
    INVALID_APPLICANT_AVATAR = "Неверная аватарка."
    INVALID_COMPANY_LOGO = "Неверный логотип компании."
    INVALID_COMPANY_DESCRIPTION = "Неверная длина описания компании."
    INVALID_COMPANY_SITE = "Неверный сайт компании."

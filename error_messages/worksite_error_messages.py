from error_messages.errors import BaseErrorsEnum


class VacancyErrors(BaseErrorsEnum):
    INVALID_ID = "Неверный id вакансии."
    INVALID_NAME = "Неверная длина названия вакансии."
    INVALID_DESCRIPTION = "Неверная длина описания вакансии."
    INVALID_MONEY = "Неверная зарплата."
    INVALID_EXPERIENCE = "Неверный требуемый опыт работы."
    INVALID_CITY = "Неверный город."
    INVALID_SKILLS = "Неверные навыки."


class OfferErrors(BaseErrorsEnum):
    INVALID_RESUME = "Неверный файл с резюме."
    INVALID_RESUME_TEXT = "Неверная длина письменного резюме."
    INVALID_VACANCY = "Резюме должно быть в одном поле."


class RatingErrors(BaseErrorsEnum):
    INVALID_RATING = "Неверная оценка компании."
    INVALID_COMMENT = "Неверная длина комментария."

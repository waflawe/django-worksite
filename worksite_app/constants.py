import pickle

# Варианты требуемого для соискателя опыта работы.
# Выбираются при создании вакансии.

EXPERIENCE_CHOICES = [("0", "не требуется"), ("1", "1 год"), ("2", "1-3 лет"), ("3", "3-5 лет"), ("4", "5+ лет")]

# Варианты оценок компании соискателями.
# Выбираются при создании отзыва на компанию соискателем.

RATINGS = [(1, "1"), (2, "2"), (3, "3"), (4, "4"), (5, "5")]

_pickle_cities = pickle.load(open("worksite_app/data/filtered_cities.txt", "rb"))
_pickle_cities.insert(0, "Любой")

# Город, в котором активна вакансия.
# Выбирается при создании новой вакансии.

FILTERED_CITIES = _pickle_cities

# Допускаемые значения в БД для EXPERIENCE_CHOICES.

EXPERIENCE_CHOICES_VALID_VALUES = [i[0] for i in EXPERIENCE_CHOICES]

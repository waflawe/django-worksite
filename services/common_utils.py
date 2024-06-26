from typing import Any, Literal, NamedTuple, Optional, TypeAlias

from django.conf import settings
from django.contrib.auth.models import AnonymousUser, User
from django.core.cache import cache
from django.http import HttpRequest

from error_messages.errors import E
from home_app.models import ApplicantSettings, CompanySettings

UserSettings: TypeAlias = CompanySettings | ApplicantSettings


class RequestHost(object):
    """Класс для обозначения источника запроса (вьюшка или апи-вьюшка)."""

    APIVIEW = "APIVIEW"
    VIEW = "VIEW"


def check_is_user_auth(request: HttpRequest) -> bool:
    return request.user.is_authenticated


def check_is_user_company(user: User | AnonymousUser) -> bool:
    try:
        return user.first_name != ""
    except AttributeError:
        return False


def get_user_settings(user: User | AnonymousUser | UserSettings) -> Literal[False] | UserSettings:
    if isinstance(user, (ApplicantSettings, CompanySettings)):
        return user
    if not user.is_authenticated:
        return False
    cache_settings_name = f"{user.pk}{settings.CACHE_NAMES_DELIMITER}{settings.USER_SETTINGS_CACHE_NAME}"
    user_settings = cache.get(cache_settings_name)
    if not user_settings:
        if check_is_user_company(user):
            user_settings = CompanySettings.objects.select_related("company").get(company=user)
        else:
            user_settings = ApplicantSettings.objects.select_related("applicant").get(applicant=user)
        cache.set(cache_settings_name, user_settings, 60 * 60 * 24 * 7)
    return user_settings


def get_timezone(user: User | AnonymousUser | UserSettings) -> Literal[False] | str:
    """Возвращает выбранную в настройках временную зону пользователя."""

    user_settings = get_user_settings(user)
    if not user_settings:
        return False
    return user_settings.timezone


def get_path_to_crop_photo(path: str) -> str:
    """Функция для формирования пути до центрированного изображения по пути исходного."""

    splitted_path = path.split("/")
    filename = splitted_path.pop()
    name, extension = filename.split(".")
    splitted_path.append(f"{name}_crop.{extension}")
    return "/".join(splitted_path)


def get_error_field(request_host: RequestHost, v: Any) -> str:
    """Получение поля, которое связано с ошибкой в валидаторе."""

    is_view = request_host == RequestHost.VIEW
    return list(v.errors.as_data().keys())[0] if is_view else v.errors.popitem(last=False)[0]


class DefaultPOSTReturn(NamedTuple):
    """Структура данных, возвращающаяся в миксинах с POST запросами."""

    status: Any | Literal[False]
    error: Optional[E] = None

from django.http import HttpRequest
from rest_framework.request import Request
from django.contrib.auth.models import User

from error_messages.errors import E
from home_app.models import CompanySettings, ApplicantSettings

from typing import Literal, Any, NamedTuple, Optional


class RequestHost(object):
    """ Класс для обозначения источника запроса (вьюшка или апи-вьюшка). """

    APIVIEW = "APIVIEW"
    VIEW = "VIEW"


def check_is_user_auth(request: HttpRequest) -> bool:
    return request.user.is_authenticated


def check_is_user_company(user: User) -> bool:
    try:
        return user.first_name != ""
    except AttributeError:
        return False


def get_timezone(request: HttpRequest | Request) -> Literal[False] | str:
    """ Возвращает выбранную в настройках временную зону пользователя. """

    if check_is_user_auth(request):
        if check_is_user_company(request.user):
            return CompanySettings.objects.get(company=request.user).timezone
        else:
            return ApplicantSettings.objects.get(applicant=request.user).timezone
    return False


def get_path_to_crop_photo(path: str) -> str:
    """ Функция для формирования пути до центрированного изображения по пути исходного. """

    splitted_path = path.split("/")
    filename = splitted_path.pop()
    name, extension = filename.split(".")
    splitted_path.append(f"{name}_crop.{extension}")
    return "/".join(splitted_path)


def get_error_field(request_host: RequestHost, v: Any) -> str:
    """ Получение поля, которое связано с ошибкой в валидаторе. """

    is_view = request_host == RequestHost.VIEW
    return list(v.errors.as_data().keys())[0] if is_view else v.errors.popitem(last=False)[0]


class DefaultPOSTReturn(NamedTuple):
    """ Структура данных, возвращающаяся в миксинах с POST запросами. """

    status: bool
    error: Optional[E] = None

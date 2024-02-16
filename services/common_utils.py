from django.http import HttpRequest, Http404
from rest_framework.request import Request
from django.contrib.auth.models import User

from home_app.models import CompanySettings, ApplicantSettings

from typing import Literal

Error_code = int


class RequestHost(object):
    APIVIEW = "API"
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

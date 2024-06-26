from __future__ import annotations

import os
from random import randrange
from typing import Callable, List, Literal, NamedTuple, NoReturn, Optional, Tuple, TypeAlias

from django.conf import settings
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.db.models.fields.files import ImageFieldFile
from django.db.models.query import QuerySet
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse

from home_app.models import ApplicantSettings, CompanySettings
from services.common_utils import (
    RequestHost,
    check_is_user_company,
    get_path_to_crop_photo,
    get_timezone,
    get_user_settings,
)
from services.worksite_app_mixins import (
    AddOfferMixin,
    AddRatingMixin,
    AddVacancyMixin,
    ApplyOfferMixin,
    CheckPermissionsToSeeVacancy,
    CheckPermissionsToSeeVacancyOffersAndDeleteVacancy,
    CompanyApplyedOffersMixin,
    DeleteVacancyMixin,
    VacancyFilterMixin,
    VacancySearchMixin,
    WithdrawOfferMixin,
    get_company_ratings,
)
from worksite_app.constants import EXPERIENCE_CHOICES, FILTERED_CITIES
from worksite_app.forms import AddOfferForm, AddRatingForm, AddVacancyForm
from worksite_app.models import Offer, Rating, Vacancy

Context = dict
num = 100000

UserSettings: TypeAlias = ApplicantSettings | CompanySettings
LogoLengthParam: TypeAlias = Optional[int | float | Literal[False]]


class CompanyData(NamedTuple):
    """Структура данных для отображения информации о компании в шаблоне."""

    company_rating: Optional[int | float] = None
    company_logo_path: Optional[str | Literal[False]] = None
    company_logo_w: LogoLengthParam = None
    company_logo_h: LogoLengthParam = None
    company_reviews_count: Optional[int] = None
    company_star_classes_list: Optional[List[str]] = None


class VacancyRenderObject(NamedTuple):
    """Структура данных для отображения информации о вакансии в шаблоне."""

    obj: Vacancy
    experience: str = ""
    city: str = ""
    skills: Optional[List] = None
    company_data: Optional[CompanyData] = None


class OfferRenderObject(NamedTuple):
    """Структура данных для отображения информации об оффере соискателя в шаблоне."""

    obj: Offer
    path_to_applicant_avatar: Optional[str] = None


class RatingRenderObject(NamedTuple):
    """Структура данных для отображения информации об отзыве соискателя на компанию в шаблоне."""

    obj: Rating
    path_to_applicant_avatar: Optional[str] = None
    star_classes: Optional[List] = None


class OffsetButton(NamedTuple):
    """Класс для хранения нужной HTML кнопке переключения оффсета информации."""

    offset: int
    view_button: bool

    def __str__(self):
        return str(self.offset)

    def __sub__(self, other):
        return self.offset - other

    def __index__(self):
        return self.offset


class ObjectsAndOffsets(NamedTuple):
    objects: QuerySet
    offset: int
    offset_next: OffsetButton
    offset_back: OffsetButton


def _get_experience(vacancy: Vacancy) -> str:
    return EXPERIENCE_CHOICES[int(vacancy.experience)][1]


def _get_offset(request: HttpRequest, objects: QuerySet[Vacancy | Rating]) -> int:
    """Получение оффсета для вакансий или отзывов на компанию."""

    try:
        offset = int(request.GET.get("offset", 0))
        if offset % 20 != 0 or offset > len(objects) or offset < 0:
            offset = 0
    except ValueError:
        offset = 0
    return offset


def _check_is_company_logo_default(user_settings: CompanySettings) -> str | Literal[False]:
    return (
        str(user_settings.company_logo)
        if str(user_settings.company_logo) == settings.DEFAULT_COMPANY_LOGO_FILENAME
        else False
    )


def _get_validated_width_and_height(image: ImageFieldFile, size: int) -> Tuple[int | float, int | float]:
    """Функция для получения правильных длины и ширины логотипа компании для рендеринга в шаблон."""

    w, h = image.width, image.height
    huges = sorted((w, h), reverse=True)
    res = huges[1] / huges[0]
    return (size * res, size) if huges[0] == h else (size, size * res)


def _get_logo_path_and_params(
    user_settings: CompanySettings, size: int, company: User
) -> Tuple[str, int | float, int | float]:
    """Функция для получения правильного пути до логотипа компании, его длины и ширины для рендеринга в шаблон."""

    flag = _check_is_company_logo_default(user_settings)
    if flag:
        return flag, size, size
    w, h = _get_validated_width_and_height(user_settings.company_logo, size)
    path_to_company_custom_logo_dir = f"{settings.CUSTOM_COMPANY_LOGOS_DIR}/{company.pk}/"
    filename = os.listdir(settings.BASE_DIR / settings.MEDIA_ROOT / path_to_company_custom_logo_dir)[0]
    return f"{path_to_company_custom_logo_dir}{filename}", w, h


def _get_rounded_rating(rating: float) -> int | float:
    if rating == 0:
        return 0
    elif rating < 1:
        q = rating * 10
        if q == 5:
            return 5
        elif q < 5:
            return 0
        elif q > 5:
            return 10
    q = rating * 10
    if int(str(q)[1]) == 0 or int(str(q)[1]) == 5:
        return q
    elif int(str(q)[1]) < 5:
        return int(str(q)[0] + "0")
    return int(str(int(str(q)[0]) + 1) + "0")


def _get_star_classes_list(rating: float) -> List[str]:
    """Функция для получения CSS классов звезд рейтинга компании."""

    classes = []
    c = _get_rounded_rating(rating)
    for i in range(5, int(c) + 1, 10):
        if i != int(c):
            classes.append("fa-star")
        else:
            classes.append("fa-star-half-o")
    while len(classes) < 5:
        classes.append("fa-star-o")
    return classes


def _get_company_data(company: User, size: int, fields: Optional[Tuple] = None) -> CompanyData:
    """
    Функция для получения различной информации о компании для рендеринга.
    (рейтинг компании, информация о логотипе и CSS классах звезд рейтинга)
    """

    company_s: CompanySettings = get_user_settings(company)
    if not fields:
        fields = ("rating", "logo", "ratings_count", "classes_list")
    path_to_custom_logo, weight, height = (
        _get_logo_path_and_params(company_s, size, company) if "logo" in fields else (None, None, None)
    )
    return CompanyData(
        company_s.rating if "rating" in fields else None,
        path_to_custom_logo,
        weight,
        height,
        get_company_ratings(company).count() if "ratings_count" in fields else None,
        _get_star_classes_list(company_s.rating) if "classes_list" in fields else None,
    )


def _get_queryset(
    request: HttpRequest, queryset: QuerySet[Vacancy | Rating], queryset_hadler: Callable
) -> ObjectsAndOffsets:
    """Функция для преобразования QuerySet'a к готовому для рендеринга виду."""

    queryset = queryset_hadler(queryset)
    offset = _get_offset(request, queryset)
    offset_next = OffsetButton(offset + 20, len(queryset[offset + 20 :]) > 0)
    offset_back = OffsetButton(offset - 20, len(queryset[:offset]) > 0)
    return ObjectsAndOffsets(queryset, offset, offset_next, offset_back)


def vacancys_queryset_handler(vacancys: QuerySet):
    return tuple(
        VacancyRenderObject(v, _get_experience(v), company_data=_get_company_data(v.company, 200, ("logo",)))
        for v in vacancys
    )


def _get_path_to_applicant_avatar(applicant: User) -> str:
    """Функция для получения пути к аватару соискателя."""

    applicant_settings: ApplicantSettings = get_user_settings(applicant)
    avatar = applicant_settings.applicant_avatar
    if str(avatar) == settings.DEFAULT_APPLICANT_AVATAR_FILENAME:
        return str(avatar)
    return get_path_to_crop_photo(str(avatar))


def _get_context(request: HttpRequest, **kwargs) -> Context:
    """Удобное получение базового контекста."""

    context: Context = Context({"offset_params": {}})
    company: User | Literal[None] = kwargs.get("company", None)

    if kwargs.get("queryset", None):
        alias = kwargs["queryset_context_alias"]
        queryset_data = _get_queryset(request, kwargs["queryset"], kwargs["queryset_handler"])
        context[alias] = queryset_data.objects if len(queryset_data.objects) > 0 else tuple()
        context["offset_params"]["offset"] = queryset_data.offset
        context["offset_params"]["offset_next"] = queryset_data.offset_next
        context["offset_params"]["offset_back"] = queryset_data.offset_back
        context[alias] = context[alias][queryset_data.offset : queryset_data.offset_next]
    context["any_random_integer"] = randrange(num) if kwargs.get("any_random_integer", None) else None
    context["company_data"] = _get_company_data(company, kwargs["size"]) if company else None
    context["show_success"] = request.GET.get("show_success", None)
    context["tzone"] = get_timezone(request.user) if kwargs.get("tzone", None) else None
    context["offset_params"]["city"] = request.GET.get("city", None)
    return context


class HomeViewUtils(VacancyFilterMixin, VacancySearchMixin):
    def home_utils(self, request: HttpRequest) -> Context:
        filter_kwargs = self.filter(request.GET)
        search_query = self.search(request.GET)
        queryset = Vacancy.objects.select_related("company").filter(**filter_kwargs).filter(search_query)
        context = _get_context(
            request,
            queryset=queryset,
            queryset_handler=vacancys_queryset_handler,
            any_random_integer=True,
            queryset_context_alias="vacancys",
        )
        return context | {"show_button": check_is_user_company(request.user)}


class AddVacancyViewUtils(AddVacancyMixin):
    validation_class = AddVacancyForm
    request_host = RequestHost.VIEW

    def add_vacancy_utils(self, view_self, request: HttpRequest) -> HttpResponse:
        flag = self.add_vacancy(request.POST, request.user)
        if flag.status:
            return redirect(f"{reverse('worksite_app:home')}?show_success=True")
        return view_self.get(request, flag_error=flag.error.message, form_data=request.POST)


class SomeVacancyViewUtils(AddOfferMixin):
    request_host = RequestHost.VIEW
    validation_class = AddOfferForm

    def some_vacancy_utils(
        self, request: HttpRequest, ids: int, flag_success: Optional[bool] = None, error_code: Optional[str] = None
    ) -> Context:
        vacancy = CheckPermissionsToSeeVacancy.check_perms(request, ids)
        context = _get_context(request, company=vacancy.company, size=250, any_random_integer=True, tzone=True)
        context["vacancy"] = VacancyRenderObject(
            vacancy, experience=_get_experience(vacancy), city=vacancy.city, skills=vacancy.skills
        )
        context["view_offer"] = self.check_perms(request.user, vacancy, raise_exception=False)
        context["view_all_offers"] = request.user == vacancy.company if not vacancy.archived else False
        context["flag_success"], context["error_code"] = flag_success, error_code
        if context["view_all_offers"]:
            context["offers_count"] = Offer.objects.filter(vacancy=vacancy, withdrawn=False).count()
        return context | {"offer_form": AddOfferForm()}

    def some_vacancy_post_utils(self, view_self, request: HttpRequest, ids: int) -> HttpResponse:
        flag = self.add_offer(request.user, ids, request.POST, request.FILES)
        if not flag.status:
            return view_self.get(request, ids, False, flag.error.message)
        return view_self.get(request, ids, True)


class SomeCompanyViewUtils(AddRatingMixin):
    validation_class = AddRatingForm
    request_host = RequestHost.VIEW

    def some_company_utils(self, request: HttpRequest, uname: str, error: Optional[str] = None) -> Context:
        company = get_object_or_404(User, username=uname)
        if not company.first_name != "":
            raise Http404
        context = _get_context(request, company=company, size=200, any_random_integer=True, show_success=True)
        company_s: CompanySettings = get_user_settings(request.user)
        company_data = {
            "company_description": company_s.company_description,
            "company_site": company_s.company_site,
            "company_first_name": company.first_name,
            "company_vacancys_count": Vacancy.objects.filter(company=company, archived=False, deleted=False).count(),
            "company_username": company.username,
        }
        context["is_user_company"] = check_is_user_company(request.user) and (request.user.username == uname)
        if self.check_perms(request.user, company):
            context["form"] = AddRatingForm()
        return context | company_data | {"error": error}

    def some_company_post_utils(self, view_self, request: HttpRequest, uname: str) -> HttpResponse:
        flag = self.add_rating(request.user, uname, request.POST)
        if flag.status:
            cache.delete(f"{flag.status.pk}{settings.CACHE_NAMES_DELIMITER}{settings.COMPANY_RATINGS_CACHE_NAME}")
            return redirect(f"{reverse('worksite_app:company_rating', kwargs={'uname': uname})}" f"?show_success=True")
        return view_self.get(request, uname, error=flag.error.message)


class CompanyRatingViewUtils(object):
    @staticmethod
    def company_rating_utils(request: HttpRequest, uname: str) -> Context:
        def queryset_handler(ratings: QuerySet) -> Tuple[RatingRenderObject, ...]:
            return tuple(
                RatingRenderObject(
                    rating, _get_path_to_applicant_avatar(rating.applicant), _get_star_classes_list(rating.rating)
                )
                for rating in ratings
            )

        company = get_object_or_404(User, username=uname)
        queryset = get_company_ratings(company)
        context = _get_context(
            request,
            queryset=queryset,
            queryset_handler=queryset_handler,
            queryset_context_alias="ratings",
            any_random_integer=True,
            tzone=True,
        )
        return context | {"company_username": company.username}


class CompanyVacancysViewUtils(VacancyFilterMixin, VacancySearchMixin):
    def company_vacancys_utils(self, request: HttpRequest, uname: str) -> Context:
        company = get_object_or_404(User, username=uname)
        filter_kwargs = self.filter(request.GET, company, (not request.user == company))
        search_query = self.search(request.GET)
        queryset = Vacancy.objects.select_related("company").filter(**filter_kwargs).filter(search_query)
        context = _get_context(
            request,
            queryset=queryset,
            queryset_handler=vacancys_queryset_handler,
            queryset_context_alias="vacancys",
            any_random_integer=True,
        )
        return context | {"company": uname, "show_archived": request.user == company}


class VacancyOffersViewUtils(CheckPermissionsToSeeVacancyOffersAndDeleteVacancy):
    def vacancy_offers_utils(self, request: HttpRequest, ids: int) -> Context:
        vacancy = self.check_perms(request, ids)
        context = _get_context(request, any_random_integer=True, tzone=True)
        offers = tuple(
            OfferRenderObject(obj=offer, path_to_applicant_avatar=_get_path_to_applicant_avatar(offer.applicant))
            for offer in Offer.objects.filter(vacancy=vacancy, withdrawn=False).select_related("applicant")
        )
        return context | {"offers": offers}


class ApplyOfferViewUtils(ApplyOfferMixin):
    def apply_offer_utils(self, request: HttpRequest, ids: int) -> Context:
        return {"offer": self.check_perms(request, ids)}

    def apply_offer_post_utils(self, request: HttpRequest, ids: int) -> HttpResponse:
        self.apply_offer(request, ids)
        return redirect(f"{reverse('worksite_app:company_applyed_offers')}?show_success=True")


class MyOffersViewUtils:
    @staticmethod
    def my_offers_utils(request: HttpRequest) -> Context:
        assert request.user.is_authenticated and (not check_is_user_company(request.user)), PermissionDenied
        context = _get_context(request, any_random_integer=True, tzone=True)
        offers = Offer.objects.select_related("vacancy", "vacancy__company").filter(
            applicant=request.user, vacancy__deleted=False
        )
        return context | {"offers": offers, "path_to_applicant_avatar": _get_path_to_applicant_avatar(request.user)}


class SearchViewUtils:
    @staticmethod
    def search_view_utils(request: HttpRequest) -> Context | HttpResponse:
        if len(request.GET) < 3:
            return Context(
                {
                    "choices_cities": FILTERED_CITIES,
                    "experience_values": EXPERIENCE_CHOICES,
                    "get_params": ((k, v) for k, v in request.GET.items()),
                }
            )
        company = request.GET.get("company", None)
        kwargs = {}
        if company:
            kwargs["uname"] = get_object_or_404(User, username=company).username
        reverse_url = "worksite_app:company_vacancys" if company else "worksite_app:home"
        return redirect(f"{reverse(reverse_url, kwargs=kwargs)}?{request.GET.urlencode()}")


class DeleteVacancyUtils(DeleteVacancyMixin):
    def delete_vacancy_utils(self, request: HttpRequest, ids: int) -> Context:
        return Context({"vacancy": CheckPermissionsToSeeVacancyOffersAndDeleteVacancy.check_perms(request, ids)})

    def delete_vacancy_utils_post(self, request: HttpRequest, ids: int) -> Vacancy | NoReturn:
        return self.delete_vacancy(request, ids)


class WithdrawOfferUtils(WithdrawOfferMixin):
    def withdraw_offer_utils(self, request: HttpRequest, ids: int) -> Context:
        return Context({"offer": self.check_perms(request, ids)})

    def withdraw_offer_utils_post(self, request: HttpRequest, ids: int) -> Literal[None]:
        self.withdraw_offer(request, ids)


class CompanyApplyedOffersUtils(CompanyApplyedOffersMixin):
    def company_applyed_offers(self, request: HttpRequest) -> Context:
        context = _get_context(request, any_random_integer=True, tzone=True)
        applyed_offers = self.get_company_applyed_offers(request.user)
        offers = tuple(
            OfferRenderObject(offer, _get_path_to_applicant_avatar(offer.applicant)) for offer in applyed_offers
        )
        return context | {"offers": offers if len(offers) > 0 else None}

from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, get_object_or_404
from django.db.models.query import QuerySet
from django.db.models.fields.files import ImageFieldFile
from django.urls import reverse

from worksite_app.forms import AddVacancyForm, AddRatingForm, AddOfferForm
from worksite_app.models import Vacancy, Offer, Rating
from home_app.models import CompanySettings, ApplicantSettings
from worksite.settings import BASE_DIR, MEDIA_ROOT
from services.common_utils import get_timezone
from services.worksite_app_mixins import *
from worksite_app.constants import FILTERED_CITIES, EXPERIENCE_CHOICES

from dataclasses import dataclass
from typing import List, Tuple, NamedTuple, Literal, Optional, NoReturn
import os
from random import randrange

Context = dict
num = 100000


class CompanyData(NamedTuple):
    """ Структура данных для отображения информации о компании в шаблоне. """

    company_rating: int | float
    company_logo_path: str | Literal[False]
    company_logo_w: int | Literal[False]
    company_logo_h: int | Literal[False]
    company_reviews_count: int
    company_star_classes_list: List[str]


@dataclass
class VacancyRenderObject:
    """ Структура данных для отображения информации о вакансии в шаблоне. """

    obj: Vacancy
    experience: str = ""
    city: str = ""
    skills: List | Literal[None] = None
    company_data: CompanyData | Literal[None] = None


@dataclass
class OfferRenderObject:
    """ Структура данных для отображения информации об оффере соискателя в шаблоне. """

    obj: Offer
    path_to_applicant_avatar: str | Literal[None] = None


@dataclass
class RatingRenderObject:
    """ Структура данных для отображения информации об отзыве соискателя на компанию в шаблоне. """

    obj: Rating
    path_to_applicant_avatar: str | Literal[None] = None
    star_classes: List | Literal[None] = None


def _get_experience(vacancy: Vacancy) -> str:
    return EXPERIENCE_CHOICES[int(vacancy.experience)][1]


def _check_offset(request: HttpRequest, objects: QuerySet[Vacancy | Rating]) -> \
        Tuple[QuerySet[Vacancy | Rating], int, int, bool]:
    """ Функция для проверки оффсета и обрезания вакансий соответственно оффсету. """

    try:
        offset = int(request.GET.get("offset", 0))
        if offset % 20 != 0 or offset > len(objects) or offset < 0:
            raise Http404
    except ValueError:
        raise Http404
    return (
        objects[offset:offset + 20],
        offset + 20,
        offset - 20,
        True if len(objects[offset + 20:]) > 0 else False
    )


def _check_is_company_logo_default(settings: CompanySettings, size: int) -> \
        Tuple[str, int | float, int | float] | Literal[False]:
    if str(settings.company_logo) == "default_company_logo.png":
        return str(settings.company_logo), size, size
    return False


def _get_validated_width_and_height(image_obj: ImageFieldFile, size: int) -> \
        Tuple[int | float, int | float]:
    """ Функция для получения правильных длины и ширины логотипа компании для рендеринга в шаблон. """

    w, h = image_obj.width, image_obj.height
    huges = sorted((w, h))[::-1]
    res = huges[1] / huges[0]
    if huges[0] == h:
        return size * res, size
    else:
        return size, size * res


def _get_photo_path_and_params(settings: CompanySettings, size: int) -> \
        Tuple[str, int | float, int | float] | Literal[False]:
    """ Функция для получения правильного пути до логотипа компании и его длины и ширины для рендеринга в шаблон. """

    flag = _check_is_company_logo_default(settings, size)
    if flag:
        return flag
    logo_path, w, h = None, *_get_validated_width_and_height(settings.company_logo, size)
    path_to_settings_dir = f"logos/{settings.company.pk}/"
    try:
        file_name = os.listdir(BASE_DIR / MEDIA_ROOT / path_to_settings_dir)[0]
        logo_path = f"{path_to_settings_dir}{file_name}"
    except FileNotFoundError:
        pass
    return logo_path, w, h


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
    elif int(str(q)[1]) > 5:
        return int(str(int(str(q)[0]) + 1) + "0")


def _get_star_classes_list(rating: float) -> List:
    """ Функция для получения CSS классов звезд рейтинга компании. """

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


def _get_company_data(company: User, size: int) -> CompanyData:
    """
    Функция для получения различной информации о компании для рендеринга.
    (рейтинг компании, информация о логотипе и CSS классах звезд рейтинга)
    """

    company_s = CompanySettings.objects.get(company=company)
    ratings_count = Rating.objects.filter(company=company).count()
    attrs = _get_photo_path_and_params(company_s, size)
    if not attrs: attrs = (False, False, False)
    return CompanyData(
        company_s.rating,
        *attrs,
        ratings_count,
        _get_star_classes_list(company_s.rating)
    )


def _get_vacancys(request: HttpRequest, queryset: QuerySet[Vacancy]) -> \
        Tuple[List[VacancyRenderObject], int, int, bool]:
    """ Функция для преобразования QuerySet'a вакансий к готовому для рендеринга виду. """

    striped_vacancys, offset_next, offset_back, buttons = _check_offset(request, queryset.order_by("-time_added"))
    return (
        [VacancyRenderObject(
            obj=v,
            experience=_get_experience(v),
            company_data=_get_company_data(v.company, 200)
        ) for v in striped_vacancys],
        offset_next,
        offset_back,
        buttons
    )


def _get_path_to_applicant_avatar(applicant: User) -> str:
    """ Функция для получения пути к аватару соискателя. """

    avatar = ApplicantSettings.objects.get(applicant=applicant).applicant_avatar
    if str(avatar) == "default_applicant_avatar.jpg":
        return str(avatar)
    splitted_path = str(avatar).split("/")
    filename = splitted_path.pop()
    name, extension = filename.split(".")
    splitted_path.append(f"{name}_crop.{extension}")
    return "/".join(splitted_path)


class HomeViewUtils(VacancyFilterMixin, VacancySearchMixin):
    def home_utils(self, request: HttpRequest) -> Context:
        context = Context({"offset_params": {}})
        filter_kwargs = self.filter(request.GET)
        search_query = self.search(request.GET)
        context["vacancys"], context["offset_params"]["offset_next"], context["offset_params"]["offset_back"], \
            context["offset_params"]["buttons"] = _get_vacancys(
                request,
                Vacancy.objects.filter(**filter_kwargs).filter(search_query)
            )
        context["offset_params"]["city"], context["any_random_integer"] = request.GET.get("city", False), randrange(num)
        context["show_success"], context["show_button"] = (
            bool(request.GET.get("show_success", False)),
            check_is_user_company(request.user)
        )

        return context


class AddVacancyViewUtils(AddVacancyMixin):
    validation_class = AddVacancyForm

    def add_vacancy_utils(self, view_self, request: HttpRequest) -> HttpResponse:
        if self.add_vacancy(request.user, request.POST):
            return redirect(f"{reverse('worksite_app:home')}?show_success=True")

        return view_self.get(request, flag_error=True, form_data=request.POST)


class SomeVacancyViewUtils(AddOfferMixin):
    validation_class = AddOfferForm

    def some_vacancy_utils(self, request: HttpRequest, ids: int, flag_success: Optional[bool] = None,
                           error_code: Optional[int] = None) -> Context:
        context = Context()

        vacancy = CheckPermissionsToSeeVacancy().check_perms(request, ids)
        context["vacancy"] = VacancyRenderObject(vacancy, experience=_get_experience(vacancy), city=vacancy.city)
        try:
            context["vacancy"].skills = ", ".join(eval(vacancy.skills))
        except Exception:
            context["vacancy"].skills = vacancy.skills
        context["company_data"] = CompanyData(*_get_company_data(vacancy.company, 300))
        context["any_random_integer"], context["tzone"] = randrange(num), get_timezone(request)
        try:
            self.check_perms(request.user, vacancy)
            context["view_offer"] = True
        except Exception:
            context["view_offer"] = False
        context["offer_form"] = AddOfferForm()
        context["view_all_offers"], context["flag_success"], context["error_code"] = request.user == vacancy.company \
            if not vacancy.archived else False, flag_success, error_code
        if context["view_all_offers"]:
            context["offers_count"] = Offer.objects.filter(vacancy=vacancy, withdrawn=False).count()

        return context

    def some_vacancy_post_utils(self, view_self, request: HttpRequest, ids: int) -> HttpResponse:
        flags = self.add_offer(request.user, ids, request.POST, request.FILES)
        if not flags[0]:
            return view_self.get(request, ids, False, flags[1])
        return view_self.get(request, ids, True)


class SomeCompanyViewUtils(AddRatingMixin):
    validation_class = AddRatingForm

    def some_company_utils(self, request: HttpRequest, uname: str, flag_success: Optional[bool] = None) -> Context:
        context = Context()
        company = get_object_or_404(User, username=uname)
        if not company.first_name != "":
            raise Http404
        company_s = CompanySettings.objects.get(company=company)
        context["company_data"] = CompanyData(*_get_company_data(company, 200))
        company_data = {"company_description": company_s.company_description, "company_site": company_s.company_site,
                        "company_first_name": company.first_name, "company_vacancys_count":
                            Vacancy.objects.filter(company=company, archived=False, deleted=False).count(),
                        "company_username": company.username}
        context["is_user_company"], context["any_random_integer"] = ((check_is_user_company(request.user) and
                                                                      (request.user.username == uname)), randrange(num))
        if self.check_perms(request.user, company):
            context["form"] = AddRatingForm()
        context["flag_success"], context["show_success"] = flag_success, request.GET.get("show_success", None)
        return context | company_data

    def some_company_post_utils(self, view_self, request: HttpRequest, uname: str) -> HttpResponse:
        flag = self.add_rating(request.user, uname, request.POST)
        if flag:
            return redirect(f"{reverse('worksite_app:company_rating', kwargs={'uname': uname})}"
                            f"?show_success=True")
        return view_self.get(request, uname, flag_success=False)


class CompanyRatingViewUtils:
    @staticmethod
    def company_rating_utils(request: HttpRequest, uname: str) -> Context:
        context = Context({"offset_params": {}})
        company = get_object_or_404(User, username=uname)
        queryset = Rating.objects.filter(company=company).select_related("applicant").order_by("-time_added")
        ratings, context["offset_params"]["offset_next"], context["offset_params"]["offset_back"], \
            context["offset_params"]["buttons"] = _check_offset(request, queryset)
        context["any_random_integer"], context["tzone"] = randrange(num), get_timezone(request)
        context["ratings"] = (RatingRenderObject(rating, _get_path_to_applicant_avatar(rating.applicant),
                                                 _get_star_classes_list(rating.rating)) for rating in ratings)
        return context | {"show_success": request.GET.get("show_success", False), "company_username": company.username}


class CompanyVacancysViewUtils(VacancyFilterMixin, VacancySearchMixin):
    def company_vacancys_utils(self, request: HttpRequest, uname: str) -> Context:
        context = Context({"offset_params": {}})
        company = get_object_or_404(User, username=uname)
        filter_kwargs = self.filter(request.GET, company=company, only_not_archived=(not request.user == company))
        search_query = self.search(request.GET)
        context["vacancys"], context["offset_params"]["offset_next"], context["offset_params"]["offset_back"], \
            context["offset_params"]["buttons"] = _get_vacancys(request, Vacancy.objects.filter(**filter_kwargs)
                                                                .filter(search_query))
        context["offset_params"]["city"] = request.GET.get("city", False)
        context["any_random_integer"], context["show_archived"] = randrange(num), request.user == company

        return context | {"company": uname}


class VacancyOffersViewUtils(CheckPermissionsToSeeVacancyOffersAndDeleteVacancy):
    def vacancy_offers_utils(self, request: HttpRequest, ids: int) -> Context:
        vacancy = self.check_perms(request, ids)
        offers = [OfferRenderObject(obj=offer, path_to_applicant_avatar=_get_path_to_applicant_avatar(offer.applicant))
                  for offer in Offer.objects.filter(vacancy=vacancy, withdrawn=False).select_related("applicant")]
        return {"offers": offers, "any_random_integer": randrange(num), "tzone": get_timezone(request)}


class ApplyOfferViewUtils(ApplyOfferMixin):
    def apply_offer_utils(self, request: HttpRequest, ids: int) -> Context:
        return {"offer": self.check_perms(request, ids)}

    def apply_offer_post_utils(self, request: HttpRequest, ids: int) -> HttpResponse:
        self.apply_offer(request, ids)
        return redirect(f"{reverse('worksite_app:company_applyed_offers')}?show_success=True")


class MyOffersViewUtils:
    @staticmethod
    def my_offers_utils(request: HttpRequest) -> Context:
        if check_is_user_company(request.user): raise Http404
        try:
            offers = Offer.objects.select_related("vacancy", "vacancy__company").filter(
                applicant=request.user, vacancy__deleted=False
            ).order_by("-time_added").all()
        except TypeError:
            raise PermissionDenied

        return {
            "offers": offers,
            "path_to_applicant_avatar": _get_path_to_applicant_avatar(request.user),
            "any_random_integer": randrange(num),
            "tzone": get_timezone(request),
            "show_success": request.GET.get("show_success", None)
        }


class SearchViewUtils:
    @staticmethod
    def search_view_utils(request: HttpRequest) -> Context | HttpResponse:
        if len(request.GET) < 3:
            return Context({
                "choices_cities": FILTERED_CITIES,
                "experience_values": EXPERIENCE_CHOICES,
                "get_params": ((k, v) for k, v in request.GET.items())
            })
        company = request.GET.get('company', None)
        kwargs = {}
        if company:
            kwargs["uname"] = get_object_or_404(User, username=company).username
        reverse_url = 'worksite_app:company_vacancys' if company else 'worksite_app:home'
        return redirect(f"{reverse(reverse_url, kwargs=kwargs)}?{request.GET.urlencode()}")


class DeleteVacancyUtils(DeleteVacancyMixin):
    def delete_vacancy_utils(self, request: HttpRequest, ids: int) -> Context:
        return Context({"vacancy": self.check_perms(request, ids)})

    def delete_vacancy_utils_post(self, request: HttpRequest, ids: int) -> Literal[None] | NoReturn:
        self.delete_vacancy(request, ids)


class WithdrawOfferUtils(WithdrawOfferMixin):
    def withdraw_offer_utils(self, request: HttpRequest, ids: int) -> Context:
        return Context({"offer": self.check_perms(request, ids)})

    def withdraw_offer_utils_post(self, request: HttpRequest, ids: int) -> Literal[None]:
        self.withdraw_offer(request, ids)


class CompanyApplyedOffersUtils(CompanyApplyedOffersMixin):
    def company_applyed_offers(self, request: HttpRequest) -> Context:
        offers = tuple(OfferRenderObject(offer, _get_path_to_applicant_avatar(offer.applicant))
                       for offer in self.get_company_applyed_offers(request.user))
        return Context({
            "offers": offers if len(offers) > 0 else None,
            "any_random_integer": randrange(num),
            "tzone": get_timezone(request),
        })

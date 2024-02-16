from django.shortcuts import render
from django.http import HttpRequest, HttpResponse
from django.views.generic import View
from django.core.exceptions import PermissionDenied

from services.worksite_app_utils import *
from .forms import *
from .constants import EXPERIENCE_CHOICES, FILTERED_CITIES

from typing import Optional


def home(request: HttpRequest) -> HttpResponse:
    return render(request, "worksite_app/home.html", context=HomeViewUtils().home_utils(request))


class AddVacancyView(View):
    def get(self, request: HttpRequest, form_data: Optional[dict] = None, flag_error: Optional[bool] = False) -> \
            HttpResponse:
        if not check_is_user_company(request.user):
            raise PermissionDenied
        return render(request, "worksite_app/add_vacancy.html", context={
            "choices_experience": EXPERIENCE_CHOICES,
            "choices_cities": FILTERED_CITIES,
            "flag_error": flag_error,
            "form": AddVacancyForm(form_data)
        })

    def post(self, request: HttpRequest) -> HttpResponse:
        if not check_is_user_company(request.user):
            raise PermissionDenied
        return AddVacancyViewUtils().add_vacancy_utils(self, request)


class SomeVacancyView(View):
    def get(self, request: HttpRequest, ids: int, flag_success: Optional[bool] = None,
            error_code: Optional[int] = None) -> HttpResponse:
        return render(request, "worksite_app/some_vacancy.html", context=SomeVacancyViewUtils().some_vacancy_utils(
            request,
            ids,
            flag_success,
            error_code
        ))

    def post(self, request: HttpRequest, ids: int) -> HttpResponse:
        return SomeVacancyViewUtils().some_vacancy_post_utils(self, request, ids)


class SomeCompanyView(View):
    def get(self, request: HttpRequest, uname: str, flag_success: Optional[bool] = None) -> HttpResponse:
        return render(request, "worksite_app/some_company.html", context=SomeCompanyViewUtils().some_company_utils(
            request,
            uname,
            flag_success
        ))

    def post(self, request: HttpRequest, uname: str) -> HttpResponse:
        return SomeCompanyViewUtils().some_company_post_utils(self, request, uname)


def company_rating(request: HttpRequest, uname: str) -> HttpResponse:
    return render(request, "worksite_app/company_rating.html", context=CompanyRatingViewUtils
                  .company_rating_utils(request, uname))


def company_vacancys(request: HttpRequest, uname: str) -> HttpResponse:
    return render(request, "worksite_app/home.html",
                  context=CompanyVacancysViewUtils().company_vacancys_utils(request, uname))


def vacancy_offers(request: HttpRequest, ids: int) -> HttpResponse:
    return render(request, "worksite_app/vacancy_offers.html", context=VacancyOffersViewUtils().vacancy_offers_utils(
        request,
        ids
    ))


class ApplyOfferView(View):
    def get(self, request: HttpRequest, ids: int) -> HttpResponse:
        return render(request, "worksite_app/apply_confirm.html", context=ApplyOfferViewUtils().apply_offer_utils(
            request,
            ids
        ))

    def post(self, request: HttpRequest, ids: int) -> HttpResponse:
        return ApplyOfferViewUtils().apply_offer_post_utils(request, ids)


def my_offers(request: HttpRequest) -> HttpResponse:
    return render(request, "worksite_app/my_offers.html", context=MyOffersViewUtils.my_offers_utils(request))


def search(request: HttpRequest) -> HttpResponse:
    utils = SearchViewUtils.search_view_utils(request)
    if isinstance(utils, dict):
        return render(request, "worksite_app/search.html", context=utils)
    return utils


class DeleteVacancyView(View):
    def get(self, request: HttpRequest, ids: int) -> HttpResponse:
        context = DeleteVacancyUtils().delete_vacancy_utils(request, ids)
        return render(request, "worksite_app/delete_vacancy.html", context=context)

    def post(self, request: HttpRequest, ids: int) -> HttpResponse:
        DeleteVacancyUtils().delete_vacancy_utils_post(request, ids)
        return redirect(f"{reverse('worksite_app:some_company', kwargs={'uname': request.user.username})}"
                        f"?show_success=True")


class WithdrawOfferView(View):
    def get(self, request: HttpRequest, ids: int) -> HttpResponse:
        context = WithdrawOfferUtils().withdraw_offer_utils(request, ids)
        return render(request, "worksite_app/withdraw_offer.html", context=context)

    def post(self, request: HttpRequest, ids: int) -> HttpResponse:
        WithdrawOfferUtils().withdraw_offer_utils_post(request, ids)
        return redirect(f"{reverse('worksite_app:my_offers')}?show_success=True")


def company_applyed_offers(request: HttpRequest) -> HttpResponse:
    return render(request, "worksite_app/company_applyed_offers.html",
                  context=CompanyApplyedOffersUtils().company_applyed_offers(request))

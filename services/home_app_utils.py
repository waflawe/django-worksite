from __future__ import annotations

from django.contrib.auth import authenticate, login
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.urls import NoReverseMatch, reverse

from home_app.forms import (AuthForm, ApplicantRegisterForm, CompanyRegisterForm, UploadAvatarForm, UploadLogoForm, 
                            AnotherCompanySettingsForm)
from services.common_utils import check_is_user_company, Error_code, RequestHost
from services.home_app_mixins import UpdateSettingsMixin
from typing import Literal, Union, NamedTuple
import pytz

Context = dict


class AuthViewUtils:
    @staticmethod
    def auth_view_utils(self, request: HttpRequest) -> HttpResponse:
        form = AuthForm(request.POST)

        if form.is_valid():
            user = authenticate(username=request.POST["username"], password=request.POST["password"])
            if user is not None:
                login(request, user)
                return AuthViewUtils._get_redirect(request)

        return self.get(request=request, flag_error=True, form=request.POST)

    @staticmethod
    def _get_redirect(request: HttpRequest) -> HttpResponse:
        try:
            return redirect(request.GET["next"] if request.GET.get("next", False) else "/")
        except NoReverseMatch:
            return redirect("/")


class RegisterViewUtils:
    @staticmethod
    def register_view_utils(self, request: HttpRequest, applicant: bool) -> HttpResponse:
        form = ApplicantRegisterForm(request.POST) if applicant else CompanyRegisterForm(request.POST)

        if form.is_valid():
            u = form.save()
            fk = "applicant" if applicant else "company"
            (ApplicantSettings if applicant else CompanySettings).objects.create(**{fk:u})
            return redirect(f"{reverse('home_app:auth')}?show_success=True")
        return self.get(request=request, flag_error=True, form=request.POST)


class SettingsViewUtils(UpdateSettingsMixin):
    request_host = RequestHost.VIEW

    @staticmethod
    def settings_view_get_utils(request: HttpRequest, flag_success: bool, flag_error: bool) -> Context:
        context = {}

        context["tzs"], company = pytz.common_timezones, check_is_user_company(request.user)
        cs = CompanySettings.objects.get(company=request.user) if company else False
        context["now"] = cs.timezone if company else ApplicantSettings.objects.get(applicant=request.user).timezone
        context["flag_error"], context["flag_success"] = flag_error, flag_success
        context["photo_form"] = UploadLogoForm() if company else UploadAvatarForm()
        context["another_company_settings_form"] = AnotherCompanySettingsForm(
            {"company_description": cs.company_description, "company_site": cs.company_site}
        ) if company else False

        return context

    def settings_view_post_utils(self, view_self, request: HttpRequest, company: bool) -> HttpResponse:
        flag_error, flag_success = self.update_settings(request, request.POST, request.FILES)

        return self._get_response(view_self, request, flag_error, flag_success, company)

    def _get_response(self, view_self, request: HttpRequest, flag_error: bool | int, flag_success: bool, company: bool) \
            -> HttpResponse:
        if company and flag_success:
            return redirect(f"{reverse('worksite_app:some_company', kwargs={'uname': request.user.username})}"
                            f"?show_success=True")
        else:
            return view_self.get(
                request=request,
                flag_error=flag_error,
                flag_success=flag_success
            )

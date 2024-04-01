from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.urls import reverse

from home_app.forms import ApplicantRegisterForm, CompanyRegisterForm, ApplicantSettingsForm, CompanySettingsForm
from services.common_utils import check_is_user_company, RequestHost
from services.home_app_mixins import UpdateSettingsMixin
from home_app.models import CompanySettings, ApplicantSettings

import pytz
from typing import Literal

Context = dict


class RegisterViewUtils:
    @staticmethod
    def register_view_utils(view_self, request: HttpRequest, applicant: bool) -> HttpResponse:
        form = ApplicantRegisterForm(request.POST) if applicant else CompanyRegisterForm(request.POST)

        if form.is_valid():
            u = form.save()
            fk = "applicant" if applicant else "company"
            (ApplicantSettings if applicant else CompanySettings).objects.create(**{fk: u})
            return redirect(f"{reverse('home_app:auth')}?show_success=True")
        return view_self.get(request=request, flag_error=True, form=request.POST)


class SettingsViewUtils(UpdateSettingsMixin):
    request_host = RequestHost.VIEW

    @staticmethod
    def settings_view_get_utils(request: HttpRequest, flag_success: bool, flag_error: Literal[False] | str) -> Context:
        context = {}

        context["tzs"], company = pytz.common_timezones, check_is_user_company(request.user)
        cs = CompanySettings.objects.get(company=request.user) if company else False
        context["now"] = cs.timezone if company else ApplicantSettings.objects.get(applicant=request.user).timezone
        context["flag_error"], context["flag_success"] = flag_error, flag_success
        context["form"] = ApplicantSettingsForm() if not company else CompanySettingsForm(
            {"company_description": cs.company_description, "company_site": cs.company_site}
        )
        return context

    def settings_view_post_utils(self, view_self, request: HttpRequest, company: bool) -> HttpResponse:
        flag = self.update_settings(request, request.POST, request.FILES)
        flag_error, flag_success = (flag.error.message if not flag.status else False), flag.status
        return self._get_response(view_self, request, flag_error, flag_success, company=company)

    def _get_response(self, view_self, request: HttpRequest, flag_error: Literal[False] | str,
                      flag_success: bool, company: bool) -> HttpResponse:
        if company and flag_success:
            return redirect(f"{reverse('worksite_app:some_company', kwargs={'uname': request.user.username})}"
                            f"?show_success=True")
        else:
            return view_self.get(
                request=request,
                flag_error=flag_error,
                flag_success=flag_success
            )

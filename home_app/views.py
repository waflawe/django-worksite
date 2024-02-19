from django.shortcuts import render
from django.http import HttpRequest, HttpResponse, Http404
from django.views.generic import View
from django.contrib.auth import logout
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin

from services.home_app_utils import *
from services.common_utils import check_is_user_auth

from typing import Optional, Mapping


def _get_registered_user(request: HttpRequest) -> bool:
    applicant = request.GET.get("applicant", 'True')
    # TEST THIS SHIT
    if isinstance(applicant, list): applicant = applicant[0]
    if applicant == 'True': return True
    if applicant == 'False': return False
    raise Http404


def home_view(request: HttpRequest) -> HttpResponse:
    return render(request, "home_app/home.html", context={
        "show_logout": bool(request.GET.get("show_logout", False)),
    })


class AuthView(View):
    def get(self, request: HttpRequest, flag_error: Optional[bool] = False, form: Optional[Mapping] = None) -> \
            HttpResponse:
        if check_is_user_auth(request): return redirect("/")
        return render(request, "home_app/user_auth.html", context={
            "form": AuthForm(form),
            "flag_error": flag_error,
            "show_success": request.GET.get("show_success", False)
        })

    def post(self, request: HttpRequest) -> HttpResponse:
        if check_is_user_auth(request): return redirect("/")
        return AuthViewUtils.auth_view_utils(self, request)


class LogoutView(View, LoginRequiredMixin):
    raise_exception = True

    def get(self, request: HttpRequest) -> HttpResponse:
        logout(request=request)
        return redirect(f'{reverse("home_app:home")}?show_logout=True')


class RegisterView(View):
    def get(self, request: HttpRequest, flag_error: Optional[bool] = False, form: Optional[Mapping] = None) -> \
            HttpResponse:
        if check_is_user_auth(request=request): return redirect("/")
        applicant = _get_registered_user(request)
        return render(request, "home_app/user_register.html", context={
            "form": ApplicantRegisterForm(form) if applicant else CompanyRegisterForm(form),
            "flag_error": flag_error,
            "applicant": applicant
        })

    def post(self, request: HttpRequest) -> HttpResponse:
        if check_is_user_auth(request=request): return redirect("/")
        return RegisterViewUtils.register_view_utils(self, request, applicant=_get_registered_user(request))


class SettingsView(LoginRequiredMixin, View):
    login_url = reverse_lazy("home_app:auth")

    def get(self, request: HttpRequest, flag_success: Optional[bool] = False, flag_error: Optional[bool] = False) -> \
            HttpResponse:
        return render(request, "home_app/settings.html", context=SettingsViewUtils.settings_view_get_utils(
            request,
            flag_success,
            flag_error
        ))

    def post(self, request: HttpRequest) -> HttpResponse:
        return SettingsViewUtils().settings_view_post_utils(self, request, company=check_is_user_company(request.user))

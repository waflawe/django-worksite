from typing import Mapping, Optional

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render, reverse
from django.urls import NoReverseMatch, reverse_lazy
from django.views.generic import View

from home_app.forms import ApplicantRegisterForm, AuthForm, CompanyRegisterForm
from services.common_utils import check_is_user_auth, check_is_user_company
from services.home_app_utils import RegisterViewUtils, SettingsViewUtils


def get_register_page(request: HttpRequest) -> bool:
    """Функция для определения запрашиваемой страницы регистрации."""

    applicant = request.GET.get("applicant", "True")
    if applicant == "True":
        return True
    if applicant == "False":
        return False
    raise Http404


def home_view(request: HttpRequest) -> HttpResponse:
    context = {"show_logout": bool(request.GET.get("show_logout", False))}
    return render(request, "home_app/home.html", context=context)


class AuthView(View):
    def get(
        self, request: HttpRequest, flag_error: Optional[bool] = False, form: Optional[Mapping] = None
    ) -> HttpResponse:
        if check_is_user_auth(request):
            return redirect("/")
        context = {
            "form": AuthForm(form),
            "flag_error": flag_error,
            "show_success": request.GET.get("show_success", False),
        }
        return render(request, "home_app/user_auth.html", context=context)

    def post(self, request: HttpRequest) -> HttpResponse:
        if check_is_user_auth(request):
            return redirect("/")

        form = AuthForm(request.POST)

        if form.is_valid():
            user = authenticate(username=request.POST["username"], password=request.POST["password"])
            if user is not None:
                login(request, user)
                return self._get_redirect(request)

        return self.get(request=request, flag_error=True, form=request.POST)

    def _get_redirect(self, request: HttpRequest) -> HttpResponse:
        try:
            return redirect(request.GET["next"] if request.GET.get("next", False) else "/")
        except NoReverseMatch:
            return redirect("/")


class LogoutView(LoginRequiredMixin, View):
    raise_exception = True

    def get(self, request: HttpRequest) -> HttpResponse:
        logout(request=request)
        return redirect(f'{reverse("home_app:home")}?show_logout=True')


class RegisterView(View):
    def get(
        self, request: HttpRequest, flag_error: Optional[bool] = False, form: Optional[Mapping] = None
    ) -> HttpResponse:
        if check_is_user_auth(request=request):
            return redirect("/")
        applicant = get_register_page(request)
        context = {
            "form": ApplicantRegisterForm(form) if applicant else CompanyRegisterForm(form),
            "flag_error": flag_error,
            "applicant": applicant,
        }
        return render(request, "home_app/user_register.html", context=context)

    def post(self, request: HttpRequest) -> HttpResponse:
        if check_is_user_auth(request=request):
            return redirect("/")
        return RegisterViewUtils.register_view_utils(self, request, applicant=get_register_page(request))


class SettingsView(LoginRequiredMixin, View):
    login_url = reverse_lazy("home_app:auth")

    def get(
        self, request: HttpRequest, flag_success: Optional[bool] = False, flag_error: Optional[bool] = False
    ) -> HttpResponse:
        return render(
            request,
            "home_app/settings.html",
            context=SettingsViewUtils.settings_view_get_utils(request, flag_success, flag_error),
        )

    def post(self, request: HttpRequest) -> HttpResponse:
        return SettingsViewUtils().settings_view_post_utils(self, request, company=check_is_user_company(request.user))

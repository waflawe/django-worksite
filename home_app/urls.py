from django.urls import path

from home_app.views import AuthView, LogoutView, RegisterView, SettingsView, home_view

app_name = "home_app"

# domain.com/
urlpatterns = [
    path("", home_view, name="home"),
    path("register/", RegisterView.as_view(), name="register"),
    path("auth/", AuthView.as_view(), name="auth"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("settings/", SettingsView.as_view(), name="settings"),
]

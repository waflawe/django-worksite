from django.urls import path
from .views import *

app_name = "worksite_app"

# domain.com/worksite/

urlpatterns = [
    path("", home, name="home"),
    path("add_vacancy/", AddVacancyView.as_view(), name="addvacancy"),
    path("vacancy/<int:ids>/", SomeVacancyView.as_view(), name="some_vacancy"),
    path("vacancy/<int:ids>/offers/", vacancy_offers, name="vacancy_offers"),
    path("vacancy/<int:ids>/delete/", DeleteVacancyView.as_view(), name="vacancy_delete"),
    path("apply_offer/<int:ids>/", ApplyOfferView.as_view(), name="apply_offer"),
    path("my_offers/", my_offers, name="my_offers"),
    path("my_offers/<int:ids>/withdraw/", WithdrawOfferView.as_view(), name="withdraw_offer"),
    path("search/", search, name="search"),
    path("my_applyed_offers/", company_applyed_offers, name="company_applyed_offers"),
    path("<str:uname>/", SomeCompanyView.as_view(), name="some_company"),
    path("<str:uname>/ratings/", company_rating, name="company_rating"),
    path("<str:uname>/vacancys/", company_vacancys, name="company_vacancys")
]

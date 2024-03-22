from django.urls import path
from .views import *

app_name = "worksite_app"

# domain.com/worksite/
urlpatterns = [
    # Общие урлы.
    path("", home, name="home"),
    path("search/", search, name="search"),
    path("<str:uname>/", SomeCompanyView.as_view(), name="some_company"),
    path("<str:uname>/ratings/", company_rating, name="company_rating"),
    path("<str:uname>/vacancys/", company_vacancys, name="company_vacancys"),
    path("vacancy/<int:ids>/", SomeVacancyView.as_view(), name="some_vacancy"),
    # Урлы компаний.
    path("vacancy/<int:ids>/offers/", vacancy_offers, name="vacancy_offers"),
    path("vacancy/<int:ids>/delete/", DeleteVacancyView.as_view(), name="vacancy_delete"),
    path("vacancy/add/", AddVacancyView.as_view(), name="addvacancy"),
    path("offers/<int:ids>/apply/", ApplyOfferView.as_view(), name="apply_offer"),
    path("offers/applyed/", company_applyed_offers, name="company_applyed_offers"),
    # Урлы соискателей.
    path("offers/my/", my_offers, name="my_offers"),
    path("offers/my/<int:ids>/withdraw/", WithdrawOfferView.as_view(), name="withdraw_offer")
]

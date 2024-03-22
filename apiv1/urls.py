from django.urls import path, include
from rest_framework.routers import SimpleRouter
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from apiv1.views import (VacancyViewSet, ApplicantOffersViewSet, GetVacancyOffersAPIView, GetCompanyDetailAPIView,
                         GetCompanyRatingsAPIView, CompanyApplyedOffersAPIView, AddRatingAPIView, ApplyOfferAPIView,
                         UpdateSettingsAPIView)

router = SimpleRouter()
router.register(r"vacancys", VacancyViewSet, basename="vacancy")
router.register(r"offers", ApplicantOffersViewSet, basename="my_offer")

urlpatterns = [
    path("", include(router.urls)),
    path("vacancys/<int:ids>/offers/", GetVacancyOffersAPIView.as_view(), name="vacancy_offers"),
    path("company/<str:uname>/", GetCompanyDetailAPIView.as_view(), name="company_detail"),
    path("company/<str:uname>/ratings/", GetCompanyRatingsAPIView.as_view(), name="company_ratings"),
    path("offers/<int:ids>/apply/", ApplyOfferAPIView.as_view(), name="apply_offer"),
    path("vacancys/offers/applyed/", CompanyApplyedOffersAPIView.as_view(), name="company_applyed_offers"),
    path("rating/add/<str:uname>/", AddRatingAPIView.as_view(), name="add_rating"),
    path("settings/update/", UpdateSettingsAPIView.as_view(), name="update_settings"),
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("schema/docs/", SpectacularSwaggerView.as_view(url_name="schema"))
]

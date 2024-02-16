from django.urls import path, include
from rest_framework.routers import SimpleRouter

from apiv1.views import (VacancyViewSet, ApplicantOffersViewSet, GetVacancyOffersAPIView, GetCompanyDetailAPIView,
                         GetCompanyRatingsAPIView, CompanyApplyedOffersAPIView, AddRatingAPIView, ApplyOfferAPIView,
                         UpdateSettingsAPIView)

router = SimpleRouter()
router.register(r"vacancys", VacancyViewSet, basename="vacancy")
router.register(r"my_offers", ApplicantOffersViewSet, basename="my_offer")

urlpatterns = [
    path("", include(router.urls)),
    path("vacancys/<int:ids>/offers/", GetVacancyOffersAPIView.as_view(), name="vacancy_offers"),
    path("company/<str:uname>/", GetCompanyDetailAPIView.as_view(), name="company_detail"),
    path("company/<str:uname>/ratings/", GetCompanyRatingsAPIView.as_view(), name="company_ratings"),
    path("my_applyed_offers/", CompanyApplyedOffersAPIView.as_view(), name="company_applyed_offers"),
    path("AddRating/", AddRatingAPIView.as_view(), name="add_rating"),
    path("ApplyOffer/", ApplyOfferAPIView.as_view(), name="apply_offer"),
    path("UpdateSettings/", UpdateSettingsAPIView.as_view(), name="update_settings")
]

from rest_framework.generics import ListAPIView
from django.contrib.auth.models import User
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from rest_framework import mixins
from rest_framework.viewsets import GenericViewSet

from apiv1.serializers import VacancysSerializer, CompanyDetailSerializer, OffersSerializer, RatingsSerializer
from services.worksite_app_mixins import *
from services.home_app_mixins import UpdateSettingsMixin
from worksite_app.models import Vacancy, Offer, Rating
from services.common_utils import RequestHost
from apiv1.permissions import IsApplicant, IsCompany, VacancyOperationsPermission


class VacancyViewSet(GenericViewSet, mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.DestroyModelMixin,
                     mixins.CreateModelMixin, VacancyFilterMixin, VacancySearchMixin, DeleteVacancyMixin,
                     AddVacancyMixin):
    serializer_class = validation_class = VacancysSerializer
    lookup_url_kwarg = "ids"
    permission_classes = (VacancyOperationsPermission,)

    def get_queryset(self):
        company = self.request.query_params.get("company", None)
        company = get_object_or_404(User, username=company) if company else None
        filter_kwargs = self.filter(self.request.query_params, company, (not self.request.user == company))
        search_query = self.search(self.request.query_params)
        return Vacancy.objects.filter(**filter_kwargs).filter(search_query).order_by("-time_added")

    def retrieve(self, request, *args, **kwargs) -> Response:
        vacancy = CheckPermissionsToSeeVacancy().check_perms(request, self.kwargs[self.lookup_url_kwarg])
        return Response({"vacancy": self.serializer_class(vacancy, context={"request": request}).data})

    def destroy(self, request, *args, **kwargs) -> Response:
        self.delete_vacancy(request, self.kwargs[self.lookup_url_kwarg])
        return Response(status=status.HTTP_204_NO_CONTENT)

    def create(self, request, *args, **kwargs) -> Response:
        vacancy = self.add_vacancy(request.user, request.data)
        return Response(status=status.HTTP_201_CREATED if vacancy else status.HTTP_400_BAD_REQUEST)


class ApplicantOffersViewSet(GenericViewSet, mixins.ListModelMixin, mixins.CreateModelMixin, mixins.DestroyModelMixin,
                             AddOfferMixin, WithdrawOfferMixin):
    serializer_class = validation_class = OffersSerializer
    lookup_url_kwarg = "ids"
    permission_classes = (IsAuthenticated, IsApplicant)

    def get_queryset(self):
        return Offer.objects.filter(applicant=self.request.user, vacancy__deleted=False).order_by("-time_added")

    def create(self, request, *args, **kwargs) -> Response:
        flags = self.add_offer(request.user, request.data["vacancy"], request.data, request.data)
        return Response(status=status.HTTP_201_CREATED if flags[0] else status.HTTP_400_BAD_REQUEST)

    def destroy(self, request, *args, **kwargs) -> Response:
        self.withdraw_offer(request, self.kwargs[self.lookup_url_kwarg])
        return Response(status=status.HTTP_204_NO_CONTENT)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        return context | {"view_withdrawn_field": True}


class UpdateSettingsAPIView(APIView, UpdateSettingsMixin):
    request_host = RequestHost.APIVIEW

    def post(self, request: Request):
        flag = self.update_settings(request, request.data, request.data)
        if flag[1]:
            return Response(status=status.HTTP_200_OK)
        return Response(status=status.HTTP_400_BAD_REQUEST)


class GetCompanyRatingsAPIView(ListAPIView):
    serializer_class = validation_class = RatingsSerializer

    def get_queryset(self):
        return Rating.objects.filter(company__username=self.kwargs["uname"]).order_by("-time_added")


class GetCompanyDetailAPIView(ListAPIView):
    serializer_class = CompanyDetailSerializer
    pagination_class = None

    def get_queryset(self):
        return User.objects.filter(username=self.kwargs["uname"])


class GetVacancyOffersAPIView(ListAPIView, CheckPermissionsToSeeVacancy):
    serializer_class = OffersSerializer

    def get_queryset(self):
        vacancy = self.check_perms(self.request, self.kwargs["ids"])
        return Offer.objects.filter(vacancy=vacancy, withdrawn=False).order_by("-time_added")

    def get_serializer_context(self):
        context = super().get_serializer_context()
        return context | {"view_vacancy_field": False}


class AddRatingAPIView(APIView, AddRatingMixin):
    permission_classes = (IsAuthenticated,)
    validation_class = RatingsSerializer

    def post(self, request: Request) -> Response:
        flag = self.add_rating(request.user, request.data.get("company", ""), request.data)
        return Response(status=status.HTTP_201_CREATED if flag else status.HTTP_400_BAD_REQUEST)


class ApplyOfferAPIView(APIView, ApplyOfferMixin):
    def post(self, request: Request) -> Response:
        self.apply_offer(request, request.data.get("offer", 0))
        return Response(status=status.HTTP_201_CREATED)


class CompanyApplyedOffersAPIView(ListAPIView, CompanyApplyedOffersMixin):
    serializer_class = OffersSerializer
    permission_classes = (IsAuthenticated, IsCompany)

    def get_queryset(self):
        return self.get_company_applyed_offers(self.request.user, False)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        return context | {"view_archived_field": False}

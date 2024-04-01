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
from drf_spectacular.utils import extend_schema, OpenApiParameter, extend_schema_view

from apiv1.serializers import (
    VacancysSerializer, CompanyDetailSerializer, VacancyOffersSerializer, RatingsSerializer, VacancyDetailSerializer,
    DefaultErrorSerializer, CompanySettingsSerializer, ApplicantSettingsSerializer, CustomErrorSerializer,
    OffersFullSerializer, CompanyApplyedOffersSerializer
)
from services.worksite_app_mixins import (
    DefaultPOSTReturn, VacancyFilterMixin, VacancySearchMixin, DeleteVacancyMixin, AddVacancyMixin,
    CheckPermissionsToSeeVacancy, CheckPermissionsToSeeVacancyOffersAndDeleteVacancy, WithdrawOfferMixin, AddOfferMixin,
    AddRatingMixin, ApplyOfferMixin, CompanyApplyedOffersMixin
)
from services.home_app_mixins import UpdateSettingsMixin
from worksite_app.models import Vacancy, Offer, Rating
from services.common_utils import RequestHost
from apiv1.permissions import IsApplicant, IsCompany, IsAuthenticatedCompanyOrReadOnly

from typing import NamedTuple, Optional


class POSTStatuses(NamedTuple):
    success: status = status.HTTP_201_CREATED
    error: status = status.HTTP_400_BAD_REQUEST


class POSTView(object):
    @staticmethod
    def get_response(flag: DefaultPOSTReturn, statuses: Optional[POSTStatuses] = None) -> Response:
        if not statuses:
            statuses = POSTStatuses()
        data = dict()
        if not flag.status:
            data = CustomErrorSerializer({"detail": flag.error.message, "code": flag.error.code}).data
        return Response(data, status=statuses.success if flag.status else statuses.error)


class VacancyViewSet(GenericViewSet, mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.DestroyModelMixin,
                     mixins.CreateModelMixin, VacancyFilterMixin, VacancySearchMixin, DeleteVacancyMixin,
                     AddVacancyMixin):
    """ Вьюсет для отображения всех, одной, удаления, добавления вакансий на сайте. """

    request_host = RequestHost.APIVIEW

    serializer_class = VacancysSerializer
    serializer_detail_class = validation_class = VacancyDetailSerializer
    lookup_url_kwarg = "ids"
    permission_classes = (IsAuthenticatedCompanyOrReadOnly,)

    def get_queryset(self):
        company = self.request.query_params.get("company", None)
        company = get_object_or_404(User, username=company) if company else None
        filter_kwargs = self.filter(self.request.query_params, company, (not self.request.user == company))
        search_query = self.search(self.request.query_params)
        return Vacancy.objects.filter(**filter_kwargs).filter(search_query)

    @extend_schema(responses={
        status.HTTP_200_OK: serializer_detail_class,
        status.HTTP_404_NOT_FOUND: DefaultErrorSerializer
    })
    def retrieve(self, request, *args, **kwargs) -> Response:
        """ Получение конктретной вакансии по ее id. """

        vacancy = CheckPermissionsToSeeVacancy.check_perms(request, self.kwargs[self.lookup_url_kwarg])
        return Response(self.serializer_detail_class(vacancy, context={"request": request}).data)

    @extend_schema(responses={
        status.HTTP_204_NO_CONTENT: None,
        status.HTTP_403_FORBIDDEN: DefaultErrorSerializer,
        status.HTTP_404_NOT_FOUND: DefaultErrorSerializer
    })
    def destroy(self, request, *args, **kwargs) -> Response:
        """ Удаление конктретной вакансии по ее id. """

        self.delete_vacancy(request, self.kwargs[self.lookup_url_kwarg])
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(request=VacancyDetailSerializer, responses={
        status.HTTP_201_CREATED: None,
        status.HTTP_400_BAD_REQUEST: CustomErrorSerializer
    })
    def create(self, request, *args, **kwargs) -> Response:
        """ Создание новой вакансии. """

        flag = self.add_vacancy(request.data, request.user)
        return POSTView.get_response(flag)


class ApplicantOffersViewSet(GenericViewSet, mixins.ListModelMixin, mixins.CreateModelMixin, mixins.DestroyModelMixin,
                             mixins.RetrieveModelMixin, AddOfferMixin, WithdrawOfferMixin):
    """ Вьюсет для отображения всех, одной, добавления, удаления предложений на вакансии со стороны соискателя. """

    serializer_class = validation_class = OffersFullSerializer
    lookup_url_kwarg = "ids"
    permission_classes = (IsAuthenticated, IsApplicant)
    request_host = RequestHost.APIVIEW

    def get_queryset(self):
        return Offer.objects.filter(applicant=self.request.user, vacancy__deleted=False)

    @extend_schema(responses={
        status.HTTP_201_CREATED: None,
        status.HTTP_400_BAD_REQUEST: CustomErrorSerializer,
        status.HTTP_403_FORBIDDEN: DefaultErrorSerializer,
        status.HTTP_404_NOT_FOUND: DefaultErrorSerializer
    })
    def create(self, request, *args, **kwargs) -> Response:
        """ Добавление нового отклика на вакансию. """

        flag = self.add_offer(request.user, request.data.get("vacancy", 0), request.data, request.data)
        return POSTView.get_response(flag)

    @extend_schema(responses={
        status.HTTP_204_NO_CONTENT: None,
        status.HTTP_403_FORBIDDEN: DefaultErrorSerializer,
        status.HTTP_404_NOT_FOUND: DefaultErrorSerializer
    }, parameters=[
            OpenApiParameter(name="ids", type=int, location=OpenApiParameter.PATH)
    ])
    def destroy(self, request, *args, **kwargs) -> Response:
        """ Отозвать отклик на вакансию по его id. """

        self.withdraw_offer(request, self.kwargs[self.lookup_url_kwarg])
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(responses={
        status.HTTP_200_OK: serializer_class,
        status.HTTP_404_NOT_FOUND: DefaultErrorSerializer
    })
    def retrieve(self, request, *args, **kwargs) -> Response:
        """ Получение оффера соискателя. """

        offer = get_object_or_404(Offer, pk=self.kwargs[self.lookup_url_kwarg])
        return Response(self.get_serializer_class()(instance=offer).data, status=status.HTTP_200_OK)


class UpdateSettingsAPIView(APIView, UpdateSettingsMixin):
    request_host = RequestHost.APIVIEW
    permission_classes = (IsAuthenticated,)

    @extend_schema(request={
        "Соискатель": ApplicantSettingsSerializer,
        "Компания": CompanySettingsSerializer
    }, responses={
        status.HTTP_201_CREATED: None,
        status.HTTP_400_BAD_REQUEST: CustomErrorSerializer,
        status.HTTP_401_UNAUTHORIZED: DefaultErrorSerializer
    })
    def post(self, request: Request):
        """ Обновление настроек пользователя (как компании, так и соискателя). """

        flag = self.update_settings(request, request.data, request.data)
        return POSTView.get_response(flag)


class GetCompanyRatingsAPIView(ListAPIView):
    """ Получение отзывов на конкретную компанию по ее username. """

    serializer_class = validation_class = RatingsSerializer
    lookup_url_kwarg = "uname"

    def get_queryset(self):
        return Rating.objects.filter(company__username=self.kwargs[self.lookup_url_kwarg])


class GetCompanyDetailAPIView(APIView):
    serializer_class = CompanyDetailSerializer

    @extend_schema(responses={
        status.HTTP_200_OK: serializer_class,
        status.HTTP_404_NOT_FOUND: DefaultErrorSerializer
    })
    def get(self, request: Request, uname: str) -> Response:
        """ Получение детальной информации о конктретной компании. """

        user = get_object_or_404(User, username=uname)
        return Response(self.serializer_class(user, context={"request": request}).data, status=status.HTTP_200_OK)


@extend_schema_view(get=extend_schema(responses={
    status.HTTP_200_OK: VacancyOffersSerializer,
    status.HTTP_403_FORBIDDEN: DefaultErrorSerializer,
    status.HTTP_404_NOT_FOUND: DefaultErrorSerializer
}))
class GetVacancyOffersAPIView(ListAPIView, CheckPermissionsToSeeVacancyOffersAndDeleteVacancy):
    """ Получение всех откликов на вакансию по ее id. """

    serializer_class = VacancyOffersSerializer
    lookup_url_kwarg = "ids"

    def get_queryset(self):
        vacancy = self.check_perms(self.request, self.kwargs[self.lookup_url_kwarg])
        return Offer.objects.filter(vacancy=vacancy, withdrawn=False)


class AddRatingAPIView(APIView, AddRatingMixin):
    permission_classes = (IsAuthenticated,)
    serializer_class = validation_class = RatingsSerializer
    request_host = RequestHost.APIVIEW

    @extend_schema(responses={
        status.HTTP_201_CREATED: None,
        status.HTTP_400_BAD_REQUEST: CustomErrorSerializer,
        status.HTTP_403_FORBIDDEN: DefaultErrorSerializer
    })
    def post(self, request: Request, uname: str) -> Response:
        """ Добавление отзыва на компанию со стороны соискателя. """

        flag = self.add_rating(request.user, uname, request.data)
        return POSTView.get_response(flag)


class ApplyOfferAPIView(APIView, ApplyOfferMixin):
    @extend_schema(responses={
        status.HTTP_201_CREATED: None,
        status.HTTP_403_FORBIDDEN: DefaultErrorSerializer,
        status.HTTP_404_NOT_FOUND: DefaultErrorSerializer
    })
    def post(self, request: Request, ids: int) -> Response:
        """ Принятие оффера от соискателя по его id. """

        self.apply_offer(request, ids)
        return Response(status=status.HTTP_201_CREATED)


class CompanyApplyedOffersAPIView(ListAPIView, CompanyApplyedOffersMixin):
    """ Получение принятых компанией офферов. """

    serializer_class = CompanyApplyedOffersSerializer
    permission_classes = (IsAuthenticated, IsCompany)

    def get_queryset(self):
        return self.get_company_applyed_offers(self.request.user, False)

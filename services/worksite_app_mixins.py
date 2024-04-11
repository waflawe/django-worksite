from typing import Any, Dict, Literal, NoReturn, Optional, Tuple, Type, Union

from django import forms
from django.conf import settings
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied
from django.db import IntegrityError, models
from django.db.models import Avg, Q
from django.db.models.query import QuerySet
from django.http import Http404, HttpRequest
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.request import Request

from error_messages.worksite_error_messages import OfferErrors, RatingErrors, VacancyErrors
from services.common_utils import (
    DefaultPOSTReturn,
    RequestHost,
    check_is_user_company,
    get_error_field,
    get_user_settings,
)
from worksite_app.constants import EXPERIENCE_CHOICES_VALID_VALUES, FILTERED_CITIES
from worksite_app.models import Offer, Rating, Vacancy

Instance = models.Model
ValidationClass = Union[Type[serializers.ModelSerializer] | Type[forms.ModelForm]]


def get_company_ratings(company: User) -> QuerySet:
    cache_ratings_name = f"{company.pk}{settings.CACHE_NAMES_DELIMITER}{settings.COMPANY_RATINGS_CACHE_NAME}"
    queryset = cache.get(cache_ratings_name)
    if not queryset:
        queryset = Rating.objects.filter(company=company).select_related("applicant")
        cache.set(cache_ratings_name, queryset, 60 * 60 * 24)
    return queryset


class CheckPermissionsToSeeVacancy(object):
    """ Проверка прав на просмотр конкретной вакансии. """

    @staticmethod
    def check_perms(request: HttpRequest | Request, ids: int) -> Vacancy | NoReturn:
        try:
            vacancy = Vacancy.objects.select_related("company").get(pk=ids)
        except ObjectDoesNotExist:
            raise Http404
        if vacancy.archived:
            applicant = Offer.objects.select_related("applicant").get(vacancy=vacancy, applyed=True).applicant
            if not (vacancy.company == request.user or request.user == applicant):
                raise Http404
        if vacancy.deleted:
            raise Http404
        return vacancy


class CheckPermissionsToSeeVacancyOffersAndDeleteVacancy(object):
    """ Проверка прав на просмотр откликов соискателей на вакансию и на удаление вакансии. """

    @staticmethod
    def check_perms(request: HttpRequest | Request, ids: int) -> Vacancy | NoReturn:
        vacancy = get_object_or_404(Vacancy, pk=ids)
        if vacancy.archived or vacancy.deleted:
            raise Http404
        elif request.user != vacancy.company:
            raise PermissionDenied
        return vacancy


class VacancySearchMixin(object):
    """ Миксин для составления запроса (класс Q()) на icontains поиск по определенным полям вакансии. """

    search_fields = "name", "description"

    def search(self, params: Dict[str, str], **kwargs) -> Q:
        query = Q()
        for field in self.search_fields:
            query = query | self._field_icontains_search(params, field)
        return query

    def _field_icontains_search(self, params: Dict[str, str], field: str) -> Q:
        search = params.get("search", None)
        if params.get(f"{field}_search", None) and search:
            return Q(**{f"{field}__icontains": search})
        return Q()


class VacancyFilterMixin(object):
    """ Миксин для фильтрации вакансий по городу, зарплате, требуемому опыту работы. """

    def filter(self, params: Dict[str, str], company_filter: Optional[User] = None,
               only_not_archived: Optional[bool] = True, **kwargs) -> Dict:
        city_kwargs = self._city_filter(params, company_filter, only_not_archived)
        celery_kwargs = self._celery_filter(params)
        experience_kwargs = self._experience_filter(params)
        return city_kwargs | celery_kwargs | experience_kwargs | {"deleted": False}

    def _city_filter(self, params: Dict[str, str], company_filter: Optional[User] = None,
                     only_not_archived: Optional[bool] = True) -> Dict:
        city = params.get("city", None)
        kwargs = {}
        if only_not_archived:
            kwargs["archived"] = False
        if company_filter:
            kwargs["company"] = company_filter
        if city not in (None, "False", "Любой") and city in FILTERED_CITIES:
            kwargs["city"] = params["city"]
        return kwargs

    def _celery_filter(self, params: Dict[str, str]) -> Dict:
        celery_from, celery_to = params.get("celery_from", None), params.get("celery_to", None)
        kwargs = {}
        if celery_from and celery_from.isnumeric() and int(celery_from) >= 1000:
            kwargs["money__gte"] = int(celery_from)
        if celery_to and celery_to.isnumeric() and int(celery_to) <= 1000000:
            kwargs["money__lte"] = int(celery_to)
        return kwargs

    def _experience_filter(self, params: Dict[str, str]) -> Dict:
        args = [ex for ex in EXPERIENCE_CHOICES_VALID_VALUES if params.get(f"ex{ex}", None)]
        if args:
            return {"experience__in": args}
        return {}


class DataValidationMixin(object):
    """ Класс для валидации через форму/сериализатор полученной от пользователя информации. """

    validation_class: ValidationClass = None  # ссылка на класс-валидатор, должна быть переопределена

    def validate_received_data(self, data: Dict, files: Dict, instance: Optional[Instance] = None,
                               validation_class: Optional[ValidationClass] = None) -> Tuple[Any, bool, Dict]:
        validation_class = validation_class if validation_class else self.validation_class
        validator_object = None

        if issubclass(validation_class, serializers.ModelSerializer):
            validator_object = validation_class(data=self.get_data_to_serializer(data, files), instance=instance)
        elif issubclass(validation_class, forms.ModelForm):
            validator_object = validation_class(data, files, instance=instance)

        if validator_object:
            is_valid = validator_object.is_valid()
            return validator_object, is_valid, getattr(
                validator_object,
                "validated_data" if hasattr(validator_object, "validated_data") else "cleaned_data"
            )
        raise TypeError(f"Invalid validation class: {validation_class}")

    def get_data_to_serializer(self, data: Dict, files: Dict) -> Dict:  # должен быть переопределен
        """
        При использовании сериализатора в качестве валидатора функция должна возвращать данные,
        передаваемые в инициализатор сериализатора.
        """

        raise NotImplementedError()


class AddVacancyMixin(DataValidationMixin):
    """ Миксин для добавления вакансии. """

    request_host = None   # переменная-источник запроса. Имеет значение RequestHost.APIVIEW или RequestHost.VIEW

    def add_vacancy(self, data: Dict, author: User) -> DefaultPOSTReturn:
        v, is_valid, data_ = self.validate_received_data(data, {}, instance=Vacancy(company=author))
        if is_valid:
            v.save()
            return DefaultPOSTReturn(True)
        return DefaultPOSTReturn(False, VacancyErrors[get_error_field(self.request_host, v)])

    def get_data_to_serializer(self, data: Dict, files: Dict) -> Dict:
        return data


class AddOfferMixin(DataValidationMixin):
    """ Миксин для создания оффера на вакансию от имени соискателя. """

    request_host = None   # переменная-источник запроса. Имеет значение RequestHost.APIVIEW или RequestHost.VIEW

    def add_offer(self, applicant: User, ids: int, data: Dict, files: Dict) -> DefaultPOSTReturn:
        vacancy = get_object_or_404(Vacancy, pk=ids)
        AddOfferMixin.check_perms(applicant, vacancy)
        resume_collection = (data if self.request_host == RequestHost.APIVIEW else files)
        offer = Offer(applicant=applicant, vacancy=vacancy,
                      resume=resume_collection.get("resume", None), resume_text=data.get("resume_text", ""))
        v, is_valid, data_ = self.validate_received_data(data, {}, instance=offer)

        if is_valid:
            try:
                if v.instance.resume_text == "":
                    v.instance.resume_text = None
                v.save()
                return DefaultPOSTReturn(True)
            except IntegrityError:
                return DefaultPOSTReturn(False, OfferErrors["vacancy"])
        return DefaultPOSTReturn(False, OfferErrors[get_error_field(self.request_host, v)])

    @staticmethod
    def check_perms(applicant: User, vacancy: Vacancy, raise_exception: Optional[bool] = True) -> bool | NoReturn:
        if vacancy.archived or vacancy.deleted:
            if raise_exception:
                raise Http404
            return False
        offers_exists = Offer.objects.filter(vacancy=vacancy, applicant=applicant).exists()
        if not applicant.is_authenticated or check_is_user_company(applicant) or offers_exists:
            if raise_exception:
                raise PermissionDenied
            return False
        return True

    def get_data_to_serializer(self, data: Dict, files: Dict) -> Dict:
        return data


class AddRatingMixin(DataValidationMixin):
    """ Миксин для добавления отзыва соискателя на компанию. """

    request_host = None   # переменная-источник запроса. Имеет значение RequestHost.APIVIEW или RequestHost.VIEW

    def add_rating(self, applicant: User, uname: str, data: Dict) -> DefaultPOSTReturn | NoReturn:
        company = get_object_or_404(User, username=uname)
        if not AddRatingMixin.check_perms(applicant, company):
            raise PermissionDenied
        instance = Rating(applicant=applicant, company=company)
        v, is_valid, data = self.validate_received_data(data, {}, instance=instance)

        if is_valid:
            v.save()
            company_s = get_user_settings(company)
            rating = Rating.objects.aggregate(Avg("rating"))["rating__avg"]
            company_s.rating = round(rating, 2)
            company_s.save()
            cache.delete(f"{company.pk}{settings.CACHE_NAMES_DELIMITER}{settings.USER_SETTINGS_CACHE_NAME}")
            return DefaultPOSTReturn(company)
        return DefaultPOSTReturn(False, RatingErrors[get_error_field(self.request_host, v)])

    @staticmethod
    def check_perms(applicant: User, company: User) -> bool:
        if (not applicant.is_authenticated) or check_is_user_company(applicant):
            return False
        offer = Offer.objects.filter(
            vacancy__in=Vacancy.objects.filter(company=company).all(), applyed=True, applicant=applicant
        ).exists()
        if offer:
            rating = Rating.objects.filter(applicant=applicant, company=company).exists()
            if not rating:
                return True
        return False

    def get_data_to_serializer(self, data: Dict, files: Dict) -> Dict:
        return data


class ApplyOfferMixin(object):
    """ Миксин для принятия оффера от соискателя на вакансию. """

    def apply_offer(self, request: Request | HttpRequest, ids: int) -> Literal[None] | NoReturn:
        offer = ApplyOfferMixin.check_perms(request, ids)
        offer.applyed = offer.vacancy.archived = True
        offer.time_applyed = timezone.now()
        offer.vacancy.save()
        offer.save()

    @staticmethod
    def check_perms(request: Request | HttpRequest, ids: int) -> Offer | NoReturn:
        try:
            offer = Offer.objects.select_related("vacancy").get(pk=ids)
        except ObjectDoesNotExist:
            raise Http404
        vacancy = offer.vacancy
        if (not request.user.is_authenticated) or (vacancy.company != request.user):
            raise PermissionDenied
        elif vacancy.archived or vacancy.deleted or offer.withdrawn or offer.applyed:
            raise Http404
        return offer


class DeleteVacancyMixin(object):
    """ Миксин для удаления вакансии. """

    def delete_vacancy(self, request: HttpRequest | Request, ids: int) -> Literal[None] | NoReturn:
        vacancy = CheckPermissionsToSeeVacancyOffersAndDeleteVacancy.check_perms(request, ids)
        vacancy.deleted = True
        vacancy.save()


class WithdrawOfferMixin(object):
    """ Миксин для отмены оффера на вакансию со стороны соискателя. """

    def withdraw_offer(self, request: HttpRequest | Request, ids: int) -> Literal[None] | NoReturn:
        offer = WithdrawOfferMixin.check_perms(request, ids)
        offer.withdrawn = True
        offer.save()

    @staticmethod
    def check_perms(request: HttpRequest | Request, ids: int) -> Offer | NoReturn:
        try:
            offer = Offer.objects.select_related("vacancy").get(pk=ids)
        except ObjectDoesNotExist:
            raise Http404
        if offer.withdrawn or offer.applyed or offer.applicant != request.user:
            raise PermissionDenied
        return offer


class CompanyApplyedOffersMixin(object):
    """ Миксин для получения всех предложений соискателей к компании, которые (предложения) были одобрены. """

    def get_company_applyed_offers(self, company: User, check_perms: Optional[bool] = True) -> QuerySet:
        if check_perms:
            CompanyApplyedOffersMixin.check_perms(company)
        return (Offer.objects.select_related("applicant", "vacancy").filter(vacancy__company=company, applyed=True)
                .order_by("-time_applyed"))

    @staticmethod
    def check_perms(company: User) -> Literal[None] | NoReturn:
        assert check_is_user_company(company), PermissionDenied

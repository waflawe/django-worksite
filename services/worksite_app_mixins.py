from django.contrib.auth.models import User
from django.db.models import Q, Avg
from django.db.models.query import QuerySet
from django.core.exceptions import PermissionDenied, ObjectDoesNotExist
from django.shortcuts import get_object_or_404
from django.db import IntegrityError
from django import forms
from django.db import models
from rest_framework import serializers
from rest_framework.request import Request
from django.http import HttpRequest, Http404
from django.utils import timezone

from worksite_app.constants import FILTERED_CITIES, EXPERIENCE_CHOICES_VALID_VALUES
from worksite_app.models import Vacancy, Offer, Rating
from home_app.models import CompanySettings
from services.common_utils import Error_code, check_is_user_company

from typing import Optional, Dict, Literal, Union, NamedTuple, NoReturn, Tuple, Any, Type

Instance = models.Model
ValidationClass = Union[Type[serializers.ModelSerializer] | Type[forms.ModelForm]]


class AddOfferReturn(NamedTuple):
    is_success: bool
    message: Union[Literal["SUCCESS"], Error_code]


class CheckPermissionsToSeeVacancy(object):
    """ Проверка прав на просмотр конкретной вакансии. """

    def check_perms(self, request: HttpRequest | Request, ids: int) -> Vacancy | NoReturn:
        try:
            vacancy = Vacancy.objects.select_related("company").get(pk=ids)
        except ObjectDoesNotExist:
            raise Http404
        if vacancy.archived:
            try:
                applicant = Offer.objects.select_related("applicant").get(vacancy=vacancy, applyed=True).applicant
            except ObjectDoesNotExist:
                raise Http404
            if not (vacancy.company == request.user or request.user == applicant):
                raise Http404
        if vacancy.deleted:
            raise Http404
        return vacancy


class CheckPermissionsToSeeVacancyOffersAndDeleteVacancy(object):
    """ Проверка прав на просмотр откликов соискателей на вакансию и на удаление вакансии. """

    def check_perms(self, request: HttpRequest | Request, ids: int) -> Vacancy | NoReturn:
        vacancy = get_object_or_404(Vacancy, pk=ids)
        if vacancy.archived or vacancy.deleted:
            raise Http404
        elif request.user != vacancy.company:
            raise PermissionDenied
        return vacancy


class VacancySearchMixin(object):
    """ Миксин для выполнения icontains поиска по определенным полям вакансии. """

    search_fields = ("name", "description")

    def search(self, params: Dict[str, str]) -> Q:
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

    def filter(self, params: Dict[str, str], company: Optional[User] = None,
               only_not_archived: Optional[bool] = True) -> Dict:
        city_kwargs = self._city_filter(params, company, only_not_archived)
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

    def validate_received_data(self, data: Dict, files: Optional[Dict] = None,
                               instance: Optional[Instance] = None,
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
        return None, False, {}

    def get_data_to_serializer(self, data: Dict, files: Dict) -> Dict:  # должен быть переопределен
        """
        При использовании сериализатора в качестве валидатора функция должна возвращать данные,
        передаваемые в инициализатор сериализатора.
        """

        raise NotImplementedError()


class AddVacancyMixin(DataValidationMixin):
    """ Миксин для добавления вакансии. """

    def add_vacancy(self, author: User, data: Dict) -> Vacancy | Literal[False]:
        try:
            vacancy = Vacancy(company=author, experience=data["experience"], skills=str(data["skills"]))
        except KeyError:
            return False
        v, is_valid, data_ = self.validate_received_data(data, instance=vacancy)

        try:
            if is_valid and data["city"] in FILTERED_CITIES and data["experience"] in EXPERIENCE_CHOICES_VALID_VALUES:
                return v.save()
        except Exception as ex:
            return False
        return False

    def get_data_to_serializer(self, data: Dict, files: Dict) -> Dict:
        return data


class AddOfferMixin(DataValidationMixin):
    """ Миксин для создания оффера компании от соискателя. """

    def add_offer(self, applicant: User, ids: int, data: Dict, files: Dict) -> AddOfferReturn:
        vacancy = get_object_or_404(Vacancy, pk=ids)
        self.check_perms(applicant, vacancy)
        offer = Offer(applicant=applicant, vacancy=vacancy, resume=files.get("resume", None))
        v, is_valid, data_ = self.validate_received_data(data, files, instance=offer)

        if is_valid:
            try:
                if v.instance.resume_text == "": v.instance.resume_text = None
                v.save()
                return AddOfferReturn(True, "SUCCESS")
            except IntegrityError:
                return AddOfferReturn(False, 3)
        return AddOfferReturn(False, 1)

    def check_perms(self, applicant: User, vacancy: Vacancy) -> Literal[None] | NoReturn:
        if vacancy.archived or vacancy.deleted:
            raise Http404
        offers_exists = Offer.objects.filter(vacancy=vacancy, applicant=applicant).exists()
        if not applicant.is_authenticated or check_is_user_company(applicant) or offers_exists:
            raise PermissionDenied

    def get_data_to_serializer(self, data: Dict, files: Dict) -> Dict:
        try:
            data_to_serializer = (data | files | {"vacancy": int(str(data.get("vacancy", None)))})
        except ValueError:
            raise Http404
        if data.get("resume_text", None):
            data_to_serializer["resume_text"] = str(data.get("resume_text", None))
        return data_to_serializer


class AddRatingMixin(DataValidationMixin):
    """ Миксин для добавления отзыва соискателя на компанию. """

    def add_rating(self, applicant: User, uname: str, data: Dict) -> bool | NoReturn:
        company = get_object_or_404(User, username=uname)
        if not self.check_perms(applicant, company):
            raise PermissionDenied
        rating = Rating(applicant=applicant, company=company)
        data = dict(data | {"applicant": applicant.pk, "rating": int(data["rating"]), "comment": str(data["comment"])})
        v, is_valid, data = self.validate_received_data(data, instance=rating)

        if is_valid:
            v.save()
            company = CompanySettings.objects.filter(company=company)
            company.update(rating=Rating.objects.aggregate(Avg("rating"))["rating__avg"])
            return True
        return False

    def check_perms(self, applicant: User, company: User) -> bool:
        offer = Offer.objects.filter(
            vacancy__in=Vacancy.objects.filter(company=company).all(), applyed=True, applicant=applicant
        ).exists()
        if offer:
            rating = Rating.objects.filter(applicant=applicant, company=company).exists()
            if not rating:
                return True
        return False

    def get_data_to_serializer(self, data: Dict, files: Dict) -> Dict:
        another_data = {
            "applicant": data.get("applicant"),
            "rating": data.get("rating"),
            "comment": str(data["comment"])
        }
        return data | another_data


class ApplyOfferMixin(object):
    """ Миксин для создания предложения компании от имени соискателя. """

    def apply_offer(self, request: Request | HttpRequest, ids: int) -> Literal[None] | NoReturn:
        offer = self.check_perms(request, ids)
        offer.applyed = offer.vacancy.archived = True
        offer.time_applyed = timezone.now()
        offer.vacancy.save()
        offer.save()

    def check_perms(self, request: HttpRequest, ids: int) -> Offer | NoReturn:
        try:
            offer = Offer.objects.select_related("vacancy").get(pk=ids)
        except ObjectDoesNotExist:
            raise Http404
        vacancy = offer.vacancy
        if (not request.user.is_authenticated) or (vacancy.company.username != request.user.username):
            raise PermissionDenied
        elif vacancy.archived or vacancy.deleted or offer.withdrawn or offer.applyed:
            raise Http404
        return offer


class DeleteVacancyMixin(CheckPermissionsToSeeVacancyOffersAndDeleteVacancy):
    """ Миксин для удаления вакансии. """

    def delete_vacancy(self, request: HttpRequest | Request, ids: int) -> Literal[None] | NoReturn:
        vacancy = self.check_perms(request, ids)
        vacancy.deleted = True
        vacancy.save()


class WithdrawOfferMixin(object):
    """ Миксин для отмены оффера на вакансию со стороны соискателя. """

    def withdraw_offer(self, request: HttpRequest | Request, ids: int) -> Literal[None] | NoReturn:
        offer = WithdrawOfferMixin().check_perms(request, ids)
        offer.withdrawn = True
        offer.save()

    def check_perms(self, request: HttpRequest | Request, ids: int) -> Offer | NoReturn:
        try:
            offer = Offer.objects.select_related("vacancy").get(pk=ids)
        except ObjectDoesNotExist:
            raise Http404
        if offer.withdrawn or offer.applyed:
            raise Http404
        elif offer.applicant != request.user:
            raise PermissionDenied
        return offer


class CompanyApplyedOffersMixin(object):
    """ Миксин для получения всех предложений соискателей компании, которые (предложения) были одобрены. """

    def get_company_applyed_offers(self, company: User, check_perms: Optional[bool] = True) -> QuerySet:
        if check_perms:
            self.check_perms(company)
        return (Offer.objects.select_related("applicant", "vacancy")
                .filter(vacancy__company=company, applyed=True).order_by("-time_added").all())

    def check_perms(self, company: User) -> Literal[None] | NoReturn:
        if not check_is_user_company(company): raise Http404

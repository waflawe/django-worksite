from rest_framework import serializers
from rest_framework.request import Request
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema_field
from drf_spectacular.types import OpenApiTypes

from worksite_app.models import Vacancy, Offer, Rating
from services.common_utils import get_timezone
from worksite_app.constants import EXPERIENCE_CHOICES
from home_app.models import CompanySettings, ApplicantSettings
from worksite.settings import BASE_DIR

from datetime import datetime
from typing import Tuple, Dict, Literal
import pytz


def set_datetime_to_timezone(dt: datetime, timezone: str) -> Tuple[datetime | Literal[None], str | Literal[None]]:
    if dt:
        dt = pytz.timezone(timezone).localize(datetime(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second))
        return (dt + dt.utcoffset()), timezone
    return None, None


def set_time_to_user_timezone(request: Request, time: datetime, attribute_name: str = "time_added") -> Dict:
    user_timezone = get_timezone(request)
    if user_timezone:
        time, timezone = set_datetime_to_timezone(time, user_timezone)
        return {attribute_name: time.strftime("%H:%M %d/%m/%Y") if time else None, "timezone": timezone}
    return {attribute_name: time.strftime("%H:%M %d/%m/%Y") if time else None, "timezone": "UTC"}


class DefaultErrorSerializer(serializers.Serializer):
    detail = serializers.CharField()


class CustomErrorSerializer(serializers.Serializer):
    detail = serializers.CharField()
    code = serializers.CharField()


class CompanySettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompanySettings
        fields = None
        extra_kwargs = {}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.context.get("view_rating", False):
            self.Meta.fields = "company_logo", "company_description", "company_site", "rating"
        else:
            self.Meta.fields = "timezone", "company_logo", "company_description", "company_site"
        for field in self.Meta.fields:
            self.Meta.extra_kwargs[field] = {'required': False}


class ApplicantSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = ApplicantSettings
        fields = "timezone", "applicant_avatar"
        extra_kwargs = {}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.Meta.fields:
            self.Meta.extra_kwargs[field] = {'required': False}


class ChoiceField(serializers.ChoiceField):
    def to_representation(self, value):
        return EXPERIENCE_CHOICES[int(value)][1]


class VacancysSerializer(serializers.ModelSerializer):
    company = serializers.SerializerMethodField()
    time_added = serializers.SerializerMethodField()
    experience = ChoiceField(choices=EXPERIENCE_CHOICES)

    class Meta:
        model = Vacancy
        fields = (
            "id", "company", "name", "money", "experience",
            "city", "time_added", "archived"
        )

    @extend_schema_field(serializers.DictField)
    def get_company(self, vacancy):
        return {"company_username": vacancy.company.username, "company_name": vacancy.company.first_name}

    @extend_schema_field(serializers.DictField)
    def get_time_added(self, vacancy):
        return set_time_to_user_timezone(self.context["request"], vacancy.time_added)

    @extend_schema_field(OpenApiTypes.STR)
    def get_experience_data(self, vacancy):
        return EXPERIENCE_CHOICES[int(vacancy.experience)][1]


class VacancyDetailSerializer(VacancysSerializer):
    class Meta:
        model = Vacancy
        fields = (
            "pk", "company", "name", "description", "money",
            "experience", "city", "skills", "time_added", "archived"
        )
        read_only_fields = "pk", "company", "time_added", "archived"
        extra_kwargs = {}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in ("name", "description", "money", "experience", "city", "skills"):
            self.Meta.extra_kwargs[field] = {"required": True}


class CompanyDetailSerializer(serializers.ModelSerializer):
    company_name = serializers.SerializerMethodField()
    company_info = serializers.SerializerMethodField()
    date_joined = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = "username", "company_name", "date_joined", "company_info"

    @extend_schema_field(OpenApiTypes.STR)
    def get_company_name(self, company):
        return company.first_name

    @extend_schema_field(serializers.DictField)
    def get_company_info(self, company):
        settings = get_object_or_404(CompanySettings, company=company)
        data = CompanySettingsSerializer(instance=settings, context={"view_rating": True})
        vacancys_count = Vacancy.objects.filter(company=company, archived=False, deleted=False).count()
        return data.data | {"vacancys_count": vacancys_count}

    @extend_schema_field(serializers.DictField)
    def get_date_joined(self, company):
        return set_time_to_user_timezone(self.context["request"], company.date_joined, "date_joined")


class _BaseOfferSerializer(serializers.ModelSerializer):
    time_added = serializers.SerializerMethodField()
    resume = serializers.SerializerMethodField()
    applicant = serializers.SerializerMethodField()

    @extend_schema_field(serializers.DictField)
    def get_time_added(self, offer):
        return set_time_to_user_timezone(self.context["request"], offer.time_added)

    @extend_schema_field(OpenApiTypes.STR)
    def get_resume(self, offer):
        if offer.resume:
            return offer.resume.path.split(str(BASE_DIR))[-1]  # POPRAVIT'!
        return None

    @extend_schema_field(OpenApiTypes.STR)
    def get_applicant(self, offer):
        return offer.applicant.username


class OffersFullSerializer(_BaseOfferSerializer):
    time_applyed = serializers.SerializerMethodField()

    class Meta:
        model = Offer
        fields = (
            "id", "vacancy", "applicant", "resume", "resume_text",
            "time_added", "time_applyed", "applyed", "withdrawn"
        )
        read_only_fields = "id", "time_added", "time_applyed", "applyed", "withdrawn"

    @extend_schema_field(serializers.DictField)
    def get_time_applyed(self, offer):
        return set_time_to_user_timezone(self.context["request"], offer.time_applyed, "time_applyed")


class CompanyApplyedOffersSerializer(OffersFullSerializer):
    time_applyed = serializers.SerializerMethodField()

    class Meta:
        model = Offer
        fields = (
            "id", "vacancy", "applicant", "resume", "resume_text",
            "time_added", "time_applyed"
        )
        read_only_fields = "id", "time_added", "time_applyed"


class VacancyOffersSerializer(_BaseOfferSerializer):
    class Meta:
        model = Offer
        fields = "id", "applicant", "resume", "resume_text", "time_added"
        read_only_fields = "id", "time_added"


class RatingsSerializer(serializers.ModelSerializer):
    time_added = serializers.SerializerMethodField()
    applicant = serializers.SerializerMethodField()

    class Meta:
        model = Rating
        fields = "applicant", "rating", "comment", "time_added"

    @extend_schema_field(serializers.DictField)
    def get_time_added(self, rating):
        return set_time_to_user_timezone(self.context["request"], rating.time_added)

    @extend_schema_field(OpenApiTypes.STR)
    def get_applicant(self, rating):
        return rating.applicant.username

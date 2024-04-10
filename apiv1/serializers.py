from rest_framework import serializers
from django.contrib.auth.models import User
from drf_spectacular.utils import extend_schema_field
from drf_spectacular.types import OpenApiTypes
from django.conf import settings

from worksite_app.models import Vacancy, Offer, Rating
from services.common_utils import get_timezone, get_user_settings
from worksite_app.constants import EXPERIENCE_CHOICES
from home_app.models import CompanySettings, ApplicantSettings

from datetime import datetime
from typing import Tuple, Dict, Literal
import pytz

UserSettings = ApplicantSettings | CompanySettings


def set_datetime_to_timezone(dt: datetime, timezone: str) -> Tuple[datetime | Literal[None], str | Literal[None]]:
    """ Приведение datetime объекта к временной зоне в общем виде. """

    if dt:
        dt = pytz.timezone(timezone).localize(datetime(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second))
        return (dt + dt.utcoffset()), timezone
    return None, None


def set_time_to_user_timezone(user: User | UserSettings, time: datetime, attribute_name: str = "time_added") -> Dict:
    """ Приведение datetime объекта к временной зоне, установленной в настройках текущего пользователя. """

    user_timezone = get_timezone(user)
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
        extra_kwargs = {"timezone": {"required": False}, "applicant_avatar": {"required": False}}


class ExperienceChoiceField(serializers.ChoiceField):
    def to_representation(self, value):
        return EXPERIENCE_CHOICES[int(value)][1]


class CompanySerializer(serializers.ModelSerializer):
    company_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = "username", "company_name"

    def get_company_name(self, company):
        return company.first_name


class CompanyDetailSerializer(CompanySerializer):
    company_info = serializers.SerializerMethodField()
    date_joined = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = "username", "company_name", "date_joined", "company_info"

    @extend_schema_field(serializers.DictField)
    def get_company_info(self, company):
        settings_ = get_user_settings(company)
        data = CompanySettingsSerializer(instance=settings_, context={"view_rating": True})
        vacancys_count = Vacancy.objects.filter(company=company, archived=False, deleted=False).count()
        return data.data | {"vacancys_count": vacancys_count}

    @extend_schema_field(serializers.DictField)
    def get_date_joined(self, company):
        return set_time_to_user_timezone(self.context["request"].user, company.date_joined, "date_joined")


class VacancysSerializer(serializers.ModelSerializer):
    company = CompanySerializer(read_only=True)
    time_added = serializers.SerializerMethodField()
    experience = ExperienceChoiceField(choices=EXPERIENCE_CHOICES)

    class Meta:
        model = Vacancy
        fields = (
            "id", "company", "name", "money", "experience",
            "city", "time_added", "archived"
        )

    @classmethod
    def setup_eager_loading(cls, queryset):
        queryset = queryset.prefetch_related("company")
        return queryset

    @extend_schema_field(serializers.DictField)
    def get_time_added(self, vacancy):
        return set_time_to_user_timezone(self.context["request"].user, vacancy.time_added)

    @extend_schema_field(OpenApiTypes.STR)
    def get_experience_data(self, vacancy):
        return EXPERIENCE_CHOICES[int(vacancy.experience)][1]


class VacancyDetailSerializer(VacancysSerializer):
    class Meta:
        immutable_fields = "name", "description", "money", "experience", "city", "skills"
        read_only_fields = "pk", "company", "time_added", "archived"
        model = Vacancy
        fields = *read_only_fields, *immutable_fields
        extra_kwargs = {}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.Meta.immutable_fields:
            self.Meta.extra_kwargs[field] = {"required": True}


class _BaseOfferSerializer(serializers.ModelSerializer):
    time_added = serializers.SerializerMethodField()
    resume = serializers.SerializerMethodField()
    applicant = serializers.SerializerMethodField()

    @extend_schema_field(serializers.DictField)
    def get_time_added(self, offer):
        return set_time_to_user_timezone(self.context["request"].user, offer.time_added)

    @extend_schema_field(OpenApiTypes.STR)
    def get_resume(self, offer):
        return settings.MEDIA_URL + offer.resume.path.split(str(settings.BASE_DIR))[-1].split(settings.MEDIA_ROOT)[-1] \
            if offer.resume else None

    @extend_schema_field(OpenApiTypes.STR)
    def get_applicant(self, offer):
        return offer.applicant.username


class OffersFullSerializer(_BaseOfferSerializer):
    time_applyed = serializers.SerializerMethodField()

    class Meta:
        model = Offer
        read_only_fields = "id", "time_added", "time_applyed", "applyed", "withdrawn"
        fields = *read_only_fields, "vacancy", "applicant", "resume", "resume_text"

    @extend_schema_field(serializers.DictField)
    def get_time_applyed(self, offer):
        return set_time_to_user_timezone(self.context["request"].user, offer.time_applyed, "time_applyed")

    @extend_schema_field(OpenApiTypes.STR)
    def get_applicant(self, offer):
        return self.context["request"].user.username


class CompanyApplyedOffersSerializer(OffersFullSerializer):
    time_applyed = serializers.SerializerMethodField()

    class Meta:
        model = Offer
        read_only_fields = "id", "time_added", "time_applyed"
        fields = *read_only_fields, "vacancy", "applicant", "resume", "resume_text"


class VacancyOffersSerializer(_BaseOfferSerializer):
    class Meta:
        model = Offer
        read_only_fields = "id", "time_added"
        fields = *read_only_fields, "applicant", "resume", "resume_text"


class RatingsSerializer(serializers.ModelSerializer):
    time_added = serializers.SerializerMethodField()
    applicant = serializers.SerializerMethodField()

    class Meta:
        model = Rating
        fields = "applicant", "rating", "comment", "time_added"

    @extend_schema_field(serializers.DictField)
    def get_time_added(self, rating):
        return set_time_to_user_timezone(self.context["request"].user, rating.time_added)

    @extend_schema_field(OpenApiTypes.STR)
    def get_applicant(self, rating):
        return rating.applicant.username

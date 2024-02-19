from rest_framework import serializers
from rest_framework.request import Request
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404

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
    if user_timezone and user_timezone != "Default":
        time, timezone = set_datetime_to_timezone(time, user_timezone)
        return {attribute_name: time.strftime("%H:%M %d/%m/%Y") if time else None, "timezone": timezone}
    return {attribute_name: time.strftime("%H:%M %d/%m/%Y") if time else None, "timezone": "UTC"}


class VacancysSerializer(serializers.ModelSerializer):
    company = serializers.SerializerMethodField()
    time_added = serializers.SerializerMethodField()
    experience = serializers.SerializerMethodField()
    skills = serializers.SerializerMethodField()

    class Meta:
        model = Vacancy
        fields = ("pk", "company", "name", "description", "money", "experience", "city", "skills", "time_added",
                  "archived")

    def get_company(self, vacancy):
        return {"company_username": vacancy.company.username, "company_name": vacancy.company.first_name}

    def get_time_added(self, vacancy):
        return set_time_to_user_timezone(self.context["request"], vacancy.time_added)

    def get_experience(self, vacancy):
        return EXPERIENCE_CHOICES[int(vacancy.experience)][1]

    def get_skills(self, vacancy):
        return vacancy.skills


class CompanySettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompanySettings
        fields = ("company_logo", "company_description", "company_site", "rating")


class CompanyDetailSerializer(serializers.ModelSerializer):
    company_name = serializers.SerializerMethodField()
    company_info = serializers.SerializerMethodField()
    date_joined = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("username", "company_name", "date_joined", "company_info")

    def get_company_name(self, company):
        return company.first_name
        
    def get_company_info(self, company):
        data = CompanySettingsSerializer(instance=get_object_or_404(CompanySettings, company=company))
        return data.data | {"vacancys_count": (Vacancy.objects.filter(company=company, archived=False,
                                                                      deleted=False).count())}

    def get_date_joined(self, company):
        return set_time_to_user_timezone(self.context["request"], company.date_joined, "date_joined")


class OffersSerializer(serializers.ModelSerializer):
    time_added = serializers.SerializerMethodField()
    time_applyed = serializers.SerializerMethodField()
    resume = serializers.SerializerMethodField()
    applicant = serializers.SerializerMethodField()

    class Meta:
        model = Offer
        fields = ["id", "applicant", "resume", "resume_text", "time_added", "time_applyed"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.context.get("view_archived_field", True):
            self.Meta.fields.append("applyed")
        if self.context.get("view_withdrawn_field", False):
            self.Meta.fields.append("withdrawn")
        if self.context.get("view_vacancy_field", True):
            self.Meta.fields.insert(0, "vacancy")

    def get_time_added(self, offer):
        return set_time_to_user_timezone(self.context["request"], offer.time_added)

    def get_time_applyed(self, offer):
        return set_time_to_user_timezone(self.context["request"], offer.time_applyed, "time_applyed")

    def get_resume(self, offer):
        if offer.resume:
            return offer.resume.path.split(str(BASE_DIR))[-1]
        return None

    def get_applicant(self, offer):
        return offer.applicant.username


class RatingsSerializer(serializers.ModelSerializer):
    time_added = serializers.SerializerMethodField()
    applicant = serializers.SerializerMethodField()

    class Meta:
        model = Rating
        fields = ("applicant", "rating", "comment", "time_added")

    def get_time_added(self, rating):
        return set_time_to_user_timezone(self.context["request"], rating.time_added)

    def get_applicant(self, rating):
        return rating.applicant.username


class SettingsSerializer(serializers.ModelSerializer):
    pass


class ApplicantSettingsSerializer(SettingsSerializer):
    class Meta:
        model = ApplicantSettings
        fields = ("applicant_avatar",)


class CompanySettingsSerializer(SettingsSerializer):
    class Meta:
        model = CompanySettings
        fields = ("company_logo", "company_description", "company_site")

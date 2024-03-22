from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator, MinLengthValidator, MaxLengthValidator

from worksite.settings import (
    DEFAULT_APPLICANT_AVATAR_FILENAME, DEFAULT_COMPANY_LOGO_FILENAME, CUSTOM_COMPANY_LOGOS_DIR,
    CUSTOM_APPLICANT_AVATARS_DIR, DEFAULT_USER_TIMEZONE
)


def company_logo_path(instance, filename: str) -> str:
    return f"{CUSTOM_COMPANY_LOGOS_DIR}/{instance.company.pk}/company_logo.{filename.split('.')[-1]}"


def applicant_avatar_path(instance, filename: str) -> str:
    return f"{CUSTOM_APPLICANT_AVATARS_DIR}/{instance.applicant.pk}/{instance.applicant.pk}.{filename.split('.')[-1]}"


class CompanySettings(models.Model):
    company = models.ForeignKey(User, on_delete=models.CASCADE)
    timezone = models.CharField(max_length=30, default=DEFAULT_USER_TIMEZONE)
    company_logo = models.ImageField(upload_to=company_logo_path, default=DEFAULT_COMPANY_LOGO_FILENAME)
    company_description = models.TextField(default="", validators=(MaxLengthValidator(5000), MinLengthValidator(64)))
    company_site = models.URLField(null=True, blank=True)
    rating = models.FloatField(validators=(MinValueValidator(0), MaxValueValidator(5)), default=0)

    def __str__(self):
        return self.company.username


class ApplicantSettings(models.Model):
    applicant = models.ForeignKey(User, on_delete=models.CASCADE)
    timezone = models.CharField(max_length=30, default=DEFAULT_USER_TIMEZONE)
    applicant_avatar = models.ImageField(upload_to=applicant_avatar_path, default=DEFAULT_APPLICANT_AVATAR_FILENAME)

    def __str__(self):
        return self.applicant.username

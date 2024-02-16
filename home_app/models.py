from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator, MinLengthValidator, MaxLengthValidator


def company_logo_path(instance, filename: str) -> str:
    return f"logos/{instance.company.pk}/company_logo.{filename.split('.')[-1]}"


def applicant_avatar_path(instance, filename: str) -> str:
    return f"avatars/{instance.applicant.pk}/{instance.applicant.pk}.{filename.split('.')[-1]}"


class CompanySettings(models.Model):
    company = models.ForeignKey(User, on_delete=models.CASCADE)
    company_logo = models.ImageField(upload_to=company_logo_path, default="default_company_logo.png")
    timezone = models.CharField(max_length=30, default="Default")
    company_description = models.TextField(default="", validators=[MaxLengthValidator(5000), MinLengthValidator(64)])
    company_site = models.URLField(null=True, blank=True)
    rating = models.FloatField(validators=(MinValueValidator(0), MaxValueValidator(5)), default=0)


class ApplicantSettings(models.Model):
    applicant = models.ForeignKey(User, on_delete=models.CASCADE)
    timezone = models.CharField(max_length=30, default="Default")
    applicant_avatar = models.ImageField(upload_to=applicant_avatar_path, default="default_applicant_avatar.jpg")

    def __str__(self):
        return self.applicant.username

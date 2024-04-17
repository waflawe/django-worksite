import json

from django.contrib.auth.models import User
from django.core.validators import MaxValueValidator, MinLengthValidator, MinValueValidator
from django.db import models
from django.db.models.query_utils import Q

from .constants import EXPERIENCE_CHOICES, RATINGS


class Vacancy(models.Model):
    """Модель для вакансий."""

    company = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=100, null=False, validators=[MinLengthValidator(8)])
    description = models.TextField(max_length=2048, validators=[MinLengthValidator(64)], blank=True, default="")
    money = models.PositiveIntegerField(validators=[MaxValueValidator(1000000), MinValueValidator(100)])
    experience = models.CharField(max_length=1, choices=EXPERIENCE_CHOICES)
    city = models.CharField(max_length=20)
    skills = models.CharField(max_length=512, blank=True, default="")
    time_added = models.DateTimeField(auto_now_add=True, blank=True)
    archived = models.BooleanField(default=False)
    deleted = models.BooleanField(default=False)

    class Meta:
        ordering = ("-time_added",)

    def __str__(self):
        return f"{self.name}"

    def set_skills(self, value):
        self.skills = json.dumps(value)


class Offer(models.Model):
    """Модель откликов соискателей на вакансии."""

    applicant = models.ForeignKey(User, on_delete=models.CASCADE)
    vacancy = models.ForeignKey(Vacancy, on_delete=models.CASCADE)
    resume = models.FileField(upload_to="offers/", default="")
    resume_text = models.TextField(max_length=2048, blank=True, default="", validators=[MinLengthValidator(64)])
    applyed = models.BooleanField(default=False)
    withdrawn = models.BooleanField(default=False)
    time_added = models.DateTimeField(auto_now_add=True)
    time_applyed = models.DateTimeField(null=True)

    class Meta:
        constraints = [
            models.CheckConstraint(  # проверка на то, что резюме написано текстом или отправлен файл с резюме.
                check=(~Q(resume="") & Q(resume_text__isnull=True)) | (Q(resume="") & Q(resume_text__isnull=False)),
                name="only_one_resume",
            )
        ]
        ordering = ("-time_added",)

    def __str__(self):
        return f"{self.pk} offer by {self.applicant}"


class Rating(models.Model):
    """Модель отзывов соискателей на компании."""

    applicant = models.ForeignKey(User, on_delete=models.CASCADE)
    company = models.ForeignKey(User, on_delete=models.CASCADE, related_name="+")
    rating = models.PositiveIntegerField(choices=RATINGS, validators=[MaxValueValidator(5)])
    comment = models.TextField(max_length=2048, validators=[MinLengthValidator(64)], blank=True, default="")
    time_added = models.DateTimeField(auto_now_add=True, null=True)

    class Meta:
        ordering = ("-time_added",)

    def __str__(self):
        return f"{self.applicant} review on the '{self.company.first_name}' company"

from django import forms
from django.core.validators import MaxValueValidator, MinValueValidator

from worksite_app.constants import EXPERIENCE_CHOICES, RATINGS
from worksite_app.models import Offer, Rating, Vacancy


class AddVacancyForm(forms.ModelForm):
    name = forms.CharField(
        max_length=100,
        min_length=8,
        widget=forms.TextInput(
            attrs={
                "style": "background-color: rgb(20, 20, 20);" "color: rgb(204, 204, 204)",
            }
        ),
        label="Название вакансии",
    )
    description = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "style": "background-color: rgb(20, 20, 20);" "color: rgb(204, 204, 204)",
            }
        ),
        label="Описание",
        min_length=64,
        max_length=2048,
    )
    money = forms.IntegerField(
        validators=[MinValueValidator(100), MaxValueValidator(1000000)],
        widget=forms.NumberInput(
            attrs={
                "style": "background-color: rgb(20, 20, 20);" "color: rgb(204, 204, 204)",
            }
        ),
        label="Зарплата ($)",
    )
    experience = forms.ChoiceField(choices=EXPERIENCE_CHOICES, required=False)
    city = forms.CharField()
    skills = forms.CharField(
        widget=forms.TextInput(
            attrs={
                "style": "background-color: rgb(20, 20, 20);" "color: rgb(204, 204, 204)",
            }
        ),
        required=False,
    )

    class Meta:
        model = Vacancy
        fields = "name", "description", "money", "experience", "city", "skills"


class AddOfferForm(forms.ModelForm):
    resume = forms.FileField(widget=forms.ClearableFileInput(), label="Ваше резюме (.pdf)", required=False)
    resume_text = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "style": "background-color: rgb(20, 20, 20);" "color: rgb(204, 204, 204)",
            }
        ),
        label="Или напишите о себе",
        required=False,
        min_length=64,
        max_length=2048,
    )

    class Meta:
        model = Offer
        fields = "resume", "resume_text"


class AddRatingForm(forms.ModelForm):
    rating = forms.ChoiceField(choices=RATINGS, required=False, label="Оценка")
    comment = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "style": "background-color: rgb(20, 20, 20);" "color: rgb(204, 204, 204)",
            }
        ),
        label="Комментарий",
        min_length=64,
        max_length=2048,
    )

    class Meta:
        model = Rating
        fields = "rating", "comment"

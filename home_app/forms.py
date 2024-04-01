from django.contrib.auth.forms import UserCreationForm
from django import forms
from django.forms import TextInput, PasswordInput, EmailInput, ClearableFileInput, URLInput, Textarea
from django.core.validators import MaxLengthValidator, MinLengthValidator
from django.contrib.auth.models import User

from home_app.models import CompanySettings, ApplicantSettings


class AuthForm(forms.Form):
    username = forms.CharField(max_length=25, min_length=5, widget=TextInput(attrs={
        'style': 'background-color: rgb(20, 20, 20); color: rgb(204, 204, 204)',
        "class": "form-input"
    }), label="Имя пользователя")
    password = forms.CharField(max_length=64, min_length=8, widget=PasswordInput(attrs={
        'style': 'background-color: rgb(20, 20, 20); color: rgb(204, 204, 204)',
        "class": "form-input"
    }), label="Пароль")


class ApplicantRegisterForm(UserCreationForm):
    class Meta:
        model = User
        fields = ("username", "password1", "password2")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].help_text = "Длина имени пользователя должна быть 5<=длина<=25, имя не " \
                                            "должно включать цифры."
        self.fields['password1'].help_text = "Длина пароля должна быть 8<=длина<=64, " \
                                             "пароль не должен состоять только из цифр."
        self.fields["password2"].help_text = "Введите пароль повторно."
        self.fields["username"].label = "Имя пользователя"
        self.fields["password1"].label = "Пароль"
        self.fields["password2"].label = "Подтверждение пароля"

        for field, input_ in {"username": TextInput, "password1": PasswordInput, "password2": PasswordInput}.items():
            self.fields[field].widget = input_(attrs={
                'style': 'background-color: rgb(20, 20, 20); color: rgb(204, 204, 204)'
            })

    def clean_username(self):
        username = self.cleaned_data["username"]
        if len(username) > 25 or len(username) < 5:
            raise forms.ValidationError("Длина имени должна быть 5<=длина<=25")
        elif any(map(str.isdigit, username)):
            raise forms.ValidationError("Имя не должно включат цифры")

        return username

    def clean_password1(self):
        password1 = self.cleaned_data["password1"]
        if len(password1) > 64 or len(password1) < 8:
            raise forms.ValidationError("Длина пароля должна быть 8<=длина<=64")

        return password1


class CompanyRegisterForm(ApplicantRegisterForm):
    class Meta:
        model = User
        fields = ("username", "first_name",  "email", "password1", "password2")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].help_text = "Введите корпоративную почту."
        self.fields["first_name"].help_text = "Введите название компании."
        self.fields["email"].label = "Почта"
        self.fields["first_name"].label = "Название компании"

        for field, input_ in {"first_name": TextInput, "email": EmailInput}.items():
            self.fields[field].widget = input_(attrs={
                'style': 'background-color: rgb(20, 20, 20); color: rgb(204, 204, 204)'
            })


class UploadPhotoFormMixin(forms.ModelForm):
    def __init__(self, photo_field, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields[photo_field].required, self.fields[photo_field].label = False, "Логотип компании:" \
            if photo_field == "company_logo" else "Ваш аватар:"
        self.fields[photo_field].widget = ClearableFileInput(attrs={
            'style': 'background-color: rgb(20, 20, 20); color: rgb(204, 204, 204)'
        })


class ApplicantSettingsForm(UploadPhotoFormMixin):
    class Meta:
        model = ApplicantSettings
        fields = "applicant_avatar",

    def __init__(self, *args, **kwargs):
        super().__init__("applicant_avatar", *args, **kwargs)

    def save(self, commit=True):
        instance = super().save(commit=False)
        if commit:
            self.instance.save(update_fields=["applicant_avatar"])
        return instance


class CompanySettingsForm(UploadPhotoFormMixin):
    company_description = forms.CharField(widget=Textarea(attrs={
        'style': 'background-color: rgb(20, 20, 20); color: rgb(204, 204, 204)'
    }), required=False, label="Описание компании:", validators=[MaxLengthValidator(5000), MinLengthValidator(64)])
    company_site = forms.URLField(widget=URLInput(attrs={
        'style': 'background-color: rgb(20, 20, 20); color: rgb(204, 204, 204)'
    }), required=False, label="Сайт компании:")

    class Meta:
        model = CompanySettings
        fields = "company_logo", "company_description", "company_site"

    def __init__(self, *args, **kwargs):
        super().__init__("company_logo", *args, **kwargs)

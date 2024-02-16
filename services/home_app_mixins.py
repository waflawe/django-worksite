from rest_framework.request import Request
from django.http.request import HttpRequest
from django.http import Http404
from django.shortcuts import get_object_or_404

from services.common_utils import Error_code, check_is_user_company, RequestHost
from home_app.models import CompanySettings, ApplicantSettings
from services.worksite_app_mixins import DataValidationMixin
from home_app.forms import UploadAvatarForm, UploadLogoForm, AnotherCompanySettingsForm
from tasks.home_app_tasks import make_center_crop
from worksite.settings import BASE_DIR, MEDIA_ROOT
from apiv1.serializers import ApplicantSettingsSerializer, CompanySettingsSerializer

from typing import Dict, Tuple, Union, Literal, NamedTuple, Any, Type
import pytz
import os


class ValidationClasses(NamedTuple):
    photo_validation_class: Type
    description_and_site_validation_class: Type


class CheckOnEditionsReturn(NamedTuple):
    an_error_occured: bool
    status: Union[Literal[None], Literal["SUCCESS"], Error_code]


class UpdateSettingsMixin(DataValidationMixin):
    """ Миксин для обновления настроек пользователя. """

    request_host = None   # переменная-источник запроса. Имеет значение RequestHost.APIVIEW или RequestHost.VIEW

    class Fields:
        """ Перечисление всех полей настроек. """

        TIMEZONE = "timezone"
        COMPANY_LOGO = "company_logo"
        APPLICANT_AVATAR = "applicant_avatar"
        DESCRIPTION = "company_description"
        SITE = "company_site"

    def update_settings(self, request: HttpRequest | Request, data: Dict, files: Dict) \
            -> Tuple[Literal[False] | int, bool]:
        if not request.user.is_authenticated: raise Http404
        validation_classes, company = self._get_validation_classes(request)
        return self._check_and_update_settings(request, data, files, validation_classes, company)

    def _get_validation_classes(self, request: HttpRequest | Request) -> Tuple[ValidationClasses, bool]:
        """ Функция для определения набора классов, по которым будет происходить валидация входных данных. """

        company = check_is_user_company(request.user)
        photo_validation_class = (UploadLogoForm if company else UploadAvatarForm) \
            if self.request_host is RequestHost.VIEW else \
            (CompanySettingsSerializer if company else ApplicantSettingsSerializer)
        description_and_site_validation_class = (
            AnotherCompanySettingsForm if self.request_host is RequestHost.VIEW else
            (CompanySettingsSerializer if company else ApplicantSettingsSerializer)
        ) if company else None
        return ValidationClasses(photo_validation_class, description_and_site_validation_class), company

    def _check_and_update_settings(self, request: HttpRequest | Request, data: Dict, files: Dict,
                                   validation_classes: ValidationClasses, company: bool) \
            -> Tuple[Literal[False] | int, bool]:
        flag_success = False
        settings = get_object_or_404(CompanySettings, company=request.user) \
            if company else get_object_or_404(ApplicantSettings, applicant=request.user)

        for flag in (
                self._check_on_editions_timezone(data, settings),
                self._check_on_editions_photo(files, settings, company, validation_classes.photo_validation_class),
                self._check_on_editions_description_and_site(data, settings, company,
                                                             validation_classes.description_and_site_validation_class)
        ):
            if flag.an_error_occured:
                return flag.status, False
            elif flag.status:
                flag_success = True

        return False, flag_success

    def _check_on_editions_timezone(self, data: Dict, settings: Union[ApplicantSettings, CompanySettings]) \
            -> CheckOnEditionsReturn:
        if data.get(self.Fields.TIMEZONE, None):
            flag = self._set_timezone(data[self.Fields.TIMEZONE], settings)
            if flag is not None:
                return CheckOnEditionsReturn(True, 3)
            return CheckOnEditionsReturn(False, "SUCCESS")
        return CheckOnEditionsReturn(False, None)

    def _check_on_editions_photo(self, files: Dict, settings: Union[ApplicantSettings, CompanySettings],
                                 company: bool, validation_class: Type) -> CheckOnEditionsReturn:
        if files.get(self.Fields.COMPANY_LOGO if company else self.Fields.APPLICANT_AVATAR, False):
            files = files.copy()
            files.pop(self.Fields.DESCRIPTION, ""), files.pop(self.Fields.SITE, "")
            v, is_valid, data = self.validate_received_data({}, files, settings, validation_class=validation_class)
            if is_valid:
                self._save_uploaded_photo(v, settings, company)
                if not company:
                    make_center_crop.delay(settings.applicant_avatar.path)
                return CheckOnEditionsReturn(False, "SUCCESS")
            else:
                return CheckOnEditionsReturn(True, 1)
        return CheckOnEditionsReturn(False, None)

    def _check_on_editions_description_and_site(self,
                                                data: Dict,
                                                settings: Union[ApplicantSettings, CompanySettings],
                                                company: bool,
                                                validation_class: Type) -> CheckOnEditionsReturn:
        if data.get(self.Fields.DESCRIPTION, False) or data.get(self.Fields.SITE, False):
            if not company: raise Http404
            data = data.copy()
            data.pop(self.Fields.COMPANY_LOGO, "")
            v, is_valid, data = self.validate_received_data(data, {}, settings, validation_class=validation_class)
            if is_valid:
                v.save()
                return CheckOnEditionsReturn(False, "SUCCESS")
            else:
                return CheckOnEditionsReturn(True, 2)
        return CheckOnEditionsReturn(False, None)

    def _set_timezone(self, timezone: str, settings: ApplicantSettings | CompanySettings) -> Literal[None] | Error_code:
        if timezone not in pytz.common_timezones_set:
            return 3
        settings.timezone = timezone
        settings.save()

    def _save_uploaded_photo(self, validator_object: Any, settings: Union[CompanySettings, ApplicantSettings],
                    company: bool) -> Literal[None]:
        path_to_photo_dir = f"{MEDIA_ROOT}logos/{settings.company.pk}/" if company else \
            f"{MEDIA_ROOT}avatars/{settings.applicant.pk}"
        try:
            for file in os.listdir(BASE_DIR / path_to_photo_dir):
                os.remove(os.path.join(BASE_DIR, path_to_photo_dir, file))
        except FileNotFoundError:
            pass
        validator_object.save()

    def get_data_to_serializer(self, data: Dict, files: Dict) -> Dict:
        data_ = {}
        if len(files.keys()) > 0:
            company_logo, applicant_avatar = files.get(self.Fields.COMPANY_LOGO), files.get(self.Fields.APPLICANT_AVATAR)
            if company_logo: data_[self.Fields.COMPANY_LOGO] = company_logo
            if applicant_avatar: data_[self.Fields.APPLICANT_AVATAR] = applicant_avatar
        elif len(data.keys()) > 0:
            data_[self.Fields.SITE] = data.get(self.Fields.SITE)
            data_[self.Fields.DESCRIPTION] = data.get(self.Fields.DESCRIPTION)
        return data_

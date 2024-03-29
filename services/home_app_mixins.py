from rest_framework.request import Request
from django.http.request import HttpRequest
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.core.exceptions import PermissionDenied

from services.common_utils import check_is_user_company, RequestHost, get_error_field, DefaultPOSTReturn
from home_app.models import CompanySettings, ApplicantSettings
from services.worksite_app_mixins import DataValidationMixin
from home_app.forms import ApplicantSettingsForm, CompanySettingsForm
from tasks.home_app_tasks import make_center_crop
from worksite.settings import BASE_DIR, MEDIA_ROOT, CUSTOM_COMPANY_LOGOS_DIR, CUSTOM_APPLICANT_AVATARS_DIR
from apiv1.serializers import ApplicantSettingsSerializer, CompanySettingsSerializer
from error_messages.home_error_messages import SettingsErrors

from typing import Dict, Tuple, Union, Literal, Any, Type
import pytz
import os


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

    def update_settings(self, request: HttpRequest | Request, data: Dict, files: Dict) -> DefaultPOSTReturn:
        validation_class, company = self._get_validation_class(request)
        return self._check_and_update_settings(request, data, files, validation_class, company)

    def _get_validation_class(self, request: HttpRequest | Request) -> Tuple[Type, bool]:
        """ Функция для определения классa, по которому будет происходить валидация входных данных. """

        company = check_is_user_company(request.user)
        validation_class = (CompanySettingsForm if company else ApplicantSettingsForm) \
            if self.request_host is RequestHost.VIEW else \
            (CompanySettingsSerializer if company else ApplicantSettingsSerializer)
        return validation_class, company

    def _check_and_update_settings(self, request: HttpRequest | Request, data: Dict, files: Dict,
                                   validation_class: Type, company: bool) -> DefaultPOSTReturn:
        settings = get_object_or_404(CompanySettings, company=request.user) \
            if company else get_object_or_404(ApplicantSettings, applicant=request.user)

        for flag in (
                self._check_on_editions_timezone(data, settings),
                self._check_on_editions_photo(files, settings, company, validation_class),
                self._check_on_editions_description_and_site(data, settings, company,
                                                             validation_class)
        ):
            if not flag.status:
                return flag
        return DefaultPOSTReturn(status=True)

    def _check_on_editions_timezone(self, data: Dict, settings: Union[ApplicantSettings, CompanySettings]) \
            -> DefaultPOSTReturn:
        if data.get(self.Fields.TIMEZONE, None):
            flag = self._set_timezone(data[self.Fields.TIMEZONE], settings)
            if flag is not None:
                return DefaultPOSTReturn(False, SettingsErrors[self.Fields.TIMEZONE])
        return DefaultPOSTReturn(True)

    def _check_on_editions_photo(self, files: Dict, settings: Union[ApplicantSettings, CompanySettings],
                                 company: bool, validation_class: Type) -> DefaultPOSTReturn:
        photo_field = self.Fields.COMPANY_LOGO if company else self.Fields.APPLICANT_AVATAR
        if files.get(photo_field, False):
            files = files.copy()
            data = dict() if self.request_host == RequestHost.VIEW else files
            if company:
                files.pop(self.Fields.DESCRIPTION, ""), files.pop(self.Fields.SITE, "")
            v, is_valid, data = self.validate_received_data(data, files, settings, validation_class=validation_class)
            if not is_valid:
                return DefaultPOSTReturn(False, SettingsErrors[photo_field])
            self._save_uploaded_photo(v, settings, company)
        return DefaultPOSTReturn(True)

    def _check_on_editions_description_and_site(self, data: Dict, settings: Union[ApplicantSettings, CompanySettings],
                                                company: bool, validation_class: Type) -> DefaultPOSTReturn:
        if data.get(self.Fields.DESCRIPTION, False) or data.get(self.Fields.SITE, False):
            if not company: raise PermissionDenied
            data = data.copy()
            data.pop(self.Fields.COMPANY_LOGO, "")
            v, is_valid, data = self.validate_received_data(data, {}, settings, validation_class=validation_class)
            if not is_valid:
                return DefaultPOSTReturn(False, SettingsErrors[get_error_field(self.request_host, v)])
            v.save()
        return DefaultPOSTReturn(True)

    def _set_timezone(self, timezone: str, settings: ApplicantSettings | CompanySettings) -> Literal[None, True]:
        if timezone not in pytz.common_timezones_set:
            return True
        settings.timezone = timezone
        settings.save()

    def _save_uploaded_photo(self, validator_object: Any, settings: Union[CompanySettings, ApplicantSettings],
                             company: bool) -> Literal[None]:
        path_to_photo_dir = f"{MEDIA_ROOT}{CUSTOM_COMPANY_LOGOS_DIR}/{settings.company.pk}/" if company else \
            f"{MEDIA_ROOT}{CUSTOM_APPLICANT_AVATARS_DIR}/{settings.applicant.pk}"
        try:
            for file in os.listdir(BASE_DIR / path_to_photo_dir):
                os.remove(os.path.join(BASE_DIR, path_to_photo_dir, file))
        except FileNotFoundError:
            pass
        validator_object.save()
        if not company:
            make_center_crop.delay(settings.applicant_avatar.path)

    def get_data_to_serializer(self, data: Dict, files: Dict) -> Dict:
        return data

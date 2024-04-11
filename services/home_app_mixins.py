import os
from typing import Any, Dict, Literal, Tuple, Type, Union

import pytz
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.http.request import HttpRequest
from rest_framework.request import Request

from apiv1.serializers import ApplicantSettingsSerializer, CompanySettingsSerializer
from error_messages.home_error_messages import SettingsErrors
from home_app.forms import ApplicantSettingsForm, CompanySettingsForm
from home_app.models import ApplicantSettings, CompanySettings
from services.common_utils import (
    DefaultPOSTReturn,
    RequestHost,
    check_is_user_company,
    get_error_field,
    get_user_settings,
)
from services.worksite_app_mixins import DataValidationMixin
from tasks.home_app_tasks import make_center_crop


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
        settings_ = get_user_settings(request.user)

        for flag in (
                self._check_on_editions_timezone(data, settings_, company),
                self._check_on_editions_photo(files, settings_, company, validation_class),
                self._check_on_editions_description_and_site(data, settings_, company,
                                                             validation_class)
        ):
            if not flag.status:
                return flag
        return DefaultPOSTReturn(status=True)

    def _check_on_editions_timezone(self, data: Dict, settings_: Union[ApplicantSettings, CompanySettings],
                                    company: bool) -> DefaultPOSTReturn:
        if data.get(self.Fields.TIMEZONE, None):
            flag = self._set_timezone(data[self.Fields.TIMEZONE], settings_)
            if flag is not None:
                return DefaultPOSTReturn(False, SettingsErrors[self.Fields.TIMEZONE])
        return DefaultPOSTReturn(True)

    def _check_on_editions_photo(self, files: Dict, settings_: Union[ApplicantSettings, CompanySettings],
                                 company: bool, validation_class: Type) -> DefaultPOSTReturn:
        photo_field = self.Fields.COMPANY_LOGO if company else self.Fields.APPLICANT_AVATAR
        if files.get(photo_field, False):
            files = files.copy()
            data = dict() if self.request_host == RequestHost.VIEW else files
            if company:
                files.pop(self.Fields.DESCRIPTION, ""), files.pop(self.Fields.SITE, "")
            v, is_valid, data = self.validate_received_data(data, files, settings_, validation_class=validation_class)
            if not is_valid:
                return DefaultPOSTReturn(False, SettingsErrors[photo_field])
            self._save_uploaded_photo(v, settings_, company)
        return DefaultPOSTReturn(True)

    def _check_on_editions_description_and_site(self, data: Dict, settings_: Union[ApplicantSettings, CompanySettings],
                                                company: bool, validation_class: Type) -> DefaultPOSTReturn:
        if data.get(self.Fields.DESCRIPTION, False) or data.get(self.Fields.SITE, False):
            assert company, PermissionDenied
            data = data.copy()
            data.pop(self.Fields.COMPANY_LOGO, "")
            v, is_valid, data = self.validate_received_data(data, {}, settings_, validation_class=validation_class)
            if not is_valid:
                return DefaultPOSTReturn(False, SettingsErrors[get_error_field(self.request_host, v)])
            v.save()
        return DefaultPOSTReturn(True)

    def _set_timezone(self, timezone: str, settings_: ApplicantSettings | CompanySettings) -> Literal[None, True]:
        if timezone not in pytz.common_timezones_set:
            return True
        settings_.timezone = timezone
        settings_.save()

    def _save_uploaded_photo(self, validator_object: Any, user_settings: Union[CompanySettings, ApplicantSettings],
                             company: bool) -> Literal[None]:
        path_to_photo_dir = f"{settings.MEDIA_ROOT}{settings.CUSTOM_COMPANY_LOGOS_DIR}/{user_settings.company.pk}/" \
            if company else f"{settings.MEDIA_ROOT}{settings.CUSTOM_APPLICANT_AVATARS_DIR}/{user_settings.applicant.pk}"
        try:
            for file in os.listdir(settings.BASE_DIR / path_to_photo_dir):
                os.remove(os.path.join(settings.BASE_DIR, path_to_photo_dir, file))
        except FileNotFoundError:
            pass
        validator_object.save()
        if not company:
            make_center_crop.delay(user_settings.applicant_avatar.path)

    def get_data_to_serializer(self, data: Dict, files: Dict) -> Dict:
        return data

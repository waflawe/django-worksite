from django.contrib import admin

from home_app.models import ApplicantSettings, CompanySettings

admin.site.register(CompanySettings)
admin.site.register(ApplicantSettings)

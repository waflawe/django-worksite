from django.contrib import admin
from home_app.models import CompanySettings, ApplicantSettings

admin.site.register(CompanySettings)
admin.site.register(ApplicantSettings)

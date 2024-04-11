from django.contrib import admin

from worksite_app.models import Offer, Rating, Vacancy

admin.site.register(Vacancy)
admin.site.register(Offer)
admin.site.register(Rating)

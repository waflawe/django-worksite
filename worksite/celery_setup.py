import os

from celery import Celery
from django.conf import settings

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "worksite.settings")

app = Celery(
    "worksite",
    include=["tasks.home_app_tasks"],
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)
app.conf.task_routes = {
    "tasks.home_app_tasks.make_center_crop": {"queue": "main_queue"},
}
app.autodiscover_tasks()

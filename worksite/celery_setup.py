from celery import Celery
from worksite.settings import CELERY_BROKER_URL, CELERY_RESULT_BACKEND
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'worksite.settings')

app = Celery('worksite', include=['tasks.home_app_tasks'], broker=CELERY_BROKER_URL, backend=CELERY_RESULT_BACKEND)
app.conf.task_routes = {
    "tasks.home_app_tasks.make_center_crop": {"queue": "main_queue"},
}
app.autodiscover_tasks()


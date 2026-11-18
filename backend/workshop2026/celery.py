"""Celery app: runs the imports out of the request (worker service in Compose).

Settings are read from Django's, prefixed with CELERY_.
"""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "workshop2026.settings")

app = Celery("workshop2026")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

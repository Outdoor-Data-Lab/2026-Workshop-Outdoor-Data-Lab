# Loaded with Django, so that tasks are sent through this app.
from .celery import app as celery_app

__all__ = ("celery_app",)

from django.test.runner import DiscoverRunner

from .celery import app


class TestRunner(DiscoverRunner):
    """Runs the Celery tasks at once, without broker nor worker, and lets their
    exceptions reach the test."""

    def setup_test_environment(self, **kwargs):
        super().setup_test_environment(**kwargs)
        app.conf.task_always_eager = True
        app.conf.task_eager_propagates = True

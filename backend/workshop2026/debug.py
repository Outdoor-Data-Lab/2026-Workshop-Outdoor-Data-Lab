from django.conf import settings


def show_toolbar(request):
    """Show the debug toolbar whenever the project runs in debug mode."""

    return settings.DEBUG

from django.db import OperationalError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler


def api_exception_handler(exc, context):
    # The free Postgres host suspends itself when idle or out of quota; say so
    # instead of returning a 500 page.
    if isinstance(exc, OperationalError):
        return Response(
            {"detail": "database unavailable, try again shortly"},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    return exception_handler(exc, context)

from collections.abc import Sequence

from django.core.exceptions import ValidationError
from django.utils.datastructures import MultiValueDictKeyError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler


def detail(arg):
    key = "detail"
    if isinstance(arg, Sequence) and not isinstance(arg, str):
        if len(arg) == 1:
            arg = arg[0]
        else:
            key += "s"
    return {key: arg}


def custom_exception_handler(exception, context):
    if isinstance(exception, MultiValueDictKeyError):
        exception = ValidationError(f"Parameter {exception} is required.")
    if isinstance(exception, ValidationError):
        return Response(detail(exception.messages), status.HTTP_400_BAD_REQUEST)
    return exception_handler(exception, context)

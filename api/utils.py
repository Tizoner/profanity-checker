from collections.abc import Iterable, Sequence

from django.core.exceptions import ValidationError
from django.db.models import BooleanField, DateTimeField
from django.utils import timezone
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


def split_quoted_text(text, max_split_len=16352):
    start, end = 0, max_split_len
    while end < len(text):
        index = text.rfind("%", start, end)
        if index > 0:
            end = index
        yield text[start:end]
        start = end
        end += max_split_len
    yield text[start:end]


def query_param(
    request, field, param_name=None, required=True, handle_unknown_params=True
):
    if param_name is None:
        param_name = field.name
    if handle_unknown_params:
        check_unknown_params(request.query_params.keys() - (param_name,))
    if not required and param_name not in request.query_params:
        return
    param = request.query_params[param_name]
    if len(param) == 0:
        raise ValidationError(f"Parameter '{param_name}' must not be blank.")
    field.run_validators(param)
    if isinstance(field, BooleanField):
        param = param.capitalize()
    param = field.to_python(param)
    if isinstance(field, DateTimeField):
        param = timezone.localtime(param, timezone=timezone.utc)
    return param


def query_params(request, fields: Iterable, required=False):
    remained_params = set(request.query_params.keys())
    for field in fields:
        if isinstance(field, Sequence):
            field, param_name = field
        else:
            param_name = field.name
        yield query_param(
            request, field, param_name, required, handle_unknown_params=False
        )
        remained_params.discard(param_name)
    check_unknown_params(remained_params)


def check_unknown_params(params):
    if params:
        raise ValidationError([f"Unknown parameter '{param}'." for param in params])


def median_datetime(queryset, term):
    try:
        count = queryset.count()
    except:
        count = 0
    if count == 0:
        datetime = timezone.now()
    else:
        datetime = queryset.values_list(term, flat=True).order_by(term)[count // 2]
    return timezone.localtime(datetime)

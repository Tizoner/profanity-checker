from itertools import chain
from json import dumps

from django.db import models
from django.db.models import DateTimeField
from django.utils import timezone


class PrintableModel(models.Model):
    def __repr__(self):
        return dumps(self.to_dict(), indent=4, default=str)

    def to_dict(self):
        options = self._meta
        data = {}
        for field in chain(options.concrete_fields, options.private_fields):
            value = field.value_from_object(self)
            if isinstance(field, DateTimeField):
                value = timezone.localtime(value)
            data[field.name] = value
        for field in options.many_to_many:
            data[field.name] = [i.id for i in field.value_from_object(self)]
        return data

    class Meta:
        abstract = True


class Site(PrintableModel):
    url = models.URLField(primary_key=True, max_length=2000)
    contains_profanity = models.BooleanField(serialize=True)
    last_check_time = models.DateTimeField(default=timezone.now)
    last_status_update_time = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.url

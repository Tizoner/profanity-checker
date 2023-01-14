import itertools

from django.db import models
from django.utils import timezone
from ujson import dumps

from api.utils import serialize_object


class BaseModel(models.Model):
    def __repr__(self):
        return dumps(
            self.to_dict(),
            indent=4,
            default=serialize_object,
            ensure_ascii=False,
            escape_forward_slashes=False,
        )

    def to_dict(self):
        data = {}
        options = self._meta
        for field in itertools.chain(options.concrete_fields, options.private_fields):
            data[field.name] = field.value_from_object(self)
        for field in options.many_to_many:
            data[field.name] = [i.id for i in field.value_from_object(self)]
        return data

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    class Meta:
        abstract = True


class Site(BaseModel):
    url = models.URLField(primary_key=True, max_length=2000)
    contains_profanity = models.BooleanField()
    last_check_time = models.DateTimeField(default=timezone.now)
    last_status_update_time = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.url

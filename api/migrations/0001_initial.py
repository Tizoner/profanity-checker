# Generated by Django 4.1.4 on 2022-12-18 16:56

from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Site",
            fields=[
                (
                    "url",
                    models.URLField(max_length=2000, primary_key=True, serialize=False),
                ),
                ("contains_profanity", models.BooleanField()),
                (
                    "last_check_time",
                    models.DateTimeField(default=django.utils.timezone.now),
                ),
                (
                    "last_status_update_time",
                    models.DateTimeField(default=django.utils.timezone.now),
                ),
            ],
            options={
                "abstract": False,
            },
        ),
    ]

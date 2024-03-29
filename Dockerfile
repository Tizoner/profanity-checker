FROM python:3.10-alpine
ENV PYTHONUNBUFFERED 1
WORKDIR /opt/app
COPY . .

RUN pip install --upgrade pip \
  && apk add --no-cache gcc musl-dev libpq libpq-dev \
  && pip install --no-cache-dir -r requirements.txt \
  && rm requirements.txt \
  && apk del --purge gcc musl-dev libpq-dev apk-tools\
  && python manage.py collectstatic --no-input

EXPOSE 10000
CMD python manage.py migrate \
  && (python manage.py createsuperuser --no-input || :) \
  && python manage.py runserver --noreload 0.0.0.0:10000

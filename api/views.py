import concurrent
from os import cpu_count
from urllib.error import URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup
from django.utils import timezone
from requests.exceptions import ReadTimeout
from requests_futures.sessions import FuturesSession
from rest_framework import status, viewsets
from rest_framework.response import Response

from .models import Site
from .serializers import SiteSerializer
from .utils import detail, split_quoted_text


class SiteViewSet(viewsets.ViewSet):
    def check(self, request):
        url = query_param(request, Site.url.field)
        request = Request(url, headers={"User-Agent": "Magic Browser"})
        try:
            response = urlopen(request)
        except URLError as exception:
            if str(exception.reason) == "[Errno -2] Name does not resolve":
                return Response(
                    detail("Could not resolve URL."), status.HTTP_400_BAD_REQUEST
                )
            raise exception
        html = response.read()
        response.close()
        unique_words = set()
        for stripped_string in BeautifulSoup(html, "html.parser").stripped_strings:
            for word in stripped_string.split():
                if len(word) > 1:
                    unique_words.add(word.lower())
        text = " ".join(unique_words)
        urls = tuple(
            "https://www.purgomalum.com/service/containsprofanity?text=" + text
            for text in split_quoted_text(quote(text))
        )
        status_code = status.HTTP_200_OK
        with FuturesSession(max_workers=cpu_count()) as session:
            futures = (session.get(url, timeout=20) for url in urls)
            for future in concurrent.futures.as_completed(futures):
                try:
                    response = future.result()
                except ReadTimeout:
                    json = detail("Request to third-party API timed out.")
                    status_code = status.HTTP_504_GATEWAY_TIMEOUT
                    break
                if response.status_code != status.HTTP_200_OK:
                    json = detail(
                        f"Request to third-party API failed with status code {response.status_code}."
                    )
                    status_code = status.HTTP_502_BAD_GATEWAY
                    break
                json = response.json()
                if json is True:
                    break
        try:
            update_fields = [Site.last_check_time.field.name]
            site = Site.objects.get(url=url)
            if site.contains_profanity != json:
                site.contains_profanity = json
                site.last_status_update_time = timezone.now()
                update_fields.extend(
                    (
                        Site.contains_profanity.field.name,
                        Site.last_status_update_time.field.name,
                    )
                )
            site.save(update_fields=update_fields)
        except Site.DoesNotExist:
            Site(url=url, contains_profanity=json).save(force_insert=True)
        return Response(json, status_code)

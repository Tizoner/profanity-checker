import concurrent
from os import cpu_count
from urllib.error import URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup
from django.core.cache import cache
from django.utils import timezone
from drf_spectacular.plumbing import (
    build_array_type,
    build_basic_type,
    build_object_type,
)
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
)
from requests.exceptions import ReadTimeout
from requests_futures.sessions import FuturesSession
from rest_framework import status, viewsets
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response

from .models import Site
from .serializers import SiteSerializer
from .utils import detail, split_quoted_text


class SiteViewSet(viewsets.ViewSet):
    @extend_schema(
        summary="check site for profanity",
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                response=bool,
                description="Successfully checked site for profanity",
                examples=[
                    OpenApiExample(name="Site contains profanity", value="true"),
                    OpenApiExample(
                        name="Site does not contain profanity", value="false"
                    ),
                ],
            ),
            status.HTTP_400_BAD_REQUEST: OpenApiResponse(
                response=dict(
                    oneOf=dict(
                        detail=build_basic_type(str),
                        details=build_array_type(build_basic_type(str), min_length=2),
                    )
                ),
                description="Site URL was missing, blank, invalid, not resolving, or unknown parameters were provided",
                examples=[
                    OpenApiExample(
                        name="Missing URL",
                        value=detail("Parameter “url” is required."),
                        status_codes=[status.HTTP_400_BAD_REQUEST],
                    ),
                    OpenApiExample(
                        name="Blank URL",
                        value=detail("Parameter “url” must not be blank."),
                        status_codes=[status.HTTP_400_BAD_REQUEST],
                    ),
                    OpenApiExample(
                        name="Invalid URL",
                        value=detail(
                            [
                                "Enter a valid URL.",
                                "Ensure this value has at most 2000 characters (it has 2022).",
                            ]
                        ),
                        status_codes=[status.HTTP_400_BAD_REQUEST],
                    ),
                    OpenApiExample(
                        name="Nonexistent URL",
                        value=detail("Could not resolve URL."),
                        status_codes=[status.HTTP_400_BAD_REQUEST],
                    ),
                    OpenApiExample(
                        name="Unknown parameters",
                        value=detail(
                            ["Unknown parameter “a”.", "Unknown parameter “b”."]
                        ),
                        status_codes=[status.HTTP_400_BAD_REQUEST],
                    ),
                ],
            ),
            status.HTTP_502_BAD_GATEWAY: OpenApiResponse(
                response=build_object_type(detail(build_basic_type(str))),
                description="One of the requests to third-party API failed",
                examples=[
                    OpenApiExample(
                        name="External service unavailable",
                        value=detail(
                            "Request to third-party API failed with status code 503."
                        ),
                        status_codes=[status.HTTP_502_BAD_GATEWAY],
                    ),
                    OpenApiExample(
                        name="External server error",
                        value=detail(
                            "Request to third-party API failed with status code 500."
                        ),
                        status_codes=[status.HTTP_502_BAD_GATEWAY],
                    ),
                ],
            ),
            status.HTTP_504_GATEWAY_TIMEOUT: OpenApiResponse(
                response=build_object_type(detail(build_basic_type(str))),
                description="One of the requests to third-party API timed out",
                examples=[
                    OpenApiExample(
                        name="Request timeout passed",
                        value=detail("Request to third-party API timed out."),
                        status_codes=[status.HTTP_504_GATEWAY_TIMEOUT],
                    )
                ],
            ),
        },
        parameters=[
            OpenApiParameter(
                name="url",
                description="Site URL",
                required=True,
                type=dict(
                    type="string", format="uri", maxLength=Site.url.field.max_length
                ),
                examples=[
                    OpenApiExample(
                        name="URL of site containing profanity",
                        value="https://github.com/public-apis/public-apis",
                    ),
                    OpenApiExample(
                        name="URL of site not containing profanity",
                        value="https://developer.mozilla.org/en-US/docs/Learn/Server-side/Django/Deployment",
                    ),
                    OpenApiExample(name="Invalid site URL", value="https://asdf"),
                    OpenApiExample(
                        name="Nonexistent site URL", value="https://www.purgomalum"
                    ),
                ],
            )
        ],
    )
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
        cache.delete_many((None, json))
        return Response(json, status_code)

    @extend_schema(
        summary="retrieve stored information about site",
        responses={
            status.HTTP_200_OK: OpenApiResponse(
                response=SiteSerializer,
                description="Successfully retrieved information about site",
                examples=[
                    OpenApiExample(
                        name="Retrieved information",
                        value=SiteSerializer(
                            Site(
                                url="https://www.purgomalum.com/profanitylist.html",
                                contains_profanity=True,
                            )
                        ).data,
                    )
                ],
            ),
            status.HTTP_400_BAD_REQUEST: OpenApiResponse(
                response=dict(
                    oneOf=dict(
                        detail=build_basic_type(str),
                        details=build_array_type(build_basic_type(str), min_length=2),
                    )
                ),
                description="Site URL was missing, blank, invalid, or unknown parameters were provided",
                examples=[
                    OpenApiExample(
                        name="Missing URL",
                        value=detail("Parameter “url” is required."),
                        status_codes=[status.HTTP_400_BAD_REQUEST],
                    ),
                    OpenApiExample(
                        name="Blank URL",
                        value=detail("Parameter “url” must not be blank."),
                        status_codes=[status.HTTP_400_BAD_REQUEST],
                    ),
                    OpenApiExample(
                        name="Invalid URL",
                        value=detail(
                            [
                                "Enter a valid URL.",
                                "Ensure this value has at most 2000 characters (it has 2022).",
                            ]
                        ),
                        status_codes=[status.HTTP_400_BAD_REQUEST],
                    ),
                    OpenApiExample(
                        name="Unknown parameters",
                        value=detail(
                            ["Unknown parameter “a”.", "Unknown parameter “b”."]
                        ),
                        status_codes=[status.HTTP_400_BAD_REQUEST],
                    ),
                ],
            ),
            status.HTTP_404_NOT_FOUND: OpenApiResponse(
                response=build_object_type(detail(build_basic_type(str))),
                description="No stored information is associated with the given URL",
                examples=[
                    OpenApiExample(
                        name="Unknown URL",
                        value=detail("Not found."),
                        status_codes=[status.HTTP_404_NOT_FOUND],
                    )
                ],
            ),
        },
        parameters=[
            OpenApiParameter(
                name="url",
                description="Site URL",
                required=True,
                type=dict(
                    type="string", format="uri", maxLength=Site.url.field.max_length
                ),
                examples=[
                    OpenApiExample(
                        name="Nonexistent site URL", value="https://www.purgomalum"
                    ),
                    OpenApiExample(name="Invalid site URL", value="https://asdf"),
                    OpenApiExample(
                        name="URL of site containing profanity",
                        value="https://github.com/public-apis/public-apis",
                    ),
                    OpenApiExample(
                        name="URL of site not containing profanity",
                        value="https://developer.mozilla.org/en-US/docs/Learn/Server-side/Django/Deployment",
                    ),
                ],
            )
        ],
    )
    def site(self, request):
        url = query_param(request, Site.url.field)
        site = get_object_or_404(Site, url=url)
        return Response(SiteSerializer(site).data, status.HTTP_200_OK)

    def sites(self, request):
        contains_profanity, last_check_after, last_status_update_after = query_params(
            request,
            (
                Site.contains_profanity.field,
                (Site.last_check_time.field, "last_check_after"),
                (Site.last_status_update_time.field, "last_status_update_after"),
            ),
        )
        sites = Site.objects.all()
        if last_check_after is None and last_status_update_after is None:
            if contains_profanity is not None:
                sites = sites.filter(contains_profanity=contains_profanity)
            sites = cache.get_or_set(contains_profanity, sites)
        else:
            if last_check_after is not None:
                sites = sites.filter(last_check_time__gt=last_check_after)
            if last_status_update_after is not None:
                sites = sites.filter(
                    last_status_update_time__gt=last_status_update_after
                )
        return Response(SiteSerializer(sites, many=True).data, status.HTTP_200_OK)

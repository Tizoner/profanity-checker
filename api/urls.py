from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from .views import SiteViewSet

urlpatterns = [
    path(
        "v1/",
        include(
            [
                path(
                    "schema/",
                    include(
                        [
                            path("", SpectacularAPIView.as_view(), name="schema"),
                            path("swagger-ui/", SpectacularSwaggerView.as_view()),
                        ]
                    ),
                ),
                path("check", SiteViewSet.as_view({"get": "check"})),
            ]
        ),
    )
]

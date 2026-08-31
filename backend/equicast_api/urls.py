from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path


def health(request):
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", health, name="health"),
    path("api/market/", include("market_data.urls")),
    path("api/identity/", include("identity.urls")),
    path("api/accounts/", include("accounts.urls")),
    path("api/pies/", include("pies.urls")),
    path("api/watchlists/", include("watchlists.urls")),
]

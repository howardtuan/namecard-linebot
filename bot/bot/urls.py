from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import JsonResponse
from django.urls import path

from cards import views


def healthz(_request):
    return JsonResponse({"ok": True})


urlpatterns = [
    path("", healthz, name="healthz"),
    path("admin/", admin.site.urls),
    path("webhook/", views.webhook, name="webhook"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.views.generic.base import RedirectView
from doctor.views import service_worker_view, manifest_view, download_apk_view

urlpatterns = [
    path('favicon.ico', RedirectView.as_view(url='/static/favicon.ico', permanent=True)),
    path('sw.js', service_worker_view, name='pwa_sw'),
    path('manifest.json', manifest_view, name='pwa_manifest'),
    path('download/app/', download_apk_view, name='download_app_apk'),
    path('download/apk/', download_apk_view, name='download_apk_alias'),
    path('admin/', admin.site.urls),
    path('patient/', include('patient.urls', namespace='patient')),
    path('', include('doctor.urls', namespace='doctor')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += staticfiles_urlpatterns()

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
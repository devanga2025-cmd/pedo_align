from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.views.generic.base import RedirectView

urlpatterns = [
    path('favicon.ico', RedirectView.as_view(url='/static/favicon.ico', permanent=True)),
    path('sw.js', RedirectView.as_view(url='/static/sw.js', permanent=True)),
    path('manifest.json', RedirectView.as_view(url='/static/manifest.json', permanent=True)),
    path('admin/', admin.site.urls),
    path('patient/', include('patient.urls', namespace='patient')),
    path('', include('doctor.urls', namespace='doctor')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += staticfiles_urlpatterns()

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
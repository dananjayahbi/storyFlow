import sys

from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings

from api.media_views import serve_media

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('api.urls')),
]

# Range-capable replacement for django.conf.urls.static.static(). The default
# helper cannot answer `Range:` requests, which prevents browsers from seeking
# in audio/video elements. Django's test runner forces DEBUG=False, so keep
# the route enabled for the test suite as well.
if settings.DEBUG or any(arg in ('test', 'pytest') for arg in sys.argv):
    urlpatterns += [
        re_path(r'^media/(?P<path>.*)$', serve_media, name='media'),
    ]


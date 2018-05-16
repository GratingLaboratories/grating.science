from django.conf.urls import url
from .views import *

urlpatterns = [
    url(r'^youtube/$', youtube_link, name='youtube-link'),
    url(r'^convert/$', convert, name='convert'),
    url(r'^query/$', query_status, name='query-status'),
    url(r'^test/$', test, name='test'),
]

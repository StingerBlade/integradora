from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/dashboard/(?P<usuario>\w+)/$', consumers.DashboardConsumer.as_asgi()),
]
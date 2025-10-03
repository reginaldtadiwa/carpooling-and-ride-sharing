# rides/routing.py
from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/pool/(?P<pool_id>\w+)/$', consumers.PoolConsumer.as_asgi()),
    re_path(r'ws/user/(?P<user_id>\w+)/$', consumers.UserConsumer.as_asgi()),
]
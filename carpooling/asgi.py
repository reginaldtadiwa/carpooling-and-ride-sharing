# carpooling/asgi.py (The correct structure)

import os
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'carpooling.settings')

django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack

import rides.routing 

application = ProtocolTypeRouter({
    # Use the initialized Django app for HTTP requests
    "http": django_asgi_app,
    
    # Use the Channels setup for WebSockets
    "websocket": AuthMiddlewareStack(
        URLRouter(
            rides.routing.websocket_urlpatterns
        )
    ),
})
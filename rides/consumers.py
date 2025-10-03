# rides/consumers.py
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import Pool, PoolMembership


class PoolConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.pool_id = self.scope['url_route']['kwargs']['pool_id']
        self.pool_group_name = f'pool_{self.pool_id}'

        token = await self.extract_token_from_query()
        if token and await self.authenticate_with_token(token):
            if await self.is_user_in_pool():
                await self.channel_layer.group_add(
                self.pool_group_name,
                self.channel_name
            )
                await self.accept()
                await self.send_current_pool_status()
            else:
                await self.close()
        else:
            await self.close()

    async def extract_token_from_query(self):
        query_string = self.scope.get('query_string', b'').decode()
        if 'token=' in query_string:
            params = dict(param.split('=') for param in query_string.split('&') if '=' in param)
            return params.get('token')
        return None
    
    @database_sync_to_async
    def authenticate_with_token(self, token):
        from rest_framework_simplejwt.tokens import AccessToken
        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            access_token = AccessToken(token)
            user_id = access_token['user_id']
            user = User.objects.get(id=user_id)
            self.scope['user'] = user
            return True
        except Exception as e:
            print(f"Token authentication failed: {e}")
            return False    

    async def disconnect(self, close_code):
        # Leave pool group
        await self.channel_layer.group_discard(
            self.pool_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message_type = text_data_json['type']
        
        if message_type == 'ping':
            await self.send(text_data=json.dumps({
                'type': 'pong',
                'message': 'Connected'
            }))

    # Receive messages from pool group
    async def pool_update(self, event):
        """Send pool updates to client"""
        await self.send(text_data=json.dumps(event))

    async def rider_joined(self, event):
        """Send notification when new rider joins"""
        await self.send(text_data=json.dumps(event))

    async def driver_assigned(self, event):
        """Send notification when driver is assigned"""
        await self.send(text_data=json.dumps(event))

    async def pool_filled(self, event):
        """Send notification when pool is full"""
        await self.send(text_data=json.dumps(event))

    @database_sync_to_async
    def is_user_in_pool(self):
        """Check if user is part of this pool"""
        try:
            user = self.scope["user"]
            if user.is_anonymous:
                return False
            return PoolMembership.objects.filter(
                pool_id=self.pool_id,
                ride_request__rider=user
            ).exists()
        except:
            return False

    @database_sync_to_async
    def get_pool_status(self):
        """Get current pool status"""
        try:
            pool = Pool.objects.get(id=self.pool_id)
            members_count = pool.members.count()
            return {
                'type': 'pool_status',
                'pool_id': self.pool_id,
                'current_riders': members_count,
                'max_riders': pool.max_riders,
                'status': pool.status,
                'is_full': members_count >= pool.max_riders
            }
        except Pool.DoesNotExist:
            return None

    async def send_current_pool_status(self):
        """Send current pool status on connect"""
        status = await self.get_pool_status()
        if status:
            await self.send(text_data=json.dumps(status))

class UserConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user_id = self.scope['url_route']['kwargs']['user_id']
        self.user_group_name = f'user_{self.user_id}'
        
        # Verify it's the same user
        if str(self.scope["user"].id) == self.user_id:
            await self.channel_layer.group_add(
                self.user_group_name,
                self.channel_name
            )
            await self.accept()
        else:
            await self.close()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.user_group_name,
            self.channel_name
        )

    async def user_notification(self, event):
        """Send personal notifications to user"""
        await self.send(text_data=json.dumps(event))
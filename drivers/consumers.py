# drivers/consumers.py
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async

class DriverConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.driver_id = self.scope['url_route']['kwargs']['driver_id']
        self.driver_group_name = f'driver_{self.driver_id}'
        
        token = await self.extract_token_from_query()
        if token and await self.authenticate_with_token(token):
            # Verify this is the actual driver
            if await self.is_valid_driver():
                await self.channel_layer.group_add(
                    self.driver_group_name,
                    self.channel_name
                )
                await self.accept()
            else:
                await self.close()
        else:
            await self.close()
    
    async def extract_token_from_query(self):
        """Extract token from query string"""
        query_string = self.scope.get('query_string', b'').decode()
        query_params = dict(qc.split('=') for qc in query_string.split('&') if '=' in qc)
        return query_params.get('token')
    
    async def authenticate_with_token(self, token):
        """Authenticate user with JWT token"""
        from channels.db import database_sync_to_async
        from rest_framework_simplejwt.tokens import AccessToken
        
        try:
            access_token = AccessToken(token)
            user_id = access_token['user_id']
            
            @database_sync_to_async
            def get_user():
                from django.contrib.auth import get_user_model
                User = get_user_model()
                return User.objects.get(id=user_id)
            
            self.user = await get_user()
            self.scope['user'] = self.user
            return True
        except Exception:
            return False

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.driver_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message_type = text_data_json['type']
        
        if message_type == 'accept_pool':
            pool_id = text_data_json['pool_id']
            await self.handle_pool_acceptance(pool_id)
        
        elif message_type == 'decline_pool':
            pool_id = text_data_json['pool_id']
            await self.handle_pool_decline(pool_id)

    async def pool_assignment(self, event):
        """Receive pool assignment notification"""
        await self.send(text_data=json.dumps(event))

    async def assignment_confirmed(self, event):
        """Receive confirmation that pool assignment is confirmed"""
        await self.send(text_data=json.dumps(event))

    async def handle_pool_acceptance(self, pool_id):
        """Handle driver accepting a pool"""
        from matching.tasks import driver_accept_pool
        driver_accept_pool.delay(self.driver_id, pool_id)
        
        await self.send(text_data=json.dumps({
            'type': 'acceptance_sent',
            'message': 'Pool acceptance sent successfully'
        }))

    async def handle_pool_decline(self, pool_id):
        """Handle driver declining a pool"""
        await self.send(text_data=json.dumps({
            'type': 'decline_sent', 
            'message': 'Pool declined'
        }))

    @database_sync_to_async
    def is_valid_driver(self):
        """Verify the user is a valid driver"""
        from rides.models import Driver
        try:
            user = self.scope["user"]
            if user.is_anonymous:
                return False
            return Driver.objects.filter(id=self.driver_id, user=user).exists()
        except:
            return False
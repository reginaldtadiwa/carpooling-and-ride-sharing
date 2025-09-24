# routing/consumers.py
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async

class PoolConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.pool_id = self.scope['url_route']['kwargs']['pool_id']
        self.pool_group_name = f'pool_{self.pool_id}'
        
        # Join pool group
        await self.channel_layer.group_add(
            self.pool_group_name,
            self.channel_name
        )
        
        await self.accept()
    
    async def disconnect(self, close_code):
        # Leave pool group
        await self.channel_layer.group_discard(
            self.pool_group_name,
            self.channel_name
        )
    
    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message_type = text_data_json['type']
        
        if message_type == 'location_update':
            # Handle location updates
            await self.handle_location_update(text_data_json)
    
    async def pool_update(self, event):
        """Send pool updates to client"""
        await self.send(text_data=json.dumps(event))
    
    async def driver_assigned(self, event):
        """Notify when driver is assigned"""
        await self.send(text_data=json.dumps(event))
    
    async def handle_location_update(self, data):
        # Broadcast location update to pool group
        await self.channel_layer.group_send(
            self.pool_group_name,
            {
                'type': 'location_update',
                'user_id': data['user_id'],
                'location': data['location']
            }
        )
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async as database_sync_to_async
from .models import user_collection

class DashboardConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope['url_route']['kwargs']['usuario']
        self.room_group_name = f'user_{self.user}'

        # Unirse al grupo del usuario
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        # Abandonar el grupo
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    # Recibir mensaje del WebSocket
    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message = text_data_json['message']

        # Enviar mensaje al grupo
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'usage_update',
                'message': message
            }
        )

    # Recibir mensaje del grupo
    async def usage_update(self, event):
        message = event['message']

        # Enviar mensaje al WebSocket
        await self.send(text_data=json.dumps({
            'message': message
        }))
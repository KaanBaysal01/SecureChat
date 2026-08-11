from channels.generic.websocket import AsyncWebsocketConsumer
import json
from channels.db import database_sync_to_async
from .models import Conversation, Message
from .crypto import encrypt_message


class ChatConsumer(AsyncWebsocketConsumer):

    MAX_MESSAGE_LENGTH = 4000

    async def connect(self):
        self.user = self.scope["user"]

        if not self.user.is_authenticated:
            await self.close(code=4001)
            return
        self.conversation_id = self.scope["url_route"]["kwargs"]["conversation_id"]
        self.room_group_name = f"chat_{self.conversation_id}"

        if not await self.user_in_conversation():
            await self.close(code=4003)
            return
        
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "room_group_name"):
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            return

        message = (data.get("message") or "").strip()

        if not message:
            return

        if len(message) > self.MAX_MESSAGE_LENGTH:
            await self.send(text_data=json.dumps({
                "error": "Mesaj çok uzun."
            }))
            return



        client_message_id = data.get("client_message_id")

        message_obj, created = await self.save_message(message, client_message_id)

        if not created:
            return


        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "chat_message",
                "message": message,
                "sender_username": self.user.username,
            }
        )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            "message": event["message"],
            "sender_username": event["sender_username"],
        }))

    @database_sync_to_async
    def user_in_conversation(self):
        return Conversation.objects.filter(
            id=self.conversation_id,
            participants=self.user,
        ).exists()

    @database_sync_to_async
    def save_message(self, content, client_message_id=None):
        message, created = Message.objects.get_or_create(
            conversation_id=self.conversation_id,
            client_message_id=client_message_id,
            defaults={
                "sender": self.user,
                "encrypted_content": encrypt_message(content),
            },
        )
        return message, created
from channels.generic.websocket import AsyncWebsocketConsumer
import json
from channels.db import database_sync_to_async
from .crypto import encrypt_message
from .models import Conversation, Message, MessageReadStatus
from django.utils import timezone
from django.contrib.auth import get_user_model

User = get_user_model()

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

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)

        await self.accept()

        if self.user.show_last_seen:
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "presence.update",
                    "username": self.user.username,
                    "status": "online",
                },
            )

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "presence.query",
                "reply_to": self.channel_name,
            },
        )

    async def disconnect(self, close_code):
        if hasattr(self, "room_group_name"):
            await self.update_last_seen()

            if self.user.show_last_seen:
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        "type": "presence.update",
                        "username": self.user.username,
                        "status": "offline",
                    },
                )

            await self.channel_layer.group_discard(
                self.room_group_name, self.channel_name
            )

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            return

        message_type = data.get("type")

        if message_type == "chat_message":
            await self.handle_chat_message(data)
        elif message_type == "mark_read":
            await self.handle_mark_read(data)
        elif message_type == "delete_message":
            await self.handle_delete_message(data)
        elif message_type == "typing":
            await self.handle_typing(data)
        elif message_type == "pin_message":
            await self.handle_pin_message(data)
        elif message_type == "unpin_message":
            await self.handle_unpin_message(data)
    

    async def handle_chat_message(self, data):
        message = (data.get("message") or "").strip()

        if not message:
            return

        if len(message) > self.MAX_MESSAGE_LENGTH:
            await self.send(
                text_data=json.dumps(
                    {
                        "type": "error",
                        "detail": "Mesaj çok uzun.",
                    }
                )
            )
            return

        client_message_id = data.get("client_message_id")
        message_obj, created = await self.save_message(message, client_message_id)

        if not created:
            return

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "chat_message",
                "message_id": message_obj.id,
                "message": message,
                "sender_username": self.user.username,
            },
        )

    async def handle_mark_read(self, data):
        message_id = data.get("message_id")
        if not message_id:
            return

        updated = await self.mark_message_read(message_id)
        if not updated:
            return

        read_count = await self.get_read_count(message_id)
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "read_receipt",
                "message_id": message_id,
                "read_by": self.user.username,
                "read_count": read_count,
            },
        )

    async def handle_delete_message(self, data):
        message_id = data.get("message_id")
        if not message_id:
            return

        deleted = await self.delete_message(message_id)
        if not deleted:
            return

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "message_deleted",
                "message_id": message_id,
            },
        )

    async def handle_typing(self, data):
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "typing.status",
                "username": self.user.username,
                "is_typing": bool(data.get("is_typing")),
            },
        )

        
    async def handle_pin_message(self, data):
        message_id = data.get("message_id")
        if not message_id:
            return

        pinned = await self.pin_message(message_id)
        if pinned is None:
            return

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "pin.update",
                "message_id": pinned["message_id"],
                "preview": pinned["preview"],
                "sender_username": pinned["sender_username"],
                "pinned_by":pinned["pinned_by"],
            },
        )

    async def handle_unpin_message(self, data):
        if not await self.unpin_message():
            return

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "pin.update",
                "message_id": None,
                "preview": None,
                "sender_username": None,
                "pinned_by": None,
            },
        )

    async def chat_message(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "type": "chat_message",
                    "message_id": event["message_id"],
                    "message": event["message"],
                    "sender_username": event["sender_username"],
                    "file_url": event.get("file_url"),
                    "file_name": event.get("file_name"),
                    "file_size_display": event.get("file_size_display"),
                    "is_image": event.get("is_image", False),
                    "is_system": event.get("is_system",False),
                    }
                )
            )

    async def read_receipt(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "type": "read_receipt",
                    "message_id": event["message_id"],
                    "read_by": event["read_by"],
                    "read_count": event["read_count"],
                }
            )
        )

    async def message_deleted(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "type": "message_deleted",
                    "message_id": event["message_id"],
                }
            )
        )

    async def typing_status(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "type": "typing",
                    "username": event["username"],
                    "is_typing": event["is_typing"],
                }
            )
        )

    async def presence_update(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "type": "presence",
                    "username": event["username"],
                    "status": event["status"],
                }
            )
        )

    async def pin_update(self, event):
        await self.send(
            text_data=json.dumps(
                {
                    "type": "pin_update",
                    "message_id": event["message_id"],
                    "preview": event["preview"],
                    "sender_username": event["sender_username"],
                    "pinned_by": event["pinned_by"],
                }
            )
        )

    async def presence_query(self, event):
        if event["reply_to"] == self.channel_name or not self.user.show_last_seen:
            return

        await self.channel_layer.send(
            event["reply_to"],
            {
                "type": "presence.update",
                "username": self.user.username,
                "status": "online",
            },
        )

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

    @database_sync_to_async
    def mark_message_read(self, message_id):
        message = Message.objects.filter(
            id=message_id,
            conversation_id=self.conversation_id,
        ).first()

        if message is None:
            return False

        if message.sender_id == self.user.id:
            return False

        status, created = MessageReadStatus.objects.get_or_create(
            message=message,
            user=self.user,
        )

        return created

    @database_sync_to_async
    def get_read_count(self, message_id):
        return MessageReadStatus.objects.filter(message__id=message_id).count()

    @database_sync_to_async
    def delete_message(self, message_id):
        deleted_count, _ = Message.objects.filter(
            id=message_id,
            conversation_id=self.conversation_id,
            sender=self.user,
        ).delete()

        return deleted_count > 0

    @database_sync_to_async
    def update_last_seen(self):
        User.objects.filter(id=self.user.id).update(last_seen=timezone.now())

    
    def _conversation_if_participant(self):
        return Conversation.objects.filter(
            id=self.conversation_id,
            participants=self.user,
        ).first()

    @database_sync_to_async
    def pin_message(self, message_id):
        conversation = self._conversation_if_participant()
        if conversation is None:
            return None

        message = (
            Message.objects.filter(id=message_id, conversation=conversation)
            .select_related("sender")
            .first()
        )

        if message is None:
            return None

        conversation.pinned_message = message
        conversation.pinned_by = self.user
        conversation.save(update_fields=["pinned_message","pinned_by"])

        preview = message.file_name if message.has_file else message.content[:80]

        return {
            "message_id": message.id,
            "preview": preview,
            "sender_username": message.sender.username,
            "pinned_by": self.user.username,
        }

    @database_sync_to_async
    def unpin_message(self):
        conversation = self._conversation_if_participant()
        if conversation is None:
            return False

        if not conversation.can_unpin(self.user):
            return False

        conversation.pinned_message = None
        conversation.pinned_by = None
        conversation.save(update_fields=["pinned_message", "pinned_by"])
        return True
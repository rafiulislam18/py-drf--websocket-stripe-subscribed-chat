import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
from .models import ChatRoom, RoomMembership, Message, TypingIndicator, MessageReadStatus
from .serializers import MessageSerializer, UserSerializer
from apps.subscription.models import Subscription
from django.contrib.auth.models import User
from django.db import models

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_id = self.scope['url_route']['kwargs']['room_id']
        self.room_group_name = f'chat_{self.room_id}'
        self.user = self.scope['user']
        
        # Check if user is authenticated
        if not self.user.is_authenticated:
            await self.close()
            return
        
        # Check if user is member of the room
        is_member = await self.check_room_membership()
        if not is_member:
            await self.close()
            return
        
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Mark user as online
        await self.update_online_status(True)
        
        # Broadcast user joined
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'user_status',
                'user_id': self.user.id,
                'username': self.user.username,
                'is_online': True,
                'online_count': await self.get_online_count()
            }
        )
    
    async def disconnect(self, close_code):
        if hasattr(self, 'room_group_name'):
            # Mark user as offline
            await self.update_online_status(False)
            
            # Remove typing indicator
            await self.remove_typing_indicator()
            
            # Leave room group
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )
            
            # Broadcast user left
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'user_status',
                    'user_id': self.user.id,
                    'username': self.user.username,
                    'is_online': False,
                    'online_count': await self.get_online_count()
                }
            )
    
    async def receive(self, text_data):
        # Check if the user is subscribed
        subscription = await database_sync_to_async(Subscription.objects.filter(user=self.user, is_active=True).first)()
        if not subscription:
            # Check if user has sent 10 messages in total (this is free tier limit). After that, require subscription.
            message_count = await database_sync_to_async(Message.objects.filter(sender=self.user).count)()
            if message_count >= 10:
                await self.send(text_data=json.dumps({
                    "type": "error",
                    "message": "You are not subscribed. Please subscribe to send more messages as you've hit the free tier limit."
                }))
                return  # Exit early if not subscribed
    
        data = json.loads(text_data)
        message_type = data.get('type')
        
        if message_type == 'chat_message':
            await self.handle_chat_message(data)
        elif message_type == 'typing_start':
            await self.handle_typing_start()
        elif message_type == 'typing_stop':
            await self.handle_typing_stop()
        elif message_type == 'message_read':
            await self.handle_message_read(data)
        elif message_type == 'delete_message':
            await self.handle_delete_message(data)
        elif message_type == 'edit_message':
            await self.handle_edit_message(data)
    
    async def handle_chat_message(self, data):
        content = data.get('content', '')
        reply_to_id = data.get('reply_to')
        
        # Save message to database
        message = await self.save_message(content, reply_to_id)
        
        if message:
            # Serialize message
            message_data = await self.serialize_message(message)
            
            # Send message to room group
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message',
                    'message': message_data
                }
            )
    
    async def handle_typing_start(self):
        await self.add_typing_indicator()
        
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'typing_indicator',
                'user_id': self.user.id,
                'username': self.user.username,
                'is_typing': True
            }
        )
    
    async def handle_typing_stop(self):
        await self.remove_typing_indicator()
        
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'typing_indicator',
                'user_id': self.user.id,
                'username': self.user.username,
                'is_typing': False
            }
        )
    
    async def handle_message_read(self, data):
        message_id = data.get('message_id')
        if message_id:
            await self.mark_message_as_read(message_id)
            
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'message_read_status',
                    'message_id': message_id,
                    'user_id': self.user.id,
                    'username': self.user.username
                }
            )
    
    async def handle_delete_message(self, data):
        message_id = data.get('message_id')
        if message_id:
            deleted = await self.delete_message(message_id)
            
            if deleted:
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'message_deleted',
                        'message_id': message_id
                    }
                )
    
    async def handle_edit_message(self, data):
        message_id = data.get('message_id')
        new_content = data.get('content')
        
        if message_id and new_content:
            message = await self.edit_message(message_id, new_content)
            
            if message:
                message_data = await self.serialize_message(message)
                
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'message_edited',
                        'message': message_data
                    }
                )
    
    # Receive message from room group
    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'type': 'chat_message',
            'message': event['message']
        }))
    
    async def user_status(self, event):
        await self.send(text_data=json.dumps({
            'type': 'user_status',
            'user_id': event['user_id'],
            'username': event['username'],
            'is_online': event['is_online'],
            'online_count': event['online_count']
        }))
    
    async def typing_indicator(self, event):
        # Don't send typing indicator to the user who is typing
        if event['user_id'] != self.user.id:
            await self.send(text_data=json.dumps({
                'type': 'typing_indicator',
                'user_id': event['user_id'],
                'username': event['username'],
                'is_typing': event['is_typing']
            }))
    
    async def message_read_status(self, event):
        await self.send(text_data=json.dumps({
            'type': 'message_read_status',
            'message_id': event['message_id'],
            'user_id': event['user_id'],
            'username': event['username']
        }))
    
    async def message_deleted(self, event):
        await self.send(text_data=json.dumps({
            'type': 'message_deleted',
            'message_id': event['message_id']
        }))
    
    async def message_edited(self, event):
        await self.send(text_data=json.dumps({
            'type': 'message_edited',
            'message': event['message']
        }))
    
    # Database operations
    @database_sync_to_async
    def check_room_membership(self):
        try:
            return ChatRoom.objects.filter(
                id=self.room_id,
                members=self.user
            ).exists()
        except:
            return False
    
    @database_sync_to_async
    def update_online_status(self, is_online):
        try:
            membership = RoomMembership.objects.get(
                room_id=self.room_id,
                user=self.user
            )
            membership.is_online = is_online
            membership.last_seen = timezone.now()
            membership.save()
        except RoomMembership.DoesNotExist:
            pass
    
    @database_sync_to_async
    def get_online_count(self):
        return RoomMembership.objects.filter(
            room_id=self.room_id,
            is_online=True
        ).count()
    
    @database_sync_to_async
    def save_message(self, content, reply_to_id=None):
        try:
            reply_to = None
            if reply_to_id:
                reply_to = Message.objects.get(id=reply_to_id)
            
            message = Message.objects.create(
                room_id=self.room_id,
                sender=self.user,
                content=content,
                message_type='text',
                reply_to=reply_to
            )
            
            # Update room timestamp
            ChatRoom.objects.filter(id=self.room_id).update(
                updated_at=timezone.now()
            )
            
            # Increment unread count for all members except sender
            RoomMembership.objects.filter(
                room_id=self.room_id
            ).exclude(user=self.user).update(
                unread_count=models.F('unread_count') + 1
            )
            
            return message
        except Exception as e:
            print(f"Error saving message: {e}")
            return None
    
    @database_sync_to_async
    def serialize_message(self, message):
        from django.core.serializers import serialize
        serializer = MessageSerializer(message)
        return serializer.data
    
    @database_sync_to_async
    def add_typing_indicator(self):
        try:
            TypingIndicator.objects.update_or_create(
                room_id=self.room_id,
                user=self.user
            )
        except Exception as e:
            print(f"Error adding typing indicator: {e}")
    
    @database_sync_to_async
    def remove_typing_indicator(self):
        try:
            TypingIndicator.objects.filter(
                room_id=self.room_id,
                user=self.user
            ).delete()
        except Exception as e:
            print(f"Error removing typing indicator: {e}")
    
    @database_sync_to_async
    def mark_message_as_read(self, message_id):
        try:
            message = Message.objects.get(id=message_id, room_id=self.room_id)
            MessageReadStatus.objects.get_or_create(
                message=message,
                user=self.user
            )
            
            # Decrement unread count
            membership = RoomMembership.objects.get(
                room_id=self.room_id,
                user=self.user
            )
            if membership.unread_count > 0:
                membership.unread_count -= 1
                membership.save()
        except Exception as e:
            print(f"Error marking message as read: {e}")
    
    @database_sync_to_async
    def delete_message(self, message_id):
        try:
            message = Message.objects.get(
                id=message_id,
                room_id=self.room_id,
                sender=self.user
            )
            message.delete()
            return True
        except Message.DoesNotExist:
            return False
        except Exception as e:
            print(f"Error deleting message: {e}")
            return False
    
    @database_sync_to_async
    def edit_message(self, message_id, new_content):
        try:
            message = Message.objects.get(
                id=message_id,
                room_id=self.room_id,
                sender=self.user
            )
            message.content = new_content
            message.is_edited = True
            message.save()
            return message
        except Message.DoesNotExist:
            return None
        except Exception as e:
            print(f"Error editing message: {e}")
            return None

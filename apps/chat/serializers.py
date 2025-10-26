from rest_framework import serializers
from django.contrib.auth.models import User
from .models import ChatRoom, RoomMembership, Message, MessageReadStatus, TypingIndicator
import uuid


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name']


class ChatRoomSerializer(serializers.ModelSerializer):
    members = UserSerializer(many=True, read_only=True)
    created_by = UserSerializer(read_only=True)
    total_members = serializers.IntegerField(read_only=True)
    online_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = ChatRoom
        fields = [
            'id', 'name', 'room_type', 'members', 'created_by', 
            'created_at', 'updated_at', 'total_members', 'online_count'
        ]


class RoomMembershipSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    room = ChatRoomSerializer(read_only=True)

    class Meta:
        model = RoomMembership
        fields = [
            'user', 'room', 'role', 'is_online', 
            'last_seen', 'joined_at', 'unread_count'
        ]


class MessageSerializer(serializers.ModelSerializer):
    sender = UserSerializer(read_only=True)
    room = serializers.PrimaryKeyRelatedField(queryset=ChatRoom.objects.all())
    reply_to = serializers.PrimaryKeyRelatedField(queryset=Message.objects.all(), allow_null=True)
    read_by = UserSerializer(many=True, read_only=True, source='read_statuses.user')

    class Meta:
        model = Message
        fields = [
            'id', 'room', 'sender', 'message_type', 'content',
            'image', 'video', 'reply_to', 'is_edited',
            'created_at', 'updated_at', 'read_by'
        ]

    def validate(self, data):
        if data.get('message_type') == 'text' and not data.get('content'):
            raise serializers.ValidationError("Content is required for text messages")
        if data.get('message_type') == 'image' and not data.get('image'):
            raise serializers.ValidationError("Image is required for image messages")
        if data.get('message_type') == 'video' and not data.get('video'):
            raise serializers.ValidationError("Video is required for video messages")
        return data


class MessageReadStatusSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    message = serializers.PrimaryKeyRelatedField(queryset=Message.objects.all())

    class Meta:
        model = MessageReadStatus
        fields = ['message', 'user', 'read_at']


class TypingIndicatorSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    room = serializers.PrimaryKeyRelatedField(queryset=ChatRoom.objects.all())

    class Meta:
        model = TypingIndicator
        fields = ['room', 'user', 'started_at']

from django.contrib import admin
from .models import ChatRoom, RoomMembership, Message, MessageReadStatus, TypingIndicator


@admin.register(ChatRoom)
class ChatRoomAdmin(admin.ModelAdmin):
    list_display = ('name', 'id', 'room_type', 'created_by', 'total_members', 'online_count', 'created_at', 'updated_at')
    list_filter = ('room_type', 'created_at', 'updated_at')
    search_fields = ('name', 'id', 'created_by__username')
    date_hierarchy = 'created_at'
    readonly_fields = ('id', 'created_at', 'updated_at')
    
    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('members', 'created_by')


@admin.register(RoomMembership)
class RoomMembershipAdmin(admin.ModelAdmin):
    list_display = ('user', 'room', 'role', 'is_online', 'last_seen', 'joined_at', 'unread_count')
    list_filter = ('role', 'is_online', 'joined_at')
    search_fields = ('user__username', 'room__name', 'room__id')
    date_hierarchy = 'joined_at'
    readonly_fields = ('joined_at',)


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'room', 'sender', 'message_type', 'content_preview', 'created_at', 'is_edited')
    list_filter = ('message_type', 'is_edited', 'created_at')
    search_fields = ('content', 'sender__username', 'room__name', 'id')
    date_hierarchy = 'created_at'
    readonly_fields = ('id', 'created_at', 'updated_at')
    
    def content_preview(self, obj):
        return obj.content[:50] + ('...' if len(obj.content) > 50 else '')
    
    content_preview.short_description = 'Content'


@admin.register(MessageReadStatus)
class MessageReadStatusAdmin(admin.ModelAdmin):
    list_display = ('message', 'user', 'read_at')
    list_filter = ('read_at',)
    search_fields = ('user__username', 'message__id')
    date_hierarchy = 'read_at'
    readonly_fields = ('read_at',)


@admin.register(TypingIndicator)
class TypingIndicatorAdmin(admin.ModelAdmin):
    list_display = ('user', 'room', 'started_at')
    list_filter = ('started_at',)
    search_fields = ('user__username', 'room__name', 'room__id')
    date_hierarchy = 'started_at'
    readonly_fields = ('started_at',)

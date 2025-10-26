from django.contrib import admin
from .models import Subscription


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'stripe_customer_id', 'stripe_subscription_id', 'subscription_length', 'is_active', 'created_at', 'updated_at')
    readonly_fields = ('id', 'created_at', 'updated_at')
    search_fields = ('user__username', 'stripe_customer_id', 'stripe_subscription_id')
    list_filter = ('is_active', 'created_at', 'updated_at')
    ordering = ('-created_at',)

    fieldsets = (
        ('Subscription Details', {
            'fields': (
                'id', 'user',
                'subscription_length', 'is_active'
            ),
        }),
        ('Stripe Info', {
            'fields': ('stripe_customer_id', 'stripe_subscription_id'),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
        }),
    )

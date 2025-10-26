from django.urls import path
from .views import CreateCheckoutSession, stripe_webhook, success_view, cancel_view


urlpatterns = [
    path('create-checkout-session/', CreateCheckoutSession.as_view()),
    path('stripe-webhook/', stripe_webhook),
    path('success/', success_view),
    path('cancel/', cancel_view),
]

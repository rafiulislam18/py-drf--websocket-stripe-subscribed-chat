import stripe
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
from django.conf import settings
from .models import Subscription
from .serializers import CreateCheckoutSessionSerializer


stripe.api_key = settings.STRIPE_SECRET_KEY

class CreateCheckoutSession(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        username = request.user.username
        try:
            customer = stripe.Customer.create(
                name=username
            )
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                mode='subscription',
                line_items=[{
                    'price': f'{settings.STRIPE_PRICE_ID}',  # Create recurring price in Stripe dashboard for R99/month
                    'quantity': 1,
                }],
                success_url='https://079d54ab7d23.ngrok-free.app/api/subscription/success/',
                cancel_url='https://079d54ab7d23.ngrok-free.app/api/subscription/cancel/',
                customer=customer.id,
            )

            # Create or update subscription
            sub = Subscription.objects.create(user=request.user)
            sub.stripe_customer_id = customer.id
            sub.save()
            return Response({'url': session.url})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

@csrf_exempt
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META['HTTP_STRIPE_SIGNATURE']
    event = None

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError as e:
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError as e:
        return HttpResponse(status=400)

    if event.type == 'checkout.session.completed':
        session = event.data.object
        customer_id = session.customer
        sub_id = session.subscription
        # sub_id = session.get('subscription')
        sub, created = Subscription.objects.get_or_create(stripe_customer_id=customer_id)
        sub.stripe_subscription_id = sub_id
        sub.is_active = True
        sub.save()
        # Send welcome email here (use django mail)

    elif event.type == 'invoice.paid':
        # Monthly payment success
        # sub_id = event.data.object.subscription
        sub_id = event.data.object.parent.subscription_details.subscription
        sub, created = Subscription.objects.get_or_create(stripe_subscription_id=sub_id)
        sub.subscription_length += 1
        sub.save()

    elif event.type == 'customer.subscription.deleted':
        sub_id = event.data.object.id
        sub, created = Subscription.objects.get_or_create(stripe_subscription_id=sub_id)
        sub.is_active = False
        sub.save()

    else:
        print(f"Unhandled event type: {event.type}")

    return HttpResponse(status=200)

def success_view(request):
    return HttpResponse("Subscription successful! Thank you for subscribing.")

def cancel_view(request):
    return HttpResponse("Subscription canceled. You have not been charged.")
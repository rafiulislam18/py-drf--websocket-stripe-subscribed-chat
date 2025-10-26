from django.contrib.auth.models import User

from .base import *
from ..serializers import (
    RegisterSerializer,
    RegisterResponseSerializer,
    UserSerializer,
)


class RegisterView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [RegisterThrottle]

    # Register a new user
    @swagger_auto_schema(
        tags=["Users"],
        operation_id="auth_register",
        operation_description="Register a new user & get JWT tokens",
        request_body=RegisterSerializer,
        responses={
            201: openapi.Response(
                '<b>Success:</b> Created',
                RegisterResponseSerializer
            ),
            400: openapi.Response(
                '<b>Error:</b> Bad request <br><b>Response detail examples:</b> "Username, password, and confirm_password are required.", "This username is already taken. Please choose a different one.", "Password must be at least 8 characters long.", "Passwords do not match.", "Invalid input."',
                ErrorResponseSerializer
            ),
            429: openapi.Response(
                '<b>Error:</b> Too many requests <br><b>Response detail examples: </b>' + r'"Request was throttled. Expected available in {integer} seconds."',
                ErrorResponseSerializer
            ),
            500: openapi.Response(
                '<b>Error:</b> Internal server error',
                ErrorResponseSerializer
            )
        }
    )
    def post(self, request):
        try:
            serializer = RegisterSerializer(data=request.data)

            if not serializer.is_valid():
                missing_fields = [field for field, errs in serializer.errors.items()]
                if 'username' in missing_fields or 'password' in missing_fields or 'confirm_password' in missing_fields:
                    return Response(
                        {
                            "detail": "Username, password, and confirm_password are required."
                        },
                        status=status.HTTP_400_BAD_REQUEST
                    )
                return Response(
                    {
                        "detail": "Invalid input."
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            username = serializer.validated_data.get('username')
            password = serializer.validated_data.get('password')
            confirm_password = serializer.validated_data.get('confirm_password')

            if User.objects.filter(username=username).exists():
                return Response(
                    {
                        "detail": "This username is already taken. Please choose a different one."
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            if len(password) < 8:
                return Response(
                    {
                        "detail": "Password must be at least 8 characters long."
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            if password != confirm_password:
                return Response(
                    {
                        "detail": "Passwords do not match."
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            user = User.objects.create_user(username=username, password=password)
            
            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)
            access_token = str(refresh.access_token)

            response = {
                "access": access_token,
                "refresh": str(refresh),
                "user": UserSerializer(user).data
            }

            return Response(
                RegisterResponseSerializer(response).data,
                status=status.HTTP_201_CREATED
            )
        
        except Exception as e:
            return Response(
                {
                    "detail": str(e)
                },
                status=status.HTTP_400_BAD_REQUEST
            )

from django.contrib.auth import authenticate

from .base import *
from ..serializers import (
    UserSerializer,
    LoginSerializer,
    LoginResponseSerializer
)


class LoginView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [HighLimitAnonRateThrottle]

    # Handle user login and return JWT tokens
    @swagger_auto_schema(
        tags=["Users"],
        operation_id="auth_login",
        operation_description="Login user & get JWT tokens",
        request_body=LoginSerializer,
        responses={
            200: openapi.Response(
                '<b>Success:</b> Ok',
                LoginResponseSerializer
            ),
            400: openapi.Response(
                '<b>Error:</b> Bad Request <br><b>Response detail examples:</b> "Both username and password are required.", "Invalid username or password.", "Invalid input."',
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
            serializer = LoginSerializer(data=request.data)

            if not serializer.is_valid():
                # Extract missing field errors
                missing_fields = [field for field, errs in serializer.errors.items()]
                if 'username' in missing_fields or 'password' in missing_fields:
                    return Response(
                        {
                            "detail": "Both username and password are required."
                        },
                        status=status.HTTP_400_BAD_REQUEST
                    )

            username = serializer.validated_data.get('username')
            password = serializer.validated_data.get('password')

            user = authenticate(request=request, username=username, password=password)
            if not user:
                return Response(
                    {
                        "detail": "Invalid username or password."
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)
            access_token = str(refresh.access_token)

            response = {
                "access": access_token,
                "refresh": str(refresh),
                "user": UserSerializer(user).data
            }

            return Response(
                LoginResponseSerializer(response).data,
                status=status.HTTP_200_OK
            )
        
        except ValidationError as e:
            return Response(
                {
                    "detail": "Invalid input."
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        except Exception as e:
            return Response(
                {
                    "detail": str(e)
                },
                status=status.HTTP_400_BAD_REQUEST
            )

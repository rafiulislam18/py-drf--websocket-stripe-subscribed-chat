from .base import *
from ..serializers import (
    LogoutSerializer,
)


class LogoutView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [HighLimitAnonRateThrottle]

    # Handle user logout
    @swagger_auto_schema(
        tags=["Users"],
        operation_id="auth_logout",
        operation_description="Logout user by refresh token",
        request_body=LogoutSerializer,
        responses={
            204: openapi.Response(
                '<b>Success:</b> No content',
            ),
            400: openapi.Response(
                '<b>Error:</b> Bad request <br><b>Response detail examples:</b> "Refresh token is required.", "Invalid input."',
                ErrorResponseSerializer
            ),
            401: openapi.Response(
                '<b>Error:</b> Unauthorized <br><b>Response detail examples:</b> "Invalid or expired refresh token.", "Invalid token type."',
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
        serializer = LogoutSerializer(data=request.data)

        if not serializer.is_valid():
            missing_fields = [field for field, errs in serializer.errors.items()]
            if 'refresh' in missing_fields:
                return Response(
                    {
                        "detail": "Refresh token is required."
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            return Response(
                {
                    "detail": "Invalid input."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        refresh_token = serializer.validated_data.get("refresh")

        try:
            token = RefreshToken(refresh_token)
            token.blacklist()

            return Response(
                status=status.HTTP_204_NO_CONTENT
            )
        
        except InvalidToken as e:
            return Response(
                {
                    "detail": "Invalid token type."
                },
                status=status.HTTP_401_UNAUTHORIZED
            )

        except TokenError as e:
            return Response(
                {
                    "detail": "Invalid or expired refresh token."
                },
                status=status.HTTP_401_UNAUTHORIZED
            )

        except Exception as e:
            return Response(
                {
                    "detail": str(e)
                },
                status=status.HTTP_400_BAD_REQUEST
            )

from rest_framework_simplejwt.views import TokenRefreshView

from .base import *
from ..serializers import (
    TokenRefreshResponseSerializer
)


class MyTokenRefreshView(TokenRefreshView):
    permission_classes = [AllowAny]
    throttle_classes = [HighLimitAnonRateThrottle]

    # Handle token refresh
    @swagger_auto_schema(
        tags=["Users"],
        operation_id="auth_refresh",
        operation_description=(
            "Takes a refresh type JSON web token and returns an access type "
            "JSON web token & a new refresh token blacklisting the previous "
            "one if the submitted refresh token is valid."
        ),
        responses={
            200: openapi.Response(
                '<b>Success:</b> Ok',
                TokenRefreshResponseSerializer
            ),
            400: openapi.Response(
                '<b>Error:</b> Bad Request <br><b>Response detail examples:</b> "Refresh token is required."',
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
    def post(self, request, *args, **kwargs):
        if not request.data.get('refresh'):
            return Response(
                {
                    "detail": "Refresh token is required."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            data = serializer.validated_data

            response_data = {
                "access": data["access"],
                "refresh": data["refresh"]
            }

            return Response(
                TokenRefreshResponseSerializer(response_data).data,
                status=status.HTTP_200_OK
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

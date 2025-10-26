To switch from session-based authentication to **JWT authentication** using `djangorestframework-simplejwt` in your Django Channels WebSocket application, you need to modify your setup to authenticate WebSocket connections using JWT tokens instead of session cookies. Below is a step-by-step guide to achieve this.

### Prerequisites
- Install `djangorestframework-simplejwt`:
  ```bash
  pip install djangorestframework-simplejwt
  ```
- Ensure `djangorestframework` is installed:
  ```bash
  pip install djangorestframework
  ```

### Steps to Implement JWT Authentication

#### 1. Configure `djangorestframework-simplejwt` in Django
Add the necessary configurations to your `settings.py` to enable `djangorestframework-simplejwt`.

```python
# settings.py
INSTALLED_APPS = [
    ...
    'rest_framework',
    'rest_framework_simplejwt',
    ...
]

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
}

from datetime import timedelta

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
    'ROTATE_REFRESH_TOKENS': False,
    'BLACKLIST_AFTER_ROTATION': False,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
}
```

#### 2. Create a Custom JWT Authentication Middleware for Channels
Django Channels doesn't natively support `djangorestframework-simplejwt` for WebSocket authentication, so you need a custom middleware to extract and validate JWT tokens from the WebSocket connection (e.g., from query parameters or headers).

Create a new file, e.g., `chat/middleware.py`:

```python
import jwt
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.auth import get_user_model
from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import AccessToken

@database_sync_to_async
def get_user_from_token(token):
    try:
        # Validate the token
        access_token = AccessToken(token)
        user_id = access_token['user_id']
        user = get_user_model().objects.get(id=user_id)
        return user
    except (InvalidToken, TokenError, User.DoesNotExist):
        return None

class JWTMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        # Extract token from query string or headers
        query_string = scope.get('query_string', b'').decode()
        token = None

        # Check query string for token (e.g., ws://localhost:8000/ws/chat/1/?token=abc)
        if query_string:
            for param in query_string.split('&'):
                if param.startswith('token='):
                    token = param.split('=')[1]
                    break

        # Alternatively, check headers for token (e.g., Authorization: Bearer <token>)
        headers = dict(scope['headers'])
        auth_header = headers.get(b'authorization', b'').decode()
        if auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]

        # Authenticate user
        if token:
            user = await get_user_from_token(token)
            if user is not None:
                scope['user'] = user
            else:
                scope['user'] = None
        else:
            scope['user'] = None

        return await super().__call__(scope, receive, send)
```

#### 3. Update Channels Routing Configuration
Modify your `routing.py` to include the JWT middleware. Replace the default `AuthMiddlewareStack` with your custom `JWTMiddleware`.

```python
# routing.py
from django.urls import re_path
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from chat.middleware import JWTMiddleware
from chat.consumers import ChatConsumer

application = ProtocolTypeRouter({
    'websocket': AllowedHostsOriginValidator(
        JWTMiddleware(
            URLRouter([
                re_path(r'ws/chat/(?P<room_id>\d+)/$', ChatConsumer.as_asgi()),
            ])
        )
    ),
})
```

#### 4. Update `ChatConsumer` to Handle JWT Authentication
Modify your `ChatConsumer` to work with JWT authentication. The `scope['user']` will now be populated by the `JWTMiddleware`. The rest of your consumer logic can remain largely unchanged, but ensure the authentication check aligns with JWT.

Update the `connect` method in `chat/consumers.py`:

```python
async def connect(self):
    self.room_id = self.scope['url_route']['kwargs']['room_id']
    self.room_group_name = f'chat_{self.room_id}'
    self.user = self.scope['user']
    
    # Check if user is authenticated
    if self.user is None or not self.user.is_authenticated:
        await self.close(code=4001)  # Custom close code for unauthorized
        return
    
    # Check if user is a member of the room
    is_member = await self.check_room_membership()
    if not is_member:
        await self.close(code=4003)  # Custom close code for forbidden
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
```

The rest of the `ChatConsumer` code can remain as is, as it doesn't directly depend on the authentication mechanism.

#### 5. Update Frontend to Send JWT Token
Your frontend needs to include the JWT token when connecting to the WebSocket. The token can be sent either in the query string or in the `Authorization` header.

**Option 1: Query String**
```javascript
// Example using JavaScript
const token = "your_jwt_access_token";
const ws = new WebSocket(`ws://localhost:8000/ws/chat/1/?token=${token}`);

// Handle WebSocket events
ws.onopen = () => console.log("Connected");
ws.onmessage = (event) => console.log("Message:", event.data);
ws.onclose = (event) => console.log("Closed:", event.code);
```

**Option 2: Authorization Header**
Some WebSocket clients (e.g., in browsers) don't support custom headers directly. If you need to use headers, you may need a server-side proxy or a WebSocket client library that supports headers (e.g., `websocket` in Node.js). Example for a compatible client:

```javascript
// Example using a WebSocket library that supports headers (e.g., in Node.js)
const WebSocket = require('ws');
const ws = new WebSocket('ws://localhost:8000/ws/chat/1/', {
    headers: {
        Authorization: `Bearer ${token}`
    }
});
```

#### 6. Generate JWT Tokens
Use `djangorestframework-simplejwt` to generate tokens for your users. Typically, you provide an endpoint for users to log in and obtain tokens.

Add token endpoints to your `urls.py`:

```python
# urls.py
from django.urls import path
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

urlpatterns = [
    ...
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]
```

Users can authenticate via the `/api/token/` endpoint (POST with username and password) to receive an access and refresh token. The access token should be used in the WebSocket connection.

#### 7. Handle Token Expiry
Since JWT access tokens have a limited lifetime (e.g., 60 minutes as configured), your frontend should handle token expiry:
- Use the refresh token to obtain a new access token via the `/api/token/refresh/` endpoint.
- Reconnect the WebSocket with the new access token if the connection is closed due to an expired token (e.g., close code 4001).

#### 8. Test the Setup
1. Authenticate a user via the `/api/token/` endpoint to get a JWT access token.
2. Connect to the WebSocket using the token (e.g., `ws://localhost:8000/ws/chat/1/?token=<your_token>`).
3. Verify that:
   - Authenticated users can connect and interact with the chat.
   - Unauthenticated users or invalid tokens result in a closed connection (code 4001).
   - Non-members of the room are rejected (code 4003).
4. Test token expiry by waiting for the access token to expire and ensuring the WebSocket connection closes.

#### 9. Optional: Enhance Security
- **Validate Token Scope**: Ensure the token is intended for WebSocket use (e.g., by adding a custom claim in the JWT).
- **Secure WebSocket**: Use `wss://` (WebSocket Secure) in production to encrypt the connection.
- **Token Blacklisting**: If you enable `BLACKLIST_AFTER_ROTATION` in `SIMPLE_JWT`, ensure your app handles token blacklisting for refresh tokens.

### Summary
- **Authentication Type**: Switched from session-based to JWT using `djangorestframework-simplejwt`.
- **Key Changes**:
  - Added `djangorestframework-simplejwt` to the project.
  - Created a custom `JWTMiddleware` to validate JWT tokens for WebSocket connections.
  - Updated `ChatConsumer` to handle JWT-authenticated users.
  - Modified the frontend to include the JWT token in WebSocket connections.
  - Added token generation endpoints (`/api/token/` and `/api/token/refresh/`).
- **Benefits**:
  - Stateless authentication suitable for scalable, cross-service applications.
  - Better suited for APIs and clients that don't rely on cookies.
- **Considerations**:
  - Handle token expiry and refresh logic in the frontend.
  - Ensure secure transmission of tokens (use `wss://` in production).

Let me know if you need help with specific parts, such as frontend integration or additional error handling!
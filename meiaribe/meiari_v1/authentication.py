import jwt
from django.core.exceptions import ValidationError
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from .models import MeiAriUser
from .methods import decode_token



class UserTokenAuthentication(BaseAuthentication):
    """
    Authenticates `Authorization: Bearer <token>` using the token returned by
    the sign-in API. Attach to a view with `authentication_classes`.
    """
    def authenticate(self, request):
        token = request.headers.get('Authorization', '').split()
        if len(token) != 2:
            raise AuthenticationFailed("Token authentication failed.")
        try:
            decoded_token = decode_token(token[1])
        except jwt.ExpiredSignatureError:
            raise AuthenticationFailed("Token authentication failed due to expired signature.")
        except jwt.InvalidTokenError:
            raise AuthenticationFailed("Token authentication failed.")

        user_id = str(decoded_token.get("id"))  # Cast ID to string
        try:
            user = MeiAriUser.objects.filter(id=user_id).first()
        except (ValueError, ValidationError):
            user = None
        if not user:
            raise AuthenticationFailed("Token authentication failed.")
        return user, decoded_token

    def authenticate_header(self, request):
        return 'Bearer'

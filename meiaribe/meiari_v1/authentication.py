import jwt
from rest_framework.authentication import BaseAuthentication    
from rest_framework.exceptions import AuthenticationFailed
from .models import UserDetails
from .methods import decode_token
from rest_framework_simplejwt.authentication import JWTAuthentication   



class UserTokenAuthentication(BaseAuthentication):
    def authenticate(self, request):
        try:
            token = request.headers.get('Authorization', '').split()
            if len(token) == 2:
                decoded_token = jwt.decode(token[1], "user_key", algorithms=["HS256"])
                print(decoded_token)
                user_id = str(decoded_token.get("id"))  # Cast ID to string
                user = UserDetails.objects.filter(id=user_id).first()
                if user:
                    return user, decoded_token["role"]
                else:
                    raise AuthenticationFailed("Token authentication failed.")
            else:
                raise AuthenticationFailed("Token authentication failed.")
        except (jwt.ExpiredSignatureError, jwt.InvalidSignatureError):
            raise AuthenticationFailed("Token authentication failed due to expired or invalid signature.")
        except Exception as e:
            raise AuthenticationFailed("Token authentication failed due to an unexpected error: {}".format(str(e)))
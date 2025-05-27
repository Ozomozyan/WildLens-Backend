from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.tokens import UntypedToken
from django.contrib.auth import get_user_model

User = get_user_model()

class SupabaseJWTAuthentication(JWTAuthentication):
    """
    Validate Supabase JWT without requiring a jti/id claim.
    """
    def get_validated_token(self, raw_token):
        return UntypedToken(raw_token)   # avoids jti/id check

    def get_user(self, validated_token):
        uid = validated_token["sub"]
        email = validated_token.get("email", "")
        user, _ = User.objects.get_or_create(
            username=uid,
            defaults={"email": email},
        )
        return user

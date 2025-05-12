import os
import jwt
from django.http import JsonResponse

SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "CHANGE_ME")

class SupabaseAuthMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        token = None

        # 1) Check if there's an Authorization header
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if auth_header.startswith('Bearer '):
            token = auth_header.split('Bearer ')[1]

        # 2) If no header, check the session for a token
        if not token and hasattr(request, 'session'):
            token = request.session.get('supabase_token')

        if token:
            try:
                # Verify the token
                payload = jwt.decode(token, SUPABASE_JWT_SECRET, audience="authenticated", algorithms=['HS256'])
                request.supabase_user = payload
            except jwt.ExpiredSignatureError:
                return JsonResponse({"error": "Token expired"}, status=401)
            except jwt.InvalidTokenError:
                return JsonResponse({"error": "Invalid token"}, status=401)

        # proceed with request
        response = self.get_response(request)
        return response

# wildlens_backend/supabase_util.py
import os
from supabase import create_client, Client
from django.conf import settings

SUPABASE_URL      = settings.SUPABASE_URL
SUPABASE_ANON_KEY = settings.SUPABASE_KEY        # anon key, NOT service key

def client_for_request(request) -> Client:
    """
    Return a fresh Supabase client whose PostgREST layer is authenticated
    with the *end-user's* JWT (so RLS policies see auth.uid()).
    """
    # 1) Get the JWT – header first, session fallback
    auth_header = request.META.get("HTTP_AUTHORIZATION", "")
    if auth_header.startswith("Bearer "):
        jwt = auth_header.split(" ", 1)[1]
    else:
        jwt = request.session.get("supabase_token")

    if not jwt:
        # Caller forgot the header → you’ll hit RLS anyway
        return create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

    # 2) New client per request (thread-safe)
    sb: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

    # 3) Attach the token so PostgREST sends `Authorization: Bearer …`
    #
    #   • v2 SDK ➜ sb.auth.set_session({"access_token": jwt, "refresh_token": None})
    #   • v1 SDK ➜ sb.auth.session = {"access_token": jwt, "token_type": "bearer"}
    #
    # Adjust depending on the version you installed:
    try:                         # works for v2
        sb.auth.set_session(access_token=jwt, refresh_token="") 
    except TypeError:            # fallback for v1
        sb.auth.session = {"access_token": jwt, "token_type": "bearer"}

    return sb

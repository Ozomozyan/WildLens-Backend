import io, os, requests, tempfile
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.conf import settings
from rest_framework.views import APIView
from rest_framework import status, permissions
from wildlens_backend.auth_decorators import supabase_login_required
from rest_framework import viewsets, status, permissions
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser
from wildlens_backend.settings import SUPABASE_CLIENT  # 🔸 create a helper (see below)
from ai.predict import predict                     # 🔸 already in repo
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.http import JsonResponse
from django.conf import settings
from postgrest.exceptions import APIError
import json
from collections import Counter
from django.shortcuts import render, redirect
from django.conf import settings
from wildlens_backend.auth_decorators import supabase_login_required



def _sb_for(request):
    """
    Return a Supabase client whose PostgREST layer is authenticated
    with the JWT that arrived on this HTTP request.
    """
    jwt = request.headers.get("Authorization", "").split(" ", 1)[-1]
    # clone-like behaviour: postgrest.auth() mutates in-place but is cheap
    SUPABASE_CLIENT.postgrest.auth(jwt)
    return SUPABASE_CLIENT

@method_decorator(csrf_exempt, name="dispatch")
class PredictView(APIView):
    """
    Accepts ONE image (multipart/form-data “file”) and
    streams it to the AI micro-service.  Never saved to disk.
    """
    permission_classes = [permissions.AllowAny]   # overridden by decorator

    @supabase_login_required
    def post(self, request, *args, **kwargs):
        uploaded = request.FILES.get("file")
        if not uploaded:
            return JsonResponse({"error": "Missing ‘file’"}, status=400)

        try:
            resp = requests.post(
                settings.AI_SERVICE_URL,
                files={"file": (uploaded.name, uploaded.read(), uploaded.content_type)},
                timeout=10,
            )
            resp.raise_for_status()
        except requests.RequestException as exc:
            return JsonResponse({"error": f"AI service unreachable: {exc}"}, status=502)

        return JsonResponse(resp.json(), status=status.HTTP_200_OK)

@permission_classes([IsAuthenticated])
class PredictionViewSet(viewsets.ViewSet):
    """
    POST /api/predictions/      – run model, store + return prediction
    GET  /api/predictions/      – list user’s predictions
    GET  /api/predictions/<id>/ – get one prediction
    """
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser]

    def list(self, request):
        sb = _sb_for(request)
        resp = sb.table("predictions")\
                       .select("*")\
                       .eq("user_id", request.user.username)\
                       .order("created_at", desc=True)\
                       .limit(50)\
                       .execute()
        return Response(resp.data)

    def retrieve(self, request, pk=None):
        sb = _sb_for(request)
        resp = sb.table("predictions")\
                       .select("*")\
                       .eq("id", pk)\
                       .eq("user_id", request.user.username)\
                       .single()\
                       .execute()
        if resp.data:
            return Response(resp.data)
        return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)
    
    def create(self, request):
        # 1) Grab uploaded image
        uploaded = request.FILES.get("image")
        if not uploaded:
            return Response(
                {"detail": "image field required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 2) Save to temp file and run AI prediction
        suffix = os.path.splitext(uploaded.name)[1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            for chunk in uploaded.chunks():
                tmp.write(chunk)
            temp_path = tmp.name

        try:
            result = predict(temp_path)    # e.g. ("Ours", 0.1369…)
        finally:
            os.remove(temp_path)

        # 3) Format the prediction exactly as ("Name",0.79)
        if isinstance(result, (list, tuple)) and len(result) == 2:
            name, confidence = result
        else:
            name = str(result)
            confidence = 1.0
        confidence = round(float(confidence), 2)
        species = f'("{name}",{confidence:.2f})'
        
        # 3b) If confidence < 0.03 (3%), ask user to retake photo
        if confidence < 0.03:
            return Response(
                {"detail": "Confidence too low (under 3 %)—please take another picture."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 4) Insert row in Supabase, using the formatted string
        insert_payload = {
            "user_id": request.user.username,
            "predicted_species": species,
            "location_text": request.data.get("location_text"),
            "latitude": request.data.get("lat"),
            "longitude": request.data.get("lon"),
            "notes": request.data.get("notes"),
        }
        _sb_for(request).table("predictions").insert(insert_payload).execute()

        # 5) Fetch one matching row from infos_especes (limit 1, never .single())
        info_res = (
            _sb_for(request)
            .table("infos_especes")
            .select("*")
            .ilike("Espèce", name)
            .limit(1)
            .execute()
        )
        species_info = info_res.data[0] if (info_res.data and len(info_res.data) > 0) else {}

        return Response(
            {"prediction": species, "species_info": species_info},
            status=status.HTTP_201_CREATED
        )
    
    
    
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def prediction_locations(request):
    res = (
        settings.SUPABASE_CLIENT
        .table("prediction_locations_v")
        .select("*")
        .execute()
    )
    return Response(res.data)


# ─────────────────────────────────────────────────────────────────────
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def species_info(request):
    """
    GET /api/species-info/?name=<species_name>
    Returns the first matching row from infos_especes.
    """
    name = request.GET.get("name")
    if not name:
        return JsonResponse({"detail": "Missing `name` parameter"}, status=400)

    sb = _sb_for(request)
    res = (
        sb.table("infos_especes")
          .select("*")
          .ilike("Espèce", name)
          .single()
          .execute()
    )
    if not res.data:
        return JsonResponse({"detail": "Species not found"}, status=404)

    return JsonResponse(res.data)


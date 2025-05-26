import io, os, requests
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


class PredictionViewSet(viewsets.ViewSet):
    """
    POST /api/predictions/      – run model, store + return prediction
    GET  /api/predictions/      – list user’s predictions
    GET  /api/predictions/<id>/ – get one prediction
    """
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser]

    def list(self, request):
        resp = SUPABASE_CLIENT.table("predictions")\
                       .select("*")\
                       .eq("user_id", str(request.user.id))\
                       .order("created_at", desc=True)\
                       .limit(50)\
                       .execute()
        return Response(resp.data)

    def retrieve(self, request, pk=None):
        resp = SUPABASE_CLIENT.table("predictions")\
                       .select("*")\
                       .eq("id", pk)\
                       .eq("user_id", str(request.user.id))\
                       .single()\
                       .execute()
        if resp.data:
            return Response(resp.data)
        return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)

    def create(self, request):
        # 1. Grab uploaded image
        uploaded = request.FILES.get("image")
        if not uploaded:
            return Response({"detail": "image field required"}, status=status.HTTP_400_BAD_REQUEST)

        # 2. Save to temp and predict
        temp_path = f"/tmp/{uploaded.name}"
        with open(temp_path, "wb+") as tmp:
            for chunk in uploaded.chunks():
                tmp.write(chunk)

        try:
            species = predict(temp_path)        # returns str
        finally:
            os.remove(temp_path)

        # 3. Insert row in Supabase
        insert_payload = {
            "user_id": str(request.user.id),
            "predicted_species": species,
            "location_text": request.data.get("location_text"),
            "latitude": request.data.get("lat"),
            "longitude": request.data.get("lon"),
            "notes": request.data.get("notes"),
        }
        SUPABASE_CLIENT.table("predictions").insert(insert_payload).execute()

        return Response({"prediction": species}, status=status.HTTP_201_CREATED)
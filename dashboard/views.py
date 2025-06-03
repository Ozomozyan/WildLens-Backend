# dashboard/views.py

import os, jwt
import requests
from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse, StreamingHttpResponse
from wildlens_backend.supabase_util import client_for_request
from wildlens_backend.auth_decorators import supabase_admin_required
from django.views.decorators.csrf import csrf_exempt
from wildlens_backend.local_runner import start_training
from wildlens_backend.auth_decorators import supabase_login_required
import json, io, os, re, time
from django.conf import settings
from django.views.decorators.cache import cache_page
from django.views.decorators.http import require_GET
from wildlens_backend.auth_decorators import supabase_login_required
from django.http import JsonResponse, HttpResponse, HttpResponseBadRequest
from collections import Counter, deque

import json
from collections import Counter

# 🔧 PATCH ❶ – put near the other imports at the top
from rest_framework.decorators import api_view
from rest_framework.response import Response

LOG_FILE = os.getenv("GUNICORN_LOG", "/app/logs/gunicorn.log")

# ─── GitHub / workflow settings ────────────────────────────────────────────
GITHUB_TOKEN  = os.getenv("GITHUB_TOKEN", None)           # same var you already use
GITHUB_OWNER  = os.getenv("GITHUB_OWNER", "Ozomozyan")    # change if needed
GITHUB_REPO   = os.getenv("GITHUB_REPO",  "MSPR_ETL")  # this project’s repo
TRAIN_WORKFLOW = os.getenv("TRAIN_WORKFLOW", "MODEL_TRAIN.yml")

@csrf_exempt
def login_view(request):
    """
    Option A: A pure-JSON login endpoint for React. 
    Expects POST {"email": "...", "password": "..."} and returns:
      { "token": "<supabase_jwt>", "user_id": "<uid>", "role": "admin"|"user" }
    Saves token and uid in request.session so that @supabase_login_required sees it.
    """

    # Only allow POST with JSON
    if request.method != "POST":
        return HttpResponseBadRequest("Only POST with JSON body is allowed.")

    # Parse JSON from request.body
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (ValueError, TypeError):
        return HttpResponseBadRequest("Invalid JSON.")

    email = payload.get("email")
    password = payload.get("password")
    if not email or not password:
        return HttpResponseBadRequest("Email and password are required.")

    # 1) Exchange credentials for a Supabase JWT
    endpoint = f"{os.getenv('SUPABASE_URL')}/auth/v1/token?grant_type=password"
    headers = {
        "apikey":       os.getenv("SUPABASE_KEY", ""),
        "Content-Type": "application/json",
    }
    resp = requests.post(
        endpoint,
        json={"email": email, "password": password},
        headers=headers
    )
    if resp.status_code != 200:
        return JsonResponse(
            {"detail": "Login failed. Check your credentials."},
            status=401
        )

    token = resp.json().get("access_token")
    if not token:
        return JsonResponse(
            {"detail": "No token returned by Supabase."},
            status=401
        )

    # 2) Decode the JWT (without verifying signature) to inspect app_metadata.role
    try:
        claims = jwt.decode(token, options={"verify_signature": False})
    except jwt.PyJWTError:
        return JsonResponse(
            {"detail": "Could not decode Supabase token."},
            status=500
        )

    app_meta = claims.get("app_metadata", {}) or {}
    is_admin = (app_meta.get("role") == "admin")

    # 3) Store in Django session so @supabase_login_required can work later
    request.session["supabase_token"] = token
    request.session["supabase_uid"]   = claims.get("sub")
    request.session.save()  # force Django to issue a sessionid cookie

    # 4) Return JSON so React can handle routing
    return JsonResponse({
        "token": token,
        "user_id": claims.get("sub"),
        "role": "admin" if is_admin else "user"
    })


@supabase_admin_required
def admin_dashboard(request):
    """
    Because species_summary_v may produce multiple rows per species
    (one for each region token), we must:
     - Dedupe by species for "Images by Species," "Completeness," etc.
     - Count each region token to show region distribution properly.
    """

    try:
        # Query the multi-row view
        res_obj = settings.SUPABASE_CLIENT.table("species_summary_v").select("*").execute()
        data = res_obj.data  # List of dicts, each possibly a different region token
    except Exception as e:
        return render(request, "dashboard/admin_dashboard.html", {
            "error": f"Supabase query failed: {str(e)}"
        })

    if not data:
        return render(request, "dashboard/admin_dashboard.html", {
            "error": "No data returned from 'species_summary_v'."
        })

    # ------------------------------------------------------
    # 1) Build a dictionary so each species is stored only once
    #    We'll merge the region tokens into a set so we can display them all.
    # ------------------------------------------------------
    species_map = {}
    for row in data:
        sid = row["species_id"]

        # If we haven't seen this species yet, initialize a record
        if sid not in species_map:
            species_map[sid] = {
                "species_id": sid,
                "species_name": row["species_name"],
                "family": row["family"],
                "taille": row["taille"],
                "description": row["description"],
                "total_images": row["total_images"],
                "completeness_percentage": row["completeness_percentage"],
                # We'll collect region buckets in a set:
                "region_set": set()
            }

        # Add this row's region bucket (or region token) to the set
        # If your view has a column "region_bucket", use that. Otherwise, it might be "region" or "region_token".
        # Example: if you named it "region_bucket" in the final SELECT...
        # species_map[sid]["region_set"].add(row["region_bucket"])

        # If your final column is just "region" but actually splitted:
        # species_map[sid]["region_set"].add(row["region"])

        # Let's assume the final splitted column is named "region_bucket"
        # If it's named differently, adjust here:
        if "region_bucket" in row and row["region_bucket"]:
            species_map[sid]["region_set"].add(row["region_bucket"])
        else:
            # fallback if your splitted column is called "region"
            # or if there's no splitted column but you want that text
            if row.get("region"):
                species_map[sid]["region_set"].add(row["region"])

    # ------------------------------------------------------
    # 2) Convert species_map -> a list of unique species for the table
    #    We'll join the region set to display multiple regions in one cell.
    # ------------------------------------------------------
    unique_species_list = []
    for sid, info in species_map.items():
        # join all region tokens into one string
        region_str = ", ".join(sorted(info["region_set"]))

        rowdict = {
            "species_id": sid,
            "species_name": info["species_name"],
            "family": info["family"],
            "taille": info["taille"],
            "description": info["description"],
            "total_images": info["total_images"],
            "completeness_percentage": info["completeness_percentage"],
            "region": region_str,
        }
        unique_species_list.append(rowdict)

    # ------------------------------------------------------
    # 3) Prepare the "Images by Species" bar chart
    #    (1 bar per species)
    # ------------------------------------------------------
    species_names = []
    images_count = []
    for sid, info in species_map.items():
        species_names.append(info["species_name"])
        images_count.append(info["total_images"])

    # ------------------------------------------------------
    # 4) Prepare "Species Count by Family" (pie chart)
    #    Also 1 record per species
    # ------------------------------------------------------
    family_counter = Counter(info["family"] for info in species_map.values())
    family_labels = list(family_counter.keys())
    family_values = list(family_counter.values())

    # ------------------------------------------------------
    # 5) Prepare "Completeness by Species"
    # ------------------------------------------------------
    completeness_list = [info["completeness_percentage"] for info in species_map.values()]

    # ------------------------------------------------------
    # 6) Region distribution: how many species in each region
    #    Each species can be counted once per region in region_set
    # ------------------------------------------------------
    region_counter = Counter()
    for info in species_map.values():
        for reg in info["region_set"]:
            region_counter[reg] += 1

    region_labels = list(region_counter.keys())
    region_values = list(region_counter.values())

    # ------------------------------------------------------
    # 7) Pass to the template
    # ------------------------------------------------------
    context = {
        # For chart #1
        "species_names_json": json.dumps(species_names),
        "images_count_json": json.dumps(images_count),

        # For chart #2
        "family_labels_json": json.dumps(family_labels),
        "family_values_json": json.dumps(family_values),

        # For chart #3
        "completeness_json": json.dumps(completeness_list),

        # For region distribution chart
        "region_labels_json": json.dumps(region_labels),
        "region_values_json": json.dumps(region_values),

        # For the details table (unique species only)
        "species_summary": unique_species_list,
    }

    return render(request, "dashboard/admin_dashboard.html", context)




@supabase_admin_required
def data_quality_dashboard(request):
    """
    Shows data-quality logs & chart for whichever table the user selects
    from a dropdown (e.g., 'infos_especes' or 'footprint_images').
    """

    # 1) Get 'table_name' from the GET params, default to 'infos_especes'
    table_requested = request.GET.get("table_name", "infos_especes")

    try:
        # 2) Fetch ALL logs. We'll filter in Python (or do a second query if you prefer).
        res = client_for_request(request).table("data_quality_log") \
            .select("*") \
            .order("execution_time", desc=True) \
            .execute()

        logs = res.data or []
    except Exception as e:
        return render(request, "dashboard/data_quality_dashboard.html", {
            "error": f"Supabase query failed: {str(e)}"
        })

    if not logs:
        return render(request, "dashboard/data_quality_dashboard.html", {
            "error": "No data in data_quality_log."
        })

    # 3) Build "latest" map for display in table, just like before
    latest_map = {}
    full_history = []
    for row in logs:
        tname = row["table_name"]
        test_str = row["test_results"]
        dt = row["execution_time"]
        err_desc = row["error_description"]

        # parse the vector from something like "[1, 2, 1]"
        try:
            tests = eval(test_str)  # or safer parse
        except:
            tests = []

        full_history.append({
            "table_name": tname,
            "execution_time": dt,
            "tests": tests,
            "error_description": err_desc,
        })

        if tname not in latest_map:
            latest_map[tname] = {
                "execution_time": dt,
                "tests": tests,
                "error_description": err_desc,
            }

    # 4) Build lists for the selected table
    #    We'll assume we want 3 test dimensions (Exhaustivité, Pertinence, Exactitude),
    #    so we only chart rows that have exactly 3 entries in 'tests'.
    dimension_times = []
    dimension_exhaust = []
    dimension_pertinence = []
    dimension_exactitude = []

    # We'll reverse() so we go ascending in time
    for row in reversed(full_history):
        if row["table_name"] == table_requested and len(row["tests"]) == 3:
            dimension_times.append(row["execution_time"])
            dimension_exhaust.append(row["tests"][0])       # index 0 = Exhaustivité
            dimension_pertinence.append(row["tests"][1])    # index 1 = Pertinence
            dimension_exactitude.append(row["tests"][2])    # index 2 = Exactitude

    # 5) Convert to JSON
    times_json = json.dumps(dimension_times)
    exhaust_json = json.dumps(dimension_exhaust)
    pertinence_json = json.dumps(dimension_pertinence)
    exactitude_json = json.dumps(dimension_exactitude)

    # 6) Convert 'latest_map' to a list for the "latest results" table
    latest_list = []
    for tbl_name, info in latest_map.items():
        latest_list.append({
            "table_name": tbl_name,
            "execution_time": info["execution_time"],
            "tests": info["tests"],
            "error_description": info["error_description"],
        })

    context = {
        "table_requested": table_requested,  # so we know which option to highlight
        "latest_results": latest_list,
        "dimension_times_json": times_json,
        "dimension_exhaust_json": exhaust_json,
        "dimension_pertinence_json": pertinence_json,
        "dimension_exactitude_json": exactitude_json,
    }
    return render(request, "dashboard/data_quality_dashboard.html", context)


# ─── API: /admin/data-quality-data/ ────────────────────────────────
@api_view(["GET"])
@supabase_admin_required
def data_quality_api(request):
    """
    JSON twin of data_quality_dashboard().
    GET /admin/data-quality-data/?table_name=infos_especes
    """
    table_name = request.GET.get("table_name", "infos_especes")

    # Pull all logs, same query as before
    res = client_for_request(request).table("data_quality_log") \
          .select("*").order("execution_time", desc=True).execute()
    logs = res.data or []

    if not logs:
        return Response({"latest_rows": [], "times": []})   # empty payload

    # ─── latest rows (one per table) ───────────────────────
    latest_map = {}
    for row in logs:
        tbl = row["table_name"]
        latest_map.setdefault(tbl, {
            "table_name": tbl,
            "execution_time": row["execution_time"],
            "tests":   row["test_results"],
            "error_description": row["error_description"],
        })

    latest_rows = list(latest_map.values())

    # ─── trend vectors for the requested table ─────────────
    times, exa, per, exa2 = [], [], [], []
    for row in reversed(logs):                # ascending time
        if row["table_name"] == table_name:
            try:
                vec = eval(row["test_results"])     # [Exh, Per, Exa]
            except Exception:
                vec = []
            if len(vec) == 3:
                times.append(row["execution_time"])
                exa.append(vec[0]);  per.append(vec[1]);  exa2.append(vec[2])

    return Response({
        "latest_rows": latest_rows,
        "times":       times,
        "exhaust":     exa,
        "pertinence":  per,
        "exactitude":  exa2,
    })


@csrf_exempt
def run_etl_via_github(request):
    """
    A simple view that triggers a GitHub Actions workflow_dispatch.
    """
    if request.method == "POST":
        token = os.getenv("GITHUB_TOKEN", None)
        if not token:
            return JsonResponse({"error": "No GITHUB_TOKEN found on server."}, status=500)

        owner = "Ozomozyan"
        repo = "MSPR_ETL"
        workflow_id = "main.yml" 
        # or you can use the numerical workflow ID or the file name in .github/workflows

        # The endpoint:
        url = f"https://api.github.com/repos/{owner}/{repo}/actions/workflows/{workflow_id}/dispatches"

        # The body must specify a "ref" that points to a branch or tag
        # Optionally pass "inputs" if your workflow is defined with them
        payload = {
            "ref": "main",            # or 'master' or whichever branch
        }

        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}"
        }

        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 204:
            # 204 means "No Content" but success from GitHub
            return JsonResponse({"message": "ETL workflow triggered successfully."})
        else:
            return JsonResponse({
                "error": "Failed to trigger workflow.",
                "status": response.status_code,
                "response": response.text
            }, status=500)
    else:
        return JsonResponse({"error": "Only POST method allowed"}, status=405)


@api_view(["POST"])
@supabase_admin_required
def run_training(request):
    # default values if the admin doesn’t fill the form
    batch_size = int(request.data.get("batch_size") or 32)
    epochs     = int(request.data.get("epochs") or 10)

    accepted = start_training(batch_size, epochs)
    if not accepted:
        return Response({"detail": "❗️Another training job is already running"},
                        status=409)         # Conflict
    return Response({"detail": "Training job started"},
                    status=202)             # Accepted
    
    
    

# ─── API: /admin-dashboard/stats-api/ ────────────────────────────────

@api_view(["GET"])
@supabase_admin_required          # ← only admins can hit this route
def admin_stats_api(request):
    """
    Pure-JSON version of admin_dashboard().
    React calls this to obtain all the numbers for charts + table.
    """
    # 1) Pull every row from the materialised view
    res_obj = (
        settings.SUPABASE_CLIENT
        .table("species_summary_v")
        .select("*")
        .execute()
    )
    data = res_obj.data or []
    if not data:
        return Response({"detail": "No data"}, status=404)

    # 2) Aggregate exactly the same way the HTML template did
    species_map   = {}
    family_counter, region_counter = Counter(), Counter()

    for row in data:
        sid = row["species_id"]
        bucket = row.get("region_bucket") or row.get("region") or ""

        species_map.setdefault(sid, {
            "species_id":  sid,
            "species_name":row["species_name"],
            "family":      row["family"],
            "taille":      row["taille"],
            "description": row["description"],
            "total_images":row["total_images"],
            "completeness_percentage": row["completeness_percentage"],
            "region_set":  set()
        })

        if bucket:
            species_map[sid]["region_set"].add(bucket)

    # 3) Flatten for the table and chart arrays
    table_rows      = []
    images_count    = []
    completeness_pc = []

    for info in species_map.values():
        table_rows.append({
            **info,
            "region": ", ".join(sorted(info["region_set"])),
        })
        images_count.append(info["total_images"])
        completeness_pc.append(info["completeness_percentage"])

        family_counter[info["family"]] += 1
        for r in info["region_set"]:
            region_counter[r] += 1

    # 4) Ship JSON
    return Response({
        "rows":            table_rows,
        "species_names":   [r["species_name"] for r in table_rows],
        "images_count":    images_count,
        "family_labels":   list(family_counter.keys()),
        "family_values":   list(family_counter.values()),
        "completeness":    completeness_pc,
        "region_labels":   list(region_counter.keys()),
        "region_values":   list(region_counter.values()),
    })
    
    
    
# ──────────────────────────────────────────────────────────
@supabase_login_required          # normal user, not the admin-only decorator
def user_dashboard(request):
    """
    Show the current user:
      • recent predictions (table)
      • pie   – species distribution
      • line  – predictions over time
    """

    # (1) Who am I?
    user_id = request.supabase_user["sub"]        # your middleware sets this
    if not user_id:
        return redirect("/login/")

    sb = client_for_request(request)
    try:
        res = (
            sb.table("predictions")
              .select("*")
              .eq("user_id", user_id)
              .order("created_at", desc=True)
              .limit(200)               # enough for the charts
              .execute()
        )
        rows = res.data or []
    except Exception as e:
        return render(request, "dashboard/user_dashboard.html",
                      {"error": f"Supabase query failed: {e}"})

    # ---------- build datasets ----------
    # table (last 25)
    table_rows = rows[:25]

    # pie – how many times each species was predicted
    species_counter = {}
    for r in rows:
        label = r["predicted_species"]
        species_counter[label] = species_counter.get(label, 0) + 1
    pie_labels  = list(species_counter.keys())
    pie_values  = list(species_counter.values())

    # line – # predictions per day
    daily_counter = {}
    for r in rows:
        day = r["created_at"][:10]            # YYYY-MM-DD
        daily_counter[day] = daily_counter.get(day, 0) + 1
    line_labels = sorted(daily_counter.keys())
    line_values = [daily_counter[d] for d in line_labels]

    context = {
        "table_rows"     : table_rows,
        "pie_labels_json": json.dumps(pie_labels),
        "pie_values_json": json.dumps(pie_values),
        "line_labels_json": json.dumps(line_labels),
        "line_values_json": json.dumps(line_values),
    }
    return render(request, "dashboard/user_dashboard.html", context)

@csrf_exempt
@api_view(["GET"])
def user_stats_api(request):
    """
    JSON endpoint for React to fetch exactly the same data
    your old user_dashboard template used to render.
    Returns:
      {
        "table_rows": [...],           # last 25 predictions
        "pie_labels": [...],
        "pie_values": [...],
        "line_labels": [...],
        "line_values": [...],
      }
    """

    # 1) Ensure the middleware decoded a valid Supabase JWT
    if not hasattr(request, "supabase_user"):
        return JsonResponse({"detail": "Not authenticated."}, status=401)

    # 2) Pull the user ID ("sub" claim) directly from the verified token
    user_id = request.supabase_user.get("sub")
    if not user_id:
        return JsonResponse({"detail": "Not authenticated."}, status=401)

    # 3) Use the Supabase client from settings
    sb = client_for_request(request)

    try:
        res = (
            sb.table("predictions")
              .select("*")
              .eq("user_id", user_id)
              .order("created_at", desc=True)
              .limit(200)
              .execute()
        )
        rows = res.data or []
    except Exception as e:
        return JsonResponse({"detail": f"Supabase query failed: {e}"}, status=500)

    # Build the “table_rows” (latest 25)
    table_rows = rows[:25]

    # Build the pie‐chart data (species distribution)
    species_counter = {}
    for r in rows:
        label = r.get("predicted_species")
        if label:
            species_counter[label] = species_counter.get(label, 0) + 1
    pie_labels = list(species_counter.keys())
    pie_values = list(species_counter.values())

    # Build the line‐chart data (# predictions per day)
    daily_counter = {}
    for r in rows:
        created_at = r.get("created_at", "")
        day = created_at[:10]  # “YYYY-MM-DD”
        if day:
            daily_counter[day] = daily_counter.get(day, 0) + 1
    line_labels = sorted(daily_counter.keys())
    line_values = [daily_counter[d] for d in line_labels]

    return JsonResponse({
        "table_rows": table_rows,
        "pie_labels": pie_labels,
        "pie_values": pie_values,
        "line_labels": line_labels,
        "line_values": line_values,
    })

# ──────────────────────────────────────────────────────────
@supabase_login_required
def user_species_summary(request):
    """
    Same aggregation logic as admin_dashboard but read-only
    and open to all authenticated users.
    """
    try:
        res_obj = (
            client_for_request(request)
            .table("species_summary_v")
            .select("*")
            .execute()
        )
        data = res_obj.data or []
    except Exception as e:
        return render(
            request,
            "dashboard/user_species_summary.html",
            {"error": f"Supabase query failed: {e}"}
        )

    if not data:
        return render(
            request,
            "dashboard/user_species_summary.html",
            {"error": "No data returned from 'species_summary_v'."}
        )

    # ────── Deduplicate & merge region buckets ──────
    species_map = {}
    for row in data:
        sid = row["species_id"]
        species_map.setdefault(sid, {
            "species_id": sid,
            "species_name": row["species_name"],
            "family": row["family"],
            "taille": row["taille"],
            "description": row["description"],
            "total_images": row["total_images"],
            "completeness_percentage": row["completeness_percentage"],
            "region_set": set()
        })
        bucket = row.get("region_bucket") or row.get("region") or ""
        if bucket:
            species_map[sid]["region_set"].add(bucket)

    # ────── Build the table and aggregation counters ──────
    unique_species = []
    family_counter, region_counter = Counter(), Counter()

    for s in species_map.values():
        unique_species.append({
            **s,
            "region": ", ".join(sorted(s["region_set"]))
        })
        family_counter[s["family"]] += 1
        for r in s["region_set"]:
            region_counter[r] += 1

    # ────── Prepare context (only family & region) ──────
    context = {
        "species_summary": unique_species,
        "family_labels_json": json.dumps(list(family_counter.keys())),
        "family_values_json": json.dumps(list(family_counter.values())),
        "region_labels_json": json.dumps(list(region_counter.keys())),
        "region_values_json": json.dumps(list(region_counter.values())),
    }
    return render(request, "dashboard/user_species_summary.html", context)

@api_view(["GET"])
@supabase_login_required
def species_summary_api(request):
    """
    JSON version of the species-summary endpoint.
    GET /user-dashboard/species-summary-data/
    Returns:
      {
        "rows":            [...],
        "family_labels":   [...],
        "family_values":   [...],
        "region_labels":   [...],
        "region_values":   [...]
      }
    """
    # ----- fetch data exactly like the template view -----
    res = (
        client_for_request(request)
        .table("species_summary_v")
        .select("*")
        .execute()
    )
    data = res.data or []

    # ----- dedupe + aggregation (identical logic) --------
    species_map, family_counter, region_counter = {}, Counter(), Counter()
    for row in data:
        sid = row["species_id"]
        bucket = row.get("region_bucket") or row.get("region") or ""
        species_map.setdefault(sid, {
            "species_id": sid,
            "species_name": row["species_name"],
            "family": row["family"],
            "region_set": set()
        })
        if bucket:
            species_map[sid]["region_set"].add(bucket)

    rows = []
    for info in species_map.values():
        rows.append({
            **info,
            "region": ", ".join(sorted(info["region_set"]))
        })
        family_counter[info["family"]] += 1
        for r in info["region_set"]:
            region_counter[r] += 1

    return Response({
        "rows":            rows,
        "family_labels":   list(family_counter.keys()),
        "family_values":   list(family_counter.values()),
        "region_labels":   list(region_counter.keys()),
        "region_values":   list(region_counter.values()),
    })

@supabase_login_required
@cache_page(60)              # 1-minute cache; map data doesn’t change often
def user_predictions_map(request):
    """
    World map with every prediction's lat/lon + species label.
    """
    try:
        res = (
            client_for_request(request) 
            .table("prediction_locations_v")
            .select("species_name,lat,lon")
            .execute()
        )
        # cast lat/lon to float to avoid JS "1E-5" strings
        points = [
            {"species_name": p["species_name"],
             "lat": float(p["lat"]), "lon": float(p["lon"])}
            for p in (res.data or [])
        ]
    except Exception as e:
        return render(
            request, "dashboard/user_map.html",
            {"error": f"Supabase query failed: {e}"}
        )

    return render(request, "dashboard/user_map.html",
                  {"points_json": json.dumps(points)})
    
    
    
    
@require_GET
@supabase_login_required
def species_info_api(request):
    """
    GET /api/species-info?name=Red%20Fox
    or   /api/species-info?id=123
    Returns JSON with the columns of infos_especes.
    """
    name = request.GET.get("name")
    sid  = request.GET.get("id")

    if not name and not sid:
        return JsonResponse({"detail": "name or id required"}, status=400)

    sb = client_for_request(request) 
    SPECIES_COL = 'Espèce'              # ← EXACT column name in Supabase

    qry = sb.table("infos_especes").select("*").limit(1)
    if sid:
        qry = qry.eq("species_id", sid)
    else:
        # For case-insensitive match you can use .ilike()
        # If the accent causes trouble, strip it or lowercase both sides.
        qry = qry.ilike(SPECIES_COL, name)

    res = qry.single().execute()
    if not res.data:
        return JsonResponse({"detail": "Not found"}, status=404)

    return JsonResponse(res.data)




@api_view(["GET"])
@supabase_admin_required
def logs_api(request):
    """
    GET /admin-dashboard/server-logs/?lines=300  (default 200)
        ?follow=1 → server-sent plain-text stream

    Always returns *plain text*, never JSON.
    """
    lines  = int(request.GET.get("lines", 200))
    follow = request.GET.get("follow") in ("1", "true")

    if not os.path.isfile(LOG_FILE):
        return Response(
            f"⚠️ log file {LOG_FILE} not found",
            status=500, content_type="text/plain"
        )

    # helper: last N lines without reading the whole file
    def tail(fp, n):
        dq = deque(fp, maxlen=n)
        return "".join(dq)

    # ── follow mode ─────────────────────────────────────────────
    if follow:
        def stream():
            with open(LOG_FILE, "r") as fp:
                fp.seek(0, os.SEEK_END)          # jump to EOF
                while True:
                    chunk = fp.readline()
                    if chunk:
                        yield chunk
                    else:
                        time.sleep(0.3)
        return StreamingHttpResponse(stream(), content_type="text/plain")

    # ── single-shot ────────────────────────────────────────────
    with open(LOG_FILE, "r") as fp:
        payload = tail(fp, lines)
    return Response(payload, content_type="text/plain")
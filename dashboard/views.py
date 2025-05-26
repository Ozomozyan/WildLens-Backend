# dashboard/views.py

import os
import requests
from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse
from django.conf import settings
from wildlens_backend.auth_decorators import supabase_admin_required
from django.views.decorators.csrf import csrf_exempt
from wildlens_backend.local_runner import start_training

import json
from collections import Counter

# 🔧 PATCH ❶ – put near the other imports at the top
from rest_framework.decorators import api_view
from rest_framework.response import Response


# ─── GitHub / workflow settings ────────────────────────────────────────────
GITHUB_TOKEN  = os.getenv("GITHUB_TOKEN", None)           # same var you already use
GITHUB_OWNER  = os.getenv("GITHUB_OWNER", "Ozomozyan")    # change if needed
GITHUB_REPO   = os.getenv("GITHUB_REPO",  "MSPR_ETL")  # this project’s repo
TRAIN_WORKFLOW = os.getenv("TRAIN_WORKFLOW", "MODEL_TRAIN.yml")


def login_view(request):
    if request.method == "GET":
        return render(request, "accounts/login.html")

    email = request.POST.get("email")
    password = request.POST.get("password")

    # 1. Make the POST request to Supabase /auth/v1/token?grant_type=password
    SUPABASE_URL = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
    endpoint = f"{SUPABASE_URL}/auth/v1/token?grant_type=password"
    headers = {
        "apikey": SUPABASE_KEY,
        "Content-Type": "application/json",
    }
    resp = requests.post(endpoint, json={"email": email, "password": password}, headers=headers)
    if resp.status_code != 200:
        return HttpResponse("Login failed. Check your credentials.", status=401)

    data = resp.json()
    token = data.get("access_token")
    if not token:
        return HttpResponse("No token returned by Supabase.", status=401)

    # 2. Store token in the session
    request.session["supabase_token"] = token

    # 3. Redirect to admin dashboard
    return redirect("/admin-dashboard/")


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
        res = settings.SUPABASE_CLIENT.table("data_quality_log") \
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
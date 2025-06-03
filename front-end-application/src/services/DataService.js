// src/services/DataService.js
import api from "./api.js";

/**
 * GET /user-dashboard/user-stats/
 * → logs the raw payload, then returns it.
 */
export const getDashboardStats = () =>
  api
    .get("/user-dashboard/user-stats/")
    .then((res) => {
      console.log("🔍  /user-dashboard/user-stats/ →", res.data);
      return res.data;         // keep the original behaviour
    });

export const getUserList = () =>
  api
    .get("/users")
    .then((res) => {
      console.log("🔍  /users →", res.data);
      return res.data;
    });
// src/services/DataService.js
export const getSpeciesSummary = () =>
  api.get("/user-dashboard/species-summary-data/").then(r => r.data);


export const getSpeciesInfo = (name) =>
  api
    .get(`/api/species-info/?name=${encodeURIComponent(name)}`)
    .then((r) => r.data);



export const listPredictions = () =>
  api.get("/api/predictions").then((r) => r.data);

export const createPrediction = (formData) =>
  api.post("/api/predictions", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });



// Fetch every prediction’s lat / lon + species label
export const listPredictionLocations = () =>
  api.get("/api/prediction-locations")   // ← endpoint already exists
     .then(r => r.data);


export async function getAdminStats(token) {
  const res = await api.get("/admin-dashboard/data/", {
    headers: { Authorization: `Bearer ${token}` },
  });
  return res.data;
}



// src/services/DataService.js
export async function getQualityStats(tableName, token) {
  const res = await api.get(
    `/admin-dashboard/data-quality-data/`,
    {
      params:     { table_name: tableName },
      headers:    { Authorization: `Bearer ${token}` },
      withCredentials: true,
    }
  );
  return res.data;     // Axios already parses JSON
}




export async function fetchLogs({ lines = 200, token }) {
  const res = await api.get("/admin-dashboard/server-logs/", {
    params:  { lines },
    headers: { Authorization: `Bearer ${token}` },
    responseType: "text",
    withCredentials: true,
  });
  return res.data;
}


// --- ETL -----------------------------------------------------------
export async function triggerETL(token) {
  const res = await api.post(
    "/admin-dashboard/run-etl-github/",
    {},                                       // ← empty body
    {
      headers:        { Authorization: `Bearer ${token}` },
      withCredentials:true,                   // keep sessionid cookie
    }
  );
  return res.data;                            // → { message }  or { error … }
}

// --- Train model ---------------------------------------------------
export async function triggerTraining({ batch, epochs, token }) {
  const res = await api.post(
    "/admin-dashboard/run-training/",
    { batch_size: batch, epochs },            // JSON body the view expects
    {
      headers:        { Authorization: `Bearer ${token}` },
      withCredentials:true,
    }
  );
  return res.data;                            // → { detail }
}


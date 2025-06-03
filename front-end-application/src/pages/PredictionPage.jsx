// ─── src/pages/PredictionPage.jsx ─────────────────────────────────────────
import { useEffect, useRef, useState } from "react";
import toast, { Toaster } from "react-hot-toast";

import {
  listPredictions,
  createPrediction,
  getSpeciesInfo,
} from "../services/DataService.js";

import UsageChart from "../components/UsageChart.jsx";
import Navbar     from "../components/Navbar.jsx";

/* helper to turn ("Fox",0.83) → "Fox" */
const extractLabel = (predStr) => {
  const m = predStr.match(/\("?(.*?)"?,/);
  return m ? m[1] : predStr;
};

export default function PredictionPage() {
  /* ── state ─────────────────────────────────────────────────────────── */
  const [preds, setPreds]           = useState(null);
  const [error, setError]           = useState(null);
  const [uploading, setUploading]   = useState(false);

  const [coordsOK, setCoordsOK]     = useState(false);
  const [coordsErr, setCoordsErr]   = useState(false);

  const [modal, setModal]           = useState(null);          // {label, info} | null

  // Preview state for the chosen file
  const [previewURL, setPreviewURL] = useState(null);
  const [fileName, setFileName]     = useState("");

  /* ── refs ──────────────────────────────────────────────────────────── */
  const fInput   = useRef(null);
  const locInput = useRef(null);
  const noteInput= useRef(null);
  const latInput = useRef(null);
  const lonInput = useRef(null);

  /* ── first geolocation attempt ─────────────────────────────────────── */
  useEffect(() => { fetchCoords(); }, []);
  const fetchCoords = () => {
    setCoordsErr(false);
    navigator.geolocation?.getCurrentPosition(
      (pos) => {
        latInput.current.value = pos.coords.latitude;
        lonInput.current.value = pos.coords.longitude;
        setCoordsOK(true);
      },
      () => setCoordsErr(true),
      { enableHighAccuracy:false, timeout:8000 }
    );
  };

  /* ── initial predictions list ──────────────────────────────────────── */
  useEffect(() => {
    listPredictions()
      .then(setPreds)
      .catch(() => setError("Could not load predictions."));
  }, []);

  /* ── chart helpers ─────────────────────────────────────────────────── */
  const pieData = (rows=[]) => {
    const c = {};
    rows.forEach(r => {
      const label = extractLabel(r.predicted_species);
      c[label] = (c[label]||0) + 1;
    });
    return { labels: Object.keys(c), values: Object.values(c) };
  };
  const lineData = (rows=[]) => {
    const d = {};
    rows.forEach(r => {
      const day = r.created_at.slice(0,10);
      d[day] = (d[day]||0) + 1;
    });
    const labels = Object.keys(d).sort();
    return { labels, values: labels.map(x => d[x]) };
  };

  /* ── handle file‐input change: show preview & filename ──────────────── */
  const handleFileChange = (e) => {
    const file = e.target.files[0];
    if (!file) {
      setPreviewURL(null);
      setFileName("");
      return;
    }
    setFileName(file.name);

    // Create a temporary object URL for preview
    const url = URL.createObjectURL(file);
    setPreviewURL(url);
  };

  /* ── submit ────────────────────────────────────────────────────────── */
  async function handleSubmit(e){
    e.preventDefault();
    setError(null);

    const file = fInput.current.files[0];
    if(!file) return setError("Pick a photo first.");
    if(!latInput.current.value || !lonInput.current.value){
      return setError("Waiting for GPS coordinates …");
    }

    const fd = new FormData();
    fd.append("image", file);
    fd.append("location_text", locInput.current.value);
    fd.append("notes", noteInput.current.value);
    fd.append("lat", latInput.current.value);
    fd.append("lon", lonInput.current.value);

    try {
      setUploading(true);
      const { data } = await createPrediction(fd);

      // Extract label from whatever the API returned
      const label = extractLabel(data.prediction);
      toast.success(`Looks like a ${label}!`);

      // Build the “new row” exactly matching the API’s shape as best as possible.
      // We’ll normalize field names: some APIs may use “location” instead of “location_text”, etc.
      const newRow = {
        created_at: new Date().toISOString(),
        predicted_species: label,
        // if the backend uses “location_text”:
        location_text: locInput.current.value || "",
        // or fallback if your API returns “location”:
        location: locInput.current.value || "",
        notes: noteInput.current.value || "",
      };

      // Optimistically add it to the top of the table
      setPreds(prev => [newRow, ...(prev||[])]);

      // Try to fetch extra species info for the modal
      let info = data.species_info;
      if (!info?.Espèce) {
        try { info = await getSpeciesInfo(label); }
        catch { /* ignore */ }
      }
      setModal({ label, info });

      // Reset form and preview
      e.target.reset();
      fInput.current.value = "";
      setPreviewURL(null);
      setFileName("");
    } catch(err) {
      const msg = err.response?.data?.detail || "Prediction failed.";
      setError(msg);
    } finally {
      setUploading(false);
    }
  }

  /* ── early returns ─────────────────────────────────────────────────── */
  if (error)       return <p className="p-4 text-red-600">{error}</p>;
  if (preds === null) return <p className="p-4">Loading…</p>;

  const pie  = pieData(preds);
  const line = lineData(preds);

  /* ── UI ────────────────────────────────────────────────────────────── */
  return (
    <>
      <Navbar />
      <Toaster position="top-center" />

      {/* ─── MODAL ─────────────────────────────────────────────────────── */}
      {modal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl">
            <h2 className="mb-3 text-2xl font-bold text-primary">{modal.label}</h2>
            {modal.info ? (
              <div className="space-y-1 text-sm">
                <p><strong>Family:</strong> {modal.info.Famille}</p>
                <p><strong>Habitat:</strong> {modal.info.Habitat || "–"}</p>
                <p><strong>Region:</strong>  {modal.info.Région  || "–"}</p>
                <p><strong>Fun fact:</strong> {modal.info.Fun_fact || "–"}</p>
              </div>
            ) : (
              <p>No extra information available.</p>
            )}
            <button
              onClick={() => setModal(null)}
              className="btn-primary mt-4"
            >
              Close
            </button>
          </div>
        </div>
      )}

      {/* ─── MAIN CONTENT ───────────────────────────────────────────────── */}
      <div className="mx-auto max-w-4xl space-y-8 p-4 pb-12 md:p-6">
        <h1 className="text-2xl font-bold">Footprint Scanner</h1>

        {/* ── UPLOAD FORM ──────────────────────────────────────────────────── */}
        <form
          onSubmit={handleSubmit}
          className="rounded-xl bg-white p-6 shadow space-y-4"
        >
          {/* camera / gallery button */}
          <label className="group flex w-full flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed border-primary bg-primary/5 py-8 text-primary/90 hover:bg-primary/10">
            <svg xmlns="http://www.w3.org/2000/svg" className="h-10 w-10" fill="none"
                 viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round"
                    d="M3 7h2l2-3h10l2 3h2a2 2 0 012 2v10a2 2 0 01-2 2H3a2 2 0 01-2-2V9a2 2 0 012-2z" />
              <circle cx="12" cy="13" r="4" />
            </svg>
            <span className="text-sm font-medium group-hover:text-primary">
              {fileName ? fileName : "Tap to take / choose photo"}
            </span>
            <input
              ref={fInput}
              type="file"
              accept="image/*"
              capture="environment"
              className="hidden"
              onChange={handleFileChange}
              required
            />
          </label>

          {/* show thumbnail preview if selected */}
          {previewURL && (
            <div className="flex justify-center">
              <img
                src={previewURL}
                alt="Preview"
                className="h-40 w-auto rounded-lg border"
              />
            </div>
          )}

          {/* optional extras */}
          <input
            ref={locInput}
            type="text"
            placeholder="Location (optional)"
            className="w-full rounded border p-2 text-sm"
          />
          <input
            ref={noteInput}
            type="text"
            placeholder="Notes"
            className="w-full rounded border p-2 text-sm"
          />

          {/* coords status */}
          {!coordsOK && !coordsErr && (
            <p className="text-sm italic text-gray-500">
              Fetching GPS coordinates&hellip;
            </p>
          )}
          {coordsErr && (
            <div className="rounded border border-red-400 bg-red-50 p-3 text-sm">
              Couldn’t fetch your location.{" "}
              <button
                onClick={fetchCoords}
                type="button"
                className="ml-1 underline"
              >
                Retry
              </button>{" "}
              or fill manually:
              <div className="mt-2 flex gap-2">
                <input
                  type="number"
                  step="any"
                  placeholder="Lat"
                  ref={latInput}
                  className="flex-1 rounded border p-1"
                />
                <input
                  type="number"
                  step="any"
                  placeholder="Lon"
                  ref={lonInput}
                  className="flex-1 rounded border p-1"
                />
              </div>
            </div>
          )}

          {/* hidden coords (auto) */}
          <input type="hidden" ref={latInput}/>
          <input type="hidden" ref={lonInput}/>

          <button
            disabled={uploading || (!coordsOK && !coordsErr)}
            className="btn-primary flex items-center justify-center gap-2 disabled:opacity-50 w-full md:w-auto"
          >
            {uploading && (
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
            )}
            Predict
          </button>
        </form>

        {/* ── CHARTS (stacked on mobile, two columns on md+) ─────────────── */}
        <div className="grid gap-8 md:grid-cols-2">
          <div className="rounded-xl bg-white p-4 shadow">
            <UsageChart type="pie" data={pie} />
          </div>
          <div className="rounded-xl bg-white p-4 shadow">
            <UsageChart
              type="line"
              data={line}
              options={{ maintainAspectRatio:false, scales:{y:{beginAtZero:true}} }}
            />
          </div>
        </div>

        {/* ── TABLE ───────────────────────────────────────────────────────── */}
        <div className="rounded-xl bg-white p-4 shadow">
          <h2 className="mb-2 text-xl font-semibold">Recent Predictions</h2>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[560px] border-collapse text-sm">
              <thead className="bg-gray-100">
                <tr>
                  <th className="p-2 text-left">Date</th>
                  <th className="p-2 text-left">Species</th>
                  <th className="p-2 text-left">Location</th>
                  <th className="p-2 text-left">Notes</th>
                </tr>
              </thead>
              <tbody>
                {preds.length === 0 && (
                  <tr>
                    <td
                      colSpan="4"
                      className="p-4 text-center text-gray-500"
                    >
                      No predictions yet.
                    </td>
                  </tr>
                )}
                {preds.map((r, i) => (
                  <tr key={i} className="border-t hover:bg-gray-50">
                    <td className="p-2">{r.created_at.slice(0,10)}</td>
                    <td className="p-2">{extractLabel(r.predicted_species)}</td>
                    {/* some APIs name it “location_text” or simply “location” */}
                    <td className="p-2">
                      {r.location_text ?? r.location ?? "–"}
                    </td>
                    <td className="p-2">{r.notes || "–"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </>
  );
}

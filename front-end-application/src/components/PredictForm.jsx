import { useEffect, useRef, useState } from "react";
import {
  listPredictions,
  createPrediction,
} from "../services/DataService.js";
import UsageChart from "../components/UsageChart.jsx";
import Navbar from "../components/Navbar.jsx";

export default function PredictPage() {
  /* ---------- state ---------- */
  const [preds, setPreds]           = useState(null);
  const [error, setError]           = useState(null);
  const [uploading, setUploading]   = useState(false);

  /* refs for form fields */
  const fileRef       = useRef(null);
  const locTextRef    = useRef(null);
  const notesRef      = useRef(null);
  const latRef        = useRef(null);
  const lonRef        = useRef(null);

  /* ---------- geolocation once ---------- */
  useEffect(() => {
    navigator.geolocation?.getCurrentPosition(
      (pos) => {
        if (latRef.current) {
          latRef.current.value = pos.coords.latitude;
          lonRef.current.value = pos.coords.longitude;
        }
      },
      console.warn
    );
  }, []);

  /* ---------- initial fetch ---------- */
  useEffect(() => {
    listPredictions()
      .then(setPreds)
      .catch((err) => {
        console.error(err);
        setError("Could not load predictions.");
      });
  }, []);

  /* ---------- derived chart data ---------- */
  function pieData(rows) {
    const counter = {};
    rows.forEach((r) => {
      counter[r.predicted_species] =
        (counter[r.predicted_species] || 0) + 1;
    });
    return { labels: Object.keys(counter), values: Object.values(counter) };
  }

  function lineData(rows) {
    const daily = {};
    rows.forEach((r) => {
      const day = r.created_at.slice(0, 10);
      daily[day] = (daily[day] || 0) + 1;
    });
    const labels = Object.keys(daily).sort();
    return { labels, values: labels.map((d) => daily[d]) };
  }

  /* ---------- submit handler ---------- */
  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);

    const file = fileRef.current?.files[0];
    if (!file) return setError("Please pick a photo.");

    const fd = new FormData();
    fd.append("image", file);
    fd.append("location_text", locTextRef.current.value);
    fd.append("notes", notesRef.current.value);
    fd.append("lat", latRef.current.value);
    fd.append("lon", lonRef.current.value);

    try {
      setUploading(true);
      const { data } = await createPrediction(fd);   // POST /api/predictions/
      const newRow = {
        created_at: new Date().toISOString(),
        predicted_species: data.prediction,
        location_text: locTextRef.current.value,
        notes: notesRef.current.value,
      };
      setPreds((prev) => [newRow, ...(prev || [])]);

      // clear inputs (keep geo)
      e.target.reset();
    } catch (err) {
      console.error(err);
      const msg =
        err.response?.data?.detail || "Prediction failed. Try again.";
      setError(msg);
    } finally {
      setUploading(false);
    }
  }

  /* ---------- render ---------- */
  if (error)      return <p className="p-4 text-red-500">{error}</p>;
  if (preds === null)
    return <p className="p-4">Loading previous predictions…</p>;

  const pie    = pieData(preds);
  const line   = lineData(preds);

  return (
    <>
      <Navbar />
      <div className="max-w-4xl mx-auto p-6">
        <h1 className="text-2xl font-bold mb-6">Make a Prediction</h1>

        {/* upload form */}
        <form
          onSubmit={handleSubmit}
          className="mb-8 p-4 border rounded bg-gray-50 space-y-3"
        >
          {error && <p className="text-red-500">{error}</p>}
          <input type="file" ref={fileRef} required className="block" />

          <input
            ref={locTextRef}
            type="text"
            placeholder="Location (optional)"
            className="border p-1 w-full"
          />
          <input
            ref={notesRef}
            type="text"
            placeholder="Notes"
            className="border p-1 w-full"
          />

          {/* hidden geolocation */}
          <input type="hidden" ref={latRef} />
          <input type="hidden" ref={lonRef} />

          <button
            disabled={uploading}
            className="bg-blue-600 text-white px-4 py-2 rounded disabled:opacity-50"
          >
            {uploading ? "Predicting…" : "Predict"}
          </button>
        </form>

        {/* charts */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
          <UsageChart type="pie" data={pie} />
          <UsageChart
            type="line"
            data={line}
            options={{ scales: { y: { beginAtZero: true } } }}
          />
        </div>

        {/* table */}
        <h2 className="text-xl font-semibold mb-2">Recent Predictions</h2>
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="bg-gray-100">
              <th className="p-2">Date</th>
              <th className="p-2">Species</th>
              <th className="p-2">Location</th>
              <th className="p-2">Notes</th>
            </tr>
          </thead>
          <tbody>
            {preds.length === 0 && (
              <tr>
                <td colSpan="4" className="p-4 text-center text-gray-500">
                  No predictions yet.
                </td>
              </tr>
            )}
            {preds.map((r, idx) => (
              <tr key={idx} className="border-t">
                <td className="p-2">{r.created_at.slice(0, 10)}</td>
                <td className="p-2">{r.predicted_species}</td>
                <td className="p-2">{r.location_text || "–"}</td>
                <td className="p-2">{r.notes || "–"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

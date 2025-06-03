/* ─── src/pages/DataQualityPage.jsx ─────────────────────────────── */
import { useEffect, useState } from "react";
import {
  Chart as ChartJS, LineElement, PointElement,
  CategoryScale, LinearScale, Tooltip, Legend,
} from "chart.js";
import { Line }   from "react-chartjs-2";
import Navbar     from "../components/Navbar.jsx";
import { useAuth } from "../context/AuthContext.jsx";
import { getQualityStats } from "../services/DataService.js";

ChartJS.register(LineElement, PointElement,
                 CategoryScale, LinearScale,
                 Tooltip, Legend);

const TABLES = ["infos_especes", "footprint_images"];   // extend if needed

export default function DataQualityPage() {
  const { user }   = useAuth();
  const token      = user?.token ?? localStorage.getItem("token");

  const [tableName, setTableName] = useState(TABLES[0]);
  const [stats,     setStats]     = useState(null);
  const [error,     setError]     = useState(null);

  /* ─── fetch every time tableName changes ─── */
  useEffect(() => {
    if (!token) return;                   // still logging-in
    setError(null);
    setStats(null);
    getQualityStats(tableName, token)
      .then((data) => {
        console.debug("QC-stats for", tableName, data); // 👀
        setStats(data);
      })
      .catch((e) => {
        console.error(e);
        setError("Failed to load data-quality information.");
      });
  }, [tableName, token]);

  /* ─── guards ─── */
  if (error)  return <p className="p-6 text-red-500">{error}</p>;
  if (!stats) return <p className="p-6">Loading…</p>;

  /* safe defaults – never let undefined through */
  const latestRows   = stats.latest_rows   ?? [];
  const times        = stats.times         ?? [];
  const exhaust      = stats.exhaust       ?? [];
  const pertinence   = stats.pertinence    ?? [];
  const exactitude   = stats.exactitude    ?? [];

  /* line-chart dataset */
  const lineData = {
    labels: times,
    datasets: [
      { label: "Exhaustivité", borderColor: "blue",  data: exhaust    },
      { label: "Pertinence",   borderColor: "green", data: pertinence },
      { label: "Exactitude",   borderColor: "red",   data: exactitude },
    ],
  };
  const lineOpts = {
    scales: { y: { beginAtZero: true, max: 2, ticks: { stepSize: 1 } } },
  };

  return (
    <>
      <Navbar />

      <div className="max-w-6xl mx-auto p-6 space-y-8">
        <h1 className="text-3xl font-bold">Data-Quality Dashboard</h1>

        {/* dropdown */}
        <div>
          <label className="mr-2 font-medium">Choose a table:</label>
          <select
            value={tableName}
            onChange={(e) => setTableName(e.target.value)}
            className="border p-1"
          >
            {TABLES.map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
        </div>

        {/* latest-results table */}
        <h2 className="text-xl font-semibold">Latest results (per table)</h2>
        <div className="overflow-x-auto border rounded">
          <table className="min-w-full text-sm">
            <thead className="bg-gray-100">
              <tr>
                <th className="p-2">Table</th>
                <th className="p-2">Execution Time</th>
                <th className="p-2">Vector</th>
                <th className="p-2">Error</th>
              </tr>
            </thead>
            <tbody>
              {latestRows.length === 0 && (
                <tr><td colSpan={4} className="p-4 text-center">
                  No logs yet.
                </td></tr>
              )}
              {latestRows.map((r, i) => (
                <tr key={i} className="border-t">
                  <td className="p-2">{r.table_name}</td>
                  <td className="p-2">{r.execution_time}</td>
                  <td className="p-2">{JSON.stringify(r.tests)}</td>
                  <td className="p-2">{r.error_description || "–"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* line chart */}
        <h2 className="text-xl font-semibold">
          Exhaustivité / Pertinence / Exactitude –
          <span className="font-normal"> {tableName}</span>
        </h2>
        {times.length ? (
          <Line data={lineData} options={lineOpts}/>
        ) : (
          <p className="text-gray-500">
            No 3-dimension test vectors stored for this table.
          </p>
        )}
      </div>
    </>
  );
}

/* ─── src/pages/AdminPanel.jsx ─────────────────────────────────────────── */
import { useEffect, useState } from "react";
import {
  Chart as ChartJS,
  ArcElement,
  BarElement,
  CategoryScale,
  LinearScale,
  Tooltip,
  Legend,
} from "chart.js";
import { Bar, Pie, Doughnut } from "react-chartjs-2";
import Navbar from "../components/Navbar.jsx";
import SpeciesTable from "../components/SpeciesTable.jsx";
import { getAdminStats } from "../services/DataService.js";
import { useAuth } from "../context/AuthContext.jsx";

ChartJS.register(
  ArcElement,
  BarElement,
  CategoryScale,
  LinearScale,
  Tooltip,
  Legend,
);

export default function AdminPanel() {
  /* grab the whole auth object */
  const { user } = useAuth();
  const token    = user?.token ?? localStorage.getItem("token");            // <──────── get JWT here

  const [stats, setStats] = useState(null);
  const [error, setError] = useState(null);

  /* fetch once when token is available */
  useEffect(() => {
    if (!token) return;                       // not ready? wait.
    getAdminStats(token)
      .then(setStats)
      .catch(() => setError("Failed to load admin stats."));
  }, [token]);

  if (error)      return <p className="p-6 text-red-500">{error}</p>;
  if (!stats)     return <p className="p-6">Loading…</p>;

  /* ── chart datasets ────────────────────────────────────────── */
  const barImages = {
    labels: stats.species_names,
    datasets: [{ label: "Total images", data: stats.images_count }],
  };

  const pieFamily = {
    labels: stats.family_labels,
    datasets: [{ data: stats.family_values }],
  };

  const barComplete = {
    labels: stats.species_names,
    datasets: [{ label: "Completeness %", data: stats.completeness }],
  };

  const doughRegion = {
    labels: stats.region_labels,
    datasets: [{ data: stats.region_values }],
  };

  /* ── UI ────────────────────────────────────────────────────── */
  return (
    <>
      <Navbar />

      <div className="max-w-7xl mx-auto p-6 space-y-10">
        <h1 className="text-3xl font-bold">Admin Dashboard</h1>

        <div className="grid md:grid-cols-2 gap-8">
          <div className="bg-white p-4 shadow rounded">
            <h2 className="font-semibold mb-2">Images by Species</h2>
            <Bar data={barImages} />
          </div>

          <div className="bg-white p-4 shadow rounded">
            <h2 className="font-semibold mb-2">Species Count by Family</h2>
            <Pie data={pieFamily} />
          </div>

          <div className="bg-white p-4 shadow rounded md:col-span-2">
            <h2 className="font-semibold mb-2">Data Completeness (%)</h2>
            <Bar
              data={barComplete}
              options={{ scales: { y: { beginAtZero: true, max: 100 } } }}
            />
          </div>

          <div className="bg-white p-4 shadow rounded md:col-span-2">
            <h2 className="font-semibold mb-2">Species Distribution by Region</h2>
            <Doughnut data={doughRegion} />
          </div>
        </div>

        <h2 className="text-2xl font-semibold mt-8">Species Details</h2>
        <SpeciesTable rows={stats.rows} />
      </div>
    </>
  );
}

// ─── src/pages/SpeciesSummaryPage.jsx ────────────────────────────────
import { useEffect, useState } from "react";
import {
  getSpeciesSummary,
  getSpeciesInfo,
} from "../services/DataService.js";

import Layout     from "../components/Layout.jsx";
import UsageChart from "../components/UsageChart.jsx";

export default function SpeciesSummaryPage() {
  const [data, setData]       = useState(null);
  const [error, setError]     = useState(null);

  /* ─── selector state ─────────────────────────── */
  const [selected, setSelected]       = useState("");
  const [info, setInfo]               = useState(null);
  const [infoLoading, setInfoLoading] = useState(false);
  const [infoError,   setInfoError]   = useState(null);

  /* ─── load summary once ──────────────────────── */
  useEffect(() => {
    getSpeciesSummary()
      .then(setData)
      .catch(() => setError("Could not load species summary."));
  }, []);

  /* ─── fetch one species on selection ─────────── */
  async function handleSelect(e) {
    const name = e.target.value;
    setSelected(name);
    setInfo(null);
    setInfoError(null);
    if (!name) return;

    setInfoLoading(true);
    try {
      const obj = await getSpeciesInfo(name);
      setInfo(obj);
    } catch {
      setInfoError("Information not found.");
    } finally {
      setInfoLoading(false);
    }
  }

  if (error) return <Layout><p className="p-6 text-red-600">{error}</p></Layout>;
  if (!data)  return <Layout><p className="p-6">Loading…</p></Layout>;

  /* ─── normalise rows ─────────────────────────── */
  const rows =
    data.rows            ||
    data.table_rows      ||
    data.species_summary ||
    [];

  /* ─── selector list ──────────────────────────── */
  const speciesNames = [...new Set(rows.map(r => r.species_name))].sort();

  return (
    <Layout>
      <div className="mx-auto max-w-6xl space-y-10 p-6">

        {/* title */}
        <h1 className="text-3xl font-bold text-primary">Species Summary</h1>

        {/* ───────────────────────────────────────────────
             1 · Species details card
           ─────────────────────────────────────────────── */}
        <section className="card">
          <h2 className="mb-4 text-2xl font-semibold">Species Properties</h2>

          <select
            value={selected}
            onChange={handleSelect}
            className="w-full rounded-lg border px-3 py-2 sm:max-w-md"
          >
            <option value="">Select a species…</option>
            {speciesNames.map(name => (
              <option key={name}>{name}</option>
            ))}
          </select>

          {/* details */}
          <div className="prose mt-6 max-w-none">
            {infoLoading && <p>Loading…</p>}
            {infoError   && <p className="text-red-600">{infoError}</p>}

            {info && (
              <>
                <p><strong>Scientific name:</strong> {info.Espèce}</p>
                <p><strong>Family:</strong> {info.Famille}</p>
                <p><strong>Size:</strong> {info.Taille || "–"}</p>
                <p><strong>Description:</strong> {info.Description || "–"}</p>
                <p><strong>Habitat:</strong> {info.Habitat || "–"}</p>
                <p><strong>Region:</strong> {info.Région || "–"}</p>
                <p><strong>Fun fact:</strong> {info.Fun_fact || "–"}</p>
              </>
            )}
          </div>
        </section>

        {/* ───────────────────────────────────────────────
             2 · Charts (responsive grid)
           ─────────────────────────────────────────────── */}
        <section className="grid gap-6 lg:grid-cols-2">
          <div className="card">
            <h2 className="mb-2 text-xl font-semibold">
              Species Count by Family
            </h2>
            <UsageChart
              type="pie"
              data={{
                labels: data.family_labels,
                values: data.family_values,
              }}
            />
          </div>

          <div className="card lg:col-span-2">
            <h2 className="mb-2 text-xl font-semibold">Region Distribution</h2>
            <UsageChart
              type="bar"
              data={{
                labels: data.region_labels,
                values: data.region_values,
              }}
              options={{ scales: { y: { beginAtZero: true } } }}
            />
          </div>
        </section>

        {/* ───────────────────────────────────────────────
             3 · Details table (scroll-x on mobile)
           ─────────────────────────────────────────────── */}
        <section className="card">
          <h2 className="mb-4 text-2xl font-semibold">Species Details</h2>

          <div className="overflow-x-auto">
            <table className="min-w-full divide-y">
              <thead className="bg-gray100 text-left text-sm font-medium">
                <tr>
                  <th className="p-2">Species</th>
                  <th className="p-2">Family</th>
                  <th className="p-2">Regions</th>
                </tr>
              </thead>
              <tbody className="divide-y text-sm">
                {rows.map(r => (
                  <tr key={r.species_id} className="hover:bg-gray100/60">
                    <td className="p-2">{r.species_name}</td>
                    <td className="p-2">{r.family}</td>
                    <td className="p-2">{r.region}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </Layout>
  );
}

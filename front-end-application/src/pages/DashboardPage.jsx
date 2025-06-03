/* ─── src/pages/DashboardPage.jsx ───────────────────────────── */
import { useEffect, useState, useContext, useMemo } from "react";
import { getDashboardStats } from "../services/DataService.js";
import UsageChart from "../components/UsageChart.jsx";
import Layout     from "../components/Layout.jsx";   // ⬅️ use the shell
import { AuthContext } from "../context/AuthContext.jsx";
import { cleanSpecies }  from "../utils/text.js";

export default function DashboardPage() {
  const [stats, setStats] = useState(null);
  const { user } = useContext(AuthContext);

  /* ---------- extract e-mail once from the JWT ---------- */
  const email = useMemo(() => {
    if (!user?.token) return null;
    try {
      const [, b64] = user.token.split(".");
      const json = atob(b64.padEnd(b64.length + (4 - (b64.length % 4)) % 4, "="));
      const payload = JSON.parse(json);
      return payload.email ||                       // Supabase v2
             payload.user_metadata?.email || null;  // fallback
    } catch {
      return null;
    }
  }, [user?.token]);

  /* ---------- fetch stats ---------- */
  useEffect(() => {
    getDashboardStats()
      .then(setStats)
      .catch(console.error);
  }, []);

  /* ---------- loading ---------- */
  if (!stats)
    return (
      <Layout>
        <p className="p-6 text-center">Loading…</p>
      </Layout>
    );

  /* ---------- UI ---------- */
  return (
    <Layout>
      <div className="mx-auto max-w-5xl px-4 py-6 lg:px-6">

        {/* greeting */}
        <h1 className="text-2xl font-bold mb-4">Welcome, {email ?? user.id}!</h1>

        {/* recent predictions table */}
        <section className="card mb-8 overflow-x-auto">
          <h2 className="mb-3 text-lg font-medium">Recent Predictions</h2>

          <table className="min-w-[540px] w-full text-sm">
            <thead className="bg-gray100 text-left uppercase tracking-wide">
              <tr>
                <th className="px-3 py-2">#</th>
                <th className="px-3 py-2">Species</th>
                <th className="px-3 py-2">Created&nbsp;At</th>
              </tr>
            </thead>
            <tbody>
              {stats.table_rows.map((row, idx) => (
                <tr
                  key={idx}
                  className="border-t hover:bg-gray100/60"
                >
                  <td className="px-3 py-2">{idx + 1}</td>
                  <td className="px-3 py-2">
                    {cleanSpecies(row.predicted_species)}
                  </td>
                  <td className="px-3 py-2 whitespace-nowrap">
                    {new Date(row.created_at).toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>

        {/* charts – stack on mobile, grid on ≥lg */}
        <div className="flex flex-col gap-8 lg:grid lg:grid-cols-2">

          {/* line chart */}
          <section className="card">
            <h2 className="mb-3 text-lg font-medium">
              Predictions Over Time
            </h2>
            <UsageChart
              data={{
                labels: stats.line_labels,
                values: stats.line_values,
              }}
            />
          </section>

          {/* pie chart */}
          <section className="card">
            <h2 className="mb-3 text-lg font-medium">
              Species Distribution
            </h2>
            <UsageChart
              type="pie"
              data={{
                labels: stats.pie_labels.map(cleanSpecies),
                values: stats.pie_values,
              }}
            />
          </section>
        </div>
      </div>
    </Layout>
  );
}
